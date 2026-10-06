"""A5: a transcrição do Studio reserva saldo antes de chamar o provedor."""
import inspect
from io import BytesIO

from werkzeug.datastructures import FileStorage

from aicentralv2.creative_media import studio
from aicentralv2.cadu_workspace.voice_input_service import LONG_MAX_AUDIO_SECONDS, MAX_AUDIO_SECONDS


def _file(size):
    return FileStorage(stream=BytesIO(b'\0' * size), filename='a.mp3')


def test_dictation_reserves_short_ceiling():
    assert studio._transcription_estimate_seconds(_file(10), False) == MAX_AUDIO_SECONDS


def test_file_estimate_scales_with_size_and_is_capped():
    assert studio._transcription_estimate_seconds(_file(16_000 * 600), True) == 600
    huge = _file(16_000 * (LONG_MAX_AUDIO_SECONDS + 10))
    assert studio._transcription_estimate_seconds(huge, True) == LONG_MAX_AUDIO_SECONDS
    stream = _file(16_000 * 600)
    studio._transcription_estimate_seconds(stream, True)
    assert stream.stream.tell() == 0


def test_authorize_runs_before_transcribe_upload():
    source = inspect.getsource(studio.studio_audio_transcriptions)
    assert source.index('.authorize(') < source.index('transcribe_upload(audio')
