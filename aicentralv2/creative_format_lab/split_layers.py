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
    if callable(predictor):
        predict = predictor
        engine = "custom"
    else:
        predict, engine = resolve_predictor()
    detections = _normalize_detections(predict(source), source.size)
    layers = []
    union = Image.new("L", source.size, 0)
    cast_ok = False
    for index, item in enumerate(detections):
        mask = item["mask"]
        if mask.getbbox() is None:
            continue
        role = "cast" if item["label"] in CAST_LABELS else "product"
        quality = _mask_quality(mask, source, engine if role == "cast" else "custom")
        if role == "cast" and not quality["ok"]:
            logger.info("Máscara de pessoa recusada: %s", quality["reason"])
            continue
        union = ImageChops.lighter(union, mask)
        crop, box = _cutout(source, mask)
        layers.append(_layer(role, item["label"], box, crop, index))
        if role == "cast":
            cast_ok = True
    field_rgb = _field_rgb(source, union)
    kind = classify_ground(source, field_rgb)
    ground, field = _ground(source, union, field_rgb, kind, cast_ok)
    layers.append(_layer("ground", "ground", {"x": 0, "y": 0, "w": 100, "h": 100}, ground, len(layers)))
    return {
        "layers": layers,
        "field": field,
        "engine": engine,
        "cast_ok": cast_ok,
        "ground_kind": kind,
        "width": source.size[0],
        "height": source.size[1],
    }


def default_predictor():
    predict, _engine = resolve_predictor()
    return predict


def resolve_predictor():
    try:
        return _load_rembg(), "rembg"
    except Exception:
        pass
    try:
        return _load_yolo_person(), "yolo"
    except Exception:
        pass
    return field_predictor, "python"


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
        "ground_kind": "paper",
    }


def tim_like_still():
    """Campo navy, blusa da tinta, pele e tipo branco. Sem segmentador a pessoa falha."""
    if Image is None:
        raise RuntimeError("Pillow é necessário para recortar camadas.")
    from PIL import ImageDraw

    canvas = Image.new("RGB", (640, 240), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([8, 8, 632, 232], radius=18, fill=(1, 21, 74))
    draw.rectangle([28, 28, 300, 64], fill=(255, 255, 255))
    draw.rectangle([28, 88, 160, 140], fill=(255, 255, 255))
    draw.ellipse([430, 20, 500, 88], fill=(196, 122, 90))
    draw.rectangle([438, 84, 494, 168], fill=(1, 21, 74))
    draw.rectangle([420, 164, 512, 220], fill=(180, 20, 40))
    return canvas


def lifestyle_still():
    """Foto com variação. Image 2 pode limpar o poço."""
    if Image is None:
        raise RuntimeError("Pillow é necessário para recortar camadas.")
    from PIL import ImageDraw

    canvas = Image.new("RGB", (320, 180), (40, 50, 40))
    pixels = canvas.load()
    for y in range(180):
        for x in range(320):
            pixels[x, y] = (
                (x * 3 + y * 2) % 170 + 30,
                (y * 5 + x) % 140 + 40,
                (x + y * 3) % 160 + 20,
            )
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([200, 24, 292, 164], fill=(196, 122, 90))
    return canvas


def field_predictor(image):
    """Pele primeiro. Tinta e sofá não viram pessoa. Sem YOLO, sem Image 2."""
    source = image.convert("RGB")
    paper = _trim_paper(source)
    card = source.crop(paper)
    work = card.copy()
    work.thumbnail((320, 320), Image.BILINEAR)
    field = _corner_field(work)
    skin = _skin_mask(work)
    seed = _pick_person(
        _blobs(skin, min_area=max(10, int(work.size[0] * work.size[1] * 0.0015))),
        work,
    )
    if seed is None:
        figure = _without_type(_difference_mask(work, field), work)
        seed = _pick_person(
            _blobs(figure, min_area=max(16, int(work.size[0] * work.size[1] * 0.004))),
            work,
        )
    if seed is None:
        return []
    filled = _fill_from_skin(seed, work)
    mask = Image.new("L", source.size, 0)
    mask.paste(filled.resize(card.size, Image.NEAREST), (paper[0], paper[1]))
    return [{"label": "person", "mask": mask}]


def _load_rembg():
    from rembg import new_session, remove

    session = new_session("u2net_human_seg")

    def predict(image):
        rgba = remove(image.convert("RGB"), session=session)
        if not isinstance(rgba, Image.Image):
            rgba = Image.open(io.BytesIO(rgba)).convert("RGBA")
        else:
            rgba = rgba.convert("RGBA")
        return [{"label": "person", "mask": rgba.split()[-1]}]

    return predict


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


def _load_yolo_person():
    raw = _load_yolo()

    def predict(image):
        return [item for item in raw(image) if item.get("label") in CAST_LABELS]

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
    if red < 50 or red < green + 4 or blue > red + 12:
        return False
    if _luma(color) > 210:
        return False
    return (red - blue) > 8 and abs(red - green) < 90


def _skin_mask(image):
    mask = Image.new("L", image.size, 0)
    pixels = image.load()
    marks = mask.load()
    for y in range(image.size[1]):
        for x in range(image.size[0]):
            if _is_skin(pixels[x, y]):
                marks[x, y] = 255
    if ImageFilter is not None:
        mask = mask.filter(ImageFilter.MaxFilter(5))
    return mask


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


def _fill_from_skin(seed, image):
    """Rosto e mãos definem a coluna. Camisa da tinta e cachecol entram. Sofá não."""
    width, height = seed.size
    box = seed.getbbox()
    if box is None:
        return seed
    if (box[2] - box[0]) / max(1, width) > 0.55:
        return seed
    pad = max(6, (box[2] - box[0]) // 2)
    left = max(0, box[0] - pad)
    right = min(width, box[2] + pad)
    filled = seed.copy()
    marks = filled.load()
    seed_px = seed.load()
    radius = max(6, height // 8)
    for y in range(max(0, box[1] - 4), min(height, box[3] + 4)):
        xs = []
        for yy in range(max(0, y - radius), min(height, y + radius + 1)):
            for x in range(left, right):
                if seed_px[x, yy] >= 128:
                    xs.append(x)
        if not xs:
            continue
        for x in range(min(xs), max(xs) + 1):
            marks[x, y] = 255
    closed = _morph_close(filled, radius=max(8, height // 8))
    out = Image.new("L", seed.size, 0)
    out_px = out.load()
    closed_px = closed.load()
    for y in range(height):
        for x in range(left, right):
            if marks[x, y] >= 128 or closed_px[x, y] >= 128:
                out_px[x, y] = 255
    return out


def _fill_figure(seed, image):
    return _fill_from_skin(seed, image)


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


def _mask_quality(mask, source, engine="python"):
    box = mask.getbbox()
    if box is None:
        return {"ok": False, "reason": "empty"}
    width, height = source.size
    hist = mask.histogram()
    covered = sum(hist[128:]) if hist else 0
    total = max(1, width * height)
    coverage = covered / total
    if coverage < 0.02:
        return {"ok": False, "reason": "tiny"}
    box_w = (box[2] - box[0]) / width
    box_h = (box[3] - box[1]) / height
    if box_w > 0.92 and box_h > 0.88:
        return {"ok": False, "reason": "full-frame"}
    rgb = source.convert("RGB")
    pixels = rgb.load()
    marks = mask.load()
    ink = 0
    white = 0
    skin = 0
    field = _corner_field(rgb)
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if marks[x, y] < 128:
                continue
            color = pixels[x, y]
            if _is_paper(color):
                white += 1
            if _is_skin(color):
                skin += 1
            dist = abs(color[0] - field[0]) + abs(color[1] - field[1]) + abs(color[2] - field[2])
            if dist < 80:
                ink += 1
    if covered and white / covered > 0.55:
        return {"ok": False, "reason": "paper"}
    if engine not in {"rembg", "yolo"} and covered and ink / covered > 0.45 and skin / covered < 0.18:
        return {"ok": False, "reason": "field-garment"}
    return {"ok": True, "reason": ""}


def classify_ground(source, field_rgb):
    rgb = source.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    near = 0
    total = width * height
    red, green, blue = field_rgb
    step = max(1, min(width, height) // 80)
    sampled = 0
    for y in range(0, height, step):
        for x in range(0, width, step):
            sampled += 1
            color = pixels[x, y]
            if abs(color[0] - red) + abs(color[1] - green) + abs(color[2] - blue) < 48:
                near += 1
    if sampled and near / sampled >= 0.28:
        return "paper"
    return "image"


def _field_rgb(source, union):
    inverted = ImageChops.invert(union)
    if inverted.getbbox() is None:
        inverted = Image.new("L", source.size, 255)
    return _median_color(source, inverted)


def _ground(source, union, field_rgb=None, ground_kind="paper", cast_ok=False):
    if field_rgb is None:
        field_rgb = _field_rgb(source, union)
    field = "#{:02X}{:02X}{:02X}".format(*field_rgb)
    if ground_kind == "paper" or not cast_ok:
        return Image.new("RGBA", source.size, field_rgb + (255,)), field
    inverted = ImageChops.invert(union)
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
