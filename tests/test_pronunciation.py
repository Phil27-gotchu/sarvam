"""Unit tests for pronunciation scoring."""

from __future__ import annotations

from app.domain import pronunciation


def test_exact_and_aspirated_tolerance() -> None:
    res = pronunciation.score("kom-bdee vah-day", "kombdi vade")
    assert res.score >= 70
    assert isinstance(res.tip, str)


def test_devanagari_input_supported() -> None:
    res = pronunciation.score("sohl kuh-dhee", "सोलकढी")
    assert 0 <= res.score <= 100


def test_mismatch_returns_syllables_and_tip() -> None:
    res = pronunciation.score("kom-bdee vah-day", "pizza")
    assert res.score < 50
    assert len(res.mismatched_syllables) >= 1
