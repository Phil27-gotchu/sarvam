"""JSON repository loading and validating seed data at startup."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from app.config import APP_DATA_DIR, FEEDBACK_PATH, ensure_runtime_dirs
from app.domain.models import Dish, FeedbackEntry, Origin


class Repository:
    def __init__(self, data_dir: Path = APP_DATA_DIR) -> None:
        self._data_dir = data_dir
        dishes_raw = json.loads((data_dir / "dishes.json").read_text(encoding="utf-8"))
        origins_raw = json.loads((data_dir / "origins.json").read_text(encoding="utf-8"))
        self.dishes: list[Dish] = TypeAdapter(list[Dish]).validate_python(dishes_raw)
        self.origins: list[Origin] = TypeAdapter(list[Origin]).validate_python(origins_raw)
        self._by_id: dict[str, Dish] = {d.id: d for d in self.dishes}
        self._by_country: dict[str, Origin] = {o.country.lower(): o for o in self.origins}

    def list_dishes(self) -> list[Dish]:
        return list(self.dishes)

    def get_dish(self, dish_id: str) -> Dish | None:
        return self._by_id.get(dish_id)

    def get_origin(self, country: str) -> Origin | None:
        return self._by_country.get(country.strip().lower())

    def list_origins(self) -> list[Origin]:
        return list(self.origins)

    def save_feedback(self, entry: FeedbackEntry) -> list[FeedbackEntry]:
        ensure_runtime_dirs()
        existing = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
        items = TypeAdapter(list[FeedbackEntry]).validate_python(existing)
        items.append(entry)
        FEEDBACK_PATH.write_text(
            json.dumps([x.model_dump() for x in items], indent=2) + "\n",
            encoding="utf-8",
        )
        return items


@lru_cache
def get_repo() -> Repository:
    ensure_runtime_dirs()
    return Repository()
