"""ffmpeg opcional: poster, MP4 menor, GIF."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def ffmpeg_available():
    return bool(shutil.which("ffmpeg"))


def poster_jpg(master_path: str) -> bytes:
    return _run_bytes(
        ["-sseof", "-0.1", "-i", master_path, "-frames:v", "1", "-q:v", "4"],
        ".jpg",
    )


def small_mp4(master_path: str) -> bytes:
    return _run_bytes(
        [
            "-i", master_path,
            "-vf", "scale=-2:480",
            "-c:v", "libx264",
            "-crf", "28",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
        ],
        ".mp4",
    )


def gif_bytes(master_path: str, *, duration: int, window: str = "first") -> bytes:
    clip = min(8, max(1, int(duration or 8)))
    start = ["-t", str(clip)]
    if window == "last" and duration and duration > clip:
        start = ["-ss", str(max(0, int(duration) - clip)), "-t", str(clip)]
    return _run_bytes(
        start + [
            "-i", master_path,
            "-vf", "fps=10,scale=-2:480:flags=lanczos",
            "-an",
        ],
        ".gif",
    )


def video_has_audio(path: str) -> bool:
    probe = shutil.which("ffprobe") or shutil.which("ffmpeg")
    if not probe:
        return False
    if Path(probe).name == "ffprobe":
        result = subprocess.run(
            [
                probe, "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return "audio" in (result.stdout or "").lower()
    result = subprocess.run(
        [probe, "-i", path],
        capture_output=True,
        text=True,
        timeout=20,
    )
    return "Audio:" in (result.stderr or "")


def mix_voiceover(video_bytes: bytes, audio_bytes: bytes) -> bytes:
    """Mixa a locução no master. Se há faixa no vídeo, faz ducking."""
    if not audio_bytes:
        return video_bytes
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg_missing")
    suffix = ".wav" if audio_bytes[:4] == b"RIFF" else ".mp3"
    with tempfile.TemporaryDirectory() as folder:
        video = Path(folder) / "base.mp4"
        voice = Path(folder) / f"vo{suffix}"
        dest = Path(folder) / "out.mp4"
        video.write_bytes(video_bytes)
        voice.write_bytes(audio_bytes)
        if video_has_audio(str(video)):
            command = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(video),
                "-i", str(voice),
                "-filter_complex",
                "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume=1.15,apad,asplit=2[side][vo];"
                "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bed];"
                "[bed][side]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=250[ducked];"
                "[ducked][vo]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "160k",
                "-shortest",
                "-movflags", "+faststart",
                str(dest),
            ]
        else:
            command = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(video),
                "-i", str(voice),
                "-map", "0:v",
                "-map", "1:a",
                "-af", "apad",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "160k",
                "-shortest",
                "-movflags", "+faststart",
                str(dest),
            ]
        subprocess.run(command, check=True, timeout=180)
        return dest.read_bytes()


def _run_bytes(args, suffix):
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg_missing")
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder) / f"out{suffix}"
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args, str(dest)]
        subprocess.run(command, check=True, timeout=120)
        return dest.read_bytes()
