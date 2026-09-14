"""Período, verba e voo mensal do Smart Planner.

O ritmo padrão não é rateio igual: começa menor para aprender e solta
mais orçamento no meio e no fim. Colunas só editam campanhas com mais
de um mês.
"""

from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

from .helpers import as_dict, text


MONTH_NAMES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}

MONTH_LABELS = ("", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")

_NAME_KEYS = sorted(MONTH_NAMES, key=len, reverse=True)
_NAME_RE = "|".join(re.escape(name) for name in _NAME_KEYS)


def fold(value: str) -> str:
    raw = unicodedata.normalize("NFD", text(value).lower())
    return "".join(char for char in raw if unicodedata.category(char) != "Mn")


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_money_digits(value: Any) -> int:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def format_money(valor: int) -> str:
    valor = max(0, as_int(valor))
    return "R$ " + f"{valor:,}".replace(",", ".")


def format_verba(valor: int, base: str = "total") -> str:
    if valor <= 0:
        return ""
    return format_money(valor) + (" por mês" if base == "mensal" else " no total")


def parse_money(raw: Any) -> dict:
    txt = fold(raw)
    if not txt:
        return {"valor": 0, "base": "total"}
    base = "mensal" if re.search(r"(por|ao|/)\s*mes|mensal", txt) else "total"
    match = re.search(r"(\d[\d.,\s]*)\s*(mil|mi|milhoes|milhao|k)?\b", txt)
    if not match:
        return {"valor": 0, "base": base}
    num = re.sub(r"\s+", "", match.group(1)).rstrip(".,")
    has_dot = "." in num
    has_comma = "," in num
    if has_dot and has_comma:
        num = num.replace(".", "").replace(",", ".")
    elif has_comma:
        num = num.replace(",", ".") if re.search(r",\d{1,2}$", num) else num.replace(",", "")
    elif has_dot and re.fullmatch(r"\d{1,3}(\.\d{3})+", num):
        num = num.replace(".", "")
    try:
        amount = float(num)
    except ValueError:
        return {"valor": 0, "base": base}
    suffix = match.group(2) or ""
    if suffix in {"mil", "k"}:
        amount *= 1000
    elif suffix:
        amount *= 1_000_000
    valor = int(round(amount))
    return {"valor": valor if valor > 0 else 0, "base": base}


def campaign_verba(campanha: dict | None) -> dict:
    campanha = campanha or {}
    texto = text(campanha.get("verba"))
    valor = as_int(campanha.get("verba_valor"))
    base = text(campanha.get("verba_base")).lower()
    if valor <= 0 or base not in {"total", "mensal"}:
        parsed = parse_money(texto)
        valor = parsed["valor"] or valor
        if base not in {"total", "mensal"}:
            base = parsed["base"]
    if base not in {"total", "mensal"}:
        base = "total"
    return {
        "valor": max(0, valor),
        "base": base,
        "texto": format_verba(valor, base) if valor > 0 else texto,
    }


def _today(hoje: date | datetime | None = None) -> date:
    if isinstance(hoje, datetime):
        return hoje.date()
    if isinstance(hoje, date):
        return hoje
    return date.today()


def _year_for_month(month: int, today: date) -> int:
    return today.year if month >= today.month else today.year + 1


def _safe_date(year: int, month: int, day: int) -> date:
    last = monthrange(year, month)[1]
    return date(year, month, min(max(1, day), last))


def _year_from_match(raw: str | None) -> int | None:
    if not raw:
        return None
    year = as_int(raw)
    if year <= 0:
        return None
    return year + 2000 if year < 100 else year


def periodo_vazio(texto: str = "") -> dict:
    return {
        "texto": texto,
        "meses": None,
        "dias": None,
        "inicio": None,
        "fim": None,
        "rotulos": [],
        "chaves": [],
        "helper": "",
        "parseou": False,
    }


def faixa_meses(inicio: date, fim: date) -> dict:
    if fim < inicio:
        inicio, fim = fim, inicio
    cursor = inicio.replace(day=1)
    limite = fim.replace(day=1)
    chaves: list[str] = []
    rotulos: list[str] = []
    guard = 0
    while cursor <= limite and guard < 24:
        chaves.append(f"{cursor.year:04d}-{cursor.month:02d}")
        rotulos.append(MONTH_LABELS[cursor.month])
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
        guard += 1
    return {"chaves": chaves, "rotulos": rotulos}


def periodo_helper(parsed: dict) -> str:
    if not parsed.get("parseou"):
        return ""
    parts: list[str] = []
    meses = as_int(parsed.get("meses"))
    if meses > 0:
        parts.append("1 mês" if meses == 1 else f"{meses} meses")
    rotulos = list(parsed.get("rotulos") or [])
    inicio = text(parsed.get("inicio"))
    fim = text(parsed.get("fim"))
    if rotulos and inicio and fim:
        try:
            start = date.fromisoformat(inicio)
            end = date.fromisoformat(fim)
        except ValueError:
            start = end = None
        if start and end:
            first = rotulos[0].lower()
            last = rotulos[-1].lower()
            if meses == 1:
                parts.append(f"{first} {start.year}")
            elif start.year == end.year:
                parts.append(f"{first} a {last} {start.year}")
            else:
                parts.append(f"{first} a {last} {start.year}/{end.year}")
    elif parsed.get("dias") and meses <= 0:
        parts.append(f"{as_int(parsed.get('dias'))} dias")
    return " · ".join(parts)


def montar_periodo(texto: str, inicio: date, fim: date) -> dict:
    if fim < inicio:
        inicio, fim = fim, inicio
    faixa = faixa_meses(inicio, fim)
    meses = len(faixa["chaves"])
    dias = (fim - inicio).days + 1
    out = {
        "texto": texto,
        "meses": meses or None,
        "dias": dias,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "rotulos": faixa["rotulos"],
        "chaves": faixa["chaves"],
        "helper": "",
        "parseou": meses > 0,
    }
    out["helper"] = periodo_helper(out)
    return out


def parse_periodo(raw: Any, hoje: date | datetime | None = None) -> dict:
    texto = text(raw)
    if not texto:
        return periodo_vazio("")
    today = _today(hoje)
    txt = fold(texto)

    match = re.search(
        r"(\d{1,2})\s*[\/.\-]\s*(\d{1,2})(?:\s*[\/.\-]\s*(\d{2,4}))?\s+(?:a|ate|e)\s+"
        r"(\d{1,2})\s*[\/.\-]\s*(\d{1,2})(?:\s*[\/.\-]\s*(\d{2,4}))?",
        txt,
    )
    if match:
        start = _safe_date(
            _year_from_match(match.group(3)) or _year_for_month(int(match.group(2)), today),
            int(match.group(2)),
            int(match.group(1)),
        )
        end_year = _year_from_match(match.group(6))
        end_month = int(match.group(5))
        if end_year is None:
            end_year = start.year
            if end_month < start.month:
                end_year += 1
        end = _safe_date(end_year, end_month, int(match.group(4)))
        return montar_periodo(texto, start, end)

    match = re.search(
        rf"(\d{{1,2}})\s+de\s+({_NAME_RE})(?:\s+de\s+(\d{{4}}))?\s+(?:a|ate|e)\s+"
        rf"(\d{{1,2}})\s+de\s+({_NAME_RE})(?:\s+de\s+(\d{{4}}))?",
        txt,
    )
    if match:
        month_a = MONTH_NAMES[match.group(2)]
        month_b = MONTH_NAMES[match.group(5)]
        start = _safe_date(
            _year_from_match(match.group(3)) or _year_for_month(month_a, today),
            month_a,
            int(match.group(1)),
        )
        end_year = _year_from_match(match.group(6)) or start.year
        if match.group(6) is None and month_b < month_a:
            end_year += 1
        end = _safe_date(end_year, month_b, int(match.group(4)))
        return montar_periodo(texto, start, end)

    names = list(re.finditer(rf"\b({_NAME_RE})\b(?:\s+de\s+(\d{{4}}))?", txt))
    if names:
        first, last = names[0], names[-1]
        month_a = MONTH_NAMES[first.group(1)]
        month_b = MONTH_NAMES[last.group(1)]
        year_a = _year_from_match(first.group(2)) or _year_for_month(month_a, today)
        start = _safe_date(year_a, month_a, 1)
        year_b = _year_from_match(last.group(2))
        if year_b is None:
            year_b = start.year
            if month_b < month_a:
                year_b += 1
        last_day = monthrange(year_b, month_b)[1]
        end = date(year_b, month_b, last_day)
        return montar_periodo(texto, start, end)

    match = re.search(r"(\d{1,2})\s*m[eê]s(?:es)?", texto, flags=re.I)
    if not match:
        match = re.search(r"(\d{1,2})\s*meses?", txt)
    if match:
        count = max(1, min(24, int(match.group(1))))
        start = today.replace(day=1)
        month = start.month - 1 + (count - 1)
        year = start.year + month // 12
        month = month % 12 + 1
        end = date(year, month, monthrange(year, month)[1])
        return montar_periodo(texto, start, end)

    match = re.search(r"(\d{1,3})\s*dias?", txt)
    if match:
        days = max(1, int(match.group(1)))
        return montar_periodo(texto, today, today + timedelta(days=days - 1))

    return periodo_vazio(texto)


def learn_release_weights(count: int) -> list[float]:
    """Menor no começo, maior no meio e no fim: aprende e solta verba."""
    if count <= 1:
        return [1.0]
    weights = []
    for index in range(count):
        progress = index / (count - 1)
        weights.append(0.48 + 0.74 * (progress ** 0.72))
    return weights


def distribute_budget(keys: list[str], total: int, atual: dict | None = None) -> dict[str, int]:
    keys = [str(key) for key in keys if str(key)]
    out = {key: 0 for key in keys}
    if not keys or total <= 0:
        return out
    atual = atual or {}
    fixed = {key: as_int(atual.get(key)) for key in keys if as_int(atual.get(key)) > 0}
    fixed_sum = sum(fixed.values())
    if fixed_sum > total:
        factor = total / fixed_sum
        for key, value in fixed.items():
            out[key] = int(value * factor)
    else:
        out.update(fixed)
        free = [key for key in keys if key not in fixed]
        if free:
            rest = total - fixed_sum
            share = rest // len(free)
            for key in free:
                out[key] = share
    leftover = total - sum(out.values())
    if leftover and out:
        biggest = max(out, key=lambda key: (out[key], -keys.index(key)))
        out[biggest] = max(0, out[biggest] + leftover)
    return out


def allocate_months(keys: list[str], total: int, atual: dict | None = None) -> dict[str, int]:
    keys = [str(key) for key in keys if str(key)]
    if not keys or total <= 0:
        return {key: 0 for key in keys}
    atual = {str(key): as_int(value) for key, value in as_dict(atual).items()}
    kept = {key: atual[key] for key in keys if atual.get(key, 0) > 0}
    if kept:
        return distribute_budget(keys, total, atual)
    weights = learn_release_weights(len(keys))
    weight_sum = sum(weights)
    out: dict[str, int] = {}
    used = 0
    for key, weight in zip(keys[:-1], weights[:-1]):
        value = int(round(total * (weight / weight_sum)))
        out[key] = value
        used += value
    out[keys[-1]] = max(0, total - used)
    return out


def budget_shares(distribuicao: dict) -> dict[str, float]:
    total = sum(as_int(value) for value in distribuicao.values())
    if total <= 0:
        return {key: 0.0 for key in distribuicao}
    return {key: round((as_int(value) / total) * 100, 1) for key, value in distribuicao.items()}


def campaign_pace(campanha: dict | None, hoje: date | datetime | None = None) -> dict:
    campanha = campanha or {}
    verba = campaign_verba(campanha)
    periodo = parse_periodo(campanha.get("periodo"), hoje)
    months = periodo["meses"]
    valor = verba["valor"]
    total = valor
    ritmo = valor
    if valor > 0 and months:
        if verba["base"] == "mensal":
            total = valor * months
            ritmo = valor
        else:
            total = valor
            ritmo = valor // months
    keys = list(periodo["chaves"])
    alocacao: dict[str, int] = {}
    if keys and total > 0 and months and months > 1:
        alocacao = allocate_months(keys, total, campanha.get("verba_alocacao"))
    elif keys and total > 0 and months == 1:
        alocacao = {keys[0]: total}
    como = ""
    if valor > 0 and months and verba["base"] == "mensal":
        label = "mês" if months == 1 else "meses"
        como = f"{format_money(valor)}/mês × {months} {label} = {format_money(total)} no período"
    elif valor > 0 and months:
        como = f"{format_money(total)} no período · ~{format_money(ritmo)}/mês"
    elif valor > 0:
        como = format_verba(valor, verba["base"])
    editavel = bool(periodo["parseou"] and months and months > 1 and months <= 12 and total > 0)
    return {
        "total": total,
        "ritmo": ritmo,
        "meses": months,
        "dias": periodo["dias"],
        "rotulos": periodo["rotulos"],
        "chaves": keys,
        "alocacao": alocacao,
        "helper": periodo["helper"],
        "como": como,
        "inicio": periodo["inicio"],
        "fim": periodo["fim"],
        "parseou": periodo["parseou"],
        "base": verba["base"],
        "valor": valor,
        "editavel": editavel,
    }


def pace_payload(pace: dict) -> dict:
    return {
        "total": as_int(pace.get("total")),
        "ritmo": as_int(pace.get("ritmo")),
        "meses": pace.get("meses"),
        "dias": pace.get("dias"),
        "rotulos": list(pace.get("rotulos") or []),
        "chaves": list(pace.get("chaves") or []),
        "alocacao": dict(pace.get("alocacao") or {}),
        "helper": text(pace.get("helper")),
        "como": text(pace.get("como")),
        "parseou": bool(pace.get("parseou")),
        "base": text(pace.get("base") or "total"),
        "editavel": bool(pace.get("editavel")),
        "inicio": text(pace.get("inicio")),
        "fim": text(pace.get("fim")),
    }
