/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class ProductMasterDashboardAction extends Component {
    static template = "product_master_dashboard.ProductMasterDashboard";

    setup() {
        this.action = useService("action");
        this.state = useState({
            loading: true,
            kpis: {},
            cards: [],
            query: "",
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const data = await rpc("/product_master_dashboard/data", {});
        this.state.kpis = data.kpis || {};
        this.state.cards = data.cards || [];
        this.state.loading = false;
    }

    openKanban() {
        this.action.doAction("product_master_dashboard.action_product_master_kanban");
    }

    get filteredCards() {
        const q = (this.state.query || "").trim().toLowerCase();
        if (!q) {
            return this.state.cards;
        }
        return this.state.cards.filter((card) => {
            const name = (card.name || "").toLowerCase();
            const sku = (card.sku || "").toLowerCase();
            return name.includes(q) || sku.includes(q);
        });
    }

    formatQty(value) {
        const number = Number(value || 0);
        const rounded = Math.round(number * 100) / 100;
        return Number.isInteger(rounded) ? `${rounded}` : rounded.toFixed(2);
    }

    warehouseBarWidth(card, qty) {
        const maxQty = Math.max(1, Number(card.warehouse_max_qty || 0));
        const width = (Math.abs(Number(qty || 0)) / maxQty) * 100;
        return `${Math.max(8, Math.round(width))}%`;
    }

    warehouseSparkHeight(card, qty) {
        const maxQty = Math.max(1, Number(card.warehouse_max_qty || 0));
        const raw = (Math.abs(Number(qty || 0)) / maxQty) * 100;
        return `${Math.max(8, Math.round(raw))}%`;
    }

    warehouseShortName(name) {
        const source = (name || "").trim();
        if (!source) {
            return "-";
        }
        const compact = source.replace(/^Tynor\s+/i, "");
        if (compact.length <= 10) {
            return compact;
        }
        const initials = compact
            .split(/\s+/)
            .filter(Boolean)
            .map((word) => word[0])
            .join("")
            .toUpperCase();
        return initials || compact.slice(0, 10);
    }
}

registry.category("actions").add("product_master_dashboard.main", ProductMasterDashboardAction);
