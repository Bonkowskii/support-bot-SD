import os
import time
from typing import Dict
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

def _load_env():
    # 1) DOTENV_PATH (jeśli ustawione ręcznie)
    explicit = os.getenv("DOTENV_PATH")
    if explicit and Path(explicit).is_file():
        load_dotenv(dotenv_path=explicit, override=True)
        return explicit

    # 2) projektowy root/ .env (app/..)
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / ".env",
        project_root / ".env.dev",
        Path.cwd() / ".env",          # aktualny katalog uruchomienia
    ]

    for p in candidates:
        if p.is_file():
            load_dotenv(dotenv_path=p, override=True)
            return str(p)

    # 3) ostatecznie: szukaj w górę od CWD
    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found, override=True)
        return found

    return "(not found)"

_ENV_SOURCE = _load_env()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.routes import router as api_router

APP_ENV = os.getenv("APP_ENV", "dev")
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "120"))

_rl_bucket: Dict[str, Dict[str, float]] = {}

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

class NoCacheDevMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        if APP_ENV == "dev":
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        return resp

app = FastAPI(title=os.getenv("APP_NAME", "Support Intake Bot"), version="1.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if APP_ENV=="dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(NoCacheDevMiddleware)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

@app.get("/")
def root():
    if os.path.isdir(STATIC_DIR):
        return RedirectResponse(url=f"/static/index.html?v={int(time.time())}")
    return PlainTextResponse("No UI here. Try /health or POST /webhook/tawk", status_code=404)

@app.get("/health")
def health():
    return {"status":"ok"}

app.include_router(api_router)
