"""Catálogo das skills internas do gerador Smart Planner."""

from __future__ import annotations

from pathlib import Path

from ..helpers import text

SKILLS_DIR = Path(__file__).resolve().parent

SKILLS = {
    "planner_truth_v1": {
        "label": "Verdade da campanha",
        "role": "extract",
        "file": "planner_truth_v1.md",
    },
    "planner_strategy_core_v1": {
        "label": "Núcleo estratégico",
        "role": "final",
        "file": "planner_strategy_core_v1.md",
    },
    "planner_estimation_v1": {
        "label": "Estimativas",
        "role": "sheet",
        "file": "planner_estimation_v1.md",
    },
    "planner_one_page_v2": {
        "label": "Página única",
        "role": "sheet",
        "file": "planner_one_page_v2.md",
    },
    "planner_commercial_defense_v1": {
        "label": "Defesa comercial",
        "role": "sheet",
        "file": "planner_commercial_defense_v1.md",
    },
    "planner_full_strategy_v2": {
        "label": "Plano · estratégia",
        "role": "final",
        "file": "planner_full_strategy_v2.md",
    },
    "planner_full_media_v2": {
        "label": "Plano · mídia",
        "role": "final",
        "file": "planner_full_media_v2.md",
    },
    "planner_full_execution_v1": {
        "label": "Plano · execução",
        "role": "final",
        "file": "planner_full_execution_v1.md",
    },
    "planner_consistency_v1": {
        "label": "Consistência",
        "role": "compose",
        "file": "planner_consistency_v1.md",
    },
    "planner_canvas_v2": {
        "label": "Quadro",
        "role": "compose",
        "file": "planner_canvas_v2.md",
    },
    "planner_image_v2": {
        "label": "Imagens",
        "role": "sheet",
        "file": "planner_image_v2.md",
    },
}

ONE_PAGE_STEPS = (
    {"id": "snapshot", "skill": "planner_truth_v1", "title": "Congelando a verdade da campanha", "kind": "python"},
    {"id": "evidence", "skill": "planner_truth_v1", "title": "Empacotando evidências e fontes", "kind": "python"},
    {"id": "core", "skill": "planner_strategy_core_v1", "title": "Escrevendo o núcleo estratégico", "kind": "llm"},
    {"id": "estimates", "skill": "planner_estimation_v1", "title": "Calculando indicadores", "kind": "python"},
    {"id": "one_page", "skill": "planner_one_page_v2", "title": "Redigindo a página única e a defesa", "kind": "llm"},
    {"id": "validate", "skill": "planner_consistency_v1", "title": "Conferindo tese, anunciante e canais", "kind": "python"},
    {"id": "images", "skill": "planner_image_v2", "title": "Gerando expressão visual", "kind": "image"},
    {"id": "publish", "skill": "planner_truth_v1", "title": "Publicando a folha", "kind": "python"},
)

COMPLETO_STEPS = ONE_PAGE_STEPS[:-1] + (
    {"id": "full_strategy", "skill": "planner_full_strategy_v2", "title": "Aprofundando estratégia e audiência", "kind": "llm"},
    {"id": "full_media", "skill": "planner_full_media_v2", "title": "Detalhando mix, canais e voo", "kind": "llm"},
    {"id": "full_execution", "skill": "planner_full_execution_v1", "title": "Escrevendo execução e mensuração", "kind": "llm"},
    {"id": "full_defense", "skill": "planner_commercial_defense_v1", "title": "Aprofundando a defesa comercial", "kind": "llm"},
    {"id": "compose", "skill": "planner_canvas_v2", "title": "Montando o quadro", "kind": "llm"},
    {"id": "publish", "skill": "planner_truth_v1", "title": "Publicando o plano", "kind": "python"},
)


KIND_LABELS = {
    "python": "motor",
    "llm": "skill",
    "image": "imagem",
}


def generation_steps(mode: str) -> list[dict]:
    chosen = (mode or "").strip().lower()
    return [dict(item) for item in (COMPLETO_STEPS if chosen == "completo" else ONE_PAGE_STEPS)]


def decorate_step(item: dict, state: str = "pending") -> dict:
    skill = text((item or {}).get("skill"))
    kind = text((item or {}).get("kind"))
    return {
        **dict(item or {}),
        "label": skill_label(skill),
        "kind_label": KIND_LABELS.get(kind, kind),
        "state": state,
    }


def load_skill(name: str) -> str:
    spec = SKILLS.get(name) or {}
    filename = text(spec.get("file"))
    if not filename:
        return ""
    path = SKILLS_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def skill_role(name: str) -> str:
    return text((SKILLS.get(name) or {}).get("role")) or "sheet"


def skill_label(name: str) -> str:
    return text((SKILLS.get(name) or {}).get("label")) or name
