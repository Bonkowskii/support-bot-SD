import os
import regex as re
from typing import Any
from datetime import datetime, timedelta
from .slots import Slots

MAX_QTY = int(os.getenv("MAX_QUANTITY","200"))
MAX_RENTAL_DAYS = int(os.getenv("MAX_RENTAL_DAYS","120"))
MIN_RENTAL_DAYS = int(os.getenv("MIN_RENTAL_DAYS","1"))

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)

def _valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except:
        return False

def validate_slot(slot: str, value: Any, slots: Slots) -> bool:
    # brak wartości
    if value in (None, "", []):
        return False if slots.defs[slot].get("required", False) else True

    # specjalne przypadki
    if slot == "device_model" and str(value).strip().upper() == "TBD":
        return True

    typ = slots.defs[slot]["type"]

    if typ == "enum":
        return str(value) in slots.defs[slot]["values"]

    if typ == "multienum":
        vals = slots.defs[slot]["values"]
        if not isinstance(value, list):
            return False
        # normalizacja i filtr tylko znanych
        cleaned = [v for v in value if v in vals]
        return len(cleaned) == len(value)

    if typ == "int":
        try:
            q = int(value)
            return 1 <= q <= MAX_QTY
        except:
            return False

    if typ == "email":
        return EMAIL_RE.search(str(value)) is not None

    if typ == "daterange":
        m = re.search(r"^(\d{4}-\d{2}-\d{2})\s*→\s*(\d{4}-\d{2}-\d{2})$", str(value))
        if not m: return False
        d1s, d2s = m.group(1), m.group(2)
        if not (_valid_date(d1s) and _valid_date(d2s)): return False
        d1, d2 = datetime.strptime(d1s,"%Y-%m-%d"), datetime.strptime(d2s,"%Y-%m-%d")
        if d2 < d1: return False
        days = (d2 - d1).days + 1
        return MIN_RENTAL_DAYS <= days <= MAX_RENTAL_DAYS

    if typ == "yesno":
        v = str(value).strip().lower()
        return v in ("yes", "no")

    # string / inne
    return True
