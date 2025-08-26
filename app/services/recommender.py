import os
from typing import Dict, Any, List

from .sd_api import fetch_devices_raw

def _enabled() -> bool:
    return (os.getenv("RECOMMENDER_ENABLED", "false") or "").lower() == "true"

def _limit() -> int:
    try:
        return int(os.getenv("SUGGESTION_LIMIT", "3"))
    except Exception:
        return 3

# ---------- Normalizacja pól z Twojego API ----------

def _norm_platform(v: str) -> str:
    v = (v or "").strip().lower()
    if v.startswith("ios") or v == "apple":
        return "iOS"
    if v.startswith("android"):
        return "Android"
    return ""

def _clean_version(ver_raw: Any, platform: str) -> str:
    """
    "18.6.1\nProductVersion" -> "iOS 18.6.1" (gdy platform='iOS')
    "7.0" + Android -> "Android 7.0"
    """
    s = str(ver_raw or "").strip()
    if not s:
        return ""
    # utnij wszystko po pierwszej linii (często "\nProductVersion")
    s = s.splitlines()[0].strip()
    if platform:
        return f"{platform} {s}"
    return s

def _group_name(g: Any) -> str:
    """
    group może być stringiem ("CLEAN") albo obiektem {"name": "..."}.
    """
    if isinstance(g, dict):
        return str(g.get("name") or "").strip()
    return str(g or "").strip()

def _is_clean_group(name: str) -> bool:
    """
    Tylko DOKŁADNIE 'CLEAN' (case-insensitive).
    Nie łapiemy 'TOCLEAN', 'CLEANING', itp.
    """
    return name.upper() == "CLEAN"

def _status_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0

def _normalize_from_sd(d: Dict[str, Any]) -> Dict[str, Any]:
    name = d.get("model") or d.get("marketName") or d.get("name") or "Device"
    platform = _norm_platform(d.get("platform") or "")
    ver = _clean_version(d.get("version"), platform)
    versions = [ver] if ver else []

    status = _status_int(d.get("status"))
    group = _group_name(d.get("group"))
    ready = bool(d.get("ready"))
    present = bool(d.get("present"))

    available = _is_clean_group(group) and status == 3 and ready and present

    return {
        "name": name,
        "platform": platform,
        "versions": versions,
        "available": available,
        # pomocniczo w debugach
        "_raw": {"group": group, "status": status, "ready": ready, "present": present},
    }

def _inventory() -> List[Dict[str, Any]]:
    if not _enabled():
        # bez ENV nic nie rób — pusta lista
        return []
    raw = fetch_devices_raw()
    return [_normalize_from_sd(x) for x in raw]

# ---------- Główna funkcja dla FSM ----------

def suggest_devices(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Zwraca:
      - status: "match" | "no_match"
      - matches: urządzenia dostępne (CLEAN + Online + ready + present)
                 po filtrze platformy/OS/model
      - alternatives: (tu nie pokazujemy nic spoza CLEAN)
      - reason: powód braku dopasowań
    """
    platform = (payload.get("platform") or "").strip()
    desired_os = (payload.get("os_version") or "").strip()
    device_model = (payload.get("device_model") or "").strip()
    need_os = (payload.get("need_os_version") or "").lower() == "yes"
    model_specified = device_model and device_model.upper() != "TBD"

    inv = _inventory()

    # 1) tylko dostępne w CLEAN
    inv_clean_av = [d for d in inv if d.get("available")]

    # 2) platforma
    if platform:
        inv_clean_av = [d for d in inv_clean_av if d["platform"] == platform]

    # 3) OS (jeśli wymagany)
    if need_os and desired_os:
        inv_clean_av = [d for d in inv_clean_av if desired_os in (d.get("versions") or [])]

    # 4) model (substring, jeśli podany)
    if model_specified:
        needle = device_model.lower()
        inv_clean_av = [d for d in inv_clean_av if needle in d["name"].lower()]

    if inv_clean_av:
        return {"status": "match", "matches": inv_clean_av[:_limit()], "alternatives": []}

    reason = "No CLEAN devices matching your constraints are available right now."
    if need_os and desired_os:
        reason = f"No CLEAN device with {desired_os} is available right now."
    elif model_specified:
        reason = f"No available CLEAN units of '{device_model}'."

    return {"status": "no_match", "matches": [], "alternatives": [], "reason": reason}
