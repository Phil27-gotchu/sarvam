"""API happy-path and architecture boundary tests using mock adapter."""

from __future__ import annotations

import ast
import os
from pathlib import Path

os.environ["MOCK_SARVAM"] = "1"

from fastapi.testclient import TestClient

from app.adapters.base import reset_adapter_cache
from app.config import get_settings
from app.main import app

get_settings.cache_clear()
reset_adapter_cache()
client = TestClient(app)


def test_health_and_30_dishes_5_origins() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["dishes"] == 30
    assert len(body["origins"]) == 5


def test_menu_scan_matches_kb_and_flags_unverified() -> None:
    r = client.post(
        "/menu/scan",
        files={"image": ("menu.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"profile_json": '{"origin":"Australia","avoid_allergens":["peanut"]}'},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["in_kb"] and i["dish"]["id"] == "kombdi-vade" for i in items)
    assert any(not i["in_kb"] and i["unverified_badge"] for i in items)
    peanut_cards = [i for i in items if i["in_kb"] and i["dish"]["id"] == "shengdana-chutney"]
    assert peanut_cards and peanut_cards[0]["safety"]["status"] == "BLOCK"


def test_tts_and_disk_cache() -> None:
    r1 = client.post("/tts", json={"dish_id": "kombdi-vade"})
    assert r1.status_code == 200
    assert r1.json()["audio_base64"]
    r2 = client.post("/tts", json={"dish_id": "kombdi-vade"})
    assert r2.status_code == 200
    assert r2.json()["cached"] is True


def test_cultural_bridge_kombdi_vade_australia() -> None:
    r = client.get("/bridge/kombdi-vade?origin=Australia")
    assert r.status_code == 200
    data = r.json()
    assert len(data["matches"]) == 3
    assert data["similar_in"]
    assert data["different_in"]


def test_order_draft_and_listen_and_coach_and_ask() -> None:
    draft = client.post(
        "/order/draft",
        json={
            "items": [{"dish_id": "kombdi-vade", "qty": 1}],
            "profile": {"max_spice": 2, "diet": "nonveg", "avoid_allergens": ["peanut"], "origin": "UK"},
        },
    )
    assert draft.status_code == 200
    assert draft.json()["marathi_text"]
    assert draft.json()["audio_base64"]

    listen = client.post("/order/listen-json", json={"profile": {"origin": "UK"}})
    assert listen.status_code == 200
    assert listen.json()["waiter_english"]

    coach = client.post("/coach/json", json={"dish_id": "kombdi-vade", "heard_text": "kom-bdee vah-day"})
    assert coach.status_code == 200
    assert coach.json()["score"] >= 80

    ask = client.post("/ask", json={"text": "Tell me about Kombdi Vade", "want_tts": True})
    assert ask.status_code == 200
    assert ask.json()["answer"]


def test_no_sarvam_imports_outside_adapters() -> None:
    root = Path(__file__).resolve().parent.parent / "app"
    for py_file in root.rglob("*.py"):
        if "adapters" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("sarvamai"), f"Forbidden import in {py_file}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("sarvamai"), f"Forbidden import in {py_file}"
