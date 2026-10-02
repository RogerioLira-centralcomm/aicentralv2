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
# Audio files picked from the computer (meetings, briefings) may be long; they
# are split into provider-sized chunks and transcribed in parallel.
LONG_MAX_AUDIO_BYTES = 200 * 1024 * 1024
LONG_MAX_AUDIO_SECONDS = 90 * 60
CHUNK_SECONDS = 600
SINGLE_REQUEST_BYTES = 24 * 1024 * 1024
MIME_SUFFIXES = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
    "audio/x-m4a": ".m4a", "audio/m4a": ".m4a", "audio/aac": ".aac", "audio/mp3": ".mp3",
    "audio/flac": ".flac", "audio/x-flac": ".flac", "video/webm": ".webm", "video/mp4": ".mp4",
}
EXTENSION_MIMES = {
    ".webm": "audio/webm", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".m4a": "audio/mp4", ".mp4": "audio/mp4",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".aac": "audio/aac", ".flac": "audio/flac",
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
    timeout = min(180.0, max(18.0, 15.0 + max(0.0, float(duration or 0)) * .25))
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


def _transcribe_file(path: Path, mime: str, duration: float) -> tuple[dict, list[str]]:
    failures = []
    for provider in _provider_order():
        try:
            result = _local_transcription(path) if provider == "local" else _remote_transcription(provider=provider, path=path, mime=mime, duration=duration)
            return result, failures
        except (requests.RequestException, RuntimeError, ValueError) as error:
            failures.append(f"{provider}: {error}")
    raise ServiceUnavailable("Não foi possível transcrever o áudio agora.")


def _transcribe_in_chunks(path: Path, duration: float) -> dict:
    """Split a long file into mono MP3 chunks and transcribe them in order."""
    import subprocess
    import tempfile
    from concurrent.futures import ThreadPoolExecutor
    with tempfile.TemporaryDirectory(prefix="cadu-voice-chunks-") as folder:
        pattern = str(Path(folder) / "part-%03d.mp3")
        try:
            subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
                "-f", "segment", "-segment_time", str(CHUNK_SECONDS), "-reset_timestamps", "1", pattern,
            ], check=True, capture_output=True, timeout=300)
        except (subprocess.SubprocessError, OSError) as error:
            raise ServiceUnavailable("Não foi possível preparar o áudio para transcrição.") from error
        parts = sorted(Path(folder).glob("part-*.mp3"))
        if not parts:
            raise ServiceUnavailable("Não foi possível preparar o áudio para transcrição.")
        from flask import current_app, has_app_context
        # Worker threads need their own app context: provider keys may be
        # stored in the integrations table, read through the app's database.
        app = current_app._get_current_object() if has_app_context() else None
        def run(part):
            if app is None:
                return _transcribe_file(part, "audio/mpeg", min(CHUNK_SECONDS, duration))
            with app.app_context():
                return _transcribe_file(part, "audio/mpeg", min(CHUNK_SECONDS, duration))
        with ThreadPoolExecutor(max_workers=min(4, len(parts))) as pool:
            outcomes = list(pool.map(run, parts))
    results = [item[0] for item in outcomes]
    cost = sum((Decimal(str(item.get("provider_cost_usd") or 0)) for item in results), Decimal("0"))
    return {
        "text": clean_transcript(" ".join(item["text"] for item in results)),
        "language": results[0].get("language") or "",
        "provider": results[0].get("provider") or "unknown",
        "model": results[0].get("model") or "unknown",
        "provider_cost_usd": str(cost),
        "chunks": len(results),
        "_failures": sum(len(item[1]) for item in outcomes),
    }


def transcribe_upload(file_storage, *, allow_long: bool = False) -> dict:
    max_bytes = LONG_MAX_AUDIO_BYTES if allow_long else MAX_AUDIO_BYTES
    max_seconds = LONG_MAX_AUDIO_SECONDS if allow_long else MAX_AUDIO_SECONDS
    mime = str(file_storage.mimetype or "").split(";", 1)[0].strip().lower()
    if allow_long and mime not in MIME_SUFFIXES:
        # Computer files often arrive as application/octet-stream; trust the extension, ffprobe still validates.
        mime = EXTENSION_MIMES.get(Path(str(file_storage.filename or "")).suffix.lower(), mime)
    if mime not in MIME_SUFFIXES:
        raise BadRequest("Formato de áudio não compatível com a transcrição.")
    payload = file_storage.stream.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise RequestEntityTooLarge(f"O áudio pode ter no máximo {max_bytes // (1024 * 1024)} MB.")
    if len(payload) < 256:
        raise BadRequest("A gravação está vazia ou curta demais.")
    descriptor, raw_path = mkstemp(prefix="cadu-voice-", suffix=MIME_SUFFIXES[mime])
    os.close(descriptor)
    path = Path(raw_path)
    try:
        path.write_bytes(payload)
        from ..creative_media.studio import probe
        try:
            duration, streams = probe(path)
        except Exception as error:
            if not allow_long:
                raise
            raise BadRequest("Não foi possível ler este arquivo de áudio.") from error
        if "audio" not in streams or not 0 < duration <= max_seconds:
            raise BadRequest(
                f"Envie um áudio com até {max_seconds // 60} minutos." if allow_long
                else "Grave uma mensagem de voz com até cinco minutos."
            )
        if allow_long and (duration > CHUNK_SECONDS or len(payload) > SINGLE_REQUEST_BYTES):
            result = _transcribe_in_chunks(path, duration)
            failures = result.pop("_failures", 0)
            result.update(text=result["text"][:60000], duration=round(duration, 2), fallback_count=failures)
            return result
        result, failures = _transcribe_file(path, mime, duration)
        result.update(text=result["text"][:20000], duration=round(duration, 2), fallback_count=len(failures))
        return result
    except (BadRequest, RequestEntityTooLarge):
        raise
    except ValueError as error:
        raise ServiceUnavailable(str(error)) from error
    finally:
        path.unlink(missing_ok=True)
