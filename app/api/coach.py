"""Pronunciation coach router."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.adapters.base import SarvamAdapter, get_sarvam_adapter
from app.config import get_settings
from app.data.repo import Repository, get_repo
from app.services import coach_service

router = APIRouter(tags=["coach"])


class CoachJsonRequest(BaseModel):
    dish_id: str
    audio_base64: str | None = None
    heard_text: str | None = None


@router.post("/coach")
async def coach_multipart(
    dish_id: str = Form(...),
    heard_text: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
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
        res = await coach_service.evaluate_pronunciation(dish_id, raw, heard_text, repo, adapter)
        return res.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/coach/json")
async def coach_json(
    req: CoachJsonRequest,
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    raw = base64.b64decode(req.audio_base64) if req.audio_base64 else b""
    try:
        res = await coach_service.evaluate_pronunciation(
            req.dish_id, raw, req.heard_text, repo, adapter
        )
        return res.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
