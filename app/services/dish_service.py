"""Dish listing, detail, TTS caching, and grounded Q&A service."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from app.adapters.base import SarvamAdapter
from app.config import AUDIO_CACHE_DIR, ensure_runtime_dirs
from app.data.repo import Repository
from app.domain import allergen_engine
from app.domain.models import TasteProfile


def list_dishes_with_safety(repo: Repository, profile: TasteProfile) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in repo.list_dishes():
        safety = allergen_engine.check(d, profile)
        out.append({"dish": d.model_dump(), "safety": safety.model_dump()})
    return out


def get_dish_card(dish_id: str, repo: Repository, profile: TasteProfile) -> dict[str, Any] | None:
    dish = repo.get_dish(dish_id)
    if dish is None:
        return None
    safety = allergen_engine.check(dish, profile)
    pairings = [
        p.model_dump()
        for pid in dish.pairs_with
        if (p := repo.get_dish(pid)) is not None
    ]
    return {
        "dish": dish.model_dump(),
        "safety": safety.model_dump(),
        "pairings": pairings,
        "safety_disclaimer": "Informational only — always confirm allergies directly with restaurant staff.",
    }


async def pronounce_dish(
    dish_id: str | None,
    text: str | None,
    lang: str,
    repo: Repository,
    adapter: SarvamAdapter,
) -> dict[str, Any]:
    ensure_runtime_dirs()
    spoken_text = text
    phonetic = ""
    if dish_id:
        dish = repo.get_dish(dish_id)
        if dish is None:
            raise KeyError(f"Dish not found: {dish_id}")
        spoken_text = dish.name_mr
        phonetic = dish.phonetic
    if not spoken_text:
        raise ValueError("dish_id or text is required")

    cache_key = hashlib.sha256(f"{lang}:{spoken_text}".encode("utf-8")).hexdigest()[:24]
    cache_file = AUDIO_CACHE_DIR / f"{cache_key}.wav"
    if cache_file.exists():
        audio_bytes = cache_file.read_bytes()
        cached = True
    else:
        audio_bytes = await adapter.tts(spoken_text, lang=lang)
        cache_file.write_bytes(audio_bytes)
        cached = False

    return {
        "dish_id": dish_id,
        "text": spoken_text,
        "phonetic": phonetic,
        "cached": cached,
        "cache_key": cache_key,
        "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
        "mime_type": "audio/wav",
        "warning": adapter.tts_warning,
    }


async def ask_assistant(
    text: str | None,
    audio: bytes | None,
    profile: TasteProfile,
    want_tts: bool,
    repo: Repository,
    adapter: SarvamAdapter,
) -> dict[str, Any]:
    question = (text or "").strip()
    if audio and not question:
        question = await adapter.stt(audio, mode="transcribe", lang=profile.ui_lang or "en-IN")

    q_lower = question.lower()
    dishes = repo.list_dishes()
    relevant = [
        d for d in dishes
        if d.name_roman.lower() in q_lower
        or d.id.replace("-", " ") in q_lower
        or any(a.lower() in q_lower for a in d.aliases)
    ]
    if not relevant:
        relevant = dishes[:8]

    slim_kb = [
        {
            "id": d.id,
            "name_roman": d.name_roman,
            "name_mr": d.name_mr,
            "description": d.description,
            "veg": d.veg,
            "spice": d.spice,
            "ingredients": d.ingredients,
            "allergens": [a.value for a in d.allergens],
            "pairs_with": d.pairs_with,
        }
        for d in relevant
    ]
    llm_resp = await adapter.ask(
        f"Answer the diner's question using ONLY the KB dishes provided. Return JSON {{\"answer\": str, \"referenced_dish_ids\": [str]}}. Question: {question}",
        {"task": "qa", "question": question, "profile": profile.model_dump(), "dishes": slim_kb},
    )
    answer = str(llm_resp.get("answer", ""))
    audio_b64: str | None = None
    if want_tts and answer:
        wav = await adapter.tts(answer, lang="en-IN")
        audio_b64 = base64.b64encode(wav).decode("ascii")
    return {
        "question": question,
        "answer": answer,
        "referenced_dish_ids": llm_resp.get("referenced_dish_ids", []),
        "audio_base64": audio_b64,
        "disclaimer": "Grounded in Malwani Mitra KB. Confirm severe allergies with the kitchen.",
    }
