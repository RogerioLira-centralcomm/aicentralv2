"""Catálogo comercial único do Cadu (planos, pacotes de tokens e armazenamento).

Fonte única de preços e volumes lida pelo backend e enviada ao front. Valores
que o dono ainda não definiu ficam ``None`` e a interface mostra "Consulte".
Sobrescreva sem deploy de código com ``CADU_PLAN_CATALOG_JSON`` (planos),
``CADU_STORAGE_PACKAGES_JSON`` (armazenamento extra) e ``CADU_FINANCE_EMAILS``.

Funções deste módulo são puras (sem banco) para serem testadas isoladamente.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# Pacotes de tokens extras. Não expiram (decisão do dono, 2026-10-06).
EXTRA_PACKAGES: tuple[dict, ...] = (
    {"slug": "extra-essencial", "name": "Extra Essencial", "tokens": 100_000, "price_brl": 49.0,
     "description": "Reforço pontual para uma operação em andamento."},
    {"slug": "extra-equipe", "name": "Extra Equipe", "tokens": 500_000, "price_brl": 179.0,
     "description": "Mais margem para planejamento, auditoria e produção."},
    {"slug": "extra-agencia", "name": "Extra Agência", "tokens": 1_000_000, "price_brl": 299.0,
     "description": "Volume para múltiplos projetos e clientes."},
)

# Planos comerciais. tokens_monthly e storage_gb ficam vazios até o dono definir.
PLAN_CATALOG: tuple[dict, ...] = (
    {"slug": "essencial", "name": "Essencial", "price_monthly": 297.0, "tokens_monthly": None, "storage_gb": None,
     "tagline": "Para começar a operar com o Cadu no dia a dia.",
     "features": ["Workspace, projetos e marcas ilimitados", "Studio, Planner e Connect"],
     "cta": "contact", "highlight": False},
    {"slug": "equipe", "name": "Equipe", "price_monthly": 697.0, "tokens_monthly": None, "storage_gb": None,
     "tagline": "Para equipes que produzem e planejam toda semana.",
     "features": ["Tudo do Essencial", "Mais tokens por mês"],
     "cta": "contact", "highlight": True},
    {"slug": "agencia", "name": "Agência", "price_monthly": 1497.0, "tokens_monthly": None, "storage_gb": None,
     "tagline": "Para agências com vários clientes e projetos.",
     "features": ["Tudo do Equipe", "Maior franquia de tokens"],
     "cta": "contact", "highlight": False},
)

# Nome comercial de planos internos (a chave interna é mantida no banco).
PLAN_DISPLAY_NAMES = {"beta_tester": "Acesso antecipado", "beta tester": "Acesso antecipado", "beta": "Acesso antecipado"}

DEFAULT_FINANCE_EMAILS = ("apolo@centralcomm.media", "financeiro@centralcomm.media", "alexandre@centralcomm.media")


def plural(count: Any, singular: str, plural_form: str) -> str:
    try:
        value = int(count)
    except (TypeError, ValueError):
        value = 0
    return singular if abs(value) == 1 else plural_form


def _key(value: Any) -> str:
    text = " ".join(str(value or "").split()).casefold()
    return text.replace("agência", "agencia").replace(" ", "-")


def package_by_key(value: Any, packages: Optional[Iterable[dict]] = None) -> Optional[dict]:
    """Aceita slug ("extra-equipe") ou nome ("Extra Equipe", com ou sem acento)."""
    key = _key(value)
    for package in (EXTRA_PACKAGES if packages is None else packages):
        if key in {package["slug"], _key(package["name"])}:
            return dict(package)
    return None


def public_packages() -> list[dict]:
    return [dict(item) for item in EXTRA_PACKAGES]


def packages_from_rows(rows: Iterable[dict]) -> list[dict]:
    """Normaliza ``cadu_credit_packages`` (catálogo único). Vazio => fallback do código."""
    result = []
    for row in rows or ():
        row = dict(row or {})
        if str(row.get("kind") or "tokens") != "tokens" or not row.get("slug") or row.get("is_active") is False:
            continue
        tokens = _positive(row.get("credits"))
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if tokens:
            result.append({"slug": str(row["slug"]), "name": str(row.get("name") or row["slug"]),
                           "tokens": tokens, "price_brl": price,
                           "description": str(row.get("description") or "")})
    return result or public_packages()


def load_packages() -> list[dict]:
    """Lê o catálogo do banco; sem a migração do catálogo, usa o fallback do código."""
    try:
        from .db import get_db
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT 1 FROM information_schema.columns
                               WHERE table_name = 'cadu_credit_packages' AND column_name = 'slug' LIMIT 1""")
            if not cursor.fetchone():
                return public_packages()
            cursor.execute("""SELECT slug, kind, name, credits, price, description, is_active
                                FROM cadu_credit_packages
                               WHERE is_active AND slug IS NOT NULL
                            ORDER BY display_order, credits, id""")
            return packages_from_rows(cursor.fetchall())
    except Exception:
        logger.warning("Catálogo de pacotes indisponível; usando o padrão do código", exc_info=True)
        try:
            from .db import recuperar_transacao_falha
            recuperar_transacao_falha()
        except Exception:
            pass
        return public_packages()


def _json_env(name: str) -> Any:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("%s inválido; usando o catálogo padrão", name)
        return None


def storage_packages() -> list[dict]:
    """GB extra (Vultr Object Storage). Vazio até o dono configurar preços."""
    data = _json_env("CADU_STORAGE_PACKAGES_JSON")
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if isinstance(item, dict) and item.get("gb"):
            result.append({"slug": str(item.get("slug") or f"storage-{item['gb']}gb"),
                           "name": str(item.get("name") or f"{item['gb']} GB extra"),
                           "gb": item.get("gb"), "price_brl": item.get("price_brl")})
    return result


def finance_recipients() -> list[str]:
    raw = os.getenv("CADU_FINANCE_EMAILS", "")
    emails = [item.strip() for item in raw.replace(";", ",").split(",") if "@" in item]
    return emails or list(DEFAULT_FINANCE_EMAILS)


def plan_display_name(name: Any, plan_type: Any = None) -> str:
    for candidate in (plan_type, name):
        label = PLAN_DISPLAY_NAMES.get(str(candidate or "").strip().casefold())
        if label:
            return label
    return str(name or plan_type or "Plano")


def _positive(value: Any) -> Optional[int]:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def commercial_plans(definitions: Iterable[dict] = (), current_plan: Optional[dict] = None) -> list[dict]:
    """Planos exibidos na página de Planos, já normalizados para o front.

    Ordem de precedência por campo: ``CADU_PLAN_CATALOG_JSON`` > definição do
    banco com o mesmo slug/nome > padrão do código. O plano atual do cliente é
    sempre incluído (marcado ``current``), mesmo que não seja um plano público.
    """
    overrides = _json_env("CADU_PLAN_CATALOG_JSON") or {}
    if not isinstance(overrides, dict):
        overrides = {}
    by_key = {}
    for row in definitions or ():
        row = dict(row or {})
        for candidate in (row.get("plan_type"), row.get("plan_name"), row.get("slug")):
            if candidate:
                by_key.setdefault(_key(candidate), row)

    current = dict(current_plan or {})
    current_keys = {_key(current.get(field)) for field in ("plan_definition_name", "plan_name", "plan_type") if current.get(field)}
    current_id = current.get("id_plan_definition")

    def normalize(base: dict, row: dict) -> dict:
        slug = base.get("slug") or _key(row.get("plan_type") or row.get("plan_name"))
        override = overrides.get(slug) if isinstance(overrides.get(slug), dict) else {}
        storage_bytes = _positive(row.get("storage_bytes_limit"))
        storage_gb = override.get("storage_gb", base.get("storage_gb"))
        if storage_gb is None and storage_bytes:
            storage_gb = round(storage_bytes / (1024 ** 3), 1)
        tokens = override.get("tokens_monthly", base.get("tokens_monthly"))
        if tokens is None:
            tokens = _positive(row.get("tokens_monthly_limit"))
        price = override.get("price_monthly", base.get("price_monthly"))
        if price is None:
            try:
                price = float(row.get("price_monthly")) if row.get("price_monthly") is not None else None
            except (TypeError, ValueError):
                price = None
        is_current = bool(slug in current_keys or (current_id and row.get("id") == current_id))
        return {
            "slug": slug,
            "name": plan_display_name(override.get("name") or base.get("name") or row.get("plan_name"), row.get("plan_type") or slug),
            "tagline": override.get("tagline", base.get("tagline") or row.get("description") or ""),
            "price_monthly": price,
            "tokens_monthly": _positive(tokens),
            "storage_gb": storage_gb if storage_gb not in ("", 0) else None,
            "users_unlimited": True,
            "features": list(override.get("features", base.get("features") or [])),
            "cta": "current" if is_current else override.get("cta", base.get("cta") or "contact"),
            "highlight": bool(override.get("highlight", base.get("highlight", False))),
            "current": is_current,
        }

    plans = [normalize(base, by_key.get(base["slug"], {})) for base in PLAN_CATALOG]
    if current and not any(plan["current"] for plan in plans):
        row = next((by_key[key] for key in current_keys if key in by_key), {})
        merged = {**row, "plan_type": current.get("plan_type") or row.get("plan_type"),
                  "plan_name": current.get("plan_definition_name") or row.get("plan_name") or current.get("plan_type"),
                  "tokens_monthly_limit": row.get("tokens_monthly_limit") or current.get("pd_tokens_monthly_limit") or current.get("tokens_monthly_limit"),
                  "storage_bytes_limit": row.get("storage_bytes_limit") or current.get("pd_storage_bytes_limit"),
                  "price_monthly": row.get("price_monthly") if row else current.get("pd_price_monthly")}
        if merged.get("plan_name") or merged.get("plan_type"):
            entry = normalize({"tagline": "Seu plano atual."}, merged)
            entry.update(current=True, cta="current", features=[])
            plans.insert(0, entry)
    return plans


# --------------------------------------------------------------------------- ciclo e uso

def current_cycle(today: date, anchor_day: int = 1) -> tuple[date, date]:
    """Ciclo mensal [início, fim] (fim inclusivo) ancorado em ``anchor_day``.

    Dias inexistentes no mês (ex.: 31 em fevereiro) usam o último dia do mês.
    """
    import calendar

    anchor_day = min(max(int(anchor_day or 1), 1), 31)

    def anchored(year: int, month: int) -> date:
        return date(year, month, min(anchor_day, calendar.monthrange(year, month)[1]))

    start = anchored(today.year, today.month)
    if start > today:
        year, month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        start = anchored(year, month)
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return start, anchored(year, month) - timedelta(days=1)


def cycle_anchor_day(plan: Optional[dict]) -> int:
    """Âncora do ciclo. ``CADU_PLAN_CYCLE_ANCHOR=contract`` usa o dia de início do plano."""
    if os.getenv("CADU_PLAN_CYCLE_ANCHOR", "month_start").strip().lower() != "contract":
        return 1
    value = (plan or {}).get("valid_from") or (plan or {}).get("plan_start_date")
    if isinstance(value, datetime):
        return value.day
    if isinstance(value, date):
        return value.day
    try:
        return date.fromisoformat(str(value)[:10]).day
    except (TypeError, ValueError):
        return 1


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _tool_label(row: dict) -> str:
    tool = str(row.get("ferramenta") or row.get("tool") or "Cadu").strip()
    return tool[:1].upper() + tool[1:] if tool else "Cadu"


_INTERACTION_KEYS = ("interaction_id", "studio_root_session_id", "conversation_id", "run_id", "session_id")


def group_interactions(rows: Iterable[dict], gap_minutes: int = 10) -> list[dict]:
    """Agrupa cobranças em interações (mais recente primeiro).

    Uma interação é: mesma chave explícita em ``metadata`` (ex.: sessão do
    Studio) ou, sem ela, cobranças seguidas da mesma ferramenta com intervalo
    de até ``gap_minutes``. Assim várias etapas de uma execução viram uma linha.
    """
    ordered = sorted(
        (dict(row) for row in rows or ()),
        key=lambda row: _as_datetime(row.get("created_at")) or datetime.min,
    )
    groups: list[dict] = []
    explicit: dict[str, dict] = {}
    last_by_tool: dict[str, dict] = {}
    for row in ordered:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        tool = _tool_label(row)
        at = _as_datetime(row.get("created_at"))
        tokens = max(0, int(row.get("amount") or row.get("tokens_cobrados") or 0))
        marker = next((f"{key}:{metadata[key]}" for key in _INTERACTION_KEYS if metadata.get(key)), None)
        group = explicit.get(marker) if marker else None
        if group is None and not marker:
            previous = last_by_tool.get(tool)
            if previous and at and previous["_last"] and not previous.get("_marker") \
                    and at - previous["_last"] <= timedelta(minutes=gap_minutes):
                group = previous
        if group is None:
            group = {"tool": tool, "tokens": 0, "steps": 0, "started_at": at, "_last": at, "_marker": marker}
            groups.append(group)
            if marker:
                explicit[marker] = group
        group["tokens"] += tokens
        group["steps"] += 1
        group["_last"] = at or group["_last"]
        last_by_tool[tool] = group
    result = []
    for group in reversed(groups):
        last = group.pop("_last")
        group.pop("_marker", None)
        started = group.pop("started_at")
        result.append({**group, "created_at": (last or started).isoformat() if (last or started) else None})
    result.sort(key=lambda item: item["created_at"] or "", reverse=True)
    return result


def usage_summary(*, plan: Optional[dict], usage_rows: Iterable[dict], lots: Iterable[dict],
                  today: date, allowance_enabled: bool = False) -> dict:
    """Monta a página de Uso a partir do ledger (``cadu_tools_token_usage``) e dos lotes.

    Nunca lê ``tokens_used_current_month`` (contador legado que nenhum fluxo de IA atualiza).
    ``usage_rows``: cobranças com ``amount``/``tokens_cobrados``, ``created_at``,
    ``ferramenta`` e ``metadata.allocations``. ``lots``: lotes de
    ``cadu_credits_extras`` (com ``source`` opcional — ``plan_allowance`` marca franquia).
    """
    plan = plan or {}
    start, end = current_cycle(today, cycle_anchor_day(plan))
    lots = [dict(lot) for lot in lots or ()]
    allowance_ids = {lot.get("id") for lot in lots if str(lot.get("source") or "") == "plan_allowance"}

    def lot_available(lot: dict) -> int:
        return max(0, int(lot.get("tokens_amount") or lot.get("credits") or 0) - int(lot.get("tokens_used") or 0))

    def active(lot: dict) -> bool:
        expires = _as_datetime(lot.get("expires_at"))
        return str(lot.get("status") or "active") == "active" and (expires is None or expires.date() >= today)

    cycle_rows, cycle_total, from_allowance = [], 0, 0
    for row in usage_rows or ():
        at = _as_datetime(row.get("created_at"))
        if not at or not (start <= at.date() <= end):
            continue
        tokens = max(0, int(row.get("amount") or row.get("tokens_cobrados") or 0))
        cycle_rows.append(row)
        cycle_total += tokens
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        for allocation in metadata.get("allocations") or []:
            if isinstance(allocation, dict) and allocation.get("lot_id") in allowance_ids:
                from_allowance += max(0, int(allocation.get("tokens") or 0))

    limit = _positive(plan.get("pd_tokens_monthly_limit") or plan.get("tokens_monthly_limit")) or 0
    allowance_lot = next((lot for lot in lots if lot.get("id") in allowance_ids and active(lot)), None)
    if allowance_enabled and allowance_lot:
        granted = int(allowance_lot.get("tokens_amount") or 0)
        used = int(allowance_lot.get("tokens_used") or 0)
        active_allowance = True
    else:
        granted, used, active_allowance = limit, min(cycle_total, limit) if limit else cycle_total, False
    extras = [lot for lot in lots if lot.get("id") not in allowance_ids and active(lot)]
    by_tool: dict[str, dict] = {}
    for group in group_interactions(cycle_rows):
        item = by_tool.setdefault(group["tool"], {"tool": group["tool"], "tokens": 0, "interactions": 0})
        item["tokens"] += group["tokens"]
        item["interactions"] += 1
    return {
        "cycle": {"start": start.isoformat(), "end": end.isoformat(), "renews_on": (end + timedelta(days=1)).isoformat()},
        "allowance": {
            "active": active_allowance,
            "granted": granted,
            "used": used,
            "available": max(granted - used, 0),
            "percentage": round(min(100.0, used * 100 / granted), 1) if granted else 0,
        },
        "extras": {
            "available": sum(lot_available(lot) for lot in extras),
            "lots": len([lot for lot in extras if lot_available(lot) > 0]),
        },
        "cycle_tokens": cycle_total,
        "extras_used_in_cycle": max(cycle_total - from_allowance, 0) if active_allowance else None,
        "by_tool": sorted(by_tool.values(), key=lambda item: item["tokens"], reverse=True),
    }
