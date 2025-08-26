import os
from fastapi import APIRouter
from app.api.models import WebhookIn
from app.core.fsm import BotEngine

router = APIRouter(prefix="/webhook", tags=["webhook"])
_engine = BotEngine()
DEV_SOFT_ERRORS = os.getenv("APP_ENV","dev") == "dev"

@router.post("/tawk")
def webhook_tawk(payload: WebhookIn):
    msg = payload.message.strip()
    sid = payload.session_id.strip()
    try:
        reply = _engine.handle_message(sid, msg)
        return {"reply": reply}
    except Exception as e:
        if DEV_SOFT_ERRORS:
            return {"reply": f"(dev) Error: {str(e)}"}
        raise
