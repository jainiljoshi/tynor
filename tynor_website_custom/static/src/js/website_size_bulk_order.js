import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { browser } from '@web/core/browser/browser';
import { rpc } from '@web/core/network/rpc';

class TynorBulkSizeOrder extends Interaction {
    static selector = '.js_tynor_bulk_size_order';
    dynamicContent = {
        '.js_tynor_size_qty': { 't-on-input': this.onQtyInput },
        '.js_tynor_bulk_clear': { 't-on-click': this.onClear },
        '.js_tynor_bulk_add': { 't-on-click.prevent': this.locked(this.onAddSizes, true) },
    };

    start() {
        this._updateSummary();
    }

    onQtyInput() {
        this._updateSummary();
    }

    onClear() {
        this.el.querySelectorAll('.js_tynor_size_qty').forEach((input) => {
            input.value = 0;
        });
        this._hideMessage();
        this._updateSummary();
    }

    async onAddSizes() {
        const addButton = this.el.querySelector('.js_tynor_bulk_add');
        const sizeLines = this._collectSizeLines();
        if (!sizeLines.length) {
            this._showMessage('Please enter quantity for at least one size.', false);
            return;
        }

        const selectedPtavIds = this._collectSelectedPtavs();
        const productTemplateId = parseInt(this.el.dataset.productTemplateId);
        if (!productTemplateId) {
            this._showMessage('Product information is incomplete. Please refresh the page.', false);
            return;
        }

        if (addButton) {
            addButton.setAttribute('disabled', 'disabled');
        }

        let response;
        try {
            response = await this.waitFor(rpc('/shop/tynor/add_bulk_sizes', {
                product_template_id: productTemplateId,
                selected_ptav_ids: selectedPtavIds,
                size_lines: sizeLines,
            }));
        } catch (error) {
            this._showMessage('Could not add sizes right now. Please try again.', false);
            if (addButton) {
                addButton.removeAttribute('disabled');
            }
            return;
        }

        if (response?.cart_quantity !== undefined) {
            this._updateCartCounter(response.cart_quantity);
        }

        if (response?.ok) {
            this._showMessage(response.message || 'Sizes added to cart.', true);
            this.el.querySelectorAll('.js_tynor_size_qty').forEach((input) => {
                input.value = 0;
            });
        } else {
            this._showMessage(response?.message || 'Unable to add selected sizes.', false);
        }

        this._updateSummary();
        if (addButton) {
            addButton.removeAttribute('disabled');
        }
    }

    _collectSizeLines() {
        return Array.from(this.el.querySelectorAll('.js_tynor_size_qty'))
            .map((input) => {
                const qty = parseInt(input.value || '0', 10);
                const ptavId = parseInt(input.dataset.ptavId || '0', 10);
                return { qty: Number.isNaN(qty) ? 0 : qty, ptav_id: ptavId };
            })
            .filter((line) => line.qty > 0 && line.ptav_id);
    }

    _collectSelectedPtavs() {
        const productContainer = this.el.closest('.o_wsale_product_page')?.querySelector('.js_product');
        if (!productContainer) {
            return [];
        }
        const selectedElements = productContainer.querySelectorAll(
            'input.js_variant_change:not(.no_variant):checked, select.js_variant_change:not(.no_variant)'
        );
        return Array.from(selectedElements)
            .map((el) => parseInt(el.value || '0', 10))
            .filter((value) => value > 0);
    }

    _updateSummary() {
        const summaryEl = this.el.querySelector('.js_tynor_bulk_summary');
        if (!summaryEl) {
            return;
        }

        const entries = [];
        let totalQty = 0;
        this.el.querySelectorAll('.js_tynor_size_qty').forEach((input) => {
            const qty = parseInt(input.value || '0', 10);
            if (qty > 0) {
                entries.push(`${input.dataset.sizeLabel || 'Size'} x${qty}`);
                totalQty += qty;
            }
        });

        const typesText = entries.length ? entries.join(' | ') : 'none';
        summaryEl.textContent = `Types: ${typesText} | Total Qty: ${totalQty}`;
    }

    _showMessage(message, isSuccess) {
        const msgEl = this.el.querySelector('.js_tynor_bulk_message');
        if (!msgEl) {
            return;
        }
        msgEl.classList.remove('d-none', 'text-success', 'text-danger');
        msgEl.classList.add(isSuccess ? 'text-success' : 'text-danger');
        msgEl.textContent = message;
    }

    _hideMessage() {
        const msgEl = this.el.querySelector('.js_tynor_bulk_message');
        if (!msgEl) {
            return;
        }
        msgEl.textContent = '';
        msgEl.classList.add('d-none');
        msgEl.classList.remove('text-success', 'text-danger');
    }

    _updateCartCounter(cartQuantity) {
        browser.sessionStorage.setItem('website_sale_cart_quantity', cartQuantity);
        document.querySelectorAll('.my_cart_quantity').forEach((el) => {
            if (cartQuantity > 0) {
                el.classList.remove('d-none');
                el.textContent = cartQuantity;
            } else {
                el.classList.add('d-none');
            }
        });
    }
}

registry.category('public.interactions').add('tynor_website_custom.bulk_size_order', TynorBulkSizeOrder);
