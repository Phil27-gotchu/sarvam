"""Deterministic allergen / diet / spice safety checks."""

from __future__ import annotations

from app.domain.models import (
    Allergen,
    Dish,
    Protein,
    SafetyResult,
    SafetyStatus,
    TasteProfile,
)

HIDDEN_ALLERGENS: dict[str, list[Allergen]] = {
    "sol kadhi": [Allergen.COCONUT],
    "solkadhi": [Allergen.COCONUT],
    "kharvas": [Allergen.DAIRY],
    "ghavne": [Allergen.GLUTEN],
    "vada": [Allergen.GLUTEN],
    "vade": [Allergen.GLUTEN],
    "modak": [Allergen.GLUTEN, Allergen.COCONUT],
    "ukadiche modak": [Allergen.GLUTEN, Allergen.COCONUT],
    "shrikhand": [Allergen.DAIRY],
    "basundi": [Allergen.DAIRY],
}

INGREDIENT_ALIASES: dict[str, Allergen] = {
    "groundnut": Allergen.PEANUT,
    "peanuts": Allergen.PEANUT,
    "peanut": Allergen.PEANUT,
    "shengdana": Allergen.PEANUT,
    "cashew": Allergen.TREE_NUT,
    "cashews": Allergen.TREE_NUT,
    "kaju": Allergen.TREE_NUT,
    "almond": Allergen.TREE_NUT,
    "walnut": Allergen.TREE_NUT,
    "pistachio": Allergen.TREE_NUT,
    "prawn": Allergen.SHELLFISH,
    "prawns": Allergen.SHELLFISH,
    "shrimp": Allergen.SHELLFISH,
    "kolambi": Allergen.SHELLFISH,
    "crab": Allergen.SHELLFISH,
    "kurlya": Allergen.SHELLFISH,
    "tisrya": Allergen.SHELLFISH,
    "clam": Allergen.SHELLFISH,
    "clams": Allergen.SHELLFISH,
    "bombil": Allergen.FISH,
    "surmai": Allergen.FISH,
    "pomfret": Allergen.FISH,
    "paplet": Allergen.FISH,
    "bangda": Allergen.FISH,
    "mackerel": Allergen.FISH,
    "fish": Allergen.FISH,
    "wheat": Allergen.GLUTEN,
    "maida": Allergen.GLUTEN,
    "atta": Allergen.GLUTEN,
    "rava": Allergen.GLUTEN,
    "semolina": Allergen.GLUTEN,
    "milk": Allergen.DAIRY,
    "ghee": Allergen.DAIRY,
    "curd": Allergen.DAIRY,
    "yogurt": Allergen.DAIRY,
    "paneer": Allergen.DAIRY,
    "cream": Allergen.DAIRY,
    "butter": Allergen.DAIRY,
    "colostrum": Allergen.DAIRY,
    "egg": Allergen.EGG,
    "eggs": Allergen.EGG,
    "sesame": Allergen.SESAME,
    "til": Allergen.SESAME,
    "coconut": Allergen.COCONUT,
    "nariyal": Allergen.COCONUT,
}


def _dish_allergens(dish: Dish) -> set[Allergen]:
    found: set[Allergen] = set(dish.allergens)
    names = " ".join([dish.name_roman, dish.name_mr, *dish.aliases]).lower()
    for key, allergens in HIDDEN_ALLERGENS.items():
        if key in names:
            found.update(allergens)
    for ing in dish.ingredients:
        key = ing.strip().lower()
        if key in INGREDIENT_ALIASES:
            found.add(INGREDIENT_ALIASES[key])
        for alias, allergen in INGREDIENT_ALIASES.items():
            if alias in key:
                found.add(allergen)
    return found


def check(dish: Dish, profile: TasteProfile) -> SafetyResult:
    reasons: list[str] = []
    status = SafetyStatus.SAFE

    allergens = _dish_allergens(dish)
    overlap = allergens & set(profile.avoid_allergens)
    if overlap:
        status = SafetyStatus.BLOCK
        reasons.append(
            "Contains allergens you avoid: " + ", ".join(sorted(a.value for a in overlap))
        )

    protein = dish.flavor_dna.protein
    if profile.diet == "veg":
        if not dish.veg or protein != Protein.VEG:
            status = SafetyStatus.BLOCK
            reasons.append(f"Diet is veg but dish protein is {protein.value}")
    elif profile.diet == "vegan":
        if not dish.veg or protein != Protein.VEG:
            status = SafetyStatus.BLOCK
            reasons.append("Diet is vegan but dish is not plant-based")
        if Allergen.DAIRY in allergens or Allergen.EGG in allergens:
            status = SafetyStatus.BLOCK
            reasons.append("Diet is vegan but dish contains dairy/egg")

    if dish.spice > profile.max_spice:
        if status != SafetyStatus.BLOCK:
            status = SafetyStatus.WARN
        reasons.append(f"Spice {dish.spice}/5 exceeds your max {profile.max_spice}/5")

    if not dish.ingredients and not dish.allergens:
        if status == SafetyStatus.SAFE:
            status = SafetyStatus.WARN
        reasons.append("Unknown ingredient data — treat with caution")

    return SafetyResult(status=status, reasons=reasons)
