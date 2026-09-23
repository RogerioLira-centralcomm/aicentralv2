from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_workspace import voice_input_service
from aicentralv2.creative_media import studio, studio_tasks


def _audio(payload=b"voice" * 100, mime="audio/webm"):
    return FileStorage(stream=BytesIO(payload), filename="voice.webm", content_type=mime)


def test_voice_input_returns_one_clean_transcript(monkeypatch):
    monkeypatch.setattr(studio, "probe", lambda _path: (12.34, {"audio"}))
    monkeypatch.setattr(studio_tasks, "transcribe", lambda _path: {
        "captions": [{"text": "Quero revisar"}, {"text": "o briefing amanhã."}],
        "language": "pt",
    })
    assert voice_input_service.transcribe_upload(_audio()) == {
        "text": "Quero revisar o briefing amanhã.", "language": "pt", "duration": 12.34,
    }


def test_voice_input_rejects_unknown_or_long_audio(monkeypatch):
    with pytest.raises(BadRequest, match="Formato de áudio"):
        voice_input_service.transcribe_upload(_audio(mime="application/octet-stream"))
    monkeypatch.setattr(studio, "probe", lambda _path: (301, {"audio"}))
    with pytest.raises(BadRequest, match="até cinco minutos"):
        voice_input_service.transcribe_upload(_audio())
