from fastapi import APIRouter

from .facebook import router as facebook_router
from .instagram import router as instagram_router
from .telegram import router as telegram_router
from .tiktok import router as tiktok_router
from .twitter import router as twitter_router
from .whatsapp_evolution import router as whatsapp_router

router = APIRouter()

for _sub_router in (
    facebook_router,
    instagram_router,
    twitter_router,
    telegram_router,
    tiktok_router,
    whatsapp_router,
):
    router.include_router(_sub_router)
