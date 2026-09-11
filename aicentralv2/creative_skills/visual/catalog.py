"""Catálogo de skills que a Mesa pode ligar ou desligar na campanha."""

from __future__ import annotations

from pathlib import Path

ADAPTER_ROOT = Path(__file__).resolve().parent

VISUAL_SKILLS = (
    {
        "id": "imagegen-frontend-web",
        "label": "Taste 16:9",
        "stage": "html",
        "default": True,
        "note": "Uma placa por cena. Sem mosaico. Sem hero esquerda/direita por default.",
        "source": "Leonxlnx/taste-skill",
        "adapter": "imagegen-frontend-web.md",
    },
    {
        "id": "frontend-design",
        "label": "Frontend design",
        "stage": "html",
        "default": False,
        "note": "Tokens da marca. Dois passes. Sem paleta genérica de IA.",
        "source": "project frontend-design",
        "adapter": "frontend-design.md",
    },
    {
        "id": "ai-image-generation",
        "label": "Gerar still",
        "stage": "raster",
        "default": False,
        "note": "Recorte de produto em PNG. Texto fica no HTML, não na foto.",
        "source": "genmedia-labs/skills",
        "adapter": "ai-image-generation.md",
    },
    {
        "id": "image-edit",
        "label": "Editar still",
        "stage": "edit",
        "default": False,
        "note": "Preserva o quadro. Muda só o que o brief pediu.",
        "source": "prime-skills/runcomfy-agent-skills",
        "adapter": "image-edit.md",
    },
)

_KNOWN = {item["id"]: item for item in VISUAL_SKILLS}


def list_visual_skills():
    return [dict(item) for item in VISUAL_SKILLS]


def default_skill_ids():
    return [item["id"] for item in VISUAL_SKILLS if item.get("default")]


def normalize_selected_skills(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    raw = payload.get("selected_skills")
    if raw is None:
        raw = payload.get("skills")
    if raw is None:
        return default_skill_ids()
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    chosen = []
    for item in raw or []:
        key = str(item or "").strip()
        if key in _KNOWN and key not in chosen:
            chosen.append(key)
    return chosen


def load_visual_brief(skill_ids=None, stage=None):
    parts = []
    for key in skill_ids or []:
        meta = _KNOWN.get(key)
        if not meta:
            continue
        if stage and meta.get("stage") != stage:
            continue
        path = ADAPTER_ROOT / meta["adapter"]
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)
