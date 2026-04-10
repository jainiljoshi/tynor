from odoo import api, fields, models

from .utils import clean_external_value, extract_external_values, normalize_payment_display


class SaleOrder(models.Model):
    _inherit = "sale.order"

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

    @api.depends("order_line.name", "order_line.display_type")
    def _compute_tynor_external_data(self):
        for order in self:
            note_lines = order.order_line.filtered(lambda line: line.display_type == "line_note" and line.name).mapped("name")
            parsed = extract_external_values(note_lines)
            order.tynor_external_order_no = parsed["order_no"]
            order.tynor_external_payment_method_raw = parsed["payment_method_raw"]
            order.tynor_external_payment_method = parsed["payment_method"]

    @api.model
    def _tynor_sync_payment_method_from_raw(self, limit=1000):
        safe_limit = max(int(limit or 0), 1)
        self.env.cr.execute(
            """
            SELECT id, tynor_external_payment_method_raw, COALESCE(tynor_external_payment_method, '')
              FROM sale_order
             WHERE COALESCE(tynor_external_payment_method_raw, '') <> ''
             ORDER BY id ASC
             LIMIT %s
            """,
            (safe_limit,),
        )
        updates = []
        for order_id, raw_method, current_method in self.env.cr.fetchall():
            cleaned_raw = clean_external_value(raw_method)
            normalized = normalize_payment_display(cleaned_raw)
            if cleaned_raw != (raw_method or "") or normalized != (current_method or ""):
                updates.append((cleaned_raw or None, normalized or None, order_id))
        if updates:
            self.env.cr.executemany(
                "UPDATE sale_order SET tynor_external_payment_method_raw = %s, tynor_external_payment_method = %s WHERE id = %s",
                updates,
            )
        return len(updates)
