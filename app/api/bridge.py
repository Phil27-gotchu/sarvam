"""Cultural bridge router."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.adapters.base import SarvamAdapter, get_sarvam_adapter
from app.data.repo import Repository, get_repo
from app.services import bridge_service

router = APIRouter(prefix="/bridge", tags=["bridge"])


class FeedbackRequest(BaseModel):
    dish_id: str
    origin: str
    vote: Literal["up", "down"]


@router.get("/{dish_id}")
async def get_bridge(
    dish_id: str,
    origin: str = Query(default="Australia"),
    lang: str | None = Query(default=None),
    repo: Repository = Depends(get_repo),
    adapter: SarvamAdapter = Depends(get_sarvam_adapter),
) -> dict[str, Any]:
    try:
        return await bridge_service.build_bridge(dish_id, origin, lang, repo, adapter)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/feedback")
def post_feedback(
    req: FeedbackRequest,
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    return bridge_service.record_feedback(req.dish_id, req.origin, req.vote, repo)
