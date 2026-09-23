"""Short-lived voice input validation and transcription for the chat composer."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import mkstemp

from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, ServiceUnavailable


MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 300
MIME_SUFFIXES = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
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
        from ..creative_media.studio_tasks import transcribe

        duration, streams = probe(path)
        if "audio" not in streams or not 0 < duration <= MAX_AUDIO_SECONDS:
            raise BadRequest("Grave uma mensagem de voz com até cinco minutos.")
        result = transcribe(path)
        text = " ".join(str(row.get("text") or "").strip() for row in result.get("captions") or []).strip()
        if not text:
            raise BadRequest("Não foi possível reconhecer fala nesta gravação.")
        return {"text": text[:20000], "language": result.get("language") or "", "duration": round(duration, 2)}
    except (BadRequest, RequestEntityTooLarge):
        raise
    except ValueError as error:
        raise ServiceUnavailable(str(error)) from error
    finally:
        path.unlink(missing_ok=True)
