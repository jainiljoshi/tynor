/** @odoo-module **/

document.addEventListener("DOMContentLoaded", () => {
    const phoneInput = document.querySelector(".js-ndis-phone");
    if (phoneInput && !phoneInput.value) {
        phoneInput.value = "+61";
    }

    const formEl = document.querySelector(".tynor-ndis-form");
    const multiselectEl = document.querySelector(".js-ndis-multiselect");
    const toggleBtn = document.querySelector(".js-ndis-dropdown-toggle");
    const searchInput = document.querySelector(".js-ndis-product-search");
    const selectEl = document.querySelector(".js-ndis-product-select");
    const optionsWrap = document.querySelector(".js-ndis-options");
    const dropdownEl = document.querySelector(".js-ndis-dropdown");
    const labelEl = document.querySelector(".js-ndis-dropdown-label");
    const tagsWrap = document.querySelector(".js-ndis-selected-tags");
    const errorEl = document.querySelector(".js-ndis-product-error");

    if (!selectEl || !tagsWrap || !optionsWrap || !dropdownEl || !toggleBtn || !multiselectEl || !labelEl) {
        return;
    }

    const getSelectedValues = () => {
        return Array.from(selectEl.selectedOptions).map((option) => option.value);
    };

    const hideError = () => {
        if (errorEl) {
            errorEl.classList.add("d-none");
        }
    };

    const updateLabel = () => {
        const selected = Array.from(selectEl.selectedOptions);
        if (!selected.length) {
            labelEl.textContent = "Select one or more products...";
            labelEl.classList.add("text-muted");
            return;
        }
        labelEl.textContent = `${selected.length} product${selected.length > 1 ? "s" : ""} selected`;
        labelEl.classList.remove("text-muted");
    };

    const renderTags = () => {
        tagsWrap.innerHTML = "";
        Array.from(selectEl.selectedOptions).forEach((option) => {
            const badge = document.createElement("span");
            badge.className = "badge rounded-pill me-1 mb-1";
            badge.textContent = option.textContent || "";
            tagsWrap.appendChild(badge);
        });
        updateLabel();
        hideError();
    };

    const buildOptions = () => {
        optionsWrap.innerHTML = "";
        Array.from(selectEl.options).forEach((option) => {
            const item = document.createElement("label");
            item.className = "tynor-ndis-option d-flex align-items-start gap-2";
            item.dataset.value = option.value;
            item.dataset.label = (option.textContent || "").toLowerCase();

            const input = document.createElement("input");
            input.type = "checkbox";
            input.className = "form-check-input mt-1";
            input.checked = option.selected;

            const text = document.createElement("span");
            text.className = "small";
            text.textContent = option.textContent || "";

            input.addEventListener("change", () => {
                option.selected = input.checked;
                renderTags();
            });

            item.addEventListener("click", (ev) => {
                // Keep dropdown open while toggling items.
                ev.stopPropagation();
                if (ev.target !== input) {
                    input.checked = !input.checked;
                    option.selected = input.checked;
                    renderTags();
                }
            });

            item.appendChild(input);
            item.appendChild(text);
            optionsWrap.appendChild(item);
        });
    };

    const syncCheckboxes = () => {
        const selectedValues = new Set(getSelectedValues());
        Array.from(optionsWrap.querySelectorAll(".tynor-ndis-option")).forEach((item) => {
            const checkbox = item.querySelector("input[type='checkbox']");
            if (checkbox) {
                checkbox.checked = selectedValues.has(item.dataset.value);
            }
        });
    };

    const applySearch = (query) => {
        const normalized = (query || "").trim().toLowerCase();
        Array.from(optionsWrap.querySelectorAll(".tynor-ndis-option")).forEach((item) => {
            const isMatch = !normalized || (item.dataset.label || "").includes(normalized);
            item.classList.toggle("d-none", !isMatch);
        });
    };

    selectEl.addEventListener("change", () => {
        syncCheckboxes();
        renderTags();
    });

    buildOptions();
    renderTags();

    toggleBtn.addEventListener("click", () => {
        const isOpen = !dropdownEl.classList.contains("d-none");
        dropdownEl.classList.toggle("d-none", isOpen);
        multiselectEl.classList.toggle("is-open", !isOpen);
        if (!isOpen && searchInput) {
            searchInput.focus();
        }
    });

    document.addEventListener("click", (ev) => {
        if (!multiselectEl.contains(ev.target)) {
            dropdownEl.classList.add("d-none");
            multiselectEl.classList.remove("is-open");
        }
    });

    dropdownEl.addEventListener("click", (ev) => {
        ev.stopPropagation();
    });

    if (searchInput) {
        searchInput.addEventListener("input", (ev) => {
            applySearch(ev.target.value || "");
        });
    }

    if (formEl) {
        formEl.addEventListener("submit", (ev) => {
            if (!getSelectedValues().length) {
                ev.preventDefault();
                if (errorEl) {
                    errorEl.classList.remove("d-none");
                }
                dropdownEl.classList.remove("d-none");
                multiselectEl.classList.add("is-open");
            }
        });
    }
});
