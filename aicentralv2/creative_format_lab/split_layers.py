"""Recorte real de um still em camadas PNG. Sem Image 2."""

from __future__ import annotations

import base64
import io
import logging

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError:  # pragma: no cover
    Image = None
    ImageChops = None
    ImageFilter = None

logger = logging.getLogger(__name__)

CAST_LABELS = {"person"}
ROLE_LABELS = {
    "cast": "Pessoa",
    "product": "Produto",
    "ground": "Fundo",
}


def split_still(image, predictor=None):
    source = _open_image(image)
    engine = "python"
    if callable(predictor):
        predict = predictor
        engine = "custom"
    else:
        predict = default_predictor()
    detections = _normalize_detections(predict(source), source.size)
    layers = []
    union = Image.new("L", source.size, 0)
    for index, item in enumerate(detections):
        mask = item["mask"]
        if mask.getbbox() is None:
            continue
        union = ImageChops.lighter(union, mask)
        role = "cast" if item["label"] in CAST_LABELS else "product"
        crop, box = _cutout(source, mask)
        layers.append(_layer(role, item["label"], box, crop, index))
    ground, field = _ground(source, union)
    layers.append(_layer("ground", "ground", {"x": 0, "y": 0, "w": 100, "h": 100}, ground, len(layers)))
    return {
        "layers": layers,
        "field": field,
        "engine": engine,
        "width": source.size[0],
        "height": source.size[1],
    }


def default_predictor():
    return field_predictor


def hypothetical_still():
    """Banner 16:9 de teste: tinta, tipo, selo e pessoa. Sem modelo."""
    if Image is None:
        raise RuntimeError("Pillow é necessário para recortar camadas.")
    from PIL import ImageDraw

    canvas = Image.new("RGB", (480, 180), (0, 51, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([24, 28, 220, 88], fill=(255, 255, 255))
    draw.rectangle([24, 120, 140, 156], fill=(245, 197, 24))
    draw.ellipse([320, 20, 460, 170], fill=(196, 122, 90))
    draw.rectangle([360, 110, 430, 170], fill=(20, 20, 28))
    return canvas


def example_still_payload():
    image = hypothetical_still()
    return {
        "image": _png_data_url(image),
        "width": image.size[0],
        "height": image.size[1],
        "engine": "python",
    }


def field_predictor(image):
    """Pessoa à direita, tinta nos cantos. Tipo claro fica fora. Sem YOLO, sem Image 2."""
    source = image.convert("RGB")
    paper = _trim_paper(source)
    card = source.crop(paper)
    work = card.copy()
    work.thumbnail((320, 320), Image.BILINEAR)
    field = _corner_field(work)
    figure = _without_type(_difference_mask(work, field), work)
    blobs = _blobs(figure, min_area=max(16, int(work.size[0] * work.size[1] * 0.004)))
    seed = _pick_person(blobs, work)
    if seed is None:
        return []
    filled = _fill_figure(seed, work)
    mask = Image.new("L", source.size, 0)
    mask.paste(filled.resize(card.size, Image.NEAREST), (paper[0], paper[1]))
    return [{"label": "person", "mask": mask}]


def _load_yolo():
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ValueError("Instale ultralytics para recortar camadas, ou passe um predictor.") from exc

    model = YOLO("yolov8n-seg.pt")

    def predict(image):
        rgb = image.convert("RGB")
        width, height = image.size
        found = []
        for result in model(rgb, verbose=False):
            if result.masks is None:
                continue
            names = getattr(result, "names", None) or getattr(model, "names", {}) or {}
            for index, mask_data in enumerate(result.masks.data):
                label = "object"
                if result.boxes is not None and index < len(result.boxes.cls):
                    class_id = int(result.boxes.cls[index])
                    label = str(names.get(class_id) or "object")
                found.append({
                    "label": label,
                    "mask": _resize_mask(mask_data, width, height),
                })
        return found

    return predict


def _luma(color):
    red, green, blue = color[:3]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _is_paper(color, luma=242):
    red, green, blue = color[:3]
    if _luma(color) < luma:
        return False
    return max(red, green, blue) - min(red, green, blue) < 16


def _is_skin(color):
    red, green, blue = (int(item) for item in color[:3])
    if red < 50 or red < green + 6 or blue > red + 8:
        return False
    if _luma(color) > 205:
        return False
    return (red - blue) > 12 and abs(red - green) < 80


def _trim_paper(image):
    """Corta margem branca de print. Campo claro da marca fica."""
    width, height = image.size
    pixels = image.load()
    left, top, right, bottom = width, height, 0, 0
    found = False
    for y in range(height):
        for x in range(width):
            if _is_paper(pixels[x, y]):
                continue
            found = True
            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)
    if not found:
        return (0, 0, width, height)
    pad = max(2, min(width, height) // 80)
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(width, right + 1 + pad),
        min(height, bottom + 1 + pad),
    )


def _corner_field(image):
    """Tinta do papel. Ignora canto branco de print e tipo claro."""
    width, height = image.size
    pixels = image.load()
    points = []
    for y_part in (0.18, 0.35, 0.5, 0.65, 0.82):
        for x_part in (0.04, 0.08, 0.14, 0.22, 0.78, 0.9):
            points.append((
                min(width - 1, max(0, int(width * x_part))),
                min(height - 1, max(0, int(height * y_part))),
            ))
    samples = []
    for x, y in points:
        color = pixels[x, y][:3]
        if _luma(color) > 210:
            continue
        samples.append(color)
    if not samples:
        samples = [pixels[width // 8, height // 2][:3]]
    mid = len(samples) // 2
    return (
        sorted(item[0] for item in samples)[mid],
        sorted(item[1] for item in samples)[mid],
        sorted(item[2] for item in samples)[mid],
    )


def _without_type(mask, image, luma=205):
    """Tipo e pill à esquerda não são pessoa. Tênis claro à direita fica."""
    cleaned = mask.copy()
    pixels = image.load()
    marks = cleaned.load()
    left_copy = int(image.size[0] * 0.48)
    for y in range(image.size[1]):
        for x in range(left_copy):
            if marks[x, y] >= 128 and _luma(pixels[x, y]) > luma:
                marks[x, y] = 0
    return cleaned


def _wide_ribbon(box, size):
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    return (width / size[0] > 0.58 and height / size[1] < 0.28) or width / size[0] > 0.78


def _blob_stats(blob, image):
    box = blob.getbbox()
    if box is None:
        return None
    pixels = image.load()
    marks = blob.load()
    count = 0
    luma_sum = 0
    x_sum = 0
    skin = 0
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if marks[x, y] < 128:
                continue
            color = pixels[x, y]
            count += 1
            luma_sum += _luma(color)
            x_sum += x
            if _is_skin(color):
                skin += 1
    if count < 12:
        return None
    return {
        "box": box,
        "count": count,
        "mean_luma": luma_sum / count,
        "cx": x_sum / count,
        "skin": skin / count,
    }


def _blob_score(blob, image):
    stats = _blob_stats(blob, image)
    if stats is None or stats["mean_luma"] > 200:
        return -1
    box = stats["box"]
    if _wide_ribbon(box, image.size):
        return -1
    width, height = image.size
    box_w = max(1, box[2] - box[0])
    box_h = max(1, box[3] - box[1])
    if box_w / width > 0.42 and box_h / height > 0.4 and stats["skin"] < 0.08:
        return -1
    rightness = stats["cx"] / max(1, width)
    tall = min(2.6, box_h / box_w)
    return (
        stats["count"]
        * (0.3 + rightness)
        * (0.35 + tall)
        * (0.25 + box_h / height)
        * (1.0 + 3.0 * stats["skin"])
    )


def _pick_person(blobs, image):
    scored = []
    for blob in blobs:
        score = _blob_score(blob, image)
        if score <= 0:
            continue
        stats = _blob_stats(blob, image)
        if stats is None:
            continue
        scored.append((score, blob, stats))
    if not scored:
        return None
    skin = [item for item in scored if item[2]["skin"] > 0.1]
    right = [item for item in scored if item[2]["cx"] > image.size[0] * 0.4]
    pool = skin or right
    if not pool:
        return None
    pool.sort(key=lambda item: item[0], reverse=True)
    anchor = pool[0]
    acx = anchor[2]["cx"]
    chosen = Image.new("L", image.size, 0)
    for score, blob, stats in scored:
        if abs(stats["cx"] - acx) > image.size[0] * 0.16:
            continue
        if _wide_ribbon(stats["box"], image.size):
            continue
        chosen = ImageChops.lighter(chosen, blob)
    return chosen if chosen.getbbox() else anchor[1]


def _odd_kernel(value):
    size = max(3, int(value))
    return size if size % 2 else size + 1


def _morph_close(mask, radius=16):
    if ImageFilter is None:
        return mask
    size = _odd_kernel(min(radius * 2 + 1, 41))
    return mask.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))


def _fill_figure(seed, image):
    """Fecha o torso quando a roupa some na tinta. Não pinta o card inteiro."""
    width, height = seed.size
    box = seed.getbbox()
    if box is None:
        return seed
    if (box[2] - box[0]) / max(1, width) > 0.55:
        return seed
    pad = max(3, (box[2] - box[0]) // 3)
    left = max(0, box[0] - pad)
    right = min(width, box[2] + pad)
    closed = _morph_close(seed, radius=max(10, height // 7))
    filled = Image.new("L", seed.size, 0)
    seed_px = seed.load()
    closed_px = closed.load()
    marks = filled.load()
    pixels = image.load()
    for y in range(height):
        for x in range(left, right):
            if _luma(pixels[x, y]) > 205:
                continue
            if seed_px[x, y] >= 128 or closed_px[x, y] >= 128:
                marks[x, y] = 255
    for x in range(left, right):
        ys = [y for y in range(height) if marks[x, y] >= 128]
        if len(ys) < 2 or (ys[-1] - ys[0]) < height * 0.22:
            continue
        for y in range(ys[0], ys[-1] + 1):
            if _luma(pixels[x, y]) <= 205:
                marks[x, y] = 255
    return filled


def _difference_mask(image, field, threshold=90):
    width, height = image.size
    mask = Image.new("L", (width, height), 0)
    pixels = image.load()
    marks = mask.load()
    red, green, blue = field
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            distance = abs(pixel[0] - red) + abs(pixel[1] - green) + abs(pixel[2] - blue)
            if distance > threshold:
                marks[x, y] = 255
    return mask


def _blobs(mask, min_area=40):
    width, height = mask.size
    pixels = mask.load()
    seen = [[False] * width for _ in range(height)]
    blobs = []
    for top in range(height):
        for left in range(width):
            if pixels[left, top] < 128 or seen[top][left]:
                continue
            stack = [(left, top)]
            seen[top][left] = True
            cells = []
            while stack:
                x, y = stack.pop()
                cells.append((x, y))
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if seen[ny][nx] or pixels[nx, ny] < 128:
                        continue
                    seen[ny][nx] = True
                    stack.append((nx, ny))
            if len(cells) < min_area:
                continue
            blob = Image.new("L", (width, height), 0)
            marks = blob.load()
            for x, y in cells:
                marks[x, y] = 255
            blobs.append((len(cells), blob))
    blobs.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in blobs[:6]]


def _open_image(image):
    if Image is None:
        raise RuntimeError("Pillow é necessário para recortar camadas.")
    if isinstance(image, Image.Image):
        return image.convert("RGBA")
    if isinstance(image, (bytes, bytearray)):
        return Image.open(io.BytesIO(image)).convert("RGBA")
    text = str(image or "").strip()
    if text.startswith("data:image/") and "," in text:
        raw = base64.b64decode(text.split(",", 1)[1], validate=False)
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    raise ValueError("Envie um still em data URL ou bytes.")


def _normalize_detections(raw, size):
    width, height = size
    items = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        mask = _resize_mask(item.get("mask"), width, height)
        if mask is None:
            continue
        items.append({
            "label": str(item.get("label") or "object").strip().lower() or "object",
            "mask": mask,
        })
    return items


def _resize_mask(mask, width, height):
    if mask is None:
        return None
    if Image is not None and isinstance(mask, Image.Image):
        bitmap = mask.convert("L")
    else:
        bitmap = _mask_from_array(mask)
        if bitmap is None:
            return None
    if bitmap.size != (width, height):
        bitmap = bitmap.resize((width, height), Image.NEAREST)
    return bitmap.point(lambda value: 255 if value > 127 else 0)


def _mask_from_array(mask):
    if hasattr(mask, "detach"):
        mask = mask.detach().cpu().numpy()
    if hasattr(mask, "tolist") and not isinstance(mask, (bytes, bytearray, str, list, tuple)):
        try:
            rows = mask.tolist()
        except Exception:
            return None
        if rows and isinstance(rows[0], (list, tuple)) and rows and isinstance(rows[0][0], (list, tuple)):
            rows = rows[0]
        return _mask_from_rows(rows)
    if isinstance(mask, (list, tuple)):
        rows = mask
        if rows and isinstance(rows[0], (list, tuple)) and rows[0] and isinstance(rows[0][0], (list, tuple)):
            rows = rows[0]
        return _mask_from_rows(rows)
    return None


def _mask_from_rows(rows):
    if not rows:
        return None
    height = len(rows)
    width = len(rows[0])
    bitmap = Image.new("L", (width, height), 0)
    pixels = bitmap.load()
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            pixels[x, y] = 255 if float(value) > 0.5 else 0
    return bitmap


def _cutout(source, mask):
    sheet = Image.new("RGBA", source.size, (0, 0, 0, 0))
    sheet.paste(source, mask=mask)
    box = mask.getbbox()
    if box is None:
        empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        return empty, {"x": 0, "y": 0, "w": 0, "h": 0}
    cropped = sheet.crop(box)
    width, height = source.size
    left, top, right, bottom = box
    return cropped, {
        "x": round(100.0 * left / width, 2),
        "y": round(100.0 * top / height, 2),
        "w": round(100.0 * (right - left) / width, 2),
        "h": round(100.0 * (bottom - top) / height, 2),
    }


def _ground(source, union):
    inverted = ImageChops.invert(union)
    hist = union.histogram()
    covered = sum(hist[128:]) if hist else 0
    total = max(1, source.size[0] * source.size[1])
    field_rgb = _median_color(source, inverted)
    field = "#{:02X}{:02X}{:02X}".format(*field_rgb)
    if (total - covered) / total < 0.02:
        return Image.new("RGBA", source.size, field_rgb + (255,)), field
    leftover = Image.new("RGBA", source.size, (0, 0, 0, 0))
    leftover.paste(source, mask=inverted)
    return leftover, field


def _median_color(source, keep):
    rgb = source.convert("RGB")
    color_data = list(rgb.getdata())
    flags = list(keep.getdata())
    samples = [color_data[index] for index, flag in enumerate(flags) if flag > 127]
    if not samples:
        samples = color_data
    mid = len(samples) // 2
    reds = sorted(item[0] for item in samples)
    greens = sorted(item[1] for item in samples)
    blues = sorted(item[2] for item in samples)
    return (reds[mid], greens[mid], blues[mid])


def _layer(role, label, box, image, index):
    return {
        "id": f"{role}-{index}",
        "role": role,
        "label": ROLE_LABELS.get(role) if role == "ground" else (label or ROLE_LABELS.get(role) or role),
        "box": box,
        "png_data_url": _png_data_url(image),
    }


def _png_data_url(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
