"""Cultural bridge service: Flavor-DNA top-3 + 105B grounding + optional Mayura translation."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import SarvamAdapter
from app.data.repo import Repository
from app.domain import similarity
from app.domain.models import FeedbackEntry

logger = logging.getLogger("malwani_mitra.bridge_service")


async def build_bridge(
    dish_id: str,
    origin_country: str,
    target_lang: str | None,
    repo: Repository,
    adapter: SarvamAdapter,
) -> dict[str, Any]:
    dish = repo.get_dish(dish_id)
    if dish is None:
        raise KeyError(f"Dish not found: {dish_id}")
    origin = repo.get_origin(origin_country)
    if origin is None:
        raise KeyError(f"Origin not found: {origin_country}")

    matches = similarity.top_k(dish.flavor_dna, origin.popular_dishes, k=3)
    top = matches[0]

    llm_json: dict[str, Any] = {}
    try:
        llm_json = await adapter.ask(
            (
                "Write a friendly cultural bridge comparing the Malwani dish to the tourist's home dishes. "
                "Return strict JSON: {\"closest\": str, \"similar_in\": [str], \"different_in\": [str], "
                "\"spice_calibration\": str, \"explanation\": str}. Always include different_in."
            ),
            {
                "task": "bridge",
                "origin": origin.country,
                "dish": {
                    "id": dish.id,
                    "name_roman": dish.name_roman,
                    "name_mr": dish.name_mr,
                    "description": dish.description,
                    "spice": dish.spice,
                    "flavor_dna": dish.flavor_dna.model_dump(),
                },
                "matches": [m.model_dump() for m in matches],
            },
        )
    except Exception as exc:
        logger.warning("LLM bridge generation failed: %s; using rule-based bridge", exc)

    explanation = str(
        llm_json.get("explanation")
        or f"{dish.name_roman} shares {', '.join(top.similar_in)} with {top.name}, while differing in {', '.join(top.different_in)}."
    )
    translated: str | None = None
    if target_lang and target_lang not in {"en", "en-IN", "en-US", "en-GB", "en-AU"}:
        translated = await adapter.translate(explanation, src="en-IN", tgt=target_lang)

    return {
        "dish_id": dish.id,
        "origin": origin.country,
        "matches": [m.model_dump() for m in matches],
        "closest": top.model_dump(),
        "similar_in": llm_json.get("similar_in") or top.similar_in,
        "different_in": llm_json.get("different_in") or top.different_in,
        "spice_calibration": llm_json.get("spice_calibration")
        or f"Malwani spice {dish.spice}/5 vs {top.name} ({top.spice_ref}/5).",
        "explanation": explanation,
        "translated": translated,
    }


def record_feedback(dish_id: str, origin: str, vote: str, repo: Repository) -> dict[str, Any]:
    entry = FeedbackEntry(dish_id=dish_id, origin=origin, vote="up" if vote == "up" else "down")
    all_entries = repo.save_feedback(entry)
    return {"saved": entry.model_dump(), "total_feedback": len(all_entries)}
