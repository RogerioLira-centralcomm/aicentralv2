"""Logo oficial por cima do vídeo pronto, só nas cenas marcadas.

O Seedance deforma logos, então a imagem de cada cena sai sem logo e ele entra aqui, depois do movimento:
- selo ("badge"): pequeno, no canto inferior direito, durante a cena;
- assinatura ("signature"): maior, no centro, do início da cena até o fim do vídeo.

No modo storyboard o Seedance recebe as cenas juntas e devolve um vídeo só; cada cena ocupa uma fatia igual da
duração. A posição no tempo é, portanto, aproximada; a assinatura do fim é sempre exata.
"""
from __future__ import annotations

import base64
import io
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

BADGE_EDGE = 0.15  # s: o selo entra e sai um pouco dentro da fatia da cena, longe do corte
FADE = 0.35
SIGNATURE_MIN = 2.0  # s: a assinatura fica no ar pelo menos isso, mesmo com muitas cenas
SIGNATURE_WIDTH, SIGNATURE_HEIGHT = 0.42, 0.20


def mark_windows(marks, duration):
    """(índice da cena, tipo, início, fim) para cada cena com logo."""
    count = len(marks)
    if not count or duration <= 0:
        return []
    slice_ = duration / count
    windows = []
    for index, mark in enumerate(marks):
        start, end = index * slice_, (index + 1) * slice_
        if mark == "badge":
            start, end = start + BADGE_EDGE, end - BADGE_EDGE
            if end - start >= 2 * FADE:
                windows.append((index, "badge", round(start, 3), round(end, 3)))
        elif mark == "signature":
            start = max(0.0, min(start, duration - SIGNATURE_MIN))
            windows.append((index, "signature", round(start, 3), round(duration, 3)))
    return windows


def _logo_images(data_urls):
    images = []
    for url in data_urls or []:
        try:
            image = Image.open(io.BytesIO(base64.b64decode(str(url).split(",", 1)[1])))
            image.load()
            images.append(image.convert("RGBA"))
        except (ValueError, OSError, IndexError):
            continue
    return images


def _background(still, width, height):
    if not still:
        return Image.new("RGB", (width, height), (128, 128, 128))
    try:
        image = Image.open(io.BytesIO(still))
        image.load()
    except OSError:
        return Image.new("RGB", (width, height), (128, 128, 128))
    return ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (width, height))


def mark_overlay(width, height, logos, kind, still=None):
    """PNG transparente do tamanho do vídeo com o logo no lugar do tipo; a variante que mais contrasta vence."""
    from ..studio_create import (LOGO_HEIGHT_RATIO, LOGO_MARGIN_RATIO, LOGO_MIN_CONTRAST, LOGO_WIDTH_RATIO,
                                 _mean_luminance, _mono_logo)
    background = _background(still, width, height)
    if kind == "signature":
        slot_w, slot_h = width * SIGNATURE_WIDTH, height * SIGNATURE_HEIGHT
    else:
        slot_w, slot_h = width * LOGO_WIDTH_RATIO, height * LOGO_HEIGHT_RATIO
    margin_x, margin_y = round(width * LOGO_MARGIN_RATIO), round(height * LOGO_MARGIN_RATIO)

    def placed(candidate):
        scale = min(slot_w / candidate.width, slot_h / candidate.height)
        mark = candidate.resize((max(1, round(candidate.width * scale)), max(1, round(candidate.height * scale))),
                                Image.Resampling.LANCZOS)
        if kind == "signature":
            left, top = (width - mark.width) // 2, (height - mark.height) // 2
        else:
            left, top = width - margin_x - mark.width, height - margin_y - mark.height
        region = background.crop((left, top, left + mark.width, top + mark.height))
        luma = _mean_luminance(mark.convert("RGB"), mark.getchannel("A"))
        return mark, left, top, abs(_mean_luminance(region) - luma)

    best = max((placed(item) for item in logos), key=lambda item: item[3])
    alpha = logos[0].getchannel("A").tobytes()
    if best[3] < LOGO_MIN_CONTRAST and sum(1 for value in alpha if value < 250) / max(1, len(alpha)) > 0.05:
        # Nenhuma variante oficial lê sobre a cena: a mesma arte, chapada em branco ou escuro.
        mono = [_mono_logo(logos[0], (255, 255, 255)), _mono_logo(logos[0], (11, 18, 25))]
        best = max([best, *(placed(item) for item in mono)], key=lambda item: item[3])
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(best[0], (best[1], best[2]))
    output = io.BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()


def _probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
         "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=20)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return int(stream["width"]), int(stream["height"]), float(data["format"]["duration"])


def apply_brand_marks(video_bytes, brand_marks, stills=()):
    """O vídeo com o logo nas cenas marcadas, num único passe do ffmpeg. Sem logo legível, devolve o original."""
    logos = _logo_images((brand_marks or {}).get("logos"))
    marks = list((brand_marks or {}).get("scenes") or [])
    if not logos or not marks:
        raise ValueError("Sem logo legível para aplicar.")
    with tempfile.TemporaryDirectory(prefix="brand-marks-") as folder:
        source = Path(folder) / "base.mp4"
        dest = Path(folder) / "out.mp4"
        source.write_bytes(video_bytes)
        width, height, duration = _probe(source)
        windows = mark_windows(marks, duration)
        if not windows:
            return video_bytes
        command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)]
        filters, last = [], "0:v"
        for number, (index, kind, start, end) in enumerate(windows, 1):
            still = stills[index] if index < len(stills) else None
            png = Path(folder) / f"mark-{number}.png"
            png.write_bytes(mark_overlay(width, height, logos, kind, still))
            command += ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(png)]
            fade = f"fade=t=in:st={start}:d={FADE}:alpha=1"
            if kind == "badge":
                fade += f",fade=t=out:st={end - FADE:.3f}:d={FADE}:alpha=1"
            filters.append(f"[{number}:v]format=rgba,{fade}[m{number}]")
            filters.append(f"[{last}][m{number}]overlay=0:0:enable='between(t,{start},{end})'[v{number}]")
            last = f"v{number}"
        command += ["-filter_complex", ";".join(filters), "-map", f"[{last}]", "-map", "0:a?", "-c:a", "copy",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-t", f"{duration:.3f}", str(dest)]
        subprocess.run(command, check=True, capture_output=True, timeout=240)
        return dest.read_bytes()
