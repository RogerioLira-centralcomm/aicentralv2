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


def _run_bytes(args, suffix):
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg_missing")
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder) / f"out{suffix}"
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args, str(dest)]
        subprocess.run(command, check=True, timeout=120)
        return dest.read_bytes()
