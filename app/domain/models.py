"""Domain models for Bolo Khana."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Allergen(str, Enum):
    PEANUT = "peanut"
    TREE_NUT = "tree_nut"
    SHELLFISH = "shellfish"
    FISH = "fish"
    GLUTEN = "gluten"
    DAIRY = "dairy"
    EGG = "egg"
    SESAME = "sesame"
    COCONUT = "coconut"


class MealFormat(str, Enum):
    CURRY_PLUS_BREAD = "curry_plus_bread"
    FRIED_SNACK = "fried_snack"
    RICE_DISH = "rice_dish"
    SOUP_DRINK = "soup_drink"
    GRILLED = "grilled"
    DESSERT = "dessert"
    FLATBREAD = "flatbread"
    STEW = "stew"
    SALAD_SIDE = "salad_side"
    PICKLE_CONDIMENT = "pickle_condiment"


class CookMethod(str, Enum):
    FRIED = "fried"
    SIMMERED = "simmered"
    GRILLED = "grilled"
    STEAMED = "steamed"
    RAW = "raw"
    BAKED = "baked"
    ROASTED = "roasted"


class MealRole(str, Enum):
    MAIN = "main"
    STARTER = "starter"
    SIDE = "side"
    DRINK = "drink"
    DESSERT = "dessert"


class Protein(str, Enum):
    CHICKEN = "chicken"
    FISH = "fish"
    PRAWN = "prawn"
    MUTTON = "mutton"
    VEG = "veg"
    EGG = "egg"
    CRAB = "crab"


class SafetyStatus(str, Enum):
    SAFE = "SAFE"
    WARN = "WARN"
    BLOCK = "BLOCK"


class FlavorDNA(BaseModel):
    format: MealFormat
    method: CookMethod
    texture: list[str] = Field(default_factory=list)
    taste: list[str] = Field(default_factory=list)
    meal_role: MealRole
    protein: Protein


class Dish(BaseModel):
    id: str
    name_mr: str
    name_roman: str
    aliases: list[str] = Field(default_factory=list)
    phonetic: str
    description: str
    veg: bool
    spice: int = Field(ge=1, le=5)
    richness: int = Field(ge=1, le=5)
    ingredients: list[str] = Field(default_factory=list)
    allergens: list[Allergen] = Field(default_factory=list)
    pairs_with: list[str] = Field(default_factory=list)
    flavor_dna: FlavorDNA
    verified: bool = False


class OriginDish(BaseModel):
    name: str
    flavor_dna: FlavorDNA
    spice_ref: int = Field(ge=1, le=5)
    note: str = ""


class Origin(BaseModel):
    country: str
    popular_dishes: list[OriginDish]


class TasteProfile(BaseModel):
    max_spice: int = Field(ge=1, le=5, default=3)
    diet: Literal["veg", "nonveg", "vegan"] = "nonveg"
    avoid_allergens: list[Allergen] = Field(default_factory=list)
    origin: str = "Australia"
    ui_lang: str = "en-IN"


class SafetyResult(BaseModel):
    status: SafetyStatus
    reasons: list[str] = Field(default_factory=list)


class MenuItem(BaseModel):
    dish: str
    price: str | None = None
    section: str | None = None


class SimilarityMatch(BaseModel):
    name: str
    score: float
    similar_in: list[str]
    different_in: list[str]
    spice_ref: int
    note: str = ""


class BridgeResult(BaseModel):
    closest: SimilarityMatch
    similar_in: list[str]
    different_in: list[str]
    spice_calibration: str
    explanation: str
    translated: str | None = None


class PronunciationResult(BaseModel):
    score: int
    mismatched_syllables: list[str]
    tip: str
    heard: str
    target: str


class FeedbackEntry(BaseModel):
    dish_id: str
    origin: str
    vote: Literal["up", "down"]
