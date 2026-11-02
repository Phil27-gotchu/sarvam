"""Unit tests for Flavor-DNA similarity ranking."""

from __future__ import annotations

from app.data.repo import get_repo
from app.domain import similarity


def test_kombdi_vade_australia_top_3_matches() -> None:
    repo = get_repo()
    kombdi = repo.get_dish("kombdi-vade")
    aus = repo.get_origin("Australia")
    assert kombdi is not None and aus is not None

    matches = similarity.top_k(kombdi.flavor_dna, aus.popular_dishes, k=3)
    assert len(matches) == 3
    assert matches[0].score >= matches[1].score >= matches[2].score
    assert "Chicken" in matches[0].name
    for m in matches:
        assert len(m.similar_in) >= 1
        assert len(m.different_in) >= 1
