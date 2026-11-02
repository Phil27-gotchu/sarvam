"""Waiter-mode order drafting and live Marathi-to-English listening."""

from __future__ import annotations

import base64
from typing import Any

from app.adapters.base import SarvamAdapter
from app.data.repo import Repository
from app.domain import allergen_engine
from app.domain.models import SafetyStatus, TasteProfile


async def draft_order(
    items: list[dict[str, Any]],
    profile: TasteProfile,
    repo: Repository,
    adapter: SarvamAdapter,
) -> dict[str, Any]:
    resolved: list[dict[str, Any]] = []
    warnings: list[str] = []
    for entry in items:
        dish_id = entry.get("dish_id", "")
        qty = int(entry.get("qty", 1))
        dish = repo.get_dish(dish_id)
        if dish is None:
            continue
        safety = allergen_engine.check(dish, profile)
        if safety.status != SafetyStatus.SAFE:
            warnings.extend([f"{dish.name_roman}: {r}" for r in safety.reasons])
        resolved.append(
            {
                "id": dish.id,
                "name_mr": dish.name_mr,
                "name_roman": dish.name_roman,
                "phonetic": dish.phonetic,
                "qty": qty,
            }
        )

    llm_out = await adapter.ask(
        (
            "Draft a polite Marathi restaurant order for these items including spice/allergy preferences. "
            "Return JSON: {\"marathi_text\": str, \"phonetic\": str, \"english_meaning\": str}"
        ),
        {
            "task": "order_draft",
            "items": resolved,
            "profile": profile.model_dump(),
        },
    )
    marathi_text = str(llm_out.get("marathi_text", "नमस्कार, आम्हाला ऑर्डर द्यायची आहे."))
    wav = await adapter.tts(marathi_text, lang="mr-IN")
    return {
        "items": resolved,
        "marathi_text": marathi_text,
        "phonetic": llm_out.get("phonetic", ""),
        "english_meaning": llm_out.get("english_meaning", ""),
        "safety_warnings": warnings,
        "audio_base64": base64.b64encode(wav).decode("ascii"),
        "tts_warning": adapter.tts_warning,
    }


async def listen_waiter(
    audio: bytes,
    profile: TasteProfile,
    repo: Repository,
    adapter: SarvamAdapter,
) -> dict[str, Any]:
    waiter_en = await adapter.stt(audio, mode="translate", lang="mr-IN")
    safe_dishes = [
        {"id": d.id, "name_roman": d.name_roman, "name_mr": d.name_mr}
        for d in repo.list_dishes()
        if allergen_engine.check(d, profile).status == SafetyStatus.SAFE
    ][:6]
    llm_out = await adapter.ask(
        (
            "The waiter spoke in Marathi (translated to English). Summarize what they said and suggest "
            "safe KB alternatives if an item is unavailable. Return JSON: "
            "{\"waiter_meaning\": str, \"suggested_alternatives\": [str], \"followup_marathi\": str, \"followup_english\": str}"
        ),
        {
            "task": "waiter_reply",
            "waiter_en": waiter_en,
            "alternatives": safe_dishes,
        },
    )
    followup_mr = str(llm_out.get("followup_marathi", "ठीक आहे, धन्यवाद."))
    wav = await adapter.tts(followup_mr, lang="mr-IN")
    return {
        "waiter_english": waiter_en,
        "waiter_meaning": llm_out.get("waiter_meaning", waiter_en),
        "suggested_alternatives": llm_out.get("suggested_alternatives", []),
        "followup_marathi": followup_mr,
        "followup_english": llm_out.get("followup_english", ""),
        "followup_audio_base64": base64.b64encode(wav).decode("ascii"),
    }
