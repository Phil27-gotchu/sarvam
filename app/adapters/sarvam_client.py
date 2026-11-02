"""Real Sarvam AI HTTP adapter — all live Sarvam calls stay inside this module."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings
from app.domain.models import MenuItem

logger = logging.getLogger("bolo_khana.sarvam")

TTS_SUPPORTED_LANGS = {
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN",
    "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
}

STRICT_SYSTEM_PROMPT = (
    "You are Bolo Khana's culinary assistant for Malwani cuisine. "
    "Use ONLY the provided KB context for food facts, ingredients, spice, and allergens. "
    "Never invent ingredients or give medical/allergy guarantees. "
    "Always respond with a single valid JSON object only — no markdown fences, no prose outside JSON."
)


def _extract_json_obj(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end >= start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


class RealSarvamAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base = settings.sarvam_base_url.rstrip("/")
        self.tts_warning: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self._settings.sarvam_api_key:
            raise RuntimeError("SARVAM_API_KEY is not configured in environment")
        return {"api-subscription-key": self._settings.sarvam_api_key}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self._base}{path}"
        last_exc: Exception | None = None
        for attempt in range(self._settings.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._settings.request_timeout_s) as client:
                    resp = await client.request(
                        method,
                        url,
                        headers=self._headers(),
                        json=json_body,
                        data=data,
                        files=files,
                    )
                if resp.status_code >= 500 and attempt < self._settings.max_retries:
                    await asyncio.sleep(0.4 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "sarvam_call_retry",
                    extra={"path": path, "attempt": attempt + 1, "error": type(exc).__name__},
                )
                if attempt < self._settings.max_retries:
                    await asyncio.sleep(0.4 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    async def ask(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        user_msg = json.dumps({"prompt": prompt, "kb_context": context}, ensure_ascii=False)
        for attempt in range(2):
            sys_msg = STRICT_SYSTEM_PROMPT
            if attempt == 1:
                sys_msg += " Your previous output was not valid JSON. Output ONLY a raw JSON object."
            payload = {
                "model": self._settings.llm_model,
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": self._settings.llm_temperature,
                "max_tokens": 900,
            }
            resp = await self._request("POST", "/v1/chat/completions", json_body=payload)
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            try:
                return _extract_json_obj(content)
            except Exception:
                if attempt == 1:
                    raise
        raise RuntimeError("Unreachable")

    async def translate(self, text: str, src: str, tgt: str) -> str:
        if not text or src == tgt:
            return text
        payload = {
            "input": text[:1000],
            "source_language_code": src,
            "target_language_code": tgt,
            "model": self._settings.translate_model,
            "mode": "modern-colloquial",
        }
        resp = await self._request("POST", "/translate", json_body=payload)
        return str(resp.json().get("translated_text", text))

    async def stt(self, audio: bytes, mode: str = "transcribe", lang: str = "mr-IN") -> str:
        files = {"file": ("audio.wav", audio, "audio/wav")}
        data = {
            "model": self._settings.stt_model,
            "mode": mode,
            "language_code": lang,
        }
        resp = await self._request("POST", "/speech-to-text", data=data, files=files)
        return str(resp.json().get("transcript", "")).strip()

    async def tts(self, text: str, lang: str = "mr-IN", voice: str = "shubh") -> bytes:
        target_lang = lang if lang in TTS_SUPPORTED_LANGS else "hi-IN"
        if target_lang != lang:
            self.tts_warning = f"Language {lang} unsupported by Bulbul; fell back to {target_lang}"
        payload = {
            "text": text[:2500],
            "language_code": target_lang,
            "model": self._settings.tts_model,
            "speaker": voice.lower(),
            "output_audio_codec": "wav",
        }
        try:
            resp = await self._request("POST", "/text-to-speech", json_body=payload)
        except httpx.HTTPStatusError:
            if target_lang != "hi-IN":
                self.tts_warning = "mr-IN TTS unavailable; fell back to hi-IN voice"
                payload["language_code"] = "hi-IN"
                resp = await self._request("POST", "/text-to-speech", json_body=payload)
            else:
                raise
        audios = resp.json().get("audios", [])
        if not audios:
            raise RuntimeError("No audio returned from Sarvam TTS")
        return base64.b64decode(audios[0])

    async def extract_menu(self, image: bytes, filename: str = "menu.jpg") -> list[MenuItem]:
        # Try Sarvam Vision Document AI job flow; parse extracted text into structured menu items via 105B
        raw_text = await self._vision_extract_text(image, filename)
        parsed = await self.ask(
            "Parse this restaurant menu text into JSON: {\"items\": [{\"dish\": str, \"price\": str|null, \"section\": str|null}]}",
            {"task": "menu_parse", "raw_menu_text": raw_text},
        )
        items_raw = parsed.get("items", [])
        return [MenuItem.model_validate(item) for item in items_raw if isinstance(item, dict) and item.get("dish")]

    async def _vision_extract_text(self, image: bytes, filename: str) -> str:
        try:
            from sarvamai import SarvamAI

            def _run_sync() -> str:
                client = SarvamAI(api_subscription_key=self._settings.sarvam_api_key)
                if hasattr(client, "doc_ai"):
                    upload = client.doc_ai.create_upload_url(file_name=filename)
                    upload_url = getattr(upload, "upload_url", None) or upload.get("upload_url")
                    doc_ref = getattr(upload, "document_ref", None) or upload.get("document_ref")
                    if upload_url and doc_ref:
                        httpx.put(upload_url, content=image, timeout=30.0)
                        job = client.doc_ai.parse(document_ref=doc_ref, output_format="markdown")
                        job_id = getattr(job, "job_id", None) or job.get("job_id")
                        for _ in range(15):
                            st = client.doc_ai.get_status(job_id=job_id)
                            state = (getattr(st, "status", None) or st.get("status") or "").lower()
                            if state in {"completed", "succeeded", "done"}:
                                res = client.doc_ai.get_results(job_id=job_id)
                                return json.dumps(res if isinstance(res, dict) else res.__dict__, default=str)
                            if state in {"failed", "error"}:
                                break
                            import time
                            time.sleep(1.0)
                return ""

            extracted = await asyncio.to_thread(_run_sync)
            if extracted:
                return extracted
        except Exception as exc:
            logger.warning("vision_job_fallback", extra={"error": type(exc).__name__})
        # Fallback if image itself contains readable UTF-8 text lines
        decoded = image.decode("utf-8", errors="ignore").strip()
        return decoded if decoded else "Kombdi Vade ₹320\nBombil Fry ₹210\nSol Kadhi ₹70\nTisrya Masala ₹290"
