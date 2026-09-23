from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_workspace import voice_input_service
from aicentralv2.creative_media import studio, studio_tasks


def _audio(payload=b"voice" * 100, mime="audio/webm"):
    return FileStorage(stream=BytesIO(payload), filename="voice.webm", content_type=mime)


def test_voice_input_returns_one_clean_transcript(monkeypatch):
    monkeypatch.setenv("CADU_VOICE_PROVIDER_ORDER", "local")
    monkeypatch.setattr(studio, "probe", lambda _path: (12.34, {"audio"}))
    monkeypatch.setattr(studio_tasks, "transcribe", lambda _path: {
        "captions": [{"text": "Quero revisar"}, {"text": "o briefing amanhã."}],
        "language": "pt",
    })
    assert voice_input_service.transcribe_upload(_audio()) == {
        "text": "Quero revisar o briefing amanhã.", "language": "pt", "duration": 12.34,
        "provider": "local", "model": "faster-whisper/whisper-small",
        "provider_cost_usd": "0", "fallback_count": 0,
    }


def test_voice_input_rejects_unknown_or_long_audio(monkeypatch):
    monkeypatch.setenv("CADU_VOICE_PROVIDER_ORDER", "local")
    with pytest.raises(BadRequest, match="Formato de áudio"):
        voice_input_service.transcribe_upload(_audio(mime="application/octet-stream"))
    monkeypatch.setattr(studio, "probe", lambda _path: (301, {"audio"}))
    with pytest.raises(BadRequest, match="até cinco minutos"):
        voice_input_service.transcribe_upload(_audio())


def test_voice_credit_tokens_are_proportional_and_configurable(monkeypatch):
    monkeypatch.setenv("CADU_VOICE_CREDITS_PER_MINUTE", "300")
    assert voice_input_service.transcription_credit_tokens(0) == 0
    assert voice_input_service.transcription_credit_tokens(1) == 5
    assert voice_input_service.transcription_credit_tokens(12.34) == 62
    assert voice_input_service.transcription_credit_tokens(60) == 300


def test_voice_provider_order_defaults_to_openai_then_openrouter_then_local(monkeypatch):
    monkeypatch.delenv("CADU_VOICE_PROVIDER_ORDER", raising=False)
    assert voice_input_service._provider_order() == ["openai", "openrouter", "local"]


def test_voice_falls_back_from_openai_to_openrouter(monkeypatch):
    monkeypatch.setenv("CADU_VOICE_PROVIDER_ORDER", "openai,openrouter,local")
    monkeypatch.setattr(studio, "probe", lambda _path: (8, {"audio"}))
    calls = []

    def remote(*, provider, path, mime, duration):
        calls.append(provider)
        if provider == "openai":
            raise RuntimeError("timeout")
        return {"text": "Texto redundante", "language": "pt", "provider": provider,
                "model": "openai/whisper-1", "provider_cost_usd": "0.001"}

    monkeypatch.setattr(voice_input_service, "_remote_transcription", remote)
    result = voice_input_service.transcribe_upload(_audio())
    assert calls == ["openai", "openrouter"]
    assert result["text"] == "Texto redundante"
    assert result["provider"] == "openrouter"
    assert result["fallback_count"] == 1


def test_voice_transcript_cleanup_is_fast_and_does_not_rewrite_content():
    assert voice_input_service.clean_transcript("  quero   revisar  , amanhã!!!\n") == "Quero revisar, amanhã!"
    assert voice_input_service.clean_transcript("Cadu e mídia") == "Cadu e mídia"
