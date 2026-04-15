import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { browser } from '@web/core/browser/browser';
import { rpc } from '@web/core/network/rpc';

class TynorBulkSizeOrder extends Interaction {
    static selector = '.js_tynor_bulk_size_order';
    dynamicContent = {
        '.js_tynor_size_qty': { 't-on-input': this.onQtyInput },
        '.js_tynor_bulk_clear': { 't-on-click': this.onClear },
        '.js_tynor_bulk_add_modal': { 't-on-click.prevent': this.locked(this.onAddSizes, true) },
    };

    start() {
        this.modalEl = document.getElementById('tynor_bulk_order_modal');
        this._onModalShow = this._onModalShow.bind(this);
        if (this.modalEl) {
            this.modalEl.addEventListener('show.bs.modal', this._onModalShow);
        }
        this._hideMessage();
        this._updateSummary();
    }

    destroy() {
        if (this.modalEl) {
            this.modalEl.removeEventListener('show.bs.modal', this._onModalShow);
        }
        super.destroy();
    }

    async _onModalShow() {
        this.onClear();
        await this._refreshRowPrices();
    }

    onQtyInput(ev) {
        const input = ev.currentTarget;
        const qty = parseInt(input.value || '0', 10);
        input.value = qty > 0 ? qty : 0;
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
        const addButton = this.el.querySelector('.js_tynor_bulk_add_modal');
        const sizeLines = this._collectSizeLines();
        if (!sizeLines.length) {
            this._showMessage('Please enter quantity for at least one size.', false);
            return;
        }

        const productTemplateId = parseInt(this.el.dataset.productTemplateId || '0', 10);
        if (!productTemplateId) {
            this._showMessage('Product information is incomplete. Please refresh and try again.', false);
            return;
        }

        const selectedPtavIds = this._collectSelectedPtavs();
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
        } catch (_error) {
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
            this.onClear();
            if (this.modalEl && window.bootstrap?.Modal) {
                window.bootstrap.Modal.getOrCreateInstance(this.modalEl).hide();
            }
        } else {
            this._showMessage(response?.message || 'Unable to add selected sizes.', false);
        }

        if (addButton) {
            addButton.removeAttribute('disabled');
        }
    }

    async _refreshRowPrices() {
        const productTemplateId = parseInt(this.el.dataset.productTemplateId || '0', 10);
        if (!productTemplateId) {
            return;
        }

        const selectedPtavIds = this._collectSelectedPtavs();
        let response;
        try {
            response = await this.waitFor(rpc('/shop/tynor/bulk_size_pricing', {
                product_template_id: productTemplateId,
                selected_ptav_ids: selectedPtavIds,
            }));
        } catch (_error) {
            this._showMessage('Could not refresh prices. Using previous values.', false);
            return;
        }

        if (!response?.ok || !Array.isArray(response?.rows)) {
            this._showMessage(response?.message || 'Could not refresh prices.', false);
            return;
        }

        const rowMap = new Map(response.rows.map((row) => [row.ptav_id, row]));
        this.el.querySelectorAll('.js_tynor_size_price').forEach((priceCell) => {
            const ptavId = parseInt(priceCell.dataset.ptavId || '0', 10);
            const row = rowMap.get(ptavId);
            if (!row) {
                priceCell.textContent = '-';
                priceCell.dataset.unitPrice = '0';
                return;
            }
            priceCell.textContent = row.price_display || this._formatPrice(row.unit_price || 0);
            priceCell.dataset.unitPrice = String(row.unit_price || 0);
        });
        this._updateSummary();
    }

    _collectSizeLines() {
        return Array.from(this.el.querySelectorAll('.js_tynor_size_qty'))
            .map((input) => ({
                ptav_id: parseInt(input.dataset.ptavId || '0', 10),
                qty: parseInt(input.value || '0', 10),
            }))
            .filter((line) => line.ptav_id > 0 && line.qty > 0);
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

        const lines = Array.from(this.el.querySelectorAll('.js_tynor_size_qty'))
            .map((input) => {
                const qty = parseInt(input.value || '0', 10);
                const ptavId = parseInt(input.dataset.ptavId || '0', 10);
                const priceCell = this.el.querySelector(`.js_tynor_size_price[data-ptav-id="${ptavId}"]`);
                const unitPrice = parseFloat(priceCell?.dataset?.unitPrice || '0') || 0;
                return {
                    label: input.dataset.sizeLabel || 'Size',
                    qty,
                    unitPrice,
                };
            })
            .filter((line) => line.qty > 0);

        const typesText = lines.length ? lines.map((line) => `${line.label} x${line.qty}`).join(' | ') : 'none';
        const totalQty = lines.reduce((sum, line) => sum + line.qty, 0);
        const totalAmount = lines.reduce((sum, line) => sum + (line.qty * line.unitPrice), 0);
        summaryEl.textContent = `Types: ${typesText} | Total Qty: ${totalQty} | Total: ${this._formatPrice(totalAmount)}`;
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

    _formatPrice(amount) {
        const value = Number.isFinite(amount) ? amount : 0;
        const symbol = this.el.dataset.currencySymbol || '$';
        const position = this.el.dataset.currencyPosition || 'before';
        const decimals = parseInt(this.el.dataset.currencyDecimals || '2', 10);
        const fixed = value.toFixed(Number.isNaN(decimals) ? 2 : decimals);
        return position === 'after' ? `${fixed} ${symbol}` : `${symbol}${fixed}`;
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

class TynorSizeChartModal extends Interaction {
    static selector = '.tynor-size-chart-modal';

    start() {
        if (this.el.parentElement !== document.body) {
            document.body.appendChild(this.el);
        }
    }
}

registry.category('public.interactions').add('tynor_website_custom.bulk_size_order', TynorBulkSizeOrder);
registry.category('public.interactions').add('tynor_website_custom.size_chart_modal', TynorSizeChartModal);
