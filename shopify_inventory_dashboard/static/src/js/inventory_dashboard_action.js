/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

class ShopifyInventoryDashboardAction extends Component {
    static template = "shopify_inventory_dashboard.InventoryDashboard";

    setup() {
        this.state = useState({
            loading: true,
            threshold: 5,
            kpis: {},
            lowStockLines: [],
            outOfStockLines: [],
            issues: [],
            reconcile: { summary: {}, lines: [] },
            reconciling: false,
            fixingIssueId: null,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const data = await rpc("/shopify_inventory_dashboard/data", {
            threshold: this.state.threshold,
        });
        this.state.kpis = data.kpis || {};
        this.state.lowStockLines = data.low_stock_lines || [];
        this.state.outOfStockLines = data.out_of_stock_lines || [];
        this.state.issues = data.inventory_issues || [];
        this.state.loading = false;
    }

    async onThresholdChange(ev) {
        const value = Number(ev.target.value || 0);
        this.state.threshold = Number.isFinite(value) ? value : 0;
    }

    async runReconcile(apply = false) {
        this.state.reconciling = true;
        try {
            const data = await rpc("/shopify_inventory_dashboard/reconcile", { apply });
            this.state.reconcile = data || { summary: {}, lines: [] };
            if (apply) {
                await this.loadData();
            }
        } finally {
            this.state.reconciling = false;
        }
    }

    async fixIssue(issueId) {
        if (!issueId) {
            return;
        }
        this.state.fixingIssueId = issueId;
        try {
            await rpc("/shopify_inventory_dashboard/fix_issue", { issue_id: issueId });
            await this.loadData();
            await this.runReconcile(false);
        } finally {
            this.state.fixingIssueId = null;
        }
    }
}

registry.category("actions").add("shopify_inventory_dashboard.main", ShopifyInventoryDashboardAction);
