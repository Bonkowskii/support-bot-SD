import os
from fastapi import APIRouter
from app.services.sd_api import fetch_devices_raw, get_last_fetch_log
from app.services.recommender import _inventory  # użyjemy tej samej normalizacji

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/config")
def config():
    base = (os.getenv("SD_API_BASE","") or "").strip()
    key  = (os.getenv("SD_API_KEY","")  or "")
    tout = os.getenv("SD_API_TIMEOUT","")
    enabled = (os.getenv("RECOMMENDER_ENABLED","") or "")
    limit   = os.getenv("SUGGESTION_LIMIT","")
    masked = (key[:6] + "..." + key[-4:]) if len(key) > 12 else ("(set)" if key else "(empty)")
    try:
        from app.main import _ENV_SOURCE  # pokazujemy skąd wczytano .env
    except Exception:
        _ENV_SOURCE = "(unknown)"
    return {
        "SD_API_BASE": base,
        "SD_API_KEY": masked,
        "SD_API_TIMEOUT": tout,
        "RECOMMENDER_ENABLED": enabled,
        "SUGGESTION_LIMIT": limit,
        "ENV_SOURCE": _ENV_SOURCE,
    }

@router.get("/raw")
def raw():
    data = fetch_devices_raw()
    slim = []
    for d in data[:20]:
        group = d.get("group")
        group_name = group.get("name") if isinstance(group, dict) else group
        slim.append({
            "model": d.get("model") or d.get("marketName") or d.get("name"),
            "platform": d.get("platform"),
            "version": d.get("version"),
            "group": group_name,
            "status": d.get("status"),
            "ready": d.get("ready"),
            "present": d.get("present"),
        })
    return {"count": len(data), "items": slim}

@router.get("/clean")
def clean_norm():
    items = _inventory()
    # pokazujemy tylko te, które są available (czyli CLEAN+3+ready+present)
    items = [i for i in items if i.get("available")]
    # skracamy wynik
    show = []
    for i in items[:20]:
        show.append({
            "name": i["name"],
            "platform": i["platform"],
            "versions": i["versions"],
            "available": i["available"],
            # pomocniczo, żebyś widział jaka była grupa/status/ready/present:
            "_raw": i.get("_raw", {})
        })
    return {"count": len(items), "items": show}

@router.get("/fetch-log")
def fetch_log():
    return {"tries": get_last_fetch_log()}
