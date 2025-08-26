import os
from typing import List, Dict, Any, Tuple, Union
import requests

_LAST_FETCH_LOG: List[Dict[str, Any]] = []

def _cfg() -> Tuple[str, str, float]:
    base = (os.getenv("SD_API_BASE", "") or "").strip().strip('"').rstrip("/")
    key  = (os.getenv("SD_API_KEY", "")  or "").strip().strip('"')
    tout = float(os.getenv("SD_API_TIMEOUT", "6"))
    return base, key, tout

def _headers(api_key: str) -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h

def _log_attempt(url: str, status: Union[int, str], count: int, note: str = ""):
    global _LAST_FETCH_LOG
    _LAST_FETCH_LOG.append({"url": url, "status": status, "count": count, "note": note})
    if len(_LAST_FETCH_LOG) > 12:
        _LAST_FETCH_LOG = _LAST_FETCH_LOG[-12:]

def get_last_fetch_log() -> List[Dict[str, Any]]:
    return _LAST_FETCH_LOG or []

def _extract_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("devices", "items", "results"):
            v = data.get(k)
            if isinstance(v, list):
                return v
        for k in ("data", "payload", "content"):
            v = data.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                out = _extract_list(v)
                if out:
                    return out
        # płytki przegląd zagnieżdżeń
        for v in data.values():
            if isinstance(v, dict):
                out = _extract_list(v)
                if out:
                    return out
    return []

def _try_get(url: str, headers: Dict[str, str], timeout: float) -> Tuple[int, List[Dict[str, Any]], str]:
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        status = r.status_code
        if status != 200:
            text = ""
            try:
                text = r.text
                if len(text) > 200:
                    text = text[:200] + "..."
            except Exception:
                pass
            return status, [], text
        try:
            data = r.json()
        except Exception:
            return status, [], "non-JSON response"
        arr = _extract_list(data)
        return status, arr if isinstance(arr, list) else [], ""
    except requests.RequestException as e:
        return -1, [], f"request error: {e!r}"
    except Exception as e:
        return -2, [], f"unexpected error: {e!r}"

def fetch_devices_raw() -> List[Dict[str, Any]]:
    """
    Preferowane: /api/v1/devices (wg Twojego kodu), ale próbujemy też:
    /api/devices, /devices, /api/public/devices?group=clean
    """
    global _LAST_FETCH_LOG
    _LAST_FETCH_LOG = []

    base, key, tout = _cfg()
    if not base:
        _log_attempt("<no-base>", "N/A", 0, "SD_API_BASE missing")
        return []

    headers = _headers(key)
    candidates = [
        f"{base}/api/v1/devices",
        f"{base}/api/devices",
        f"{base}/devices",
        f"{base}/api/public/devices?group=clean",
    ]

    for url in candidates:
        status, arr, note = _try_get(url, headers=headers, timeout=tout)
        _log_attempt(url, status, len(arr), note)
        if status == 200 and arr:
            return arr

    return []
