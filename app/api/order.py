"""Order drafting and waiter live-translate router."""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.adapters.base import SarvamAdapter, get_sarvam_adapter
from app.config import get_settings
from app.data.repo import Repository, get_repo
from app.domain.models import TasteProfile
from app.services import order_service

router = APIRouter(prefix="/order", tags=["order"])


class OrderItemInput(BaseModel):
    dish_id: str
    qty: int = Field(default=1, ge=1, le=20)


class DraftOrderRequest(BaseModel):
    items: list[OrderItemInput]
    profile: TasteProfile = Field(default_factory=TasteProfile)


class ListenBodyRequest(BaseModel):
    audio_base64: str | None = None
    profile: TasteProfile = Field(default_factory=TasteProfile)


@router.post("/draft")
async def draft_order_endpoint(
    req: DraftOrderRequest,
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    items_raw = [i.model_dump() for i in req.items]
    return await order_service.draft_order(items_raw, req.profile, repo, adapter)


@router.post("/listen")
async def listen_waiter_endpoint(
    audio: UploadFile | None = File(default=None),
    profile_json: str = Form(default="{}"),
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    settings = get_settings()
    raw = b""
    if audio is not None:
        raw = await audio.read()
        if len(raw) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Audio exceeds 5MB limit")
    try:
        pdict = json.loads(profile_json) if profile_json else {}
    except Exception:
        pdict = {}
    profile = TasteProfile.model_validate(pdict)
    return await order_service.listen_waiter(raw, profile, repo, adapter)


@router.post("/listen-json")
async def listen_waiter_json_endpoint(
    req: ListenBodyRequest,
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    raw = base64.b64decode(req.audio_base64) if req.audio_base64 else b""
    return await order_service.listen_waiter(raw, req.profile, repo, adapter)
