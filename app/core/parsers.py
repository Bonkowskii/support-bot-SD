import regex as re
from typing import Dict, Any, Optional
from .slots import Slots

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
DATE_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*(?:to|→|-|–|\s)\s*(\d{4}-\d{2}-\d{2})", re.I)

QTY_RE_1 = re.compile(r"\b(?:need|want|require|rent|hire|order)\s+(\d{1,3})\b", re.I)
QTY_RE_2 = re.compile(r"\b(\d{1,3})\s*(?:devices?|phones?|units?)\b", re.I)
QTY_BARE = re.compile(r"^\s*(\d{1,3})\s*$")

UNK_RE = re.compile(r"\b(idk|i\s*don'?t\s*know|not\s*sure|any|whatever)\b", re.I)
BRAND_RE = re.compile(r"\b(samsung|iphone|apple|galaxy|pixel|oneplus|xiaomi|huawei|sony)\b", re.I)
DEVICE_PAT = re.compile(r"(pixel\s?\d+\s?(pro|max)?|iphone\s?\d+\s?(pro|max)?|galaxy\s?[a-z0-9]+)", re.I)

COUNTRY_MAP = {
    "poland": "Poland", "polska": "Poland", "pl": "Poland", "warsaw": "Poland", "warszawa": "Poland",
    "germany": "Germany", "niemcy": "Germany", "de": "Germany", "deutschland": "Germany", "berlin": "Germany",
    "ghana": "Ghana", "gh": "Ghana", "accra": "Ghana",
}

NUMBER_WORDS = { "one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10 }
NUMWORD_RE = re.compile(r"\b(" + "|".join(NUMBER_WORDS.keys()) + r")\b", re.I)

def parse_message(text: str, slots: Slots) -> Dict[str, Any]:
    t = (text or "").strip()
    out: Dict[str, Any] = {}

    # platform
    if re.search(r"\bandroid\b", t, re.I): out["platform"] = "Android"
    if re.search(r"\bios\b|iphone|ipad|apple", t, re.I): out["platform"] = "iOS"

    # ilość (z kontekstem)
    m = QTY_RE_1.search(t) or QTY_RE_2.search(t)
    if m:
        try:
            q = int(m.group(1))
            if q > 0: out["quantity"] = q
        except: pass

    # e-mail
    m = EMAIL_RE.search(t)
    if m: out["contact_email"] = m.group(0)

    # zakres dat
    m = DATE_RANGE_RE.search(t)
    if m:
        out["rental_dates"] = f"{m.group(1)} \u2192 {m.group(2)}"

    # accessories
    acc_vals = slots.defs.get("accessories", {}).get("values", [])
    sel = [v for v in acc_vals if re.search(rf"\b{re.escape(v)}\b", t, re.I)]
    if sel: out["accessories"] = sel

    # os_version (np. Android 14 / iOS 17)
    m = re.search(r"\b(android|ios)\s*([0-9]{1,2})\b", t, re.I)
    if m:
        out["os_version"] = f"{m.group(1).capitalize()} {m.group(2)}"

    # model (konkret) / IDK
    m = DEVICE_PAT.search(t)
    if m:
        out["device_model"] = re.sub(r"\s+", " ", m.group(0).strip()).title()
    elif UNK_RE.search(t):
        out["device_model"] = "TBD"

    # location
    for key, canon in COUNTRY_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", t, re.I):
            out["location"] = canon
            break
    if re.search(r"\bother\b", t, re.I):
        out["location"] = "Other"

    return out

def try_coerce_quantity_loose(text: str) -> Optional[int]:
    t = (text or "").strip()
    if not t: return None
    m = NUMWORD_RE.search(t)
    if m: return NUMBER_WORDS[m.group(1).lower()]
    m = QTY_BARE.match(t)
    if m:
        try:
            q = int(m.group(1))
            if q > 0: return q
        except: return None
    return None
