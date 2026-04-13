/** @odoo-module **/

const TARGET_ID = "shop-by-category-section";
const TARGET_HASH = `#${TARGET_ID}`;

const normalize = (value) => (value || "").replace(/\s+/g, " ").trim().toLowerCase();

const goToCategorySection = () => {
    const onHomepage = window.location.pathname === "/" || window.location.pathname === "/odoo";
    if (!onHomepage) {
        window.location.href = `/${TARGET_HASH}`;
        return;
    }
    const section = document.getElementById(TARGET_ID);
    if (!section) {
        window.location.hash = TARGET_HASH;
        return;
    }
    section.scrollIntoView({ behavior: "smooth", block: "start" });
    window.history.replaceState(null, "", TARGET_HASH);
};

document.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link) {
        return;
    }
    if (normalize(link.textContent) !== "shop by category") {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    goToCategorySection();
});

