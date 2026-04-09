/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { formatDateTime, serializeDateTime } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class TynorWholesalerDashboardAction extends Component {
    static template = "tynor_wholesaler_reporting.WholesalerDashboard";

    setup() {
        this.action = useService("action");
        this.state = useState({
            loading: true,
            kpis: {},
            channels: [],
            dateFrom: false,
            dateTo: false,
        });
        const getPickerProps = () => ({
            value: [this.state.dateFrom || false, this.state.dateTo || false],
            type: "datetime",
            range: true,
        });
        this.dateTimePicker = useDateTimePicker({
            target: "range-trigger",
            startDateRefName: "range-start",
            endDateRefName: "range-end",
            get pickerProps() {
                return getPickerProps();
            },
            onApply: (value) => this.onDateRangeApply(value),
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    onDateRangeApply(value) {
        const [fromValue, toValue] = Array.isArray(value) ? value : [value, false];
        this.state.dateFrom = this._normalizeBoundaryDateTime(fromValue, false);
        this.state.dateTo = this._normalizeBoundaryDateTime(toValue, true);
    }

    _normalizeBoundaryDateTime(value, isEnd) {
        if (!value) {
            return false;
        }
        const parts = isEnd
            ? { hour: 23, minute: 59, second: 59, millisecond: 0 }
            : { hour: 0, minute: 0, second: 0, millisecond: 0 };
        if (typeof value.set === "function") {
            return value.set(parts);
        }
        const normalized = new Date(value);
        normalized.setHours(parts.hour, parts.minute, parts.second, parts.millisecond);
        return normalized;
    }

    buildDateDomain() {
        const domain = [];
        const fromValue = this.state.dateFrom ? serializeDateTime(this.state.dateFrom) : "";
        const toValue = this.state.dateTo ? serializeDateTime(this.state.dateTo) : "";
        if (fromValue) {
            domain.push(["invoice_datetime", ">=", fromValue]);
        }
        if (toValue) {
            domain.push(["invoice_datetime", "<=", toValue]);
        }
        return domain;
    }

    async loadData() {
        this.state.loading = true;
        const payload = {
            date_from: this.state.dateFrom ? serializeDateTime(this.state.dateFrom) : "",
            date_to: this.state.dateTo ? serializeDateTime(this.state.dateTo) : "",
        };
        const data = await rpc("/tynor_wholesaler/dashboard_data", payload);
        this.state.kpis = data.kpis || {};
        this.state.channels = data.channels || [];
        this.state.loading = false;
    }

    async applyFilters() {
        await this.loadData();
    }

    async clearFilters() {
        this.state.dateFrom = false;
        this.state.dateTo = false;
        await this.loadData();
    }

    onDateRangeClick() {
        this.dateTimePicker.open(0);
    }

    get dateRangeLabel() {
        const fromLabel = this.state.dateFrom ? formatDateTime(this.state.dateFrom) : "";
        const toLabel = this.state.dateTo ? formatDateTime(this.state.dateTo) : "";
        if (fromLabel && toLabel) {
            return `${fromLabel} -> ${toLabel}`;
        }
        if (fromLabel) {
            return `${fromLabel} ->`;
        }
        return "Select from / to";
    }

    openPivot() {
        this.action.doAction("tynor_wholesaler_reporting.action_tynor_wholesaler_report", {
            additionalContext: {
                search_default_group_invoice_date: 1,
            },
            domain: this.buildDateDomain(),
        });
    }

    openPaymentMapping() {
        this.action.doAction("tynor_shopify_inbound_bridge.action_tynor_payment_journal_map");
    }

    formatAmount(value) {
        const number = Number(value || 0);
        return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
}

registry.category("actions").add("tynor_wholesaler_reporting.dashboard", TynorWholesalerDashboardAction);
