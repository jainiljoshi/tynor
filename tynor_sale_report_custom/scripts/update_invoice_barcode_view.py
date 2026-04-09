view = env["ir.ui.view"].browse(4595)

xml = """<data>
    <xpath expr="//div[@id='informations']" position="before">
        <div class="row mb-3 mt-2">
            <div class="col-12">
                <t t-if="o.name and o.name != '/'">
                    <div style="margin-bottom: 5px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="35" viewBox="0 0 180 35" aria-label="Invoice barcode">
                            <rect x="0" y="0" width="180" height="35" fill="#ffffff" stroke="#d8d8d8"/>
                            <rect x="4" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="8" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="11" y="3" width="3" height="28" fill="#111111"/>
                            <rect x="17" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="22" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="27" y="3" width="4" height="28" fill="#111111"/>
                            <rect x="34" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="39" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="43" y="3" width="3" height="28" fill="#111111"/>
                            <rect x="49" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="53" y="3" width="4" height="28" fill="#111111"/>
                            <rect x="60" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="65" y="3" width="3" height="28" fill="#111111"/>
                            <rect x="71" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="75" y="3" width="4" height="28" fill="#111111"/>
                            <rect x="82" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="87" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="91" y="3" width="3" height="28" fill="#111111"/>
                            <rect x="97" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="102" y="3" width="4" height="28" fill="#111111"/>
                            <rect x="109" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="113" y="3" width="3" height="28" fill="#111111"/>
                            <rect x="119" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="124" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="128" y="3" width="4" height="28" fill="#111111"/>
                            <rect x="135" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="140" y="3" width="3" height="28" fill="#111111"/>
                            <rect x="146" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="150" y="3" width="4" height="28" fill="#111111"/>
                            <rect x="157" y="3" width="2" height="28" fill="#111111"/>
                            <rect x="162" y="3" width="1" height="28" fill="#111111"/>
                            <rect x="166" y="3" width="3" height="28" fill="#111111"/>
                            <rect x="172" y="3" width="2" height="28" fill="#111111"/>
                        </svg>
                        <div style="color: #666; font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 0.12em; margin-top: 2px;">
                            <span t-field="o.name"/>
                        </div>
                    </div>
                </t>
                <div t-if="o.partner_id.email" style="font-size: 13px; margin-top: 5px;">
                    <strong>Email:</strong> <span t-field="o.partner_id.email"/>
                </div>
            </div>
        </div>
    </xpath>

    <xpath expr="//td[@name='account_invoice_line_name']/span[@t-field='line.name']" position="before">
        <t t-if="line.display_type == 'product' and line.product_id">
            <span t-if="line.product_id.image_128 or line.product_id.product_tmpl_id.image_128" t-field="line.product_id.product_tmpl_id.image_128" t-options="{'widget': 'image', 'style': 'max-height: 60px; max-width: 60px; float: left; margin-right: 10px; border: 1px solid #eee; object-fit: contain;'}"/>
        </t>
    </xpath>

    <xpath expr="//td[@name='account_invoice_line_name']/span[@t-field='line.name']" position="after">
        <t t-if="line.display_type == 'product' and line.product_id">
            <div t-if="line.product_id.barcode" style="font-size:10px; color:#666; margin-top:3px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="130" height="25" viewBox="0 0 130 25" aria-label="Product barcode" style="display:block; margin-bottom: 2px;">
                    <rect x="0" y="0" width="130" height="25" fill="#ffffff" stroke="#d8d8d8"/>
                    <rect x="4" y="2" width="2" height="19" fill="#111111"/>
                    <rect x="8" y="2" width="1" height="19" fill="#111111"/>
                    <rect x="12" y="2" width="3" height="19" fill="#111111"/>
                    <rect x="18" y="2" width="2" height="19" fill="#111111"/>
                    <rect x="23" y="2" width="1" height="19" fill="#111111"/>
                    <rect x="27" y="2" width="4" height="19" fill="#111111"/>
                    <rect x="34" y="2" width="2" height="19" fill="#111111"/>
                    <rect x="39" y="2" width="3" height="19" fill="#111111"/>
                    <rect x="45" y="2" width="1" height="19" fill="#111111"/>
                    <rect x="49" y="2" width="4" height="19" fill="#111111"/>
                    <rect x="56" y="2" width="2" height="19" fill="#111111"/>
                    <rect x="61" y="2" width="1" height="19" fill="#111111"/>
                    <rect x="65" y="2" width="3" height="19" fill="#111111"/>
                    <rect x="71" y="2" width="2" height="19" fill="#111111"/>
                    <rect x="76" y="2" width="4" height="19" fill="#111111"/>
                    <rect x="83" y="2" width="1" height="19" fill="#111111"/>
                    <rect x="87" y="2" width="3" height="19" fill="#111111"/>
                    <rect x="93" y="2" width="2" height="19" fill="#111111"/>
                    <rect x="98" y="2" width="1" height="19" fill="#111111"/>
                    <rect x="102" y="2" width="4" height="19" fill="#111111"/>
                    <rect x="109" y="2" width="2" height="19" fill="#111111"/>
                    <rect x="114" y="2" width="3" height="19" fill="#111111"/>
                    <rect x="120" y="2" width="1" height="19" fill="#111111"/>
                </svg>
                <strong>Barcode:</strong> <span t-field="line.product_id.barcode"/>
            </div>
        </t>
    </xpath>

    <xpath expr="//t[@t-call='account.document_tax_totals']" position="after">
        <tr style="color:#666; border-top: 2px solid #333;">
            <td><strong>Net payment</strong></td>
            <td class="text-end">
                <strong><span t-field="o.amount_residual"/></strong>
            </td>
        </tr>
    </xpath>

    <xpath expr="//span[@t-field='o.payment_reference']" position="attributes">
        <attribute name="t-field">o.ref</attribute>
    </xpath>
</data>"""

view.with_context(lang="en_US").write({"arch_db": xml})
env.cr.commit()
print("UPDATED_VIEW", view.id)
