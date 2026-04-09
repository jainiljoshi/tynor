from odoo import fields, http
from odoo.http import request


class TynorWholesalerDashboardController(http.Controller):
    @staticmethod
    def _normalize_datetime_input(value, is_end=False):
        text = (value or "").strip()
        if not text:
            return False
        text = text.replace("T", " ")
        if len(text) == 10:
            text = f"{text} {'23:59:59' if is_end else '00:00:00'}"
        if len(text) == 16:
            text = f"{text}:{'59' if is_end else '00'}"
        parsed = fields.Datetime.to_datetime(text)
        if not parsed:
            return False
        return fields.Datetime.to_string(parsed)

    @http.route("/tynor_wholesaler/dashboard_data", type="json", auth="user")
    def get_dashboard_data(self, date_from=None, date_to=None):
        report_model = request.env["tynor.wholesaler.report"].sudo()
        domain = []
        from_dt = self._normalize_datetime_input(date_from, is_end=False)
        to_dt = self._normalize_datetime_input(date_to, is_end=True)
        if from_dt:
            domain.append(("invoice_datetime", ">=", from_dt))
        if to_dt:
            domain.append(("invoice_datetime", "<=", to_dt))

        aggregate_specs = [
            "product_sales_ex_gst:sum",
            "shipping_ex_gst:sum",
            "gst_collected:sum",
            "refunds:sum",
            "fees_commission:sum",
            "net_amount:sum",
        ]
        totals = report_model._read_group(domain, groupby=[], aggregates=aggregate_specs)
        totals_row = totals[0] if totals else tuple(0.0 for _ in aggregate_specs)

        channels_rows = report_model._read_group(
            domain,
            groupby=["payment_method"],
            aggregates=["product_sales_ex_gst:sum", "refunds:sum", "net_amount:sum"],
        )

        channels = sorted(
            [
                {
                    "payment_method": row[0] or "Unmapped",
                    "product_sales_ex_gst": float(row[1] or 0.0),
                    "refunds": float(row[2] or 0.0),
                    "net_amount": float(row[3] or 0.0),
                }
                for row in channels_rows
            ],
            key=lambda row: row["net_amount"],
            reverse=True,
        )[:10]

        return {
            "kpis": {
                "product_sales_ex_gst": float(totals_row[0] or 0.0),
                "shipping_ex_gst": float(totals_row[1] or 0.0),
                "gst_collected": float(totals_row[2] or 0.0),
                "refunds": float(totals_row[3] or 0.0),
                "fees_commission": float(totals_row[4] or 0.0),
                "net_amount": float(totals_row[5] or 0.0),
            },
            "channels": channels,
            "filters": {
                "date_from": from_dt or "",
                "date_to": to_dt or "",
            },
        }
