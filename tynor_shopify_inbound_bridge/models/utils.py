import re


ORDER_PATTERNS = [
    re.compile(r"shopify\s*order\s*(?:no|number)?\s*[:#-]\s*([A-Za-z0-9\-_/]+)", re.IGNORECASE),
    re.compile(r"\border\s*(?:no|number)?\s*[:#-]\s*([A-Za-z0-9\-_/]+)", re.IGNORECASE),
]

PAYMENT_PATTERNS = [
    re.compile(r"shopify\s*payment\s*method\s*[:#-]\s*(.+)$", re.IGNORECASE),
    re.compile(r"\bpayment\s*method\s*[:#-]\s*(.+)$", re.IGNORECASE),
]

PAYMENT_ALIASES = {
    "visa": "visa",
    "master": "mastercard",
    "master card": "mastercard",
    "mastercard": "mastercard",
    "mc": "mastercard",
    "paypal": "paypal",
    "pay pal": "paypal",
    "afterpay": "afterpay",
    "after pay": "afterpay",
    "cash": "cash",
    "manual": "manual",
    "mydeal": "mydeal",
    "my deal": "mydeal",
}


def strip_shopify_label(text):
    value = (text or "").strip()
    if not value:
        return ""
    value = re.sub(r"^\s*shopify\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_payment_key(raw_value):
    value = (raw_value or "").strip()
    if not value:
        return ""
    value = strip_shopify_label(value)
    value = re.sub(r"^\s*payment\s*method\s*[:#-]?\s*", "", value, flags=re.IGNORECASE).strip()
    if not value:
        return ""
    first_value = re.split(r"[,;/|]+", value)[0].strip().lower()
    first_value = re.sub(r"\s+", " ", first_value)
    return PAYMENT_ALIASES.get(first_value, re.sub(r"[^a-z0-9]+", "_", first_value).strip("_"))


def normalize_payment_display(raw_value):
    normalized = normalize_payment_key(raw_value)
    if not normalized:
        return ""
    label = normalized.replace("_", " ").strip()
    if label == "paypal":
        return "PayPal"
    if label == "mydeal":
        return "MyDeal"
    if label == "mastercard":
        return "Mastercard"
    if label == "visa":
        return "Visa"
    return label.title()


def extract_external_values(lines):
    order_no = ""
    payment_raw = ""
    for line in lines or []:
        text = (line or "").strip()
        if not text:
            continue
        if not order_no:
            for pattern in ORDER_PATTERNS:
                match = pattern.search(text)
                if match:
                    order_no = (match.group(1) or "").strip()
                    break
        if not payment_raw:
            for pattern in PAYMENT_PATTERNS:
                match = pattern.search(text)
                if match:
                    payment_raw = (match.group(1) or "").strip()
                    break
    return {
        "order_no": order_no,
        "payment_method_raw": payment_raw,
        "payment_method": normalize_payment_display(payment_raw),
    }
