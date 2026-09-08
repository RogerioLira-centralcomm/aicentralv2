"""Organização da fila de acompanhamento de campanhas PI."""

from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
import re
import unicodedata


ACTIVE_STATUS_KEYS = frozenset({"ativa", "ativo", "andamento", "em andamento"})
HISTORY_STATUS_ORDER = {
    "aguardando": 0,
    "pausada": 1,
    "pausado": 1,
    "finalizada": 2,
    "finalizado": 2,
    "cancelada": 3,
    "cancelado": 3,
    "sem status": 5,
}


def build_campaign_list_filters(args):
    """Aceita somente filtros explícitos que não recortam competência/status."""
    filters = {}
    for query_name in ("id_cliente", "id_plataforma", "id_pi", "resp_comercial"):
        raw = args.get(query_name)
        if raw in (None, ""):
            continue
        try:
            filters[query_name] = int(raw)
        except (TypeError, ValueError):
            continue
    return filters


def normalize_status(value):
    """Normaliza apenas para comparação, preservando o rótulo original na UI."""
    text = " ".join(str(value or "").strip().split()).lower()
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def is_active_campaign(campanha):
    return normalize_status(campanha.get("status_nome")) in ACTIVE_STATUS_KEYS


def _sortable_date(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value or "")


def _campaign_sort_key(campanha):
    try:
        campaign_id = int(campanha.get("id_campanha") or 0)
    except (TypeError, ValueError):
        campaign_id = 0
    return (
        _sortable_date(
            campanha.get("periodo_fim")
            or campanha.get("periodo_inicio")
            or campanha.get("created_at")
        ),
        campaign_id,
    )


def _number(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text = re.sub(r"[^\d,.\-]", "", str(value))
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _build_group(label, key, campanhas, active=False):
    ordered = sorted(campanhas, key=_campaign_sort_key, reverse=True)
    return {
        "key": key,
        "label": label,
        "active": active,
        "campanhas": ordered,
        "count": len(ordered),
        "total_previsto": sum(_number(c.get("custo_midia_previsto")) for c in ordered),
        "total_gasto": sum(_number(c.get("totalizador_gasto")) for c in ordered),
    }


def group_campaigns_by_status(campanhas):
    """Retorna a fila ativa e os grupos históricos na ordem operacional."""
    active = []
    history = OrderedDict()

    for campanha in campanhas or []:
        status_label = " ".join(str(campanha.get("status_nome") or "").strip().split())
        status_key = normalize_status(status_label) or "sem status"
        if status_key in ACTIVE_STATUS_KEYS:
            active.append(campanha)
            continue
        if status_key not in history:
            history[status_key] = {
                "label": status_label or "Sem status",
                "campanhas": [],
            }
        history[status_key]["campanhas"].append(campanha)

    history_groups = [
        _build_group(data["label"], key, data["campanhas"])
        for key, data in history.items()
    ]
    history_groups.sort(
        key=lambda group: (
            HISTORY_STATUS_ORDER.get(group["key"], 4),
            group["label"].casefold(),
        )
    )

    return {
        "active": _build_group("Ativas", "ativas", active, active=True),
        "history": history_groups,
        "history_count": sum(group["count"] for group in history_groups),
        "total_count": len(active) + sum(group["count"] for group in history_groups),
    }
