"""Métodos de balanceamento de mídia para o executivo parametrizar o mix."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .catalog import (
    CHANNEL_CATALOG,
    CHANNEL_GROUPS,
    CHANNEL_LOGOS,
    GROUP_KPIS,
    INTERATIVOS_FORMATS,
    PORTAL_CHANNELS,
    SPECIAL_MIX_IDS,
    SPECIAL_SUGGESTED_PCT,
    media_channel_keys,
)
from .helpers import as_bool, as_dict, as_list, text
from .pace import as_int, format_money


METHODS = (
    {
        "id": "funil",
        "label": "Funil do objetivo",
        "summary": "Pesa os grupos pelo estágio da campanha.",
        "when": "Use quando o objetivo está claro e o mix deve seguir o funil.",
    },
    {
        "id": "alcance",
        "label": "Alcance único",
        "summary": "Espalha a verba entre tipos de tela diferentes.",
        "when": "Use para não concentrar o investimento no mesmo tipo de mídia.",
    },
    {
        "id": "frequencia",
        "label": "Frequência efetiva",
        "summary": "Reserva a maior parte nos dois grupos mais fortes.",
        "when": "Use quando o público precisa ver a marca com repetição.",
    },
    {
        "id": "eficiencia",
        "label": "Custo por resultado",
        "summary": "Privilegia performance, dados e programática.",
        "when": "Use quando o voo precisa de clique, lead ou venda.",
    },
    {
        "id": "presenca",
        "label": "Presença de marca",
        "summary": "Privilegia CTV, portais, OOH e vídeo.",
        "when": "Use para construir lembrança e cobertura de marca.",
    },
    {
        "id": "manual",
        "label": "Manual do executivo",
        "summary": "Você define o percentual de cada canal.",
        "when": "Use quando a mesa já tem uma tese e só precisa fechar 100%.",
    },
)

METHOD_IDS = {item["id"] for item in METHODS}

RECOMMEND = {
    "reconhecimento": ("funil", "presenca"),
    "consideracao": ("alcance", "funil"),
    "conversao": ("funil", "eficiencia"),
    "trafego": ("alcance", "eficiencia"),
    "leads": ("funil", "eficiencia"),
    "vendas": ("funil", "eficiencia"),
    "retencao": ("frequencia", "presenca"),
}

FUNIL_TABLE = {
    "reconhecimento": {
        "ctv": 26, "video": 16, "portais": 14, "ooh": 14, "social": 12,
        "programmatic": 8, "audio": 6, "performance": 4, "data": 0,
    },
    "consideracao": {
        "social": 22, "video": 16, "portais": 14, "programmatic": 14,
        "ctv": 10, "performance": 10, "ooh": 6, "audio": 4, "data": 4,
    },
    "conversao": {
        "performance": 32, "data": 16, "social": 16, "programmatic": 14,
        "portais": 8, "video": 6, "ctv": 4, "audio": 2, "ooh": 2,
    },
    "trafego": {
        "performance": 24, "social": 22, "programmatic": 16, "portais": 12,
        "video": 10, "data": 6, "ctv": 4, "audio": 4, "ooh": 2,
    },
    "leads": {
        "performance": 30, "data": 18, "social": 16, "programmatic": 14,
        "portais": 8, "video": 6, "ctv": 4, "audio": 2, "ooh": 2,
    },
    "vendas": {
        "performance": 34, "social": 16, "data": 14, "programmatic": 12,
        "portais": 8, "video": 6, "ctv": 4, "audio": 4, "ooh": 2,
    },
    "retencao": {
        "social": 24, "ctv": 16, "video": 14, "portais": 12, "audio": 10,
        "programmatic": 8, "performance": 8, "data": 4, "ooh": 4,
    },
}

EFICIENCIA_TABLE = {
    "default": {
        "performance": 36, "data": 18, "programmatic": 16, "social": 14,
        "portais": 6, "video": 4, "ctv": 2, "audio": 2, "ooh": 2,
    },
    "reconhecimento": {
        "performance": 18, "social": 16, "programmatic": 16, "portais": 12,
        "video": 12, "ctv": 10, "data": 8, "audio": 4, "ooh": 4,
    },
}

PRESENCA_TABLE = {
    "default": {
        "ctv": 22, "portais": 18, "ooh": 16, "video": 16, "audio": 10,
        "social": 8, "programmatic": 6, "performance": 2, "data": 2,
    },
    "conversao": {
        "ctv": 16, "portais": 14, "video": 14, "ooh": 12, "social": 12,
        "performance": 12, "programmatic": 10, "audio": 6, "data": 4,
    },
    "vendas": {
        "ctv": 16, "portais": 14, "video": 14, "ooh": 12, "social": 12,
        "performance": 12, "programmatic": 10, "audio": 6, "data": 4,
    },
}

MIX_TABLES = {
    "funil": FUNIL_TABLE,
    "eficiencia": EFICIENCIA_TABLE,
    "presenca": PRESENCA_TABLE,
}

_DEFAULT_GROUP_WEIGHT = 4


def recommend_methods(objetivo: str) -> list[str]:
    pair = RECOMMEND.get((objetivo or "").strip().lower(), ("funil", "alcance"))
    return list(pair)


def method_ids() -> set[str]:
    return set(METHOD_IDS)


def media_keys(canais: Any) -> list[str]:
    wanted = {text(key) for key in as_list(canais) if text(key)}
    return [key for key in media_channel_keys() if key in wanted]


def group_of(channel_id: str) -> str:
    return text((CHANNEL_CATALOG.get(channel_id) or {}).get("group")) or "performance"


def _table_weights(method: str, objetivo: str) -> dict[str, float]:
    table = MIX_TABLES.get(method) or {}
    return dict(table.get((objetivo or "").strip().lower()) or table.get("default") or {})


def _frequencia_weights(objetivo: str, groups: list[str]) -> dict[str, float]:
    ranking = FUNIL_TABLE.get((objetivo or "").strip().lower()) or FUNIL_TABLE["conversao"]
    ranked = sorted(groups, key=lambda group: ranking.get(group, 0), reverse=True)
    weights = {group: 0.0 for group in groups}
    if not ranked:
        return weights
    if len(ranked) == 1:
        weights[ranked[0]] = 100
        return weights
    if len(ranked) == 2:
        weights[ranked[0]] = 70
        weights[ranked[1]] = 30
        return weights
    weights[ranked[0]] = 40
    weights[ranked[1]] = 30
    rest = ranked[2:]
    share = 30 / len(rest)
    for group in rest:
        weights[group] = share
    return weights


def group_weights(method: str, objetivo: str, groups: list[str] | None = None) -> dict[str, float]:
    method = text(method).lower()
    selected = list(groups or CHANNEL_GROUPS.keys())
    if method == "alcance":
        return {group: 1.0 for group in selected}
    if method == "frequencia":
        return _frequencia_weights(objetivo, selected)
    table = _table_weights(method if method in MIX_TABLES else "funil", objetivo)
    return {group: float(table.get(group, _DEFAULT_GROUP_WEIGHT)) for group in selected}


def normalize_pcts(pairs: list[tuple[str, float]]) -> dict[str, int]:
    if not pairs:
        return {}
    total = sum(max(float(weight), 0.0) for _, weight in pairs)
    if total <= 0:
        pairs = [(key, 1.0) for key, _ in pairs]
        total = float(len(pairs))
    exact = [(key, 100.0 * max(float(weight), 0.0) / total) for key, weight in pairs]
    floors = [(key, int(value)) for key, value in exact]
    remainder = 100 - sum(value for _, value in floors)
    order = sorted(exact, key=lambda item: (item[1] - int(item[1])), reverse=True)
    bump = {key for key, _ in order[: max(remainder, 0)]}
    return {key: value + (1 if key in bump else 0) for key, value in floors}


def _weight_map(weights: Any) -> dict[str, float]:
    mapped = {}
    for item in as_list(weights):
        row = as_dict(item)
        key = text(row.get("id") or row.get("key"))
        if not key:
            continue
        try:
            mapped[key] = float(row.get("pct") if row.get("pct") is not None else row.get("valor") or 0)
        except (TypeError, ValueError):
            mapped[key] = 0.0
    return mapped


def _rows_from_pcts(keys: list[str], pcts: dict[str, int]) -> list[dict]:
    return [
        {
            "id": key,
            "label": (CHANNEL_CATALOG.get(key) or {}).get("label", key),
            "group": group_of(key),
            "pct": pcts.get(key, 0),
        }
        for key in keys
    ]


def _allocate_core(keys: list[str], objetivo: str, method: str, weights: Any) -> list[dict]:
    if not keys:
        return []
    if method == "manual":
        previous = _weight_map(weights)
        raw = [(key, previous[key] if key in previous else 0.0) for key in keys]
    else:
        groups = [group_of(key) for key in keys]
        gw = group_weights(method, objetivo, list(dict.fromkeys(groups)))
        counts = Counter(groups)
        raw = [(key, gw.get(group_of(key), _DEFAULT_GROUP_WEIGHT) / max(counts[group_of(key)], 1)) for key in keys]
    return _rows_from_pcts(keys, normalize_pcts(raw))


def allocate(canais: Any, objetivo: str = "", method: str = "funil", weights: Any = None) -> list[dict]:
    keys = media_keys(canais)
    if not keys:
        return []
    method = text(method).lower()
    if method not in METHOD_IDS:
        method = recommend_methods(objetivo)[0]
    digital = [key for key in keys if key not in SPECIAL_MIX_IDS]
    special = [key for key in keys if key in SPECIAL_MIX_IDS]
    if method == "manual" or not special:
        return _allocate_core(keys, objetivo, method, weights)
    digital_rows = _allocate_core(digital, objetivo, method, weights)
    previous = _weight_map(weights)
    special_raw = [
        (key, previous[key] if key in previous else float(SPECIAL_SUGGESTED_PCT))
        for key in special
    ]
    if not digital_rows:
        return _rows_from_pcts(special, normalize_pcts(special_raw))
    special_share = min(sum(max(pct, 0.0) for _, pct in special_raw), 40.0)
    if special_share <= 0:
        special_share = float(SPECIAL_SUGGESTED_PCT * len(special))
    remaining = max(100.0 - special_share, 0.0)
    digital_pairs = [(row["id"], float(row["pct"]) * remaining / 100.0) for row in digital_rows]
    spec_total = sum(max(pct, 0.0) for _, pct in special_raw) or 1.0
    special_pairs = [(key, special_share * max(pct, 0.0) / spec_total) for key, pct in special_raw]
    return _rows_from_pcts(keys, normalize_pcts(digital_pairs + special_pairs))


def normalize_mix(raw: Any, canais: Any, objetivo: str = "") -> dict:
    data = as_dict(raw)
    method = text(data.get("method")).lower()
    if method not in METHOD_IDS:
        method = recommend_methods(objetivo)[0]
    use_method = "manual" if data.get("locked") and method != "manual" else method
    weights = allocate(canais, objetivo, use_method, data.get("weights"))
    return {
        "method": method,
        "weights": weights,
        "locked": bool(data.get("locked")) or method == "manual",
    }


def shares_to_money(weights: Any, total: int | float) -> dict[str, int]:
    items = [as_dict(item) for item in as_list(weights)]
    pairs = []
    for item in items:
        key = text(item.get("id"))
        if not key:
            continue
        try:
            pct = float(item.get("pct") or 0)
        except (TypeError, ValueError):
            pct = 0.0
        pairs.append((key, max(pct, 0.0)))
    if not pairs:
        return {}
    try:
        amount = int(total or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return {key: 0 for key, _ in pairs}
    exact = [(key, amount * pct / 100.0) for key, pct in pairs]
    floors = [(key, int(value)) for key, value in exact]
    remainder = amount - sum(value for _, value in floors)
    order = sorted(exact, key=lambda item: (item[1] - int(item[1])), reverse=True)
    bump = {key for key, _ in order[: max(remainder, 0)]}
    return {key: value + (1 if key in bump else 0) for key, value in floors}


def spec_for_js() -> dict:
    return {
        "methods": [dict(item) for item in METHODS],
        "recommend": {key: list(value) for key, value in RECOMMEND.items()},
        "tables": MIX_TABLES,
        "groups": {key: meta.get("group") for key, meta in CHANNEL_CATALOG.items()},
        "labels": {key: meta.get("label", key) for key, meta in CHANNEL_CATALOG.items()},
        "media": media_channel_keys(),
        "logos": dict(CHANNEL_LOGOS),
        "kpis": {key: list(value) for key, value in GROUP_KPIS.items()},
        "specialMix": list(SPECIAL_MIX_IDS),
        "specialPct": SPECIAL_SUGGESTED_PCT,
        "portalChannels": list(PORTAL_CHANNELS),
        "interativosFormats": [dict(item) for item in INTERATIVOS_FORMATS],
        "defaultGroupWeight": _DEFAULT_GROUP_WEIGHT,
    }


def should_progress(months: Any, mix: Any = None) -> bool:
    count = as_int(months)
    if count < 2 or count > 12:
        return False
    data = as_dict(mix)
    if "progress" in data:
        return as_bool(data.get("progress"))
    return True


def _blend_pcts(early: dict[str, int], late: dict[str, int], keys: list[str], t: float) -> dict[str, int]:
    ratio = min(max(float(t), 0.0), 1.0)
    raw = [
        (key, (1.0 - ratio) * float(early.get(key, 0)) + ratio * float(late.get(key, 0)))
        for key in keys
    ]
    return normalize_pcts(raw)


def month_mix_weights(
    canais: Any,
    objetivo: str,
    method: str,
    months: int,
    index: int,
    weights: Any = None,
    progress: bool = True,
) -> list[dict]:
    keys = media_keys(canais)
    if not keys:
        return []
    method = text(method).lower()
    if method not in METHOD_IDS:
        method = recommend_methods(objetivo)[0]
    late = allocate(canais, objetivo, method, weights)
    if not progress or months <= 1 or method == "manual":
        return late
    early = allocate(canais, "reconhecimento", method if method != "alcance" else "funil")
    early_map = {item["id"]: item["pct"] for item in early}
    late_map = {item["id"]: item["pct"] for item in late}
    t = index / (months - 1) if months > 1 else 1.0
    pcts = _blend_pcts(early_map, late_map, keys, t)
    labels = {item["id"]: item["label"] for item in late}
    groups = {item["id"]: item["group"] for item in late}
    return [
        {
            "id": key,
            "label": labels.get(key, (CHANNEL_CATALOG.get(key) or {}).get("label", key)),
            "group": groups.get(key, group_of(key)),
            "pct": pcts.get(key, 0),
        }
        for key in keys
    ]


def progress_calendar(
    canais: Any,
    objetivo: str,
    method: str,
    pace: Any,
    mix: Any = None,
    progress: bool | None = None,
) -> dict:
    pace = as_dict(pace)
    keys = [text(key) for key in as_list(pace.get("chaves")) if text(key)]
    labels = [text(label) for label in as_list(pace.get("rotulos"))]
    if len(labels) < len(keys):
        labels.extend(keys[len(labels):])
    alocacao = {text(key): as_int(value) for key, value in as_dict(pace.get("alocacao")).items()}
    months = as_int(pace.get("meses")) or len(keys)
    recipe = as_dict(mix)
    use_progress = should_progress(months, recipe) if progress is None else bool(progress) and 2 <= months <= 12
    weights = recipe.get("weights")
    rows = []
    for item in allocate(canais, objetivo, method, weights):
        cells = []
        for index, key in enumerate(keys):
            month_weights = month_mix_weights(
                canais, objetivo, method, months, index, weights, use_progress
            )
            pct = next((row["pct"] for row in month_weights if row["id"] == item["id"]), item["pct"])
            month_total = alocacao.get(key, 0)
            valor = shares_to_money(month_weights, month_total).get(item["id"], 0)
            cells.append({
                "key": key,
                "pct": pct,
                "valor": valor,
                "valor_label": format_money(valor) if valor else "—",
            })
        rows.append({
            "id": item["id"],
            "label": item["label"],
            "group": item["group"],
            "pct": item["pct"],
            "cells": cells,
        })
    return {
        "months": months,
        "keys": keys,
        "labels": labels[: len(keys)],
        "progress": use_progress,
        "editavel": bool(pace.get("editavel")),
        "totals": [{"key": key, "label": labels[i] if i < len(labels) else key, "valor": alocacao.get(key, 0)} for i, key in enumerate(keys)],
        "rows": rows,
    }
