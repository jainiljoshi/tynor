/** @odoo-module **/

document.addEventListener("DOMContentLoaded", () => {
    const banner = document.querySelector("[data-tynor-banner='1']");
    if (!banner) {
        return;
    }
    const closeBtn = banner.querySelector("[data-tynor-banner-close='1']");
    if (!closeBtn) {
        return;
    }

    const text = (banner.textContent || "").trim();
    const key = `tynor_wholesale_banner_dismissed_${btoa(unescape(encodeURIComponent(text))).slice(0, 24)}`;

    if (window.localStorage.getItem(key) === "1") {
        banner.style.display = "none";
        return;
    }

    closeBtn.addEventListener("click", () => {
        banner.style.display = "none";
        window.localStorage.setItem(key, "1");
    });
});
