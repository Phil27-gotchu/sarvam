"""Flavor-DNA similarity for cultural bridge."""

from __future__ import annotations

from app.domain.models import FlavorDNA, OriginDish, SimilarityMatch

W_FORMAT = 0.30
W_METHOD = 0.15
W_MEAL_ROLE = 0.15
W_PROTEIN = 0.15
W_TASTE = 0.15
W_TEXTURE = 0.10


def _jaccard(a: list[str], b: list[str]) -> float:
    sa = {x.strip().lower() for x in a if x.strip()}
    sb = {x.strip().lower() for x in b if x.strip()}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def score_pair(a: FlavorDNA, b: FlavorDNA) -> tuple[float, list[str], list[str]]:
    similar: list[str] = []
    different: list[str] = []
    total = 0.0

    if a.format == b.format:
        total += W_FORMAT
        similar.append(f"format:{a.format.value}")
    else:
        different.append(f"format:{a.format.value} vs {b.format.value}")

    if a.method == b.method:
        total += W_METHOD
        similar.append(f"method:{a.method.value}")
    else:
        different.append(f"method:{a.method.value} vs {b.method.value}")

    if a.meal_role == b.meal_role:
        total += W_MEAL_ROLE
        similar.append(f"meal_role:{a.meal_role.value}")
    else:
        different.append(f"meal_role:{a.meal_role.value} vs {b.meal_role.value}")

    if a.protein == b.protein:
        total += W_PROTEIN
        similar.append(f"protein:{a.protein.value}")
    else:
        different.append(f"protein:{a.protein.value} vs {b.protein.value}")

    tj = _jaccard(a.taste, b.taste)
    total += W_TASTE * tj
    shared_taste = sorted({x.lower() for x in a.taste} & {y.lower() for y in b.taste})
    if shared_taste:
        similar.append(f"taste:{','.join(shared_taste)}")
    if tj < 1.0:
        different.append(f"taste:{','.join(a.taste)} vs {','.join(b.taste)}")

    xj = _jaccard(a.texture, b.texture)
    total += W_TEXTURE * xj
    shared_tex = sorted({x.lower() for x in a.texture} & {y.lower() for y in b.texture})
    if shared_tex:
        similar.append(f"texture:{','.join(shared_tex)}")
    if xj < 1.0:
        different.append(f"texture:{','.join(a.texture)} vs {','.join(b.texture)}")

    if not different:
        different.append("spicing:Malwani roasted coconut-chili masala vs home seasoning")

    return total, similar, different


def top_k(dish_dna: FlavorDNA, candidates: list[OriginDish], k: int = 3) -> list[SimilarityMatch]:
    ranked: list[SimilarityMatch] = []
    for c in candidates:
        s, sim, diff = score_pair(dish_dna, c.flavor_dna)
        ranked.append(
            SimilarityMatch(
                name=c.name,
                score=round(s, 4),
                similar_in=sim if sim else ["comfort-food role"],
                different_in=diff,
                spice_ref=c.spice_ref,
                note=c.note,
            )
        )
    ranked.sort(key=lambda m: m.score, reverse=True)
    return ranked[:k]
