"""Native chat channel inbound webhooks (Facebook, Instagram, Telegram,
TikTok, X, WhatsApp), aggregated under a single router.
"""

from fastapi import APIRouter

from api_gateway.app.adapters.inbound.http.channels.facebook import router as facebook_router
from api_gateway.app.adapters.inbound.http.channels.instagram import router as instagram_router
from api_gateway.app.adapters.inbound.http.channels.telegram import router as telegram_router
from api_gateway.app.adapters.inbound.http.channels.tiktok import router as tiktok_router
from api_gateway.app.adapters.inbound.http.channels.twitter import router as twitter_router
from api_gateway.app.adapters.inbound.http.channels.whatsapp_evolution import router as whatsapp_router

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
