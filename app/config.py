"""Application configuration from environment."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
APP_DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIO_CACHE_DIR = DATA_DIR / "audio_cache"
FEEDBACK_PATH = DATA_DIR / "feedback.json"
WEB_DIR = ROOT / "web"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


class Settings(BaseModel):
    sarvam_api_key: str = Field(default="")
    mock_sarvam: bool = True
    sarvam_base_url: str = "https://api.sarvam.ai"
    request_timeout_s: float = 60.0
    max_retries: int = 2
    max_upload_bytes: int = 5 * 1024 * 1024
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:8000",
        ]
    )
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "shubh"
    stt_model: str = "saaras:v3"
    translate_model: str = "mayura:v1"
    llm_model: str = "sarvam-105b"
    llm_temperature: float = 0.2


@lru_cache
def get_settings() -> Settings:
    mock_raw = os.environ.get("MOCK_SARVAM", "1").strip().lower()
    mock = mock_raw in {"1", "true", "yes", "on"}
    cors_env = os.environ.get("CORS_ORIGINS", "").strip()
    kwargs: dict[str, object] = {
        "sarvam_api_key": os.environ.get("SARVAM_API_KEY", ""),
        "mock_sarvam": mock,
    }
    if cors_env:
        kwargs["cors_origins"] = [o.strip() for o in cors_env.split(",") if o.strip()]
    return Settings(**kwargs)


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK_PATH.exists():
        FEEDBACK_PATH.write_text("[]\n", encoding="utf-8")
