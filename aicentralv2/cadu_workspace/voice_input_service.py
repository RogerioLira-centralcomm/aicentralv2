"""Short-lived voice input validation and transcription for the chat composer."""

from __future__ import annotations

import os
import math
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import mkstemp

import requests
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, ServiceUnavailable


MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 300
MIME_SUFFIXES = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
}


def transcription_credit_tokens(duration_seconds: float) -> int:
    """Commercial credits charged proportionally to successfully transcribed audio."""
    try:
        credits_per_minute = max(1, int(os.getenv("CADU_VOICE_CREDITS_PER_MINUTE", "300")))
        duration = max(0.0, float(duration_seconds or 0))
    except (TypeError, ValueError):
        credits_per_minute, duration = 300, 0.0
    return max(1, int(math.ceil(duration * credits_per_minute / 60))) if duration else 0


def _provider_order() -> list[str]:
    configured = os.getenv("CADU_VOICE_PROVIDER_ORDER", "openai,openrouter,local")
    allowed = {"openai", "openrouter", "local"}
    order = [item.strip().lower() for item in configured.split(",") if item.strip().lower() in allowed]
    return list(dict.fromkeys(order)) or ["local"]


def _provider_cost(payload) -> Decimal:
    usage = payload.get("usage") if isinstance(payload, dict) and isinstance(payload.get("usage"), dict) else {}
    try:
        return max(Decimal("0"), Decimal(str(usage.get("cost") or usage.get("total_cost") or 0)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def clean_transcript(value: str) -> str:
    """Normalize provider output without rewriting what the person said."""
    text = unicodedata.normalize("NFC", str(value or ""))
    text = re.sub(r"[\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])\1{2,}", r"\1", text)
    if text and text[0].isalpha():
        text = text[0].upper() + text[1:]
    return text


def _remote_transcription(*, provider: str, path: Path, mime: str, duration: float) -> dict:
    if provider == "openai":
        from ..services.openrouter_service import resolve_openai_api_key
        api_key = resolve_openai_api_key()
        if not api_key:
            raise RuntimeError("OpenAI não configurada")
        url = "https://api.openai.com/v1/audio/transcriptions"
        model = os.getenv("CADU_VOICE_OPENAI_MODEL", "gpt-transcribe").strip() or "gpt-transcribe"
    else:
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OpenRouter não configurado")
        url = "https://openrouter.ai/api/v1/audio/transcriptions"
        model = os.getenv("CADU_VOICE_OPENROUTER_MODEL", "openai/whisper-1").strip() or "openai/whisper-1"
    language = (os.getenv("CADU_VOICE_LANGUAGE", "pt") or "pt").strip()[:12]
    prompt = (os.getenv("CADU_VOICE_PROMPT") or "Conversa de trabalho sobre Cadu, mídia, briefing, campanha, cliente e projeto.").strip()[:500]
    fields = {"model": model, "response_format": "json", "prompt": prompt}
    if provider == "openai" and model == "gpt-transcribe":
        fields["languages[]"] = language
    else:
        fields["language"] = language
    timeout = min(55.0, max(18.0, 15.0 + max(0.0, float(duration or 0)) * .25))
    with path.open("rb") as source:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            data=fields,
            files={"file": (path.name, source, mime)},
            timeout=(4, timeout),
        )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not response.ok:
        error = payload.get("error") if isinstance(payload, dict) else {}
        detail = error.get("message") if isinstance(error, dict) else ""
        raise RuntimeError(str(detail or f"{provider} recusou a transcrição")[:240])
    text = clean_transcript(payload.get("text"))
    if not text:
        raise RuntimeError(f"{provider} não retornou texto")
    return {
        "text": text,
        "language": str(payload.get("language") or ""),
        "provider": provider,
        "model": str(payload.get("model") or model),
        "provider_cost_usd": str(_provider_cost(payload)),
    }


def _local_transcription(path: Path) -> dict:
    from ..creative_media.studio_tasks import transcribe
    result = transcribe(path)
    text = clean_transcript(" ".join(str(row.get("text") or "").strip() for row in result.get("captions") or []))
    if not text:
        raise RuntimeError("O modelo local não reconheceu fala na gravação")
    return {
        "text": text,
        "language": result.get("language") or "",
        "provider": "local",
        "model": "faster-whisper/whisper-small",
        "provider_cost_usd": "0",
    }


def transcribe_upload(file_storage) -> dict:
    mime = str(file_storage.mimetype or "").split(";", 1)[0].strip().lower()
    if mime not in MIME_SUFFIXES:
        raise BadRequest("Formato de áudio não compatível com a transcrição.")
    payload = file_storage.stream.read(MAX_AUDIO_BYTES + 1)
    if len(payload) > MAX_AUDIO_BYTES:
        raise RequestEntityTooLarge("A gravação pode ter no máximo 10 MB.")
    if len(payload) < 256:
        raise BadRequest("A gravação está vazia ou curta demais.")
    descriptor, raw_path = mkstemp(prefix="cadu-voice-", suffix=MIME_SUFFIXES[mime])
    os.close(descriptor)
    path = Path(raw_path)
    try:
        path.write_bytes(payload)
        from ..creative_media.studio import probe
        duration, streams = probe(path)
        if "audio" not in streams or not 0 < duration <= MAX_AUDIO_SECONDS:
            raise BadRequest("Grave uma mensagem de voz com até cinco minutos.")
        failures = []
        result = None
        for provider in _provider_order():
            try:
                result = _local_transcription(path) if provider == "local" else _remote_transcription(provider=provider, path=path, mime=mime, duration=duration)
                break
            except (requests.RequestException, RuntimeError, ValueError) as error:
                failures.append(f"{provider}: {error}")
        if not result:
            raise ServiceUnavailable("Não foi possível transcrever o áudio agora.")
        result.update(text=result["text"][:20000], duration=round(duration, 2), fallback_count=len(failures))
        return result
    except (BadRequest, RequestEntityTooLarge):
        raise
    except ValueError as error:
        raise ServiceUnavailable(str(error)) from error
    finally:
        path.unlink(missing_ok=True)
