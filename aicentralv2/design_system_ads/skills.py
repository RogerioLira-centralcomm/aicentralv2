"""Mapa documental das skills Ads. Regras executáveis: runtime_policy.py."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .runtime_policy import (
    CONFLICTS,
    POLICY_VERSION,
    RULES,
    prompt_fragment,
    rules_for,
)

SKILL_DIR = Path(__file__).resolve().parents[2] / ".agents" / "skills" / "design-system-ads"

# consumidor: dev_agent | runtime_policy | runtime_code | docs
SKILL_FILES = (
    {
        "id": "design-system-ads",
        "file": "SKILL.md",
        "consumer": "dev_agent",
        "stage": "orientação",
        "runtime": False,
        "select": "sempre para o agente; nunca para o chat do produto",
        "fallback": "contrato em schema.py + components.py",
    },
    {
        "id": "advertising",
        "file": "advertising.md",
        "consumer": "dev_agent",
        "stage": "adaptação",
        "runtime": False,
        "select": "agente em layout/IAB; runtime usa components.py + adapt.py",
        "fallback": "COMPONENTS / DENSITY / layouts.py",
    },
    {
        "id": "backgrounds",
        "file": "backgrounds.md",
        "consumer": "dev_agent",
        "stage": "fundos",
        "runtime": False,
        "select": "agente em trilhas/chão; runtime usa GROUND_KINDS + apply_background",
        "fallback": "components.apply_background",
    },
    {
        "id": "extract-map",
        "file": "extract-map.md",
        "consumer": "dev_agent",
        "stage": "extração",
        "runtime": False,
        "select": "agente em ingest; runtime usa ingest.py",
        "fallback": "ingest.ingest_extracted",
    },
    {
        "id": "centralcomm-ads",
        "file": "centralcomm-ads.md",
        "consumer": "dev_agent",
        "stage": "preset",
        "runtime": False,
        "select": "somente no_client ou house_client; nunca outro cliente",
        "fallback": "centralcomm.centralcomm_preset",
    },
)

# Satélites que o *agente* deve abrir por tarefa. Runtime não lê o Markdown.
TASK_SATELLITES = {
    "extract": ("design-system-ads", "extract-map"),
    "brand": ("design-system-ads", "advertising", "backgrounds"),
    "adapt": ("advertising",),
    "background": ("backgrounds",),
    "refine": ("design-system-ads", "advertising"),
    "review": ("advertising",),
    "campaign": ("design-system-ads", "advertising", "backgrounds"),
    "preset": ("centralcomm-ads",),
}

def skill_path(file_id):
    meta = next((item for item in SKILL_FILES if item["id"] == file_id), None)
    if not meta:
        return None
    return SKILL_DIR / meta["file"]


def file_hash(file_id):
    path = skill_path(file_id)
    if path is None or not path.is_file():
        return {"id": file_id, "exists": False, "sha256": "", "bytes": 0}
    raw = path.read_bytes()
    return {
        "id": file_id,
        "exists": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "path": str(path.relative_to(Path(__file__).resolve().parents[2])),
    }


def consumption_matrix():
    rows = []
    for item in SKILL_FILES:
        hashed = file_hash(item["id"])
        rows.append({
            **item,
            "exists": hashed["exists"],
            "sha256": hashed["sha256"],
            "tests": _tests_for(item["id"]),
        })
    return rows


def _tests_for(file_id):
    return {
        "design-system-ads": "test_design_system_ads + skills alignment",
        "advertising": "test_adapt / P0 no stack",
        "backgrounds": "test_fundo + image requires asset",
        "extract-map": "test_ingest / provenance",
        "centralcomm-ads": "test_preset_context",
    }.get(file_id, "")


def satellites_for(task, *, preset_context=None):
    from .centralcomm import may_apply_house_preset

    task_id = str(task or "brand").strip().lower()
    chosen = list(TASK_SATELLITES.get(task_id) or TASK_SATELLITES["brand"])
    if task_id == "preset" and not may_apply_house_preset(preset_context):
        return []
    if "centralcomm-ads" in chosen and not may_apply_house_preset(preset_context):
        chosen = [item for item in chosen if item != "centralcomm-ads"]
    return chosen


def rule_ids_for(task, *, preset_context=None):
    return [item["id"] for item in rules_for(task, preset_context=preset_context)]


def skill_bundle(task="brand", *, preset_context=None):
    selected = satellites_for(task, preset_context=preset_context)
    files = [file_hash(item) for item in selected]
    missing = [item["id"] for item in files if not item["exists"]]
    return {
        "policy_version": POLICY_VERSION,
        "task": task,
        "preset_context": preset_context or "",
        "selected": selected,
        "files": files,
        "missing": missing,
        "rules": rule_ids_for(task),
        "conflicts": [item["id"] for item in CONFLICTS],
        "runtime_loads_markdown": False,
    }
