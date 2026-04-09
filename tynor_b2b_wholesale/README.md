# Tynor B2B Wholesale App

This custom Odoo module (`tynor_b2b_wholesale`) is responsible for managing the specialized B2B customer onboarding flow and portal logic for Tynor Australia.

It acts as a bridge between the CRM (Leads), Sales (Pricelists/Payment Terms), and Portal environments to create a seamless wholesale customer experience.

## Business Process Flow

This module handles the workflow when a business (Pharmacy, Physiotherapist, Retailer, etc.) applies to become a wholesale distributor.

### 1. Lead / Application Generation
When a wholesale prospect applies, a new CRM Lead is created. This module extends the standard Odoo Lead model (`crm.lead`) to capture necessary B2B data points:
- **Tax ID / ABN** (`x_wholesale_tax_id`): For verifying business legitimacy.
- **Business Type** (`x_wholesale_business_type`): Categorizes the partner (Pharmacy, Physiotherapist, Retailer, or Distributor).

### 2. The Approval Action
When a sales manager approves the application by clicking the **Approve Wholesale** button, the `action_approve_wholesale()` method triggers an automated pipeline:

1. **Partner Creation**: If an Odoo Contact (Res Partner) hasn't been linked to the Lead, the system automatically creates one.
2. **Pricelist Assignment**: The partner is instantly assigned the unique **Wholesale VIP** pricelist (see Economics below).
3. **Wholesale Tagging**: The partner is tagged with a system-wide `Wholesale` badge (`res.partner.category`). This allows for easy filtering in accounting, marketing, and sales systems.
4. **Automated Portal Invite**: The Odoo Portal wizard is triggered programmatically. An email is sent to the customer inviting them to set a password and log in to their wholesale portal account.
5. **Set to Won**: A success message is posted to the chatter, and the CRM Lead is marked as **Won**.

---

## Wholesale Economics & Pre-Loaded Data

The module installs with pre-configured XML data (`b2b_wholesale_data.xml`) designed to manage the B2B financial rules out-of-the-box.

### The "Wholesale VIP" Pricelist
A global pricelist automatically applied to approved partners. 
- **Rule**: Minimum Order Quantity (**MOQ**) = 10 items.
- **Discount**: Grants an automatic **40% global discount** at checkout when the MOQ condition is met.

### The Payment Term
- **Net 30 (Pay on Account)**: A payment term installed by the module for B2B customers, enforcing payment 30 days immediately following the invoice date. 

### Portal Configuration
- Injects `website_sale.b2b_checkout = True` into the global `ir.config_parameter`, ensuring the Odoo B2B checkout flow is enabled.

---

## Technical Dependencies

If extending this module, note that it deeply interacts with:
* `crm` (For CRM Lead extensions and Approval Buttons)
* `sale_management` (For Pricelists and Payment terms)
* `portal` (Wizard injection for user onboarding)
* `website_sale` (For enforcing minimum cart quantities online)
