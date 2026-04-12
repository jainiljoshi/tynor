from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    shades_lead_source = fields.Selection(
        selection=[
            ("google_ads", "Google Ads"),
            ("facebook_ads", "Facebook Ads"),
            ("tiktok", "TikTok"),
            ("website", "Website"),
            ("referral", "Referral"),
            ("walk_in", "Walk-in"),
            ("google_business", "Google My Business"),
            ("phone", "Phone Call"),
            ("whatsapp", "WhatsApp"),
            ("social_media", "Social Media"),
            ("other", "Other"),
        ],
        string="How did you hear about us?",
        required=True,
        default="website",
        tracking=True,
    )
    shades_interaction_notes = fields.Text(string="Interaction Notes")
