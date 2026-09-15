"""Modelo e resoluções do Seedance 2.5 — um único lugar."""

from __future__ import annotations

import os

MODEL = os.getenv("CREATIVE_VIDEO_MODEL", "bytedance/seedance-2.5")
FALLBACK_MODEL = os.getenv("CREATIVE_VIDEO_FALLBACK_MODEL", "kwaivgi/kling-v3.0-pro")
FALLBACK_MAX_DURATION = max(4, min(int(os.getenv("CREATIVE_VIDEO_FALLBACK_MAX_SECONDS", "8") or 8), 10))
DRAFT_RESOLUTION = os.getenv("CREATIVE_VIDEO_DRAFT_RESOLUTION", "480p")
PRODUCTION_RESOLUTION = os.getenv("CREATIVE_VIDEO_PRODUCTION_RESOLUTION", "720p")
POLL_INTERVAL = max(3, int(os.getenv("CREATIVE_VIDEO_POLL_INTERVAL_SECONDS", "5") or 5))
MAX_DURATION = max(5, min(int(os.getenv("CREATIVE_VIDEO_MAX_DURATION_SECONDS", "30") or 30), 30))
TOKEN_USD = 0.0000107
TOKEN_USD_VIDEO_REF = 0.0000064
FPS_FOR_QUOTE = 24
DURATIONS = (4, 5, 8, 10, 15, 20, 30)
STORYBOARD_MIN = 2
STORYBOARD_MAX = 30

TTS_MODEL = os.getenv("CREATIVE_TTS_MODEL", "google/gemini-3.1-flash-tts-preview")
TTS_INPUT_USD = 0.000001
TTS_OUTPUT_USD = 0.00002
TTS_MAX_CHARS = 800
TTS_MAX_WORDS_PER_SEC = 4.0
TTS_PACES = {"normal": 2.2, "fast": 3.2}
TTS_VOICES = {"male": "Charon", "female": "Kore"}

SEEDANCE_RATIOS = ("16:9", "4:3", "1:1", "3:4", "9:16", "21:9")

SIZES = {
    "480p": {
        "16:9": (854, 480),
        "4:3": (752, 560),
        "1:1": (640, 640),
        "3:4": (560, 752),
        "9:16": (480, 854),
        "21:9": (992, 432),
    },
    "720p": {
        "16:9": (1280, 720),
        "4:3": (1112, 834),
        "1:1": (960, 960),
        "3:4": (834, 1112),
        "9:16": (720, 1280),
        "21:9": (1470, 630),
    },
}

UI_STAGES = (
    ("prepare", "Preparando composição"),
    ("submit", "Enviando ao modelo"),
    ("queue", "Aguardando na fila"),
    ("generate", "Gerando movimento"),
    ("download", "Baixando master"),
    ("compositing", "Protegendo textos e logos"),
    ("tts", "Gerando locução"),
    ("mix", "Mixando voz no master"),
    ("validate", "Validando formato, duração e áudio"),
    ("transcode", "Preparando formatos"),
    ("persist", "Salvando no histórico"),
    ("ready", "Pronto"),
)
