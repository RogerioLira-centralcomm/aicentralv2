"""Roteiro falado: palavras, voz Gemini e tags de ritmo."""

from __future__ import annotations

from .settings import (
    TTS_MAX_CHARS,
    TTS_MAX_WORDS_PER_SEC,
    TTS_PACES,
    TTS_VOICES,
)

VOICES = ("male", "female")
PACES = ("normal", "fast")


def word_count(script: str) -> int:
    return len([item for item in str(script or "").split() if item])


def budget_words(duration: int, pace: str) -> int:
    rate = TTS_PACES.get(pace) or TTS_PACES["normal"]
    return max(1, int(int(duration or 8) * rate))


def normalize_script(raw, *, required=True) -> str:
    text = " ".join(str(raw or "").split())
    if not text:
        if required:
            raise ValueError("Escreva o roteiro da locução.")
        return ""
    if len(text) > TTS_MAX_CHARS:
        raise ValueError("O roteiro da locução é longo demais.")
    if word_count(text) < 3:
        raise ValueError("O roteiro precisa de pelo menos três palavras.")
    return text


def assert_fits(script: str, duration: int):
    words = word_count(script)
    ceiling = int(int(duration or 8) * TTS_MAX_WORDS_PER_SEC)
    if words > ceiling:
        raise ValueError("O roteiro não cabe nesta duração. Encurte o texto ou aumente os segundos.")


def resolve_voice(gender: str) -> str:
    return TTS_VOICES.get(gender) or TTS_VOICES["male"]


def spoken_input(script: str, pace: str) -> str:
    text = str(script or "").strip()
    if pace == "fast":
        return f"[excited] {text}"
    return text
