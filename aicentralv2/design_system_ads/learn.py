"""Treino assertivo: nível × conceito × template × formato, com lote de ouro e score."""

from __future__ import annotations

from pathlib import Path

CURRICULUM = (
    {
        "id": "L1",
        "label": "Packshot limpo",
        "difficulty": 1,
        "format": "feed-1x1",
        "archetype": "product-hero",
        "concept": "packshot",
        "template": "isolated-product",
        "lab": "campaign-pack",
        "crop_first": False,
        "teach": "Um produto no poço. Tipo fora da arte ou uma linha só. Trilha packshot.",
        "signals": ("packshot", "no_type_on_image", "single_object"),
    },
    {
        "id": "L2",
        "label": "Tipo na arte",
        "difficulty": 2,
        "format": "linkedin-landscape",
        "archetype": "product-hero",
        "concept": "product-kv",
        "template": "product-left-type",
        "lab": "format-lab-swap-read",
        "crop_first": False,
        "teach": "Headline e CTA dentro do KV. Um ousado só. Não inventar card SaaS.",
        "signals": ("type_on_image", "product", "one_cta"),
    },
    {
        "id": "L3",
        "label": "Lifestyle no feed",
        "difficulty": 3,
        "format": "feed-4x5",
        "archetype": "lifestyle",
        "concept": "lifestyle",
        "template": "overlay-card",
        "lab": "campaign-pack",
        "crop_first": True,
        "teach": "Pessoa + overlay + CTA nativo da rede. Recortar o chrome do app antes.",
        "signals": ("face", "overlay", "meta_chrome"),
    },
    {
        "id": "L4",
        "label": "Evento / elenco",
        "difficulty": 4,
        "format": "feed-1x1",
        "archetype": "promotion",
        "concept": "event-cast",
        "template": "name-pills",
        "lab": "decompose",
        "crop_first": False,
        "teach": "Muitos recortes, selos de nome, data, legal. Separar elenco e campo de tinta.",
        "signals": ("many_faces", "name_pills", "pattern"),
    },
    {
        "id": "L5",
        "label": "Print da rede",
        "difficulty": 5,
        "format": "feed-4x5",
        "archetype": "brand",
        "concept": "network-chrome",
        "template": "crop-frame",
        "lab": "crop-then-learn",
        "crop_first": True,
        "teach": "Print mistura editorial, chrome e anúncio. Recortar só a peça, depois cair no L2 ou L3.",
        "signals": ("screenshot", "browser_chrome", "sponsored_label"),
    },
)

CONCEPTS = (
    {"id": "packshot", "level": "L1", "teach": "Produto isolado. RSA e chrome ficam fora."},
    {"id": "product-kv", "level": "L2", "teach": "Produto + tipo no mesmo retângulo."},
    {"id": "comparison", "level": "L2", "teach": "Dois objetos, um rótulo cada. Não virar carrossel."},
    {"id": "event-kv", "level": "L2", "teach": "Data, nome do evento, tipo grande. Poucas caras."},
    {"id": "editorial-mock", "level": "L2", "teach": "Celular ou recorte de matéria. Não é o chrome da rede."},
    {"id": "lifestyle", "level": "L3", "teach": "Pessoa na cena + overlay. CTA da marca, não o da Meta."},
    {"id": "testimonial", "level": "L3", "teach": "Uma cara, uma citação. Quote é camada, não foto."},
    {"id": "event-cast", "level": "L4", "teach": "Elenco + selos. Decompose antes de recompor."},
    {"id": "network-chrome", "level": "L5", "teach": "Ainda não é a peça. Recortar."},
)

TEMPLATES = (
    {"id": "isolated-product", "concept": "packshot", "format": "feed-1x1"},
    {"id": "product-left-type", "concept": "product-kv", "format": "linkedin-landscape"},
    {"id": "full-bleed-type", "concept": "event-kv", "format": "feed-4x5"},
    {"id": "comparison-pair", "concept": "comparison", "format": "linkedin-landscape"},
    {"id": "speaker-card", "concept": "event-kv", "format": "linkedin-landscape"},
    {"id": "phone-mock", "concept": "editorial-mock", "format": "feed-4x5"},
    {"id": "overlay-card", "concept": "lifestyle", "format": "feed-4x5"},
    {"id": "quote-overlay", "concept": "testimonial", "format": "feed-4x5"},
    {"id": "face-overlay", "concept": "lifestyle", "format": "story-9x16"},
    {"id": "name-pills", "concept": "event-cast", "format": "feed-1x1"},
    {"id": "crop-frame", "concept": "network-chrome", "format": ""},
)

LAB_PROCESS = {
    "campaign-pack": {
        "route": "/parametros/api/campaigns/pack",
        "use": "Ler o criativo: headline, apoio, CTA, oferta. Vira campaign_pack da campanha.",
        "skill": "reconstruct",
    },
    "format-lab-swap-read": {
        "route": "/parametros/api/format-lab/swap/read",
        "use": "Ler a composição da peça (hierarquia, crop, frames) sem redesenhar o efeito.",
        "skill": "reconstruct",
    },
    "decompose": {
        "route": "creative_format_lab.decompose",
        "use": "Partir elenco e fundo. O campo de tinta vira wash; as pessoas vão ao poço.",
        "skill": "reconstruct",
    },
    "crop-then-learn": {
        "route": "",
        "use": "Recortar só o retângulo do anúncio. Jogar fora URL bar, tab, notícia vizinha.",
        "skill": "orchestrator",
    },
    "learn-line": {
        "route": "/parametros/api/clients/<id>/creative-line",
        "use": "Vários criativos da mesma marca → linha criativa e tinta, não um anúncio só.",
        "skill": "create",
    },
}

SCORE_AXES = ("id", "inner", "concept", "template", "format", "lab")

# Lote real (prints do Discover/Meta + Arraial). Hints = o que a visão deveria extrair.
GOLD_CORPUS = (
    (
        "arraial",
        {"faces": 6, "name_pills": True, "aspect": "1:1", "event": True},
        {
            "id": "L4",
            "inner": "L4",
            "concept": "event-cast",
            "template": "name-pills",
            "format": "feed-1x1",
            "lab": "decompose",
        },
    ),
    (
        "tom-ford",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": False, "faces": 0, "product": True},
        {
            "id": "L5",
            "inner": "L1",
            "concept": "packshot",
            "template": "isolated-product",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "joompro",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": False, "faces": 0, "product": True},
        {
            "id": "L5",
            "inner": "L1",
            "concept": "packshot",
            "template": "isolated-product",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "mg-cyberster",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 0, "product": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "nissan",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 0, "product": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "adjust",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 0},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "lacoste",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 0, "product": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "aviator",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 0, "product": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "arzopa",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 0, "product": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "meshy",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 0, "comparison": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "comparison",
            "template": "comparison-pair",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "avenue",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 1, "event": True, "speaker": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "event-kv",
            "template": "speaker-card",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "minimal-club",
        {"screenshot": True, "chrome": "google", "aspect": "1.91:1", "type_on_image": True, "faces": 2, "product": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    ),
    (
        "btg",
        {"screenshot": True, "chrome": "meta", "aspect": "4:5", "faces": 1, "overlay": True, "type_on_image": True},
        {
            "id": "L5",
            "inner": "L3",
            "concept": "lifestyle",
            "template": "overlay-card",
            "format": "feed-4x5",
            "lab": "crop-then-learn",
        },
    ),
    (
        "prudential",
        {"screenshot": True, "chrome": "meta", "aspect": "4:5", "faces": 1, "quote": True, "overlay": True},
        {
            "id": "L5",
            "inner": "L3",
            "concept": "testimonial",
            "template": "quote-overlay",
            "format": "feed-4x5",
            "lab": "crop-then-learn",
        },
    ),
    (
        "claro",
        {"screenshot": True, "chrome": "meta", "aspect": "9:16", "faces": 1, "overlay": True, "type_on_image": True},
        {
            "id": "L5",
            "inner": "L3",
            "concept": "lifestyle",
            "template": "face-overlay",
            "format": "story-9x16",
            "lab": "crop-then-learn",
        },
    ),
    (
        "seniortec",
        {"screenshot": True, "chrome": "meta", "aspect": "4:5", "faces": 2, "type_on_image": True, "event": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "event-kv",
            "template": "full-bleed-type",
            "format": "feed-4x5",
            "lab": "crop-then-learn",
        },
    ),
    (
        "sabesp",
        {"screenshot": True, "chrome": "meta", "aspect": "4:5", "faces": 0, "type_on_image": True, "editorial": True},
        {
            "id": "L5",
            "inner": "L2",
            "concept": "editorial-mock",
            "template": "phone-mock",
            "format": "feed-4x5",
            "lab": "crop-then-learn",
        },
    ),
    (
        "seniortec-cropped",
        {"cropped": True, "aspect": "4:5", "faces": 2, "type_on_image": True, "event": True},
        {
            "id": "L2",
            "inner": "L2",
            "concept": "event-kv",
            "template": "full-bleed-type",
            "format": "feed-4x5",
            "lab": "format-lab-swap-read",
        },
    ),
    (
        "joompro-cropped",
        {"cropped": True, "aspect": "1.91:1", "type_on_image": False, "faces": 0, "product": True},
        {
            "id": "L1",
            "inner": "L1",
            "concept": "packshot",
            "template": "isolated-product",
            "format": "linkedin-landscape",
            "lab": "campaign-pack",
        },
    ),
    (
        "btg-cropped",
        {"cropped": True, "aspect": "4:5", "faces": 1, "overlay": True, "type_on_image": True},
        {
            "id": "L3",
            "inner": "L3",
            "concept": "lifestyle",
            "template": "overlay-card",
            "format": "feed-4x5",
            "lab": "campaign-pack",
        },
    ),
)

# Dois criativos reais do lote (arquivos em tests/fixtures/creatives/).
LIVE_PAIR = (
    {
        "id": "arraial",
        "filename": "arraial-1x1.png",
        "hints": {"faces": 6, "name_pills": True, "event": True},
        "inspect": {"width": 640, "height": 640, "screenshot": False},
        "expect": {
            "id": "L4",
            "inner": "L4",
            "concept": "event-cast",
            "template": "name-pills",
            "format": "feed-1x1",
            "lab": "decompose",
        },
    },
    {
        "id": "mg-cyberster",
        "filename": "mg-discover.jpg",
        "hints": {
            "chrome": "google",
            "aspect": "1.91:1",
            "type_on_image": True,
            "product": True,
            "screenshot": True,
        },
        "inspect": {"width": 473, "height": 1024, "screenshot": True},
        "expect": {
            "id": "L5",
            "inner": "L2",
            "concept": "product-kv",
            "template": "product-left-type",
            "format": "linkedin-landscape",
            "lab": "crop-then-learn",
        },
    },
)

PORTRAIT = {"4:5", "9:16", "feed-4x5", "story-9x16"}
LANDSCAPE = {"1.91:1", "16:9", "linkedin-landscape", "1200:627"}


def curriculum():
    return [dict(item) for item in CURRICULUM]


def training_catalog():
    return {
        "levels": curriculum(),
        "concepts": [dict(item) for item in CONCEPTS],
        "templates": [dict(item) for item in TEMPLATES],
        "labs": {key: dict(value) for key, value in LAB_PROCESS.items()},
        "axes": list(SCORE_AXES),
    }


def inspect_creative_file(path):
    """Lê o arquivo: canvas, se é print de celular, aspect da peça (não do telefone)."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(str(file_path))
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow é necessário para inspecionar criativos") from exc
    with Image.open(file_path) as image:
        width, height = image.size
    ratio = width / max(1, height)
    phone = height / max(1, width) >= 1.85 and width <= 720
    hints = {"screenshot": phone, "width": width, "height": height}
    if not phone:
        hints["aspect"] = _aspect_from_ratio(ratio)
    return {
        "path": str(file_path),
        "width": width,
        "height": height,
        "ratio": round(ratio, 3),
        "screenshot": phone,
        "hints": hints,
    }


def lesson_from_file(path, hints=None):
    """Inspeciona o PNG/JPG e classifica. Hints do rótulo/visão sobrescrevem o canvas."""
    inspected = inspect_creative_file(path)
    merged = dict(inspected.get("hints") or {})
    extra = hints if isinstance(hints, dict) else {}
    for key, value in extra.items():
        if value not in (None, ""):
            merged[key] = value
    lesson = classify_creative(merged)
    lesson["inspect"] = inspected
    return lesson


def live_pair():
    return [dict(item) for item in LIVE_PAIR]


def classify_creative(hints=None):
    """Classifica superfície + aula interna (conceito, template, formato, skill)."""
    hints = hints if isinstance(hints, dict) else {}
    flags, aspect, faces = _flags(hints)
    screenshot = _is_screenshot(flags) and "cropped" not in flags
    inner = _classify_inner(flags, aspect, faces)
    format_key = _format_for(aspect, inner["format"], flags)

    if screenshot:
        lesson = _lesson("L5")
        lesson["inner"] = inner["id"]
        lesson["inner_lab"] = inner["lab"]
        lesson["concept"] = inner["concept"]
        lesson["template"] = inner["template"]
        lesson["archetype"] = inner["archetype"]
        lesson["next"] = inner["id"]
    else:
        lesson = dict(inner)
        lesson["inner"] = inner["id"]
        lesson["inner_lab"] = inner["lab"]
        lesson["next"] = _next_level(inner["id"])

    lesson["format"] = format_key
    lesson["lab_process"] = dict(LAB_PROCESS.get(lesson["lab"]) or {})
    lesson["flags"] = sorted(flags)
    lesson["confidence"] = _confidence(flags, aspect, lesson, screenshot)
    lesson["labs"] = _labs_for(lesson)
    return lesson


def plan_training(hints=None):
    """Aula + bundle mínimo das skills do Lab (reconstruct/create + formato)."""
    lesson = classify_creative(hints)
    try:
        from aicentralv2.creative_skills.loader import resolve_pack
    except ImportError:
        return lesson
    intent = "reconstruct" if lesson.get("inner") else "create"
    if lesson.get("id") == "L5":
        intent = "reconstruct"
    pack = resolve_pack(intent, lesson["format"], has_reference=True)
    lesson["labs"] = {
        "intent": pack["intent"],
        "packs": list(pack["packs"]),
        "format_skill": pack["format_skill"],
        "skills": [item["id"] for item in pack["skills"]],
        "after_crop": lesson.get("inner") or lesson["id"],
    }
    return lesson


def score_corpus(classifier=None, corpus=None):
    """Mede eixos do lote de ouro. classifier=None usa o classificador atual."""
    fn = classifier or classify_creative
    rows = corpus or GOLD_CORPUS
    hits = 0
    total = 0
    misses = []
    for case_id, hints, expect in rows:
        got = fn(dict(hints))
        for axis in SCORE_AXES:
            if axis not in expect:
                continue
            total += 1
            actual = got.get(axis)
            if axis == "inner":
                actual = got.get("inner") or got.get("id")
            if actual == expect[axis]:
                hits += 1
            else:
                misses.append(
                    {
                        "id": case_id,
                        "axis": axis,
                        "expected": expect[axis],
                        "got": actual,
                    }
                )
    return {
        "hits": hits,
        "total": total,
        "accuracy": hits / total if total else 0.0,
        "misses": misses,
        "cases": len(rows),
    }


def measure_training():
    """Antes (v1: só nível/formato) vs depois (nível + aula interna)."""
    before = score_corpus(_classify_v1)
    after = score_corpus(classify_creative)
    return {
        "before": before,
        "after": after,
        "delta": after["accuracy"] - before["accuracy"],
        "axes": list(SCORE_AXES),
    }


def _classify_inner(flags, aspect, faces):
    if "many_faces" in flags or faces >= 4:
        return _lesson("L4", concept="event-cast", template="name-pills")
    if "editorial" in flags:
        return _lesson("L2", concept="editorial-mock", template="phone-mock", archetype="brand")
    if "speaker" in flags:
        return _lesson("L2", concept="event-kv", template="speaker-card", archetype="promotion")
    if "event" in flags:
        return _lesson("L2", concept="event-kv", template="full-bleed-type", archetype="promotion")
    if "quote" in flags:
        return _lesson("L3", concept="testimonial", template="quote-overlay")
    if "comparison" in flags:
        return _lesson("L2", concept="comparison", template="comparison-pair")
    if _is_lifestyle(flags, aspect, faces):
        template = "face-overlay" if aspect in {"9:16", "story-9x16"} else "overlay-card"
        return _lesson("L3", concept="lifestyle", template=template)
    if "type_on_image" in flags or "one_cta" in flags:
        template = "product-left-type" if _is_landscape(aspect) else "full-bleed-type"
        return _lesson("L2", concept="product-kv", template=template)
    template = "isolated-product"
    lesson = _lesson("L1", concept="packshot", template=template)
    if _is_landscape(aspect):
        lesson["format"] = "linkedin-landscape"
    return lesson


def _is_lifestyle(flags, aspect, faces):
    if faces < 1 or "event" in flags or "name_pills" in flags or "speaker" in flags:
        return False
    if "overlay" in flags or "quote" in flags or "lifestyle" in flags:
        return True
    if "meta_chrome" in flags and "cropped" not in flags:
        return True
    if aspect in PORTRAIT and "type_on_image" not in flags:
        return True
    return False


def _is_screenshot(flags):
    return bool(flags & {"screenshot", "browser_chrome", "sponsored_label"})


def _is_landscape(aspect):
    return aspect in LANDSCAPE


def _lesson(level, concept=None, template=None, archetype=None):
    lesson = dict(next(item for item in CURRICULUM if item["id"] == level))
    if concept:
        lesson["concept"] = concept
    if template:
        lesson["template"] = template
    if archetype:
        lesson["archetype"] = archetype
    return lesson


def _flags(hints):
    chrome = str(hints.get("chrome") or hints.get("channel") or "").strip().lower()
    aspect = str(hints.get("aspect") or hints.get("format") or "").strip().lower()
    faces = _int(hints.get("faces"), 0)
    flags = {
        str(item).strip().lower()
        for item in (hints.get("flags") or hints.get("signals") or [])
        if str(item).strip()
    }
    if hints.get("screenshot") or "screenshot" in flags or chrome in {"browser", "print"}:
        flags.add("screenshot")
    if chrome in {"meta", "facebook", "instagram"} or "meta_chrome" in flags:
        flags.add("meta_chrome")
    if chrome in {"google", "discover", "gdn"} or "google_chrome" in flags:
        flags.add("google_chrome")
    if hints.get("type_on_image"):
        flags.add("type_on_image")
    if faces >= 4 or hints.get("name_pills"):
        flags.add("many_faces")
    if faces >= 1:
        flags.add("face")
    if hints.get("cropped"):
        flags.add("cropped")
    if hints.get("event"):
        flags.add("event")
    if hints.get("quote") or hints.get("testimonial"):
        flags.add("quote")
    if hints.get("comparison"):
        flags.add("comparison")
    if hints.get("editorial") or hints.get("phone_mock"):
        flags.add("editorial")
    if hints.get("speaker"):
        flags.add("speaker")
    if hints.get("overlay"):
        flags.add("overlay")
    if hints.get("product") or hints.get("packshot"):
        flags.add("product")
    if hints.get("lifestyle"):
        flags.add("lifestyle")
    return flags, aspect, faces


def _aspect_from_ratio(ratio):
    candidates = (
        (1.0, "1:1"),
        (0.8, "4:5"),
        (0.5625, "9:16"),
        (1.91, "1.91:1"),
        (16 / 9, "16:9"),
    )
    closest = min(candidates, key=lambda item: abs(ratio - item[0]))
    if abs(ratio - closest[0]) > 0.12:
        return ""
    return closest[1]


def _format_for(aspect, default, flags):
    mapping = {
        "1:1": "feed-1x1",
        "feed-1x1": "feed-1x1",
        "4:5": "feed-4x5",
        "feed-4x5": "feed-4x5",
        "9:16": "story-9x16",
        "story-9x16": "story-9x16",
        "reels-9x16": "story-9x16",
        "shorts-9x16": "story-9x16",
        "1.91:1": "linkedin-landscape",
        "16:9": "linkedin-landscape",
        "linkedin-landscape": "linkedin-landscape",
        "1200:627": "linkedin-landscape",
        "300x250": "iab-medium",
        "970x250": "iab-billboard",
        "728x90": "iab-leaderboard",
    }
    if aspect in mapping:
        return mapping[aspect]
    if "meta_chrome" in flags and default == "linkedin-landscape":
        return "feed-4x5"
    return default


def _next_level(level):
    order = [item["id"] for item in CURRICULUM]
    try:
        index = order.index(level)
    except ValueError:
        return ""
    if index + 1 >= len(order):
        return ""
    return order[index + 1]


def _confidence(flags, aspect, lesson, screenshot):
    score = 0.35
    if aspect:
        score += 0.2
    if lesson.get("concept") and lesson["concept"] != "network-chrome":
        score += 0.15
    if flags & {"name_pills", "quote", "event", "comparison", "editorial", "speaker"}:
        score += 0.15
    if not screenshot:
        score += 0.1
    if "type_on_image" in flags or "face" in flags or "product" in flags:
        score += 0.05
    return min(1.0, round(score, 2))


def _labs_for(lesson):
    format_key = lesson.get("format") or "feed-1x1"
    if str(format_key).startswith("iab-") or str(format_key).startswith(
        ("feed-", "story-", "reels-", "shorts-", "linkedin-")
    ):
        format_skill = "iab-banner"
    else:
        format_skill = "video-15"
    packs = ["reconstruct", "implement", "validate"]
    if lesson.get("id") == "L5":
        packs = ["reconstruct"]
    return {
        "intent": "reconstruct",
        "packs": packs,
        "format_skill": format_skill,
        "skills": ["orchestrator", *packs, format_skill],
        "after_crop": lesson.get("inner") or lesson.get("id"),
    }


def _classify_v1(hints=None):
    """Baseline: print come a aula; retrato vira lifestyle; sem conceito/template."""
    hints = hints if isinstance(hints, dict) else {}
    flags, aspect, faces = _flags(hints)
    if _is_screenshot(flags):
        level = "L5"
    elif "many_faces" in flags or faces >= 4:
        level = "L4"
    elif "meta_chrome" in flags or aspect in PORTRAIT:
        level = "L3"
    elif "type_on_image" in flags or "one_cta" in flags:
        level = "L2"
    else:
        level = "L1"
    lesson = _lesson(level)
    lesson["format"] = _format_for(aspect, lesson["format"], flags)
    lesson["inner"] = level
    lesson["concept"] = ""
    lesson["template"] = ""
    lesson["lab_process"] = dict(LAB_PROCESS.get(lesson["lab"]) or {})
    lesson["flags"] = sorted(flags)
    return lesson


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
