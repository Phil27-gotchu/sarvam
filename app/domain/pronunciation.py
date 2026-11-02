"""Pronunciation scoring — pure, no I/O."""

from __future__ import annotations

import re
import unicodedata

from app.domain.models import PronunciationResult

ASPIRATED = {
    "kh": "k",
    "gh": "g",
    "chh": "c",
    "ch": "c",
    "jh": "j",
    "th": "t",
    "dh": "d",
    "ph": "p",
    "bh": "b",
    "sh": "s",
}
RETROFLEX = {"ṭ": "t", "ḍ": "d", "ṇ": "n", "ṣ": "s", "ṛ": "r", "ळ": "l"}

DEVANAGARI_MAP = {
    "क": "ka", "ख": "kha", "ग": "ga", "घ": "gha", "ङ": "nga",
    "च": "cha", "छ": "chha", "ज": "ja", "झ": "jha", "ञ": "nya",
    "ट": "ta", "ठ": "tha", "ड": "da", "ढ": "dha", "ण": "na",
    "त": "ta", "थ": "tha", "द": "da", "ध": "dha", "न": "na",
    "प": "pa", "फ": "pha", "ब": "ba", "भ": "bha", "म": "ma",
    "य": "ya", "र": "ra", "ल": "la", "व": "va", "श": "sha",
    "ष": "sha", "स": "sa", "ह": "ha", "ळ": "la",
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ः": "",
    "्": "", "ँ": "n", "ॉ": "o", "ॅ": "e",
    "अ": "a", "आ": "aa", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऋ": "ri",
}


def _romanize_devanagari(text: str) -> str:
    return "".join(DEVANAGARI_MAP.get(ch, ch if ord(ch) < 128 else " ") for ch in text)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip().lower())
    if any("\u0900" <= c <= "\u097F" for c in text):
        text = _romanize_devanagari(text)
    for src, dst in RETROFLEX.items():
        text = text.replace(src, dst)
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"[^a-z\s]", " ", text)
    for src, dst in ASPIRATED.items():
        text = text.replace(src, dst)
    text = re.sub(r"([aeiou])h\b", r"\1", text)
    text = re.sub(r"aa+", "a", text)
    text = re.sub(r"ee+|ii+", "i", text)
    text = re.sub(r"oo+|uu+", "u", text)
    text = re.sub(r"ay\b", "e", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_tokens(text: str) -> list[str]:
    norm = normalize(text)
    raw = norm.replace(" ", "")
    if not raw:
        return []
    syl = re.findall(r"[^aeiou]*[aeiou]+", raw)
    if syl and sum(len(x) for x in syl) < len(raw):
        syl[-1] += raw[sum(len(x) for x in syl) :]
    return syl if syl else [raw]


def levenshtein(a: list[str], b: list[str]) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def score(target: str, heard: str) -> PronunciationResult:
    t_tokens = to_tokens(target)
    h_tokens = to_tokens(heard)
    if not t_tokens:
        return PronunciationResult(score=0, mismatched_syllables=[], tip="No target.", heard=heard, target=target)
    if not h_tokens:
        return PronunciationResult(
            score=0,
            mismatched_syllables=t_tokens,
            tip=f"Try saying each beat clearly: {' · '.join(t_tokens)}",
            heard=heard,
            target=target,
        )
    maxlen = max(len(t_tokens), len(h_tokens), 1)
    dist = levenshtein(t_tokens, h_tokens)
    val = max(0, min(100, int(round(100 * (1 - dist / maxlen)))))

    mismatched: list[str] = []
    for i, tok in enumerate(t_tokens):
        if i >= len(h_tokens) or h_tokens[i] != tok:
            mismatched.append(tok)

    if val >= 90:
        tip = "Spot on — a local waiter will understand immediately."
    elif mismatched:
        tip = f"Emphasize syllable(s): {' - '.join(mismatched[:4])}"
    else:
        tip = f"Say slowly: {target}"

    return PronunciationResult(
        score=val,
        mismatched_syllables=mismatched,
        tip=tip,
        heard=heard,
        target=target,
    )
