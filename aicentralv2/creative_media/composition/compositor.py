"""ffmpeg: crop 4:5 e overlay no master. Sem Seedance."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..geometry import crop_box_4x5
from ..transcode import ffmpeg_available, _run_bytes


def crop_video(video_bytes: bytes, width: int, height: int, piece_ratio: str) -> bytes:
    if str(piece_ratio or "") != "4:5":
        return video_bytes
    left, top, crop_w, crop_h = crop_box_4x5(width, height)
    if crop_w == width and crop_h == height:
        return video_bytes
    return _run_on_bytes(
        video_bytes,
        [f"crop={crop_w}:{crop_h}:{left}:{top}"],
        ".mp4",
        encode=True,
    )


def window_enable(start, end):
    return f"between(t,{float(start):.3f},{float(end):.3f})"


def overlay_covers_time(at_seconds, start, end):
    return float(start) <= float(at_seconds) < float(end)


def overlay_video(video_bytes: bytes, overlay_png: bytes, *, start=None, end=None) -> bytes:
    if not overlay_png:
        return video_bytes
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg_missing")
    enable = ""
    if start is not None or end is not None:
        enable = f":enable='{window_enable(start or 0, end if end is not None else 1e6)}'"
    with tempfile.TemporaryDirectory() as folder:
        video = Path(folder) / "base.mp4"
        overlay = Path(folder) / "overlay.png"
        dest = Path(folder) / "out.mp4"
        video.write_bytes(video_bytes)
        overlay.write_bytes(overlay_png)
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-i", str(overlay),
            "-filter_complex",
            f"[1:v][0:v]scale2ref[ov][base];[base][ov]overlay=0:0:format=auto{enable}",
            "-c:v", "libx264",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(dest),
        ]
        import subprocess

        subprocess.run(command, check=True, timeout=180)
        return dest.read_bytes()


def _run_on_bytes(payload: bytes, filters, suffix, encode=False):
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg_missing")
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / f"in{suffix}"
        source.write_bytes(payload)
        vf = ",".join(filters)
        extra = ["-vf", vf]
        if encode:
            extra.extend(["-c:v", "libx264", "-c:a", "copy", "-movflags", "+faststart"])
        return _run_bytes(["-i", str(source), *extra], suffix)
