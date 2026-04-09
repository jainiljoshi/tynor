import re

from odoo import api, fields, models

from .utils import normalize_payment_display, normalize_payment_key


class TynorPaymentJournalMap(models.Model):
    _name = "tynor.payment.journal.map"
    _description = "Tynor Payment Method to Journal Mapping"
    _order = "sequence, id"

    name = fields.Char(required=True)
    method_key = fields.Char(required=True, index=True)
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank', 'cash', 'credit'))]",
    )
    journal_type = fields.Selection(
        [("bank", "Bank"), ("cash", "Cash"), ("credit", "Credit Card")],
        default="bank",
        required=True,
    )
    journal_code = fields.Char(help="Optional manual code when creating a journal automatically.")
    auto_create_journal = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)

    _tynor_method_company_uniq = models.Constraint(
        "unique(method_key, company_id)",
        "Payment method key must be unique per company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("method_key"):
                vals["method_key"] = normalize_payment_key(vals["method_key"])
            if vals.get("name") and not vals.get("method_key"):
                vals["method_key"] = normalize_payment_key(vals["name"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("method_key"):
            vals["method_key"] = normalize_payment_key(vals["method_key"])
        return super().write(vals)

    @api.model
    def _build_default_code(self, method_key, company_id):
        base = re.sub(r"[^A-Z0-9]+", "", (method_key or "").upper())[:5] or "PMT"
        journal_model = self.env["account.journal"]
        code = base
        suffix = 1
        while journal_model.search_count([("code", "=", code), ("company_id", "=", company_id)]):
            trimmed = base[: max(1, 5 - len(str(suffix)))]
            code = f"{trimmed}{suffix}"
            suffix += 1
        return code

    def _ensure_journal(self):
        for mapping in self:
            if mapping.journal_id or not mapping.auto_create_journal:
                continue
            journal = self.env["account.journal"].search(
                [
                    ("company_id", "=", mapping.company_id.id),
                    ("type", "=", mapping.journal_type),
                    ("name", "=ilike", f"{mapping.name} Receipts"),
                ],
                limit=1,
            )
            if not journal:
                code = mapping.journal_code or self._build_default_code(mapping.method_key, mapping.company_id.id)
                journal = self.env["account.journal"].create(
                    {
                        "name": f"{mapping.name} Receipts",
                        "code": code,
                        "type": mapping.journal_type,
                        "company_id": mapping.company_id.id,
                    }
                )
            mapping.journal_id = journal.id
        return self

    @api.model
    def get_or_create_for_method(self, raw_method, company):
        normalized_key = normalize_payment_key(raw_method)
        if not normalized_key:
            return self.browse()
        company = company or self.env.company
        mapping = self.search(
            [("method_key", "=", normalized_key), ("company_id", "=", company.id)],
            limit=1,
        )
        if not mapping:
            mapping = self.create(
                {
                    "name": normalize_payment_display(raw_method) or normalized_key.replace("_", " ").title(),
                    "method_key": normalized_key,
                    "company_id": company.id,
                    "journal_type": "bank",
                    "auto_create_journal": True,
                }
            )
        mapping._ensure_journal()
        return mapping
