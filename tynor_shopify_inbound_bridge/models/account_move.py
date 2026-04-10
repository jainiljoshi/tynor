import logging
import re
import base64

from odoo import _, api, fields, models

from .utils import extract_external_values, normalize_payment_display

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    tynor_external_order_no = fields.Char(
        string="External Order No",
        compute="_compute_tynor_external_data",
        store=True,
        readonly=True,
    )
    tynor_external_payment_method_raw = fields.Char(
        string="External Payment Method (Raw)",
        compute="_compute_tynor_external_data",
        store=True,
        readonly=True,
    )
    tynor_external_payment_method = fields.Char(
        string="External Payment Method",
        compute="_compute_tynor_external_data",
        store=True,
        readonly=True,
    )
    tynor_bridge_payment_id = fields.Many2one(
        "account.payment",
        string="Bridge Payment",
        copy=False,
        readonly=True,
    )
    tynor_bridge_payment_synced = fields.Boolean(default=False, copy=False, readonly=True, index=True)
    tynor_paid_email_sent = fields.Boolean(default=False, copy=False, readonly=True, index=True)
    tynor_paid_email_sent_at = fields.Datetime(copy=False, readonly=True)
    tynor_paid_chatter_posted = fields.Boolean(default=False, copy=False, readonly=True, index=True)

    @api.depends(
        "invoice_line_ids.display_type",
        "invoice_line_ids.name",
        "invoice_line_ids.sale_line_ids.order_id.tynor_external_order_no",
        "invoice_line_ids.sale_line_ids.order_id.tynor_external_payment_method",
        "invoice_line_ids.sale_line_ids.order_id.tynor_external_payment_method_raw",
        "invoice_origin",
    )
    def _compute_tynor_external_data(self):
        for move in self:
            values = move._tynor_resolve_external_values()
            move.tynor_external_order_no = values["order_no"]
            move.tynor_external_payment_method_raw = values["payment_method_raw"]
            move.tynor_external_payment_method = values["payment_method"]

    def _tynor_get_related_sale_orders(self):
        self.ensure_one()
        orders = self.invoice_line_ids.sale_line_ids.order_id
        if orders:
            return orders
        origins = [token.strip() for token in re.split(r"[,;]+", self.invoice_origin or "") if token and token.strip()]
        if not origins:
            return self.env["sale.order"]
        return self.env["sale.order"].search([("name", "in", origins)], limit=5)

    def _tynor_resolve_external_values(self):
        self.ensure_one()
        order_no = self.tynor_external_order_no or ""
        payment_method_raw = self.tynor_external_payment_method_raw or ""
        payment_method = self.tynor_external_payment_method or ""

        orders = self._tynor_get_related_sale_orders()
        for order in orders:
            order_no = order_no or order.tynor_external_order_no or ""
            payment_method_raw = payment_method_raw or order.tynor_external_payment_method_raw or ""
            payment_method = payment_method or order.tynor_external_payment_method or ""
            if order_no and payment_method and payment_method_raw:
                break

        if not (order_no and payment_method):
            note_lines = self.invoice_line_ids.filtered(lambda line: line.display_type == "line_note" and line.name).mapped("name")
            parsed = extract_external_values(note_lines)
            order_no = order_no or parsed["order_no"]
            payment_method_raw = payment_method_raw or parsed["payment_method_raw"]
            payment_method = payment_method or parsed["payment_method"]

        normalized_from_raw = normalize_payment_display(payment_method_raw)
        if normalized_from_raw:
            payment_method = normalized_from_raw

        return {
            "order_no": order_no,
            "payment_method_raw": payment_method_raw,
            "payment_method": payment_method,
        }

    @api.model
    def _tynor_sync_payment_method_from_raw(self, limit=1000):
        safe_limit = max(int(limit or 0), 1)
        self.env.cr.execute(
            """
            SELECT id, tynor_external_payment_method_raw, COALESCE(tynor_external_payment_method, '')
              FROM account_move
             WHERE COALESCE(tynor_external_payment_method_raw, '') <> ''
             ORDER BY id ASC
             LIMIT %s
            """,
            (safe_limit,),
        )
        updates = []
        for move_id, raw_method, current_method in self.env.cr.fetchall():
            normalized = normalize_payment_display(raw_method)
            if normalized and normalized != (current_method or ""):
                updates.append((normalized, move_id))
        if updates:
            self.env.cr.executemany(
                "UPDATE account_move SET tynor_external_payment_method = %s WHERE id = %s",
                updates,
            )
        return len(updates)

    def _tynor_get_existing_bridge_payment(self):
        self.ensure_one()
        return self.env["account.payment"].search(
            [
                ("tynor_source_invoice_id", "=", self.id),
                ("state", "!=", "cancel"),
            ],
            limit=1,
        )

    def _tynor_reconcile_with_payment(self, payment):
        self.ensure_one()
        invoice_lines = self.line_ids.filtered(
            lambda line: line.account_type in ("asset_receivable", "liability_payable") and not line.reconciled
        )
        payment_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_type in ("asset_receivable", "liability_payable") and not line.reconciled
        )
        if not invoice_lines or not payment_lines:
            return
        for account in (invoice_lines + payment_lines).mapped("account_id"):
            lines = (invoice_lines + payment_lines).filtered(lambda line: line.account_id == account and not line.reconciled)
            if len(lines) >= 2:
                lines.reconcile()

    def _tynor_create_payment_from_bridge(self):
        self.ensure_one()
        if self.state != "posted" or self.move_type not in ("out_invoice", "out_receipt"):
            return False
        if self.amount_residual <= 0:
            return False
        if self._tynor_get_existing_bridge_payment():
            return False
        if not self.tynor_external_payment_method:
            return False

        mapping = self.env["tynor.payment.journal.map"].get_or_create_for_method(
            self.tynor_external_payment_method, self.company_id
        )
        if not mapping:
            return False
        mapping._ensure_journal()
        journal = mapping.journal_id
        if not journal:
            return False

        payment_method_line = journal.inbound_payment_method_line_ids.filtered(lambda line: line.code == "manual")[:1]
        payment_method_line = payment_method_line or journal.inbound_payment_method_line_ids[:1]
        if not payment_method_line:
            _logger.warning("No inbound payment method line found for journal %s", journal.display_name)
            return False

        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.commercial_partner_id.id,
                "amount": abs(self.amount_residual),
                "currency_id": self.currency_id.id,
                "date": fields.Date.context_today(self),
                "journal_id": journal.id,
                "payment_method_line_id": payment_method_line.id,
                "payment_reference": self.payment_reference or self.name or self.ref or "",
            }
        )
        payment.action_post()
        self._tynor_reconcile_with_payment(payment)
        payment.write(
            {
                "tynor_source_invoice_id": self.id,
                "tynor_external_order_no": self.tynor_external_order_no or "",
                "tynor_external_payment_method": self.tynor_external_payment_method or "",
                "tynor_bridge_generated": True,
            }
        )
        self.with_context(tynor_skip_bridge=True).write(
            {
                "tynor_bridge_payment_id": payment.id,
                "tynor_bridge_payment_synced": True,
            }
        )
        return payment

    def _tynor_is_shopify_related_invoice(self):
        self.ensure_one()
        if self.tynor_external_order_no or self.tynor_external_payment_method or self.tynor_external_payment_method_raw:
            return True
        for order in self._tynor_get_related_sale_orders():
            if "shopify_order_id" in order._fields and order.shopify_order_id:
                return True
            if "shopify_id" in order._fields and order.shopify_id:
                return True
            if "is_shopify_order" in order._fields and order.is_shopify_order:
                return True
            if "shopify_instance_id" in order._fields and order.shopify_instance_id:
                return True
        return False

    def _tynor_send_paid_invoice_email(self):
        self.ensure_one()
        if self.tynor_paid_chatter_posted:
            return False
        if self.state != "posted" or self.move_type not in ("out_invoice", "out_receipt"):
            return False
        if self.payment_state != "paid" or self.tynor_paid_email_sent:
            return False
        recipient_email = (self.partner_id.email or self.commercial_partner_id.email or "").strip()
        if not recipient_email:
            return False
        template = self._get_mail_template() or self.env.ref("account.email_template_edi_invoice", raise_if_not_found=False)
        if not template:
            return False
        attachment = self._tynor_get_invoice_pdf_mail_attachment()
        chatter_attachment = False
        if attachment:
            filename, content = attachment
            chatter_attachment = self.env["ir.attachment"].sudo().create(
                {
                    "name": filename,
                    "datas": content,
                    "res_model": self._name,
                    "res_id": self.id,
                    "mimetype": "application/pdf",
                    "type": "binary",
                }
            )
        email_values = {
            "email_to": recipient_email,
        }
        if chatter_attachment:
            email_values["attachment_ids"] = [(4, chatter_attachment.id)]
        elif attachment:
            email_values["attachments"] = [attachment]
        try:
            mail_id = template.send_mail(self.id, force_send=True, email_values=email_values)
        except Exception:
            _logger.exception("Failed to auto-send paid invoice email for invoice %s", self.id)
            if chatter_attachment and not self.tynor_paid_chatter_posted:
                try:
                    self._tynor_post_paid_invoice_pdf_in_chatter(
                        recipient_email=recipient_email,
                        chatter_attachment=chatter_attachment,
                    )
                except Exception:
                    _logger.exception("Failed to post fallback paid invoice PDF chatter note for invoice %s", self.id)
            return False
        if mail_id:
            self.sudo().with_context(tynor_skip_bridge=True).write(
                {
                    "tynor_paid_email_sent": True,
                    "tynor_paid_email_sent_at": fields.Datetime.now(),
                }
            )
            self._tynor_post_paid_invoice_pdf_in_chatter(
                recipient_email=recipient_email,
                chatter_attachment=chatter_attachment,
            )
        return bool(mail_id)

    def _tynor_post_paid_invoice_pdf_in_chatter(self, recipient_email=None, chatter_attachment=False):
        self.ensure_one()
        if self.tynor_paid_chatter_posted:
            return False
        if self.state != "posted" or self.move_type not in ("out_invoice", "out_receipt"):
            return False
        if self.payment_state != "paid":
            return False

        if not chatter_attachment:
            attachment = self._tynor_get_invoice_pdf_mail_attachment()
            if attachment:
                filename, content = attachment
                chatter_attachment = self.env["ir.attachment"].sudo().create(
                    {
                        "name": filename,
                        "datas": content,
                        "res_model": self._name,
                        "res_id": self.id,
                        "mimetype": "application/pdf",
                        "type": "binary",
                    }
                )

        if not chatter_attachment:
            return False

        recipient = recipient_email or (self.partner_id.email or self.commercial_partner_id.email or "").strip()
        body = _("Invoice PDF attached in chatter for paid invoice.")
        if recipient:
            body = _("Invoice email auto-sent for paid invoice to <b>%s</b>. PDF attached in chatter.") % recipient

        self.message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
            attachment_ids=[chatter_attachment.id],
        )
        # Keep this idempotent even if downstream flows retry this method.
        self.sudo().with_context(tynor_skip_bridge=True).write(
            {
                "tynor_paid_chatter_posted": True,
                "tynor_paid_email_sent": True,
                "tynor_paid_email_sent_at": self.tynor_paid_email_sent_at or fields.Datetime.now(),
            }
        )
        return True

    def _tynor_get_invoice_pdf_mail_attachment(self):
        """Return invoice PDF as a mail.template-style attachment tuple."""
        self.ensure_one()
        if self.invoice_pdf_report_id and self.invoice_pdf_report_id.raw:
            return (
                self.invoice_pdf_report_id.name or self._get_invoice_report_filename(),
                base64.b64encode(self.invoice_pdf_report_id.raw),
            )

        report = self.env.ref("account.account_invoices")
        pdf_content, report_type = report._render_qweb_pdf(report.report_name, self.ids)
        if not pdf_content:
            return False
        extension = report_type or "pdf"
        return (
            self._get_invoice_report_filename(extension=extension, report=report),
            base64.b64encode(pdf_content),
        )

    def _tynor_process_bridge(self):
        for move in self:
            if move.state != "posted" or move.move_type not in ("out_invoice", "out_receipt"):
                continue
            try:
                values = move._tynor_resolve_external_values()
                updates = {}
                if values["order_no"] and values["order_no"] != move.tynor_external_order_no:
                    updates["tynor_external_order_no"] = values["order_no"]
                if values["payment_method_raw"] and values["payment_method_raw"] != move.tynor_external_payment_method_raw:
                    updates["tynor_external_payment_method_raw"] = values["payment_method_raw"]
                if values["payment_method"] and values["payment_method"] != move.tynor_external_payment_method:
                    updates["tynor_external_payment_method"] = values["payment_method"]
                if updates:
                    move.with_context(tynor_skip_bridge=True).write(updates)

                if move.amount_residual > 0 and move.tynor_external_payment_method and not move._tynor_get_existing_bridge_payment():
                    move._tynor_create_payment_from_bridge()

                if move.payment_state == "paid":
                    if not self.env.context.get("tynor_disable_paid_email"):
                        if not move.tynor_paid_email_sent:
                            move._tynor_send_paid_invoice_email()
                    if not move.tynor_paid_chatter_posted:
                        move._tynor_post_paid_invoice_pdf_in_chatter()

                if move._tynor_get_existing_bridge_payment() or move.payment_state == "paid":
                    move.with_context(tynor_skip_bridge=True).write({"tynor_bridge_payment_synced": True})
            except Exception:
                _logger.exception("Tynor inbound bridge failed for invoice %s", move.id)
        return True

    @api.model
    def _cron_tynor_bridge_backfill(self, limit=200):
        synced_orders = self.env["sale.order"]._tynor_sync_payment_method_from_raw(limit=limit * 5)
        synced_moves = self._tynor_sync_payment_method_from_raw(limit=limit * 5)
        if synced_orders or synced_moves:
            _logger.info(
                "Tynor payment method sync from raw updated %s sale orders and %s invoices.",
                synced_orders,
                synced_moves,
            )
        moves = self.search(
            [
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_receipt")),
                "|",
                "|",
                ("tynor_bridge_payment_synced", "=", False),
                ("tynor_paid_email_sent", "=", False),
                ("tynor_paid_chatter_posted", "=", False),
            ],
            order="id asc",
            limit=limit,
        )
        moves._tynor_process_bridge()
        return True

    def action_post(self):
        res = super().action_post()
        self.filtered(lambda move: move.move_type in ("out_invoice", "out_receipt"))._tynor_process_bridge()
        return res

    def write(self, vals):
        old_states = {move.id: move.payment_state for move in self}
        result = super().write(vals)
        if self.env.context.get("tynor_skip_bridge"):
            return result
        candidates = self.filtered(lambda move: move.state == "posted" and move.move_type in ("out_invoice", "out_receipt"))
        to_process = candidates.filtered(
            lambda move: (
                old_states.get(move.id) != "paid"
                and move.payment_state == "paid"
            ) or (not move.tynor_bridge_payment_synced or (move.tynor_external_payment_method and move.amount_residual > 0))
        )
        to_process._tynor_process_bridge()
        return result
