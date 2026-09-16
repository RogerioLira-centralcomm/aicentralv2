"""Storage privado para fontes e derivados do Analyzer."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess

from flask import current_app, has_app_context
from werkzeug.utils import secure_filename

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_VIDEO_SECONDS = 300
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class AnalyzerStorage:
    def __init__(self, root=None):
        self._root = Path(root) if root else None

    def root(self):
        if self._root is not None:
            path = self._root
        elif has_app_context():
            path = Path(current_app.instance_path) / "creative_analyzer"
        else:
            path = Path.cwd() / "instance" / "creative_analyzer"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_image(self, public_id, upload):
        payload = upload.stream.read(MAX_IMAGE_BYTES + 1)
        upload.stream.seek(0)
        if not payload:
            raise ValueError("O criativo está vazio.")
        if len(payload) > MAX_IMAGE_BYTES:
            raise ValueError("Envie uma imagem de até 15 MB.")
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(payload))
            image.load()
        except Exception as exc:
            raise ValueError("O arquivo enviado não é uma imagem válida.") from exc
        detected = (Image.MIME.get(image.format) or "").lower()
        if detected not in ALLOWED_IMAGE_MIMES:
            raise ValueError("Formato inválido. Use PNG, JPG ou WEBP.")
        width, height = image.size
        if width < 32 or height < 32 or width * height > 60_000_000:
            raise ValueError("Use uma imagem entre 32 px e 60 megapixels.")
        folder = self.root() / _safe_id(public_id)
        folder.mkdir(parents=True, exist_ok=True)
        extension = EXTENSIONS[detected]
        source = folder / f"source{extension}"
        source.write_bytes(payload)
        thumb = folder / "thumbnail.jpg"
        preview = image.convert("RGB")
        preview.thumbnail((720, 720))
        preview.save(thumb, format="JPEG", quality=84, optimize=True)
        return {
            "original_name": secure_filename(upload.filename or f"criativo{extension}")[:255],
            "mime_type": detected,
            "format": extension.lstrip(".").upper(),
            "source_key": str(source),
            "thumbnail_key": str(thumb),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "width": width,
            "height": height,
            "data_url": f"data:{detected};base64,{base64.b64encode(payload).decode('ascii')}",
        }

    def save_video(self, public_id, upload):
        extension = Path(secure_filename(upload.filename or "video.mp4")).suffix.lower()
        if extension not in {".mp4", ".mov", ".webm"}:
            raise ValueError("Formato inválido. Use MP4, MOV ou WebM.")
        payload = upload.stream.read(MAX_VIDEO_BYTES + 1)
        upload.stream.seek(0)
        if not payload:
            raise ValueError("O vídeo está vazio.")
        if len(payload) > MAX_VIDEO_BYTES:
            raise ValueError("Envie um vídeo de até 200 MB.")
        folder = self.root() / _safe_id(public_id)
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / f"source{extension}"
        source.write_bytes(payload)
        try:
            metadata = _probe_video(source)
            duration = metadata["duration"]
            if not 0 < duration <= MAX_VIDEO_SECONDS:
                raise ValueError("Use um vídeo com até 5 minutos.")
            times = four_frame_seconds(duration)
            frames = []
            for position, second in enumerate(times):
                path = folder / f"frame-{position}.jpg"
                actual_second = _extract_frame(source, path, second)
                raw = path.read_bytes()
                frames.append({
                    "position": position,
                    "second": actual_second,
                    "storage_key": str(path),
                    "mime_type": "image/jpeg",
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "data_url": f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}",
                })
            thumbnail = folder / "thumbnail.jpg"
            thumbnail.write_bytes(Path(frames[0]["storage_key"]).read_bytes())
        except Exception:
            for child in folder.iterdir():
                if child.is_file():
                    child.unlink()
            folder.rmdir()
            raise
        mime = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}[extension]
        return {
            "original_name": secure_filename(upload.filename or f"video{extension}")[:255],
            "mime_type": mime,
            "format": extension.lstrip(".").upper(),
            "source_key": str(source),
            "thumbnail_key": str(thumbnail),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "width": metadata["width"],
            "height": metadata["height"],
            "duration": duration,
            "has_audio": metadata["has_audio"],
            "video_codec": metadata["video_codec"],
            "audio_codec": metadata["audio_codec"],
            "frames": frames,
        }

    def read(self, public_id, kind):
        folder = self.root() / _safe_id(public_id)
        if kind == "thumbnail":
            path = folder / "thumbnail.jpg"
            mime = "image/jpeg"
        elif kind == "source":
            matches = [path for path in folder.glob("source.*") if path.suffix in {".jpg", ".png", ".webp", ".mp4", ".mov", ".webm"}]
            path = matches[0] if len(matches) == 1 else None
            mime = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}.get(path.suffix if path else "")
        elif kind.startswith("frame-") and kind[6:].isdigit() and 0 <= int(kind[6:]) <= 3:
            path = folder / f"frame-{int(kind[6:])}.jpg"
            mime = "image/jpeg"
        else:
            return None, None
        if path is None or not path.is_file():
            return None, None
        try:
            path.resolve().relative_to(self.root().resolve())
        except ValueError:
            return None, None
        return path, mime

    def remove(self, public_id):
        folder = self.root() / _safe_id(public_id)
        if folder.parent != self.root() or not folder.is_dir():
            return
        for path in folder.iterdir():
            if path.is_file():
                path.unlink()
        folder.rmdir()


def _safe_id(value):
    text = "".join(ch for ch in str(value or "") if ch.isalnum() or ch in {"-", "_"})
    return text[:64] or "invalid"


def four_frame_seconds(duration):
    try:
        duration = float(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError("Duração de vídeo inválida.") from exc
    if duration <= 0:
        raise ValueError("Duração de vídeo inválida.")
    last = max(0.001, duration - min(0.05, duration / 20))
    values = [duration * 0.02, duration * 0.30, duration * 0.65, duration * 0.95]
    return [round(max(0, min(value, last)), 3) for value in values]


def _probe_video(path):
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                "-format_whitelist", "mov,matroska,webm", "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height", "-of", "json", str(path),
            ],
            check=True, capture_output=True, text=True, timeout=25,
        )
        data = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ValueError("Não foi possível ler o vídeo. Confira o arquivo enviado.") from exc
    streams = data.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video:
        raise ValueError("O arquivo enviado não contém vídeo.")
    try:
        duration = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Não foi possível identificar a duração do vídeo.") from exc
    return {
        "duration": round(duration, 3),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "video_codec": video.get("codec_name"),
        "has_audio": bool(audio),
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def _extract_frame(source, destination, second):
    last_error = None
    for candidate in dict.fromkeys((second, max(0, second - 0.15), max(0, second - 0.35), 0)):
        destination.unlink(missing_ok=True)
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-i", str(source), "-ss", str(candidate),
                    "-frames:v", "1", "-vf",
                    "scale='min(1600,iw)':-2:force_original_aspect_ratio=decrease",
                    "-c:v", "mjpeg", "-pix_fmt", "yuvj420p", "-q:v", "3", str(destination),
                ],
                check=False, capture_output=True, timeout=35,
            )
            if result.returncode == 0 and destination.is_file() and destination.stat().st_size > 0:
                return round(float(candidate), 3)
            last_error = RuntimeError((result.stderr or b"").decode("utf-8", "replace")[-500:])
        except (OSError, subprocess.SubprocessError) as exc:
            last_error = exc
    raise ValueError("Não foi possível extrair os quatro frames do vídeo.") from last_error
