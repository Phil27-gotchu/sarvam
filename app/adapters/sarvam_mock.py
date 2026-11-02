"""Deterministic offline mock adapter (MOCK_SARVAM=1)."""

from __future__ import annotations

import io
import math
import struct
import wave
from typing import Any

from app.domain.models import MenuItem


def _synth_wav_bytes(seed_text: str, duration_s: float = 0.55) -> bytes:
    rate = 16000
    n = int(rate * duration_s)
    base_freq = 320 + (sum(ord(c) for c in seed_text) % 180)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            t = i / rate
            env = math.sin(math.pi * i / n)
            val = int(12000 * env * math.sin(2 * math.pi * base_freq * t))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


class MockSarvamAdapter:
    def __init__(self) -> None:
        self.tts_warning: str | None = None

    async def extract_menu(self, image: bytes, filename: str = "menu.jpg") -> list[MenuItem]:
        # Allow custom text menu encoded in test payloads if prefix "TEXT_MENU:"
        if image.startswith(b"TEXT_MENU:"):
            lines = image.decode("utf-8", errors="ignore").removeprefix("TEXT_MENU:").splitlines()
            items: list[MenuItem] = []
            for ln in lines:
                if "|" in ln:
                    parts = [p.strip() for p in ln.split("|")]
                    items.append(
                        MenuItem(
                            dish=parts[0],
                            price=parts[1] if len(parts) > 1 else None,
                            section=parts[2] if len(parts) > 2 else "Mains",
                        )
                    )
            if items:
                return items
        return [
            MenuItem(dish="Kombdi Vade", price="₹320", section="Thali & Mains"),
            MenuItem(dish="Bombil Fry", price="₹210", section="Coastal Starters"),
            MenuItem(dish="Sol Kadhi", price="₹70", section="Coolers"),
            MenuItem(dish="Tisrya Masala", price="₹290", section="Seafood Specials"),
            MenuItem(dish="Shengdana Chutney", price="₹50", section="Sides"),
            MenuItem(dish="Ajibaichi Secret Crab Roast", price="₹380", section="Chef Specials"),
        ]

    async def ask(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        task = context.get("task", "qa")
        if task == "unverified_explain":
            dish_name = context.get("dish_name", "Special Dish")
            return {
                "summary": (
                    f"{dish_name} appears on the menu but is not in our verified Malwani knowledge base. "
                    "Ask the server about ingredients, spice level, and allergens before ordering."
                ),
                "unverified": True,
            }
        if task == "order_draft":
            items = context.get("items", [])
            profile = context.get("profile", {})
            names_mr = ", ".join(i.get("name_mr", i.get("name_roman", "")) for i in items) or "एक प्लेट कोंबडी वडे"
            names_en = ", ".join(f"{i.get('qty', 1)}x {i.get('name_roman', '')}" for i in items) or "1x Kombdi Vade"
            avoid = ", ".join(profile.get("avoid_allergens", []))
            spice_note_mr = "तिखट कमी ठेवा" if profile.get("max_spice", 3) <= 2 else "मध्यम तिखट चालेल"
            allergy_mr = f", आणि कृपया {avoid} अजिबात घालू नका" if avoid else ""
            marathi = f"नमस्कार दादा, आम्हाला {names_mr} द्या. कृपया {spice_note_mr}{allergy_mr}. धन्यवाद!"
            english = (
                f"Hello brother, please bring us {names_en}. "
                f"Please keep the spice {'mild' if profile.get('max_spice', 3) <= 2 else 'medium'}"
                f"{f' and strictly no {avoid}' if avoid else ''}. Thank you!"
            )
            return {
                "marathi_text": marathi,
                "phonetic": "nuh-mus-kaar dah-dah, aam-haa-laa ऑर्डर dya, kripaya tikhat kamee theva, dhanyavaad",
                "english_meaning": english,
            }
        if task == "waiter_reply":
            waiter_en = context.get("waiter_en", "")
            avail = [d.get("name_roman") for d in context.get("alternatives", [])[:3]]
            return {
                "waiter_meaning": waiter_en or "Sorry, Bombil Fry just finished; we have fresh Surmai Fry and Kombdi Vade.",
                "suggested_alternatives": avail or ["Surmai Fry", "Kombdi Vade", "Sol Kadhi"],
                "followup_marathi": "ठीक आहे, मग त्याऐवजी सुरमई फ्राय द्या.",
                "followup_english": "Okay, then please bring Surmai Fry instead.",
            }
        if task == "bridge":
            dish = context.get("dish", {})
            matches = context.get("matches", [])
            top = matches[0] if matches else {"name": "Home Classic", "similar_in": ["savory"], "different_in": ["spices"], "spice_ref": 2}
            dish_spice = dish.get("spice", 3)
            ref_spice = top.get("spice_ref", 2)
            calib = (
                f"{dish.get('name_roman', 'This dish')} is rated {dish_spice}/5 on the Malwani spice scale "
                f"(compared with {ref_spice}/5 for {top.get('name')}). Pair with Sol Kadhi to cool the palate."
            )
            return {
                "closest": top.get("name"),
                "similar_in": top.get("similar_in", ["comfort format"]),
                "different_in": top.get("different_in", ["roasted coconut & kokum"]),
                "spice_calibration": calib,
                "explanation": (
                    f"Think of {dish.get('name_roman', 'this dish')} as a coastal cousin to {top.get('name')}: "
                    f"similar {', '.join(top.get('similar_in', [])[:2])}, but layered with Malwani roasted coconut and kokum."
                ),
            }
        # Default grounded Q&A
        dishes = context.get("dishes", [])
        names = ", ".join(d.get("name_roman", "") for d in dishes[:4])
        return {
            "answer": (
                f"Based on the Malwani knowledge base ({names}): Kombdi Vade is our signature spiced chicken curry "
                "with fluffy fried vade breads, and Sol Kadhi is a cooling coconut-kokum drink that balances heat."
            ),
            "referenced_dish_ids": [d.get("id") for d in dishes[:3] if d.get("id")],
        }

    async def translate(self, text: str, src: str, tgt: str) -> str:
        if tgt == src or not text:
            return text
        if tgt.startswith("mr"):
            return f"[मराठी] {text}"
        if tgt.startswith("de"):
            return f"[DE] {text}"
        if tgt.startswith("ja"):
            return f"[JA] {text}"
        return text

    async def stt(self, audio: bytes, mode: str = "transcribe", lang: str = "mr-IN") -> str:
        if audio.startswith(b"MOCK_TEXT:"):
            return audio.decode("utf-8", errors="ignore").removeprefix("MOCK_TEXT:").strip()
        if mode == "translate":
            return "Sorry sir, Bombil Fry is finished right now, but fresh Surmai Fry and Kombdi Vade are hot and ready."
        if mode in {"translit", "verbatim"}:
            return "kom bdi va de"
        return "Which Malwani dish is mild and good with rice?"

    async def tts(self, text: str, lang: str = "mr-IN", voice: str = "shubh") -> bytes:
        return _synth_wav_bytes(f"{lang}:{voice}:{text}")
