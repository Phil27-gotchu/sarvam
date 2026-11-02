"""Menu scanning router."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.adapters.base import SarvamAdapter, get_sarvam_adapter
from app.config import get_settings
from app.data.repo import Repository, get_repo
from app.domain.models import TasteProfile
from app.services import menu_service

router = APIRouter(prefix="/menu", tags=["menu"])


@router.post("/scan")
async def scan_menu_endpoint(
    image: UploadFile | None = File(default=None),
    profile_json: str = Form(default="{}"),
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    settings = get_settings()
    raw_bytes = b""
    filename = "menu.jpg"
    if image is not None:
        raw_bytes = await image.read()
        filename = image.filename or "menu.jpg"
        if len(raw_bytes) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Upload exceeds 5MB limit")
    try:
        profile_dict = json.loads(profile_json) if profile_json else {}
    except Exception:
        profile_dict = {}
    profile = TasteProfile.model_validate(profile_dict)
    return await menu_service.scan_menu(raw_bytes, filename, profile, repo, adapter)
