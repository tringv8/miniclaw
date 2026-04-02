from __future__ import annotations

from fastapi import APIRouter

from backend.utils.channels_catalog import launcher_channel_catalog

router = APIRouter()


@router.get("/api/channels/catalog")
async def channels_catalog():
    return {"channels": launcher_channel_catalog()}
