import os
from typing import Dict, Any, List, Tuple

ENABLED = os.getenv("RECOMMENDER_ENABLED", "false").lower() == "true"
API_URL = os.getenv("DEVICES_API_URL", "").strip()
API_KEY = os.getenv("DEVICES_API_KEY", "").strip()
LIMIT = int(os.getenv("SUGGESTION_LIMIT", "3"))


# --- MOCKOWANA BAZA URZĄDZEŃ (offline) ---
# Możesz dowolnie rozszerzyć/podmienić. Każdy rekord:
# name: nazwa modelu
# platform: "Android" | "iOS"
# versions: lista wspieranych wersji OS (dokładne ciągi, typu "iOS 17" / "Android 14")
# available: True jeśli mamy fizycznie na stanie (tu i teraz)
INVENTORY: List[Dict[str, Any]] = [
    {"name": "iPhone 15",      "platform": "iOS",     "versions": ["iOS 17"],     "available": True},
    {"name": "iPhone 14",      "platform": "iOS",     "versions": ["iOS 17"],     "available": True},
    {"name": "iPhone 13",      "platform": "iOS",     "versions": ["iOS 17"],     "available": False},

    {"name": "Samsung Galaxy S23", "platform": "Android", "versions": ["Android 14"], "available": True},
    {"name": "Google Pixel 7",     "platform": "Android", "versions": ["Android 14"], "available": True},
    {"name": "OnePlus 11",         "platform": "Android", "versions": ["Android 14"], "available": False},
]


def _parse_os_version(os_ver: str) -> Tuple[str, str]:
    """
    Zamienia "iOS 17" -> ("ios","17"), "Android 14" -> ("android","14").
    Zwraca ("","") jeśli brak.
    """
    if not os_ver:
        return "", ""
    parts = os_ver.strip().split()
    if len(parts) < 2:
        return parts[0].lower(), ""
    return parts[0].lower(), parts[1]


def fetch_inventory(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Warstwa dostępu do danych:
    - Na DEV zwraca lokalną listę INVENTORY.
    - Docelowo podmień na wywołanie API (GET/POST) i zwróć listę słowników o tej samej strukturze.
    """
    # Przykład jak wyglądałoby wołanie API:
    # if ENABLED and API_URL:
    #     import requests
    #     headers = {"Authorization": f"Bearer {API_KEY}"}
    #     resp = requests.get(API_URL, headers=headers, timeout=6)
    #     resp.raise_for_status()
    #     return resp.json()  # upewnij się, że struktura pasuje (name/platform/versions/available)
    return INVENTORY


def suggest_devices(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Zwraca słownik:
      - status: "match" | "no_match"
      - matches: [lista urządzeń spełniających OS i platformę (+ ewentualnie model)], dostępne teraz
      - alternatives: [lista dostępnych urządzeń w tej platformie, jeśli brak matchy]
      - reason (opcjonalnie): krótki powód, czemu nie ma dopasowania
    """
    platform = (payload.get("platform") or "").strip()
    desired_os = (payload.get("os_version") or "").strip()
    device_model = (payload.get("device_model") or "").strip()
    model_specified = device_model and device_model.upper() != "TBD"

    os_family, os_major = _parse_os_version(desired_os)

    inv = fetch_inventory(payload)

    # 1) Filtrowanie po platformie
    inv_plat = [d for d in inv if (not platform or d.get("platform") == platform)]

    # 2) Filtrowanie po wersji OS (dokładne dopasowanie stringu w versions)
    inv_os = inv_plat
    if desired_os:
        inv_os = [d for d in inv_plat if desired_os in (d.get("versions") or [])]

    # 3) Jeżeli użytkownik wskazał konkretny model (device_model != TBD), zawęź
    if model_specified:
        needle = device_model.lower()
        inv_os = [d for d in inv_os if needle in (d.get("name") or "").lower()]

    # 4) Dostępne teraz
    matches_available = [d for d in inv_os if d.get("available")]

    if matches_available:
        return {
            "status": "match",
            "matches": matches_available[:LIMIT],
            "alternatives": [],
        }

    # 5) Jeśli brak matchy → pokaż dostępne alternatywy w tej platformie
    alternatives = [d for d in inv_plat if d.get("available")]
    reason = "No exact device with the requested OS version is available right now."
    if desired_os and not inv_os:
        reason = f"No device with {desired_os} is available right now."
    elif model_specified:
        reason = f"No available units of '{device_model}' matching your request."

    return {
        "status": "no_match",
        "matches": [],
        "alternatives": alternatives[:LIMIT],
        "reason": reason,
    }
