"""Waiter-mode order drafting and live Marathi-to-English listening."""

from __future__ import annotations

import base64
import logging
from typing import Any

from app.adapters.base import SarvamAdapter
from app.data.repo import Repository
from app.domain import allergen_engine
from app.domain.models import SafetyStatus, TasteProfile

logger = logging.getLogger("malwani_mitra.order_service")


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
    text: str | None = None,
) -> dict[str, Any]:
    waiter_mr = (text or "").strip()
    waiter_en = ""
    if len(audio) > 100:
        try:
            waiter_en = await adapter.stt(audio, mode="translate", lang="mr-IN")
            waiter_mr = await adapter.stt(audio, mode="transcribe", lang="mr-IN")
        except Exception as e:
            logger.warning("Waiter STT failed: %s", e)

    if not waiter_en:
        if waiter_mr:
            try:
                waiter_en = await adapter.translate(waiter_mr, src="mr-IN", tgt="en-IN")
            except Exception as e:
                logger.warning("Waiter translation failed: %s", e)
                waiter_en = waiter_mr
        else:
            # Default realistic waiter situation if user clicked listen without microphone
            waiter_mr = "सुरमई फ्राय संपले आहे, पण पापलेट फ्राय आणि कोळंबी मसाला तयार आहे."
            try:
                waiter_en = await adapter.translate(waiter_mr, src="mr-IN", tgt="en-IN")
            except Exception:
                waiter_en = "Surmai Fry is finished right now, but Pomfret Fry and Prawn Masala are ready."

    safe_dishes = [
        {"id": d.id, "name_roman": d.name_roman, "name_mr": d.name_mr}
        for d in repo.list_dishes()
        if allergen_engine.check(d, profile).status == SafetyStatus.SAFE
    ][:6]

    llm_out = {}
    try:
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
    except Exception as e:
        logger.warning("Waiter reply LLM failed: %s", e)

    followup_mr = str(llm_out.get("followup_marathi") or "ठीक आहे, पापलेट फ्राय द्या.")
    followup_wav = b""
    try:
        followup_wav = await adapter.tts(followup_mr, lang="mr-IN")
    except Exception as e:
        logger.warning("Followup TTS failed: %s", e)

    return {
        "waiter_marathi": waiter_mr,
        "waiter_english": waiter_en,
        "waiter_meaning": llm_out.get("waiter_meaning") or waiter_en,
        "suggested_alternatives": llm_out.get("suggested_alternatives", ["Pomfret Fry", "Prawn Masala"]),
        "followup_marathi": followup_mr,
        "followup_english": llm_out.get("followup_english") or "Okay, please bring one Pomfret Fry instead.",
        "followup_audio_base64": base64.b64encode(followup_wav).decode("ascii") if followup_wav else "",
    }


async def speak_english(
    text: str | None,
    audio_base64: str | None,
    profile: TasteProfile,
    repo: Repository,
    adapter: SarvamAdapter,
) -> dict[str, Any]:
    english_text = (text or "").strip()
    if not english_text and audio_base64:
        raw_audio = base64.b64decode(audio_base64)
        if len(raw_audio) > 100:
            try:
                english_text = await adapter.stt(raw_audio, mode="transcribe", lang="en-IN")
            except Exception as e:
                logger.warning("English STT failed: %s", e)

    if not english_text:
        english_text = "Please make our food less spicy and bring extra rice."

    marathi_text = await adapter.translate(english_text, src="en-IN", tgt="mr-IN")
    wav_bytes = b""
    try:
        wav_bytes = await adapter.tts(marathi_text, lang="mr-IN")
    except Exception as e:
        logger.warning("English-to-Marathi TTS failed: %s", e)

    return {
        "english_text": english_text,
        "marathi_text": marathi_text,
        "audio_base64": base64.b64encode(wav_bytes).decode("ascii") if wav_bytes else "",
    }
