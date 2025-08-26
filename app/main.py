import os
import time
from typing import Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.routes import router as api_router

APP_ENV = os.getenv("APP_ENV", "dev")
MAX_MESSAGE_LEN = int(os.getenv("MAX_MESSAGE_LEN", "2000"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "120"))

# prosta pamięć rate-limit
_rl_bucket: Dict[str, Dict[str, float]] = {}  # ip -> {"cnt": n, "ts": epoch}

class SizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and int(cl) > 256 * 1024:
            return JSONResponse({"detail":"Payload too large"}, status_code=413)
        return await call_next(request)

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "0.0.0.0"
        now = time.time()
        bucket = _rl_bucket.get(ip, {"cnt": 0, "ts": now})
        if now - bucket["ts"] > RATE_LIMIT_WINDOW:
            bucket = {"cnt": 0, "ts": now}
        bucket["cnt"] += 1
        _rl_bucket[ip] = bucket
        if bucket["cnt"] > RATE_LIMIT_MAX:
            return JSONResponse({"detail": "Too many requests"}, status_code=429)
        return await call_next(request)

app = FastAPI(title=os.getenv("APP_NAME", "Support Intake Bot"), version="1.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if APP_ENV=="dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)

# === Statyki ===
# Zakładam plik: app/static/index.html
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Root → redirect do /static/index.html (jeśli statyki istnieją), inaczej 404-info
@app.get("/")
def root():
    if os.path.isdir(STATIC_DIR):
        return RedirectResponse(url="/static/index.html")
    return PlainTextResponse("No UI here. Try POST /webhook/tawk or /health.", status_code=404)

@app.get("/health")
def health():
    return {"status":"ok"}

# Debug tylko w dev
if APP_ENV == "dev":
    from app.core.slots import Slots
    @app.get("/debug/slots", response_class=PlainTextResponse)
    def debug_slots():
        s = Slots.load(force_reload=True)
        return f"ORDER: {s.order}\nDEFS: {list(s.defs.keys())}"

app.include_router(api_router)
