"""Caminho A/C do desdobrador: cenas, modelos e custo previsto."""

from __future__ import annotations

from .creative_format_geometry import FORMAT_IAB_FAMILY, resolve_scene_count
from .creative_image_fidelity import DRAFT, PUBLISH, resolve_image_tier
from .creative_modeling_fx import annotate_cost, brl_from_usd


ENGINE_PAINT = "paint"
ENGINE_CONSTRUCT = "construct"

KV_ITEM_IDS = (
    "logo",
    "product_lockup",
    "talent",
    "headline",
    "offer",
    "benefits",
    "cta",
    "legal",
    "background",
)

KV_ITEM_LABELS = {
    "logo": "Logo",
    "product_lockup": "Lockup do produto",
    "talent": "Talent / cena",
    "headline": "Headline",
    "offer": "Oferta",
    "benefits": "Benefícios",
    "cta": "CTA",
    "legal": "Legal",
    "background": "Fundo",
}

SCENE_KEYS = {
    "square": {
        "label": "Feed 1:1",
        "slugs": ("instagram-feed", "facebook-feed"),
        "output": "1080×1080",
    },
    "story": {
        "label": "Story 9:16",
        "slugs": ("instagram-story", "tiktok-vertical"),
        "output": "1080×1920",
    },
    "landscape": {
        "label": "Paisagem social",
        "slugs": ("linkedin-share",),
        "output": "1200×627",
    },
    "half_page": {
        "label": "Half Page",
        "slugs": ("iab-half-page",),
        "output": "300×600",
    },
    "rectangle": {
        "label": "Medium Rectangle",
        "slugs": ("iab-medium-rectangle",),
        "output": "300×250",
    },
    "wide": {
        "label": "Leaderboard",
        "slugs": ("iab-leaderboard",),
        "output": "728×90",
    },
    "mobile": {
        "label": "Mobile Banner",
        "slugs": ("iab-mobile-banner",),
        "output": "320×50",
    },
}

SCENE_PACKS = {
    4: ("square", "story", "landscape", "half_page"),
    6: ("square", "story", "landscape", "half_page", "rectangle", "wide"),
    8: (
        "square", "story", "landscape", "half_page",
        "rectangle", "wide", "mobile", "square_ab",
    ),
}

SLUG_SCENE = {
    slug: key
    for key, spec in SCENE_KEYS.items()
    for slug in spec["slugs"]
}

IMAGE_MODELS = {
    "openai/gpt-image-2": {
        "id": "openai/gpt-image-2",
        "label": "GPT Image 2",
        "unit_usd": {DRAFT: 0.006, PUBLISH: 0.22},
        "note": "Já no gerador. Sem PNG transparente.",
    },
    "black-forest-labs/flux.2-pro": {
        "id": "black-forest-labs/flux.2-pro",
        "label": "FLUX.2 Pro",
        "unit_usd": {DRAFT: 0.08, PUBLISH: 0.11},
        "note": "Padrão do C: recorte do talent.",
    },
    "google/gemini-2.5-flash-image": {
        "id": "google/gemini-2.5-flash-image",
        "label": "Gemini Flash Image",
        "unit_usd": {DRAFT: 0.06, PUBLISH: 0.12},
        "note": "Alpha / recorte com fundo transparente.",
    },
}


def resolve_engine(value, default=ENGINE_PAINT):
    key = str(value or default).strip().lower()
    aliases = {
        "a": ENGINE_PAINT,
        "paint": ENGINE_PAINT,
        "atual": ENGINE_PAINT,
        "c": ENGINE_CONSTRUCT,
        "construct": ENGINE_CONSTRUCT,
        "construcao": ENGINE_CONSTRUCT,
        "construção": ENGINE_CONSTRUCT,
    }
    key = aliases.get(key, key)
    return key if key in {ENGINE_PAINT, ENGINE_CONSTRUCT} else default


def resolve_scene_pack(value, default=6):
    try:
        pack = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        pack = default
    return pack if pack in SCENE_PACKS else default


def resolve_image_model(value, engine=ENGINE_PAINT):
    key = str(value or "").strip()
    if key in IMAGE_MODELS:
        return key
    if resolve_engine(engine) == ENGINE_CONSTRUCT:
        return "black-forest-labs/flux.2-pro"
    return "openai/gpt-image-2"


def resolve_path_fidelity(engine, value=None):
    if resolve_engine(engine) == ENGINE_CONSTRUCT:
        return resolve_image_tier(value or PUBLISH)["name"]
    return resolve_image_tier(value or DRAFT)["name"]


def resolve_construct_path(payload=None):
    data = payload if isinstance(payload, dict) else {}
    nested = data.get("construct_path")
    if isinstance(nested, dict):
        data = {**nested, **{
            key: data[key] for key in (
                "engine", "scene_pack", "image_model", "fidelity",
            ) if data.get(key) not in (None, "")
        }}
    engine = resolve_engine(data.get("engine"))
    fidelity = resolve_path_fidelity(engine, data.get("fidelity"))
    model = resolve_image_model(data.get("image_model"), engine)
    pack = resolve_scene_pack(data.get("scene_pack"))
    return {
        "engine": engine,
        "engine_label": (
            "C · construção em camadas" if engine == ENGINE_CONSTRUCT
            else "A · pintura atual"
        ),
        "scene_pack": pack,
        "image_model": model,
        "image_model_label": IMAGE_MODELS[model]["label"],
        "fidelity": fidelity,
        "compose": engine == ENGINE_CONSTRUCT,
    }


def scene_key_for_slug(slug, pack=6):
    pack = resolve_scene_pack(pack)
    key = SLUG_SCENE.get(str(slug or "").strip())
    if key == "mobile" and pack < 8:
        return "wide"
    if key and key in SCENE_PACKS[pack]:
        return key
    if key == "rectangle" and pack < 6:
        return "half_page"
    if key == "wide" and pack < 6:
        return "landscape"
    return key


def unique_scenes_for_slugs(slugs, pack=6):
    seen = []
    for slug in slugs or []:
        key = scene_key_for_slug(slug, pack)
        if key and key not in seen:
            seen.append(key)
    return seen


def model_unit_usd(model, fidelity):
    spec = IMAGE_MODELS.get(model) or IMAGE_MODELS["openai/gpt-image-2"]
    tier = resolve_image_tier(fidelity)
    return float(spec["unit_usd"][tier["name"]])


def quote_unfold_path(payload=None, slugs=None):
    data = payload if isinstance(payload, dict) else {}
    path = resolve_construct_path(data)
    slugs = [str(item or "").strip() for item in (slugs or []) if str(item or "").strip()]
    unit = model_unit_usd(path["image_model"], path["fidelity"])
    batch = resolve_scene_count(data.get("scene_count"), default=None)
    if batch:
        calls = batch
        pieces = batch
        shared = 0
        scenes = [
            {"key": f"beat_{index}", "label": f"Cena {index}", "output": ""}
            for index in range(1, batch + 1)
        ]
    else:
        scenes = unique_scenes_for_slugs(slugs, path["scene_pack"])
        pieces = len(slugs)
        if path["engine"] == ENGINE_CONSTRUCT:
            calls = 0
            shared = pieces
        else:
            calls = pieces
            shared = 0
        scenes = [
            {
                "key": key,
                "label": SCENE_KEYS.get(key, {}).get("label") or key,
                "output": SCENE_KEYS.get(key, {}).get("output") or "",
            }
            for key in scenes
        ]
    total = round(unit * calls, 6)
    quoted = annotate_cost({
        **path,
        "pieces": pieces,
        "photo_calls": calls,
        "shared_pieces": shared,
        "scenes": scenes,
        "unit_usd": unit,
        "unit_brl": brl_from_usd(unit),
        "total_usd": total,
        "total_brl": brl_from_usd(total),
        "compose_usd": 0,
    }, total)
    return quoted


def describe_unfold_paths():
    models = []
    for spec in IMAGE_MODELS.values():
        models.append({
            "id": spec["id"],
            "label": spec["label"],
            "note": spec["note"],
            "unit_brl_draft": brl_from_usd(spec["unit_usd"][DRAFT]),
            "unit_brl_publish": brl_from_usd(spec["unit_usd"][PUBLISH]),
        })
    return {
        "engines": [
            {
                "id": ENGINE_PAINT,
                "label": "A · pintura atual",
                "summary": "GPT pinta social inteiro. IAB usa still + overlay.",
            },
            {
                "id": ENGINE_CONSTRUCT,
                "label": "C · construção",
                "summary": "Recorte do KV. Copy e logo entram no compositor.",
            },
        ],
        "scene_packs": [
            {
                "id": pack,
                "label": f"{pack} cenas",
                "scenes": [
                    SCENE_KEYS[key]["label"]
                    for key in keys if key in SCENE_KEYS
                ],
            }
            for pack, keys in SCENE_PACKS.items()
        ],
        "models": models,
        "kv_items": [
            {"id": item_id, "label": KV_ITEM_LABELS[item_id]}
            for item_id in KV_ITEM_IDS
        ],
        "format_scenes": {
            slug: SLUG_SCENE.get(slug)
            for slug in FORMAT_IAB_FAMILY
            if slug in SLUG_SCENE
        },
    }


def _item_status(value, text, default="absent"):
    raw = str(value or "").strip().lower()
    if raw in {"seen", "uncertain", "absent"}:
        return raw
    if text:
        return "uncertain"
    return default


def normalize_kv_items(value):
    data = dict(value) if isinstance(value, dict) else {}
    raw_items = data.get("items") if isinstance(data.get("items"), dict) else {}
    for key in ("headline", "subhead", "cta", "has_logo", "other_lines", "benefits"):
        if data.get(key) not in (None, "", [], False) :
            continue
        lifted = raw_items.get(key)
        if lifted not in (None, "") and not isinstance(lifted, dict):
            data[key] = lifted
    benefits = data.get("benefits") or raw_items.get("benefits") or []
    if isinstance(benefits, str):
        benefits = [line.strip() for line in benefits.splitlines() if line.strip()]
    if not isinstance(benefits, list):
        benefits = []
    items = {}
    for item_id in KV_ITEM_IDS:
        source = raw_items.get(item_id)
        if not isinstance(source, dict):
            source = {}
        if item_id == "headline":
            text = str(source.get("text") or data.get("headline") or "").strip()
        elif item_id == "cta":
            text = str(source.get("text") or data.get("cta") or "").strip()
        elif item_id == "offer":
            text = str(source.get("text") or data.get("subhead") or "").strip()
        elif item_id == "product_lockup":
            text = str(source.get("text") or "").strip()
        elif item_id == "legal":
            text = str(source.get("text") or "").strip()
        elif item_id == "background":
            text = str(source.get("text") or "").strip()
        elif item_id == "talent":
            text = str(source.get("text") or "").strip()
        elif item_id == "logo":
            text = str(source.get("text") or "").strip()
            if not text and data.get("has_logo") is True:
                text = "logo"
        elif item_id == "benefits":
            lines = source.get("lines") or benefits
            if not isinstance(lines, list):
                lines = []
            text = "\n".join(str(line).strip() for line in lines if str(line).strip())
        else:
            text = str(source.get("text") or "").strip()
        status = _item_status(source.get("status"), text)
        if item_id == "cta" and not text:
            status = "absent"
        items[item_id] = {
            "id": item_id,
            "label": KV_ITEM_LABELS[item_id],
            "text": text,
            "status": status,
        }
        if item_id == "benefits":
            items[item_id]["lines"] = [
                line for line in text.splitlines() if line
            ]
    return items


def locks_from_kv_items(items, locks=None):
    items = normalize_kv_items({"items": items} if items else locks)
    locks = locks if isinstance(locks, dict) else {}
    other = [
        line
        for line in (items["benefits"].get("lines") or [])
        if line
    ]
    if items["offer"]["text"]:
        other = [items["offer"]["text"], *[
            line for line in other if line != items["offer"]["text"]
        ]]
    if items["product_lockup"]["text"]:
        other.append(items["product_lockup"]["text"])
    if items["legal"]["text"]:
        other.append(items["legal"]["text"])
    seen = []
    for line in other:
        if line and line not in seen:
            seen.append(line)
    return {
        "headline": items["headline"]["text"] or str(locks.get("headline") or "").strip(),
        "subhead": items["offer"]["text"] or str(locks.get("subhead") or "").strip(),
        "cta": items["cta"]["text"] or str(locks.get("cta") or "").strip(),
        "other_lines": seen,
        "has_logo": items["logo"]["status"] != "absent" or locks.get("has_logo") is True,
        "items": items,
    }


def _truthy(value, default=True):
    if value in (None, ""):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def normalize_context_design(payload=None, scene_count=4):
    data = payload if isinstance(payload, dict) else {}
    count = resolve_scene_count(scene_count, default=4) or 4
    try:
        cast_count = int(data.get("cast_count") or 1)
    except (TypeError, ValueError):
        cast_count = 1
    if cast_count not in {1, 2}:
        cast_count = 1
    scenography = str(data.get("scenography") or "line").strip().lower()
    if scenography not in {"line", "change"}:
        scenography = "line"
    raw_scenes = data.get("scenes") if isinstance(data.get("scenes"), list) else []
    by_pos = {}
    for item in raw_scenes:
        if not isinstance(item, dict):
            continue
        try:
            position = int(item.get("position") or 0)
        except (TypeError, ValueError):
            continue
        if 1 <= position <= count:
            by_pos[position] = item
    scenes = []
    for position in range(1, count + 1):
        raw = by_pos.get(position) or {}
        default_copy = position >= count
        scenes.append({
            "position": position,
            "job": str(raw.get("job") or "").strip()[:400],
            "set_note": str(raw.get("set_note") or "").strip()[:1000],
            "action_note": str(raw.get("action_note") or "").strip()[:1000],
            "copy_on_frame": _truthy(raw.get("copy_on_frame"), default_copy),
        })
    return {
        "cast_count": cast_count,
        "cast_lock": _truthy(data.get("cast_lock"), True),
        "product_lock": _truthy(data.get("product_lock"), True),
        "scenography": scenography,
        "scenes": scenes,
    }


def scene_copy_on_frame(design, position, scene_count=None):
    design = design if isinstance(design, dict) else {}
    scenes = design.get("scenes") or []
    wanted = int(position or 0)
    for item in scenes:
        if int(item.get("position") or 0) == wanted:
            return bool(item.get("copy_on_frame"))
    total = int(scene_count or len(scenes) or 1)
    return wanted >= total and wanted > 0
