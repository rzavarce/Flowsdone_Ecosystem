"""Native chat channel inbound webhooks (Facebook, Instagram, Telegram,
TikTok, X, WhatsApp via Evolution and 360dialog, Chatwoot), aggregated under a single router.
"""

from fastapi import APIRouter

from app.adapters.inbound.http.channels.chatwoot import router as chatwoot_router
from app.adapters.inbound.http.channels.facebook import router as facebook_router
from app.adapters.inbound.http.channels.instagram import router as instagram_router
from app.adapters.inbound.http.channels.telegram import router as telegram_router
from app.adapters.inbound.http.channels.tiktok import router as tiktok_router
from app.adapters.inbound.http.channels.twitter import router as twitter_router
from app.adapters.inbound.http.channels.whatsapp_evolution import router as whatsapp_router
from app.adapters.inbound.http.channels.whatsapp_360dialog import router as whatsapp_360dialog_router

router = APIRouter()

for _sub_router in (
    facebook_router,
    instagram_router,
    twitter_router,
    telegram_router,
    tiktok_router,
    whatsapp_router,
    whatsapp_360dialog_router,
    chatwoot_router,
):
    router.include_router(_sub_router)
