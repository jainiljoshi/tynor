from odoo import fields, models, tools


class TynorWholesalerReport(models.Model):
    _name = "tynor.wholesaler.report"
    _description = "Tynor Wholesaler Reporting"
    _auto = False
    _order = "invoice_date desc, id desc"

    move_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    sale_order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    invoice_date = fields.Date(readonly=True)
    invoice_datetime = fields.Datetime(readonly=True)
    payment_method = fields.Char(readonly=True)
    channel = fields.Char(readonly=True)
    product_sales_ex_gst = fields.Monetary(currency_field="currency_id", readonly=True)
    shipping_ex_gst = fields.Monetary(currency_field="currency_id", readonly=True)
    gst_collected = fields.Monetary(currency_field="currency_id", readonly=True)
    refunds = fields.Monetary(currency_field="currency_id", readonly=True)
    fees_commission = fields.Monetary(currency_field="currency_id", readonly=True)
    net_amount = fields.Monetary(currency_field="currency_id", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS
            WITH sale_link AS (
                SELECT
                    aml.move_id,
                    MIN(sol.order_id) AS sale_order_id
                FROM account_move_line aml
                JOIN sale_order_line_invoice_rel rel
                    ON rel.invoice_line_id = aml.id
                JOIN sale_order_line sol
                    ON sol.id = rel.order_line_id
                GROUP BY aml.move_id
            ),
            delivery_flags AS (
                SELECT
                    rel.invoice_line_id,
                    BOOL_OR(sol.is_delivery) AS is_delivery
                FROM sale_order_line_invoice_rel rel
                JOIN sale_order_line sol
                    ON sol.id = rel.order_line_id
                GROUP BY rel.invoice_line_id
            ),
            line_stats AS (
                SELECT
                    am.id AS move_id,
                    SUM(
                        CASE
                            WHEN aml.display_type = 'product'
                                AND COALESCE(delivery_flags.is_delivery, FALSE) = FALSE
                                AND am.move_type IN ('out_invoice', 'out_receipt')
                            THEN aml.price_subtotal
                            ELSE 0
                        END
                    ) AS product_sales_ex_gst,
                    SUM(
                        CASE
                            WHEN aml.display_type = 'product'
                                AND (
                                    COALESCE(delivery_flags.is_delivery, FALSE) = TRUE
                                    OR COALESCE(aml.name, '') ILIKE '%shipping%'
                                )
                                AND am.move_type IN ('out_invoice', 'out_receipt')
                            THEN aml.price_subtotal
                            ELSE 0
                        END
                    ) AS shipping_ex_gst,
                    SUM(
                        CASE
                            WHEN aml.display_type = 'product'
                                AND am.move_type = 'out_refund'
                            THEN ABS(aml.price_subtotal)
                            ELSE 0
                        END
                    ) AS refunds,
                    SUM(
                        CASE
                            WHEN aml.tax_line_id IS NOT NULL
                                AND (
                                    COALESCE(atg.name::text, '') ILIKE '%GST%'
                                    OR COALESCE(aml.name, '') ILIKE '%GST%'
                                    OR COALESCE(at.name::text, '') ILIKE '%GST%'
                                )
                            THEN CASE
                                WHEN am.move_type = 'out_refund' THEN -ABS(aml.balance)
                                ELSE ABS(aml.balance)
                            END
                            ELSE 0
                        END
                    ) AS gst_collected
                FROM account_move am
                LEFT JOIN account_move_line aml
                    ON aml.move_id = am.id
                LEFT JOIN account_tax at
                    ON at.id = aml.tax_line_id
                LEFT JOIN account_tax_group atg
                    ON atg.id = at.tax_group_id
                LEFT JOIN delivery_flags
                    ON delivery_flags.invoice_line_id = aml.id
                WHERE am.state = 'posted'
                  AND am.move_type IN ('out_invoice', 'out_refund', 'out_receipt')
                GROUP BY am.id
            ),
            fee_stats AS (
                SELECT
                    am.id AS move_id,
                    SUM(
                        CASE
                            WHEN aa.account_type IN ('expense', 'expense_depreciation', 'expense_direct_cost')
                                 AND (
                                     COALESCE(aml.name, '') ~* '(commission|fee)'
                                     OR COALESCE(aa.name::text, '') ~* '(commission|fee)'
                                 )
                            THEN ABS(aml.balance)
                            ELSE 0
                        END
                    ) AS fees_commission
                FROM account_move am
                LEFT JOIN account_move_line aml
                    ON aml.move_id = am.id
                LEFT JOIN account_account aa
                    ON aa.id = aml.account_id
                WHERE am.state = 'posted'
                  AND am.move_type IN ('out_invoice', 'out_refund', 'out_receipt')
                GROUP BY am.id
            )
            SELECT
                am.id AS id,
                am.id AS move_id,
                sale_link.sale_order_id,
                am.company_id,
                am.partner_id,
                am.currency_id,
                am.invoice_date,
                am.create_date AS invoice_datetime,
                COALESCE(NULLIF(am.tynor_external_payment_method, ''), 'Unmapped') AS payment_method,
                COALESCE(NULLIF(am.tynor_external_payment_method, ''), 'Unmapped') AS channel,
                COALESCE(line_stats.product_sales_ex_gst, 0.0) AS product_sales_ex_gst,
                COALESCE(line_stats.shipping_ex_gst, 0.0) AS shipping_ex_gst,
                COALESCE(line_stats.gst_collected, 0.0) AS gst_collected,
                COALESCE(line_stats.refunds, 0.0) AS refunds,
                COALESCE(fee_stats.fees_commission, 0.0) AS fees_commission,
                (
                    COALESCE(line_stats.product_sales_ex_gst, 0.0)
                    + COALESCE(line_stats.shipping_ex_gst, 0.0)
                    - COALESCE(line_stats.refunds, 0.0)
                    - COALESCE(fee_stats.fees_commission, 0.0)
                ) AS net_amount
            FROM account_move am
            LEFT JOIN line_stats
                ON line_stats.move_id = am.id
            LEFT JOIN fee_stats
                ON fee_stats.move_id = am.id
            LEFT JOIN sale_link
                ON sale_link.move_id = am.id
            WHERE am.state = 'posted'
              AND am.move_type IN ('out_invoice', 'out_refund', 'out_receipt')
            """
        )
