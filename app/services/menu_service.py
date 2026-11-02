"""Menu scan + fuzzy KB matching service."""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process

from app.adapters.base import SarvamAdapter
from app.data.repo import Repository
from app.domain import allergen_engine
from app.domain.models import Dish, TasteProfile


def _match_dish(query: str, dishes: list[Dish], threshold: int = 80) -> Dish | None:
    choices: dict[str, Dish] = {}
    for d in dishes:
        for label in [d.name_roman, d.name_mr, d.id.replace("-", " "), *d.aliases]:
            choices[label.lower()] = d
    hit = process.extractOne(query.strip().lower(), list(choices.keys()), scorer=fuzz.token_sort_ratio)
    if hit and hit[1] >= threshold:
        return choices[hit[0]]
    return None


async def scan_menu(
    image: bytes,
    filename: str,
    profile: TasteProfile,
    repo: Repository,
    adapter: SarvamAdapter,
) -> dict[str, Any]:
    extracted = await adapter.extract_menu(image, filename=filename)
    all_dishes = repo.list_dishes()
    cards: list[dict[str, Any]] = []
    for item in extracted:
        matched = _match_dish(item.dish, all_dishes)
        if matched is not None:
            safety = allergen_engine.check(matched, profile)
            cards.append(
                {
                    "in_kb": True,
                    "unverified_badge": not matched.verified,
                    "menu_name": item.dish,
                    "price": item.price,
                    "section": item.section,
                    "dish": matched.model_dump(),
                    "safety": safety.model_dump(),
                }
            )
        else:
            llm_info = await adapter.ask(
                f"Briefly explain what the menu item '{item.dish}' might be for a tourist, noting it is unverified.",
                {"task": "unverified_explain", "dish_name": item.dish},
            )
            cards.append(
                {
                    "in_kb": False,
                    "unverified_badge": True,
                    "badge_text": "not in KB · unverified",
                    "menu_name": item.dish,
                    "price": item.price,
                    "section": item.section,
                    "dish": None,
                    "explanation": llm_info.get("summary", "Unverified menu item — ask the waiter about ingredients."),
                    "safety": {
                        "status": "WARN",
                        "reasons": ["Not in verified KB — confirm allergens and spice with waiter"],
                    },
                }
            )
    return {"count": len(cards), "items": cards}
