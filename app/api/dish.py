"""Dishes, TTS pronunciation, and grounded Q&A router."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.adapters.base import SarvamAdapter, get_sarvam_adapter
from app.data.repo import Repository, get_repo
from app.domain.models import Allergen, TasteProfile
from app.services import dish_service

router = APIRouter(tags=["dish"])


class TTSRequest(BaseModel):
    dish_id: str | None = None
    text: str | None = None
    lang: str = "mr-IN"


class AskRequest(BaseModel):
    text: str | None = None
    audio_base64: str | None = None
    profile: TasteProfile = Field(default_factory=TasteProfile)
    want_tts: bool = False


class SafetyCheckRequest(BaseModel):
    dish_id: str
    profile: TasteProfile


@router.get("/dishes")
def list_dishes(
    max_spice: int = Query(default=3, ge=1, le=5),
    diet: str = Query(default="nonveg"),
    avoid_allergens: str = Query(default=""),
    origin: str = Query(default="Australia"),
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    allergens = [
        Allergen(a.strip().lower())
        for a in avoid_allergens.split(",")
        if a.strip()
    ]
    profile = TasteProfile(
        max_spice=max_spice,
        diet=diet if diet in {"veg", "nonveg", "vegan"} else "nonveg",
        avoid_allergens=allergens,
        origin=origin,
    )
    items = dish_service.list_dishes_with_safety(repo, profile)
    return {
        "count": len(items),
        "origins": [o.country for o in repo.list_origins()],
        "items": items,
    }


@router.get("/dishes/{dish_id}")
def get_dish(
    dish_id: str,
    max_spice: int = Query(default=3, ge=1, le=5),
    diet: str = Query(default="nonveg"),
    avoid_allergens: str = Query(default=""),
    origin: str = Query(default="Australia"),
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    allergens = [
        Allergen(a.strip().lower())
        for a in avoid_allergens.split(",")
        if a.strip()
    ]
    profile = TasteProfile(
        max_spice=max_spice,
        diet=diet if diet in {"veg", "nonveg", "vegan"} else "nonveg",
        avoid_allergens=allergens,
        origin=origin,
    )
    card = dish_service.get_dish_card(dish_id, repo, profile)
    if card is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    return card


@router.post("/tts")
async def tts_endpoint(
    req: TTSRequest,
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    try:
        return await dish_service.pronounce_dish(req.dish_id, req.text, req.lang, repo, adapter)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ask")
async def ask_endpoint(
    req: AskRequest,
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    audio_bytes = base64.b64decode(req.audio_base64) if req.audio_base64 else None
    return await dish_service.ask_assistant(
        req.text,
        audio_bytes,
        req.profile,
        req.want_tts,
        repo,
        adapter,
    )
