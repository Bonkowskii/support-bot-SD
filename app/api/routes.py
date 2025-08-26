from fastapi import APIRouter
from .webhook_tawk import router as tawk_router
import os

router = APIRouter()
router.include_router(tawk_router)

if os.getenv("APP_ENV","dev") == "dev":
    from .routes_debug import router as debug_router
    router.include_router(debug_router)
