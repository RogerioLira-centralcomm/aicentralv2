"""Carrega só as skills do intent. Nunca o catálogo inteiro."""

from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent
ENGINEER_SKILL = "creative-format-engineer.md"
FORMAT_SKILL_KEYS = (
    "video-linear-15",
    "video-qr-15",
    "ctv-video-linear-30",
    "ctv-video-qr",
    "iab-banner",
    "iab-billboard",
    "iab-leaderboard",
    "iab-medium",
    "iab-halfpage",
    "iab-skyscraper",
    "iab-mobile",
    "feed-1x1",
    "feed-4x5",
    "story-9x16",
    "reels-9x16",
    "shorts-9x16",
    "linkedin-landscape",
    "youtube-infeed",
)

PACK_BY_INTENT = {
    "reconstruct": ("reconstruct", "implement", "validate"),
    "create": ("create", "implement", "validate"),
    "adapt": ("create", "refine", "implement", "validate"),
    "refine": ("refine", "validate"),
    "html": ("implement", "validate"),
    "vary": ("create", "implement", "validate"),
}

FORMAT_SKILL_PATHS = {
    "video-linear-15": "formats/video-15/SKILL.md",
    "video-cta-15": "formats/video-15/SKILL.md",
    "video-15": "formats/video-15/SKILL.md",
    "ctv-video-linear-30": "formats/video-15/SKILL.md",
    "ctv-video-cta": "formats/video-15/SKILL.md",
    "ctv-video": "formats/ctv-video/SKILL.md",
    "video-qr-15": "formats/ctv-qr/SKILL.md",
    "ctv-video-qr": "formats/ctv-qr/SKILL.md",
    "ctv-qr": "formats/ctv-qr/SKILL.md",
    "iab-billboard": "formats/iab-banner/SKILL.md",
    "iab-leaderboard": "formats/iab-banner/SKILL.md",
    "iab-medium": "formats/iab-banner/SKILL.md",
    "iab-halfpage": "formats/iab-banner/SKILL.md",
    "iab-skyscraper": "formats/iab-banner/SKILL.md",
    "iab-mobile": "formats/iab-banner/SKILL.md",
    "iab-banner": "formats/iab-banner/SKILL.md",
    "feed-1x1": "formats/iab-banner/SKILL.md",
    "feed-4x5": "formats/iab-banner/SKILL.md",
    "story-9x16": "formats/iab-banner/SKILL.md",
    "reels-9x16": "formats/iab-banner/SKILL.md",
    "shorts-9x16": "formats/iab-banner/SKILL.md",
    "linkedin-landscape": "formats/iab-banner/SKILL.md",
    "youtube-infeed": "formats/video-15/SKILL.md",
}

_LEGACY_FORMAT_FILES = {
    "ctv-video-linear-30": "formats/ctv-video-linear-30.md",
    "ctv-video-cta": "formats/ctv-video-linear-30.md",
    "ctv-video-qr": "formats/ctv-video-qr.md",
}

INTENT_LABELS = {
    "reconstruct": "Recriar",
    "create": "Criar",
    "adapt": "Adaptar",
    "refine": "Refinar",
    "html": "HTML",
    "vary": "Variar",
}


def skill_dir():
    return SKILL_ROOT


def load_skill(name=ENGINEER_SKILL):
    path = SKILL_ROOT / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    orchestrator = SKILL_ROOT / "orchestrator" / "SKILL.md"
    if name in {ENGINEER_SKILL, "orchestrator"} and orchestrator.is_file():
        return orchestrator.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Skill não encontrada: {name}")


def load_pack_skill(pack):
    path = SKILL_ROOT / "packs" / str(pack) / "SKILL.md"
    if not path.is_file():
        raise FileNotFoundError(f"Pack não encontrado: {pack}")
    return path.read_text(encoding="utf-8")


def load_format_skill(format_key):
    key = str(format_key or "").strip()
    relative = FORMAT_SKILL_PATHS.get(key) or _LEGACY_FORMAT_FILES.get(key)
    if not relative:
        raise ValueError(f"Formato sem skill: {key}")
    path = SKILL_ROOT / relative
    if not path.is_file():
        legacy = _LEGACY_FORMAT_FILES.get(key)
        path = SKILL_ROOT / legacy if legacy else path
    if not path.is_file():
        raise FileNotFoundError(f"Skill de formato não encontrada: {key}")
    return path.read_text(encoding="utf-8")


def resolve_pack(intent, format_key, has_reference=False):
    key = str(intent or "create").strip().lower()
    if key not in PACK_BY_INTENT:
        key = "create"
    if key == "reconstruct" and not has_reference:
        key = "create"
    packs = list(PACK_BY_INTENT[key])
    if str(format_key or "").endswith("qr") or str(format_key or "").endswith("qr-15"):
        format_id = "ctv-qr"
    elif str(format_key or "").startswith(("iab-", "feed-", "story-", "reels-", "shorts-", "linkedin-")):
        format_id = "iab-banner"
    else:
        format_id = "video-15"
    skills = [
        {"id": "orchestrator", "kind": "orchestrator", "label": "Orquestrador", "path": "orchestrator/SKILL.md"},
    ]
    for pack in packs:
        skills.append({
            "id": pack,
            "kind": "pack",
            "label": pack.title(),
            "path": f"packs/{pack}/SKILL.md",
        })
    skills.append({
        "id": format_id,
        "kind": "format",
        "label": format_id,
        "path": FORMAT_SKILL_PATHS.get(format_key) or FORMAT_SKILL_PATHS[format_id],
        "format_key": format_key,
    })
    return {
        "intent": key,
        "intent_label": INTENT_LABELS.get(key, key),
        "packs": packs,
        "format_skill": format_id,
        "skills": skills,
    }


def load_bundle(intent, format_key, has_reference=False):
    plan = resolve_pack(intent, format_key, has_reference=has_reference)
    texts = {
        "orchestrator": load_skill("orchestrator/SKILL.md") if (SKILL_ROOT / "orchestrator" / "SKILL.md").is_file() else load_skill(),
        "format": load_format_skill(format_key),
    }
    for pack in plan["packs"]:
        texts[pack] = load_pack_skill(pack)
    plan["texts"] = texts
    return plan


def combined_system_prompt(bundle, packs):
    parts = [bundle["texts"].get("orchestrator") or ""]
    for pack in packs:
        text = bundle["texts"].get(pack)
        if text:
            parts.append(text)
    parts.append(bundle["texts"]["format"])
    return "\n\n".join(part for part in parts if part)
