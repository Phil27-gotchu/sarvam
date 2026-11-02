"""Pronunciation coach service."""

from __future__ import annotations

from app.adapters.base import SarvamAdapter
from app.data.repo import Repository
from app.domain import pronunciation
from app.domain.models import PronunciationResult


async def evaluate_pronunciation(
    dish_id: str,
    audio: bytes,
    heard_override: str | None,
    repo: Repository,
    adapter: SarvamAdapter,
) -> PronunciationResult:
    dish = repo.get_dish(dish_id)
    if dish is None:
        raise KeyError(f"Dish not found: {dish_id}")

    heard = (
        heard_override.strip()
        if heard_override is not None and heard_override.strip()
        else await adapter.stt(audio, mode="translit", lang="mr-IN")
    )
    return pronunciation.score(target=dish.phonetic, heard=heard)
