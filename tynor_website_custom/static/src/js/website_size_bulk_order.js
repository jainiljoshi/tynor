import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { browser } from '@web/core/browser/browser';
import { rpc } from '@web/core/network/rpc';

class TynorBulkSizeOrder extends Interaction {
    static selector = '.js_tynor_bulk_size_order';
    dynamicContent = {
        '.js_tynor_single_qty': { 't-on-input': this.onQtyInput },
        '.js_tynor_add_line': { 't-on-click.prevent': this.onAddLine },
        '.js_tynor_bulk_clear': { 't-on-click': this.onClear },
        '.js_tynor_bulk_add': { 't-on-click.prevent': this.locked(this.onAddSizes, true) },
    };

    start() {
        this.pendingLines = new Map();
        this._onContainerClick = this._onContainerClick.bind(this);
        this.el.addEventListener('click', this._onContainerClick);
        this._hideMessage();
        this._renderPendingLines();
        this._updateSummary();
    }

    destroy() {
        this.el.removeEventListener('click', this._onContainerClick);
        super.destroy();
    }

    onQtyInput() {
        const qtyInput = this.el.querySelector('.js_tynor_single_qty');
        if (!qtyInput) {
            return;
        }
        const qty = parseInt(qtyInput.value || '1', 10);
        qtyInput.value = qty > 0 ? qty : 1;
    }

    onAddLine() {
        const sizeSelect = this.el.querySelector('.js_tynor_size_select');
        const qtyInput = this.el.querySelector('.js_tynor_single_qty');
        if (!sizeSelect || !qtyInput) {
            this._showMessage('Size controls are unavailable. Please refresh the page.', false);
            return;
        }

        const ptavId = parseInt(sizeSelect.value || '0', 10);
        const qty = parseInt(qtyInput.value || '0', 10);
        const selectedOption = sizeSelect.options[sizeSelect.selectedIndex];
        const sizeLabel = selectedOption?.dataset?.sizeLabel || selectedOption?.textContent?.trim() || 'Size';

        if (!ptavId || !qty || qty < 1) {
            this._showMessage('Please choose a size and quantity.', false);
            return;
        }

        const existingLine = this.pendingLines.get(ptavId);
        const mergedQty = qty + (existingLine?.qty || 0);
        this.pendingLines.set(ptavId, { ptav_id: ptavId, qty: mergedQty, label: sizeLabel });

        qtyInput.value = 1;
        this._hideMessage();
        this._renderPendingLines();
        this._updateSummary();
    }

    onClear() {
        this.pendingLines.clear();
        this._hideMessage();
        this._renderPendingLines();
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
            this._playCartJumpAnimation(response?.total_added || sizeLines.length, addButton);
            this._showMessage(response.message || 'Sizes added to cart.', true);
            this.pendingLines.clear();
            this._renderPendingLines();
        } else {
            this._showMessage(response?.message || 'Unable to add selected sizes.', false);
        }

        this._updateSummary();
        if (addButton) {
            addButton.removeAttribute('disabled');
        }
    }

    _collectSizeLines() {
        return Array.from(this.pendingLines.values())
            .map((line) => ({ ptav_id: line.ptav_id, qty: line.qty }))
            .filter((line) => line.qty > 0 && line.ptav_id > 0);
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

        const entries = Array.from(this.pendingLines.values()).map((line) => `${line.label} x${line.qty}`);
        const totalQty = Array.from(this.pendingLines.values()).reduce((acc, line) => acc + line.qty, 0);

        const typesText = entries.length ? entries.join(' | ') : 'none';
        summaryEl.textContent = `Types: ${typesText} | Total Qty: ${totalQty}`;
    }

    _renderPendingLines() {
        const listEl = this.el.querySelector('.js_tynor_bulk_selected_list');
        if (!listEl) {
            return;
        }
        if (!this.pendingLines.size) {
            listEl.innerHTML = '<span class="text-muted small">No sizes added yet.</span>';
            return;
        }

        const lineHtml = Array.from(this.pendingLines.values())
            .map(
                (line) =>
                    `<span class="badge rounded-pill text-bg-light border me-1 mb-1">${line.label} x${line.qty} <button type="button" class="btn-close btn-close-sm ms-1 js_tynor_remove_line" data-ptav-id="${line.ptav_id}" aria-label="Remove"></button></span>`
            )
            .join('');

        listEl.innerHTML = lineHtml;
    }

    _onContainerClick(ev) {
        const removeBtn = ev.target.closest('.js_tynor_remove_line');
        if (!removeBtn) {
            return;
        }
        const ptavId = parseInt(removeBtn.dataset.ptavId || '0', 10);
        if (!ptavId) {
            return;
        }
        this.pendingLines.delete(ptavId);
        this._renderPendingLines();
        this._updateSummary();
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

    _playCartJumpAnimation(addedQty, sourceEl) {
        if (!sourceEl) {
            return;
        }
        const cartEl =
            document.querySelector('.o_wsale_my_cart') ||
            document.querySelector('a[href*="/shop/cart"]') ||
            document.querySelector('.my_cart_quantity');
        if (!cartEl) {
            return;
        }

        const from = sourceEl.getBoundingClientRect();
        const to = cartEl.getBoundingClientRect();
        const bubble = document.createElement('div');
        bubble.className = 'tynor-cart-jump-bubble';
        bubble.textContent = `+${addedQty}`;
        bubble.style.left = `${from.left + from.width / 2}px`;
        bubble.style.top = `${from.top + from.height / 2}px`;
        document.body.appendChild(bubble);

        const dx = to.left + to.width / 2 - (from.left + from.width / 2);
        const dy = to.top + to.height / 2 - (from.top + from.height / 2);
        bubble.animate(
            [
                { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 },
                { transform: `translate(${dx - 20}px, ${dy - 20}px) scale(0.55)`, opacity: 0.25 },
            ],
            { duration: 650, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)', fill: 'forwards' }
        ).onfinish = () => {
            bubble.remove();
        };
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
