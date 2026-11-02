"""Sarvam adapter Protocol and factory."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.config import get_settings
from app.domain.models import MenuItem


@runtime_checkable
class SarvamAdapter(Protocol):
    tts_warning: str | None

    async def extract_menu(self, image: bytes, filename: str = "menu.jpg") -> list[MenuItem]: ...

    async def ask(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]: ...

    async def translate(self, text: str, src: str, tgt: str) -> str: ...

    async def stt(self, audio: bytes, mode: str = "transcribe", lang: str = "mr-IN") -> str: ...

    async def tts(self, text: str, lang: str = "mr-IN", voice: str = "shubh") -> bytes: ...


_adapter_instance: SarvamAdapter | None = None


def get_sarvam_adapter() -> SarvamAdapter:
    global _adapter_instance
    settings = get_settings()
    if _adapter_instance is not None:
        return _adapter_instance
    if settings.mock_sarvam:
        from app.adapters.sarvam_mock import MockSarvamAdapter

        _adapter_instance = MockSarvamAdapter()
    else:
        from app.adapters.sarvam_client import RealSarvamAdapter

        _adapter_instance = RealSarvamAdapter(settings=settings)
    return _adapter_instance


def reset_adapter_cache() -> None:
    global _adapter_instance
    _adapter_instance = None
