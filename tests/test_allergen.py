"""Unit tests for deterministic allergen_engine."""

from __future__ import annotations

from app.data.repo import get_repo
from app.domain import allergen_engine
from app.domain.models import (
    Allergen,
    CookMethod,
    Dish,
    FlavorDNA,
    MealFormat,
    MealRole,
    Protein,
    SafetyStatus,
    TasteProfile,
)


def test_peanut_allergy_blocks_peanut_dish() -> None:
    repo = get_repo()
    chutney = repo.get_dish("shengdana-chutney")
    assert chutney is not None
    profile = TasteProfile(avoid_allergens=[Allergen.PEANUT])
    res = allergen_engine.check(chutney, profile)
    assert res.status == SafetyStatus.BLOCK
    assert any("peanut" in r for r in res.reasons)


def test_hidden_allergen_sol_kadhi_coconut() -> None:
    dish = Dish(
        id="custom-sol-kadhi",
        name_mr="सोलकढी",
        name_roman="Sol Kadhi",
        phonetic="sohl kuh-dhee",
        description="Kokum drink",
        veg=True,
        spice=2,
        richness=2,
        ingredients=["kokum", "water"],
        allergens=[],
        flavor_dna=FlavorDNA(
            format=MealFormat.SOUP_DRINK,
            method=CookMethod.RAW,
            meal_role=MealRole.DRINK,
            protein=Protein.VEG,
        ),
    )
    profile = TasteProfile(avoid_allergens=[Allergen.COCONUT])
    res = allergen_engine.check(dish, profile)
    assert res.status == SafetyStatus.BLOCK


def test_veg_profile_blocks_chicken_and_fish() -> None:
    repo = get_repo()
    kombdi = repo.get_dish("kombdi-vade")
    assert kombdi is not None
    profile = TasteProfile(diet="veg", max_spice=5)
    res = allergen_engine.check(kombdi, profile)
    assert res.status == SafetyStatus.BLOCK


def test_spice_exceeded_returns_warn() -> None:
    repo = get_repo()
    bhakri = repo.get_dish("kulith-pithla")
    assert bhakri is not None
    profile = TasteProfile(diet="veg", max_spice=1)
    res = allergen_engine.check(bhakri, profile)
    assert res.status == SafetyStatus.WARN


def test_unknown_ingredients_returns_warn() -> None:
    mystery = Dish(
        id="mystery",
        name_mr="अज्ञात",
        name_roman="Mystery Dish",
        phonetic="mis-tree",
        description="No ingredients listed",
        veg=True,
        spice=1,
        richness=1,
        ingredients=[],
        allergens=[],
        flavor_dna=FlavorDNA(
            format=MealFormat.STEW,
            method=CookMethod.SIMMERED,
            meal_role=MealRole.MAIN,
            protein=Protein.VEG,
        ),
    )
    res = allergen_engine.check(mystery, TasteProfile())
    assert res.status == SafetyStatus.WARN
