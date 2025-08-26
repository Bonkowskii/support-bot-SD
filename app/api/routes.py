from fastapi import APIRouter
from .webhook_tawk import router as tawk_router

router = APIRouter()
router.include_router(tawk_router)
