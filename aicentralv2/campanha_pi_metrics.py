"""
Métricas de preço por métrica e volumes para campanhas PI (Operação / Faturamento).
Extraído de routes.init_routes para reutilização em APIs (ex.: DV360).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional


def parse_brl_float(value: Any) -> Optional[float]:
    """Converte valor monetário (VARCHAR/Numeric) para float — alinhado ao SQL do dashboard."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            return float(value)
    except ImportError:
        pass
    if isinstance(value, str) and not value.strip():
        return None
    if not value and value != 0:
        return None
    s = re.sub(r"[^0-9.,]", "", str(value).strip().replace("R$", "").strip())
    if not s:
        return None
    try:
        if re.match(r"^[0-9]+,[0-9]+$", s):
            return float(s.replace(",", "."))
        if re.match(r"^[0-9.]+,[0-9]+$", s):
            return float(s.replace(".", "").replace(",", "."))
        if s.count(".") == 1:
            return float(s)
        if "." in s:
            return float(s.replace(".", ""))
        if re.match(r"^[0-9]+$", s):
            return float(s)
        return float(s.replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def volume_qty_campanha(value: Any) -> Optional[float]:
    """Volume (impressões, meta, etc.) para CPM e metas. None se vazio ou <= 0."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if v > 0 else None
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            v = float(value)
            return v if v > 0 else None
    except ImportError:
        pass
    s = re.sub(r"[^0-9.,]", "", str(value).strip())
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        parts = s.split(".")
        if len(parts) > 2:
            s = s.replace(".", "")
        elif len(parts) == 2:
            if len(parts[1]) <= 2:
                pass
            else:
                s = s.replace(".", "")
    try:
        v = float(s)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def parse_volume_float(value: Any) -> float:
    """Igual ao filtro Jinja parse_volume_campanha (ausente → 0.0)."""
    v = volume_qty_campanha(value)
    return float(v) if v is not None else 0.0


def volume_para_preco_campanha(obj_contratados: Any, totalizador_atingido: Any) -> Optional[float]:
    """Usa meta contratada; se vazia, volume atingido (para não ficar em branco)."""
    v = volume_qty_campanha(obj_contratados)
    if v is not None:
        return v
    return volume_qty_campanha(totalizador_atingido)


def investimento_para_preco_campanha(row: Any) -> Optional[float]:
    """Investimento de mídia usado no cálculo do Valor KPI."""
    v_total = parse_brl_float(row.get("valor_total_plataforma")) or 0
    v_plat = parse_brl_float(row.get("valor_plataforma")) or 0
    valor = v_total if v_total > 0 else v_plat
    if valor <= 0:
        valor = parse_brl_float(row.get("totalizador_gasto")) or 0
    return float(valor) if valor > 0 else None


_CPM_KPI_TOKENS = ("VCPM", "CPM")
_UNIT_KPI_TOKENS = ("CPV", "CPC", "CPA", "CPL", "CPI", "CPE", "CPO", "FIXO")
_KPI_SIGLA_TOKENS = _CPM_KPI_TOKENS + _UNIT_KPI_TOKENS


def _kpi_token_present(texto: str, token: str) -> bool:
    """Match de token KPI com word boundary."""
    return bool(re.search(rf"\b{re.escape(token)}\b", texto, flags=re.IGNORECASE))


def kpi_sigla_from_text(kpi_text: Any) -> Optional[str]:
    """Extrai sigla KPI (CPM, CPC, …) do texto explícito cadastrado."""
    if kpi_text is None or not str(kpi_text).strip():
        return None
    k = str(kpi_text).strip().upper()
    for token in _KPI_SIGLA_TOKENS:
        if _kpi_token_present(k, token):
            return "CPM" if token == "VCPM" else token
    return None


def _modalidade_from_kpi_text(kpi_text: Any) -> Optional[str]:
    """Retorna 'cpm' ou 'unit' somente a partir do KPI explícito; None se vazio."""
    if kpi_text is None or not str(kpi_text).strip():
        return None
    k = str(kpi_text).strip().upper()
    for token in _CPM_KPI_TOKENS:
        if _kpi_token_present(k, token):
            return "cpm"
    for token in _UNIT_KPI_TOKENS:
        if _kpi_token_present(k, token):
            return "unit"
    return None


def _modalidade_kpi(
    objetivo_nome: Any,
    nome_campanha: Any = None,
    kpi_nome: Any = None,
) -> str:
    """Modalidade de preço só pelo KPI definido (objetivo/cotação). Nome da campanha não entra."""
    del nome_campanha  # legado: ignorado de propósito
    for src in (objetivo_nome, kpi_nome):
        modalidade = _modalidade_from_kpi_text(src)
        if modalidade:
            return modalidade
    return "cpm"


def preco_unitario_por_metrica(
    objetivo_nome: Any,
    obj_contratados: Any,
    valor_reais: Any,
    nome_campanha: Any = None,
    totalizador_atingido: Any = None,
    kpi_nome: Any = None,
) -> tuple[Optional[float], Optional[str]]:
    """
    CPM: (investimento / impressões) * 1000 (volume = impressões totais).
    CPV, CPA, CPC, CPL, etc.: investimento / unidade.
    Sem palavra-chave: assume CPM (mídia display / volume + investimento).
    """
    vol = volume_para_preco_campanha(obj_contratados, totalizador_atingido)
    if vol is None or valor_reais is None or float(valor_reais) <= 0:
        return None, None
    vr = float(valor_reais)
    modalidade = _modalidade_kpi(objetivo_nome, nome_campanha, kpi_nome)
    if modalidade == "unit":
        return vr / vol, "unit"
    return (vr / vol) * 1000, "cpm"


def _custo_midia_de_preco_unitario(row: Any) -> Optional[float]:
    """Deriva custo de mídia a partir de preco_unitario_orcado × volume contratado."""
    preco = parse_brl_float(row.get("preco_unitario_orcado"))
    vol = volume_qty_campanha(row.get("obj_contratados"))
    if preco is None or preco <= 0 or vol is None:
        return None
    modalidade = _modalidade_kpi(
        row.get("objetivo_nome"), row.get("nome_campanha"), row.get("kpi_nome")
    )
    if modalidade == "unit":
        return round(preco * vol, 2)
    return round((preco * vol) / 1000, 2)


def _custo_midia_base_row(row: Any) -> Optional[float]:
    """Custo mídia orçado (cotação ou derivado); sem fallback legado valor_plataforma."""
    v = parse_brl_float(row.get("custo_midia_orcado"))
    if v is not None and v > 0:
        return float(v)
    v = _custo_midia_de_preco_unitario(row)
    return float(v) if v is not None and v > 0 else None


def custo_midia_previsto_campanha(row: Any) -> Optional[float]:
    """Custo de mídia orçado; fallback derivado e valor_plataforma (legado)."""
    v = _custo_midia_base_row(row)
    if v is not None and v > 0:
        return v
    v = parse_brl_float(row.get("valor_plataforma"))
    return float(v) if v is not None and v > 0 else None


def preco_unitario_realizado(
    objetivo_nome: Any,
    totalizador_gasto: Any,
    totalizador_atingido: Any,
    nome_campanha: Any = None,
    kpi_nome: Any = None,
) -> Optional[float]:
    """Custo unitário realizado: gasto / volume atingido, normalizado por KPI."""
    gasto = parse_brl_float(totalizador_gasto)
    vol = volume_qty_campanha(totalizador_atingido)
    if gasto is None or gasto <= 0 or vol is None:
        return None
    modalidade = _modalidade_kpi(objetivo_nome, nome_campanha, kpi_nome)
    if modalidade == "unit":
        return round(gasto / vol, 2)
    return round((gasto / vol) * 1000, 2)


def preco_unitario_orcado_campanha(row: Any) -> Optional[float]:
    """Preço unitário orçado da cotação ou derivado de custo mídia / volume."""
    v = parse_brl_float(row.get("preco_unitario_orcado"))
    if v is not None and v > 0:
        return round(float(v), 2)
    custo = _custo_midia_base_row(row) or custo_midia_previsto_campanha(row)
    vol = volume_para_preco_campanha(row.get("obj_contratados"), row.get("totalizador_atingido"))
    if custo is None or vol is None or vol <= 0:
        return None
    modalidade = _modalidade_kpi(
        row.get("objetivo_nome"), row.get("nome_campanha"), row.get("kpi_nome")
    )
    if modalidade == "unit":
        return round(custo / vol, 2)
    return round((custo / vol) * 1000, 2)


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip()[:10], fmt).date()
            except ValueError:
                continue
    return None


def calcular_periodo_progresso(
    periodo_inicio: Any,
    periodo_fim: Any,
    hoje: Optional[date] = None,
) -> dict[str, Any]:
    """Percentual de tempo decorrido e dias restantes da campanha."""
    d_ini = _to_date(periodo_inicio)
    d_fim = _to_date(periodo_fim)
    ref = hoje or date.today()
    if not d_ini or not d_fim or d_fim < d_ini:
        return {"periodo_pct_elapsed": None, "periodo_dias_restantes": None, "periodo_dias_total": None}
    total = (d_fim - d_ini).days
    if total <= 0:
        pct = 100 if ref >= d_ini else 0
        restantes = max((d_fim - ref).days, 0)
        return {
            "periodo_pct_elapsed": pct,
            "periodo_dias_restantes": restantes,
            "periodo_dias_total": 0,
        }
    elapsed = (ref - d_ini).days
    pct = round(max(0, min(100, (elapsed / total) * 100)))
    restantes = max((d_fim - ref).days, 0)
    return {
        "periodo_pct_elapsed": pct,
        "periodo_dias_restantes": restantes,
        "periodo_dias_total": total,
    }


def anexar_preco_metrica_campanha(row: Any) -> dict[str, Any]:
    """Anexa métricas de preço, custo de mídia, objetivo e período à campanha."""
    r = dict(row)
    valor_para_preco = investimento_para_preco_campanha(r) or 0
    vol_kpi = volume_para_preco_campanha(r.get("obj_contratados"), r.get("totalizador_atingido"))
    preco_metrica, modalidade_preco = preco_unitario_por_metrica(
        r.get("objetivo_nome"),
        r.get("obj_contratados"),
        valor_para_preco,
        r.get("nome_campanha"),
        r.get("totalizador_atingido"),
        r.get("kpi_nome"),
    )
    r["investimento_kpi_brl"] = valor_para_preco if valor_para_preco > 0 else None
    r["volume_kpi"] = vol_kpi
    r["preco_metrica_brl"] = round(preco_metrica, 2) if preco_metrica is not None else None
    r["preco_metrica_modalidade"] = modalidade_preco

    custo_prev = custo_midia_previsto_campanha(r)
    gasto = parse_brl_float(r.get("totalizador_gasto")) or 0
    r["custo_midia_previsto"] = custo_prev
    r["custo_midia_realizado"] = float(gasto) if gasto > 0 else None
    if custo_prev and custo_prev > 0 and gasto > 0:
        r["pct_custo_midia"] = round((gasto / custo_prev) * 100)
    else:
        r["pct_custo_midia"] = 0 if not custo_prev else 0

    obj = parse_volume_float(r.get("obj_contratados"))
    ating = parse_volume_float(r.get("totalizador_atingido"))
    r["pct_objetivo"] = round((ating / obj) * 100) if obj > 0 else 0

    r["preco_unitario_orcado_brl"] = preco_unitario_orcado_campanha(r)
    r["preco_unitario_realizado_brl"] = preco_unitario_realizado(
        r.get("objetivo_nome"),
        r.get("totalizador_gasto"),
        r.get("totalizador_atingido"),
        r.get("nome_campanha"),
        r.get("kpi_nome"),
    )

    periodo = calcular_periodo_progresso(r.get("periodo_inicio"), r.get("periodo_fim"))
    r.update(periodo)
    return r


def calc_progress_tier(pct: Any) -> str:
    """Tier visual da barra de progresso (espelha campanhas-ui.js)."""
    try:
        p = int(round(float(pct or 0)))
    except (TypeError, ValueError):
        p = 0
    if p <= 0:
        return "empty"
    if p < 34:
        return "low"
    if p < 70:
        return "mid"
    if p < 100:
        return "high"
    if p == 100:
        return "complete"
    return "over"


def format_volume_ptbr(value: Any) -> str:
    """Volume inteiro formatado pt-BR (ex.: 1.234.567)."""
    if isinstance(value, (int, float)):
        n = round(float(value))
    else:
        n = round(parse_volume_float(value))
    return f"{n:,}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl_ptbr(value: Any, with_prefix: bool = True) -> str:
    """Valor monetário formatado pt-BR."""
    v = parse_brl_float(value)
    if v is None:
        v = 0.0
    s = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}" if with_prefix else s


def sigla_metrica_preco(
    objetivo_nome: Any,
    modalidade: Any = None,
    kpi_nome: Any = None,
) -> str:
    """Sigla KPI (CPM, CPC, …) a partir do KPI definido; fallback mínimo por modalidade."""
    for src in (objetivo_nome, kpi_nome):
        sigla = kpi_sigla_from_text(src)
        if sigla:
            return sigla
    if modalidade == "cpm":
        return "CPM"
    return "—"


def meses_ref_pi_seguros(meses_raw: Any, fallback_mes_ref: Any) -> list[str]:
    """Só entradas M/AA ou MM/AA; evita IndexError no Jinja e SQL divergente."""
    out: list[str] = []
    for m in meses_raw or []:
        s = str(m).strip() if m is not None else ""
        if "/" not in s:
            continue
        parts = s.split("/")
        if len(parts) < 2:
            continue
        try:
            int(parts[0].strip())
            int(parts[1].strip())
        except ValueError:
            continue
        out.append(s)
    fb = str(fallback_mes_ref).strip() if fallback_mes_ref else ""
    if not out and fb and "/" in fb:
        try:
            p = fb.split("/")
            int(p[0].strip())
            int(p[1].strip())
            out = [fb]
        except (ValueError, IndexError):
            pass
    return out
