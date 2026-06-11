"""
Métricas de preço por métrica e volumes para campanhas PI (Operação / Faturamento).
Extraído de routes.init_routes para reutilização em APIs (ex.: DV360).
"""
from __future__ import annotations

import re
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


def preco_unitario_por_metrica(
    objetivo_nome: Any,
    obj_contratados: Any,
    valor_reais: Any,
    nome_campanha: Any = None,
    totalizador_atingido: Any = None,
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
    partes = [
        (objetivo_nome or "").strip().upper(),
        (nome_campanha or "").strip().upper(),
    ]
    texto = " ".join(p for p in partes if p).strip()

    if texto:
        if any(k in texto for k in ("CPV", "CPA", "CPC", "CPL", "CPI")):
            return vr / vol, "unit"
        if any(
            k in texto
            for k in (
                "CONVERS",
                "LEAD",
                "CLIQUE",
                "CLICK",
                "AÇÃO",
                "ACAO",
                "INSTALL",
                "INSTALA",
                "CADASTRO",
                "COMPRA",
                "VENDA",
            )
        ):
            return vr / vol, "unit"

        if any(
            k in texto
            for k in (
                "CPM",
                "IMPRESS",
                "DISPLAY",
                "VIEWABILITY",
                "ALCANCE",
                "REACH",
                "AWARENESS",
                "RECONHECIMENTO",
                "BRANDING",
                "VISUALIZAÇÃO",
                "VISUALIZACAO",
            )
        ):
            return (vr / vol) * 1000, "cpm"

    return (vr / vol) * 1000, "cpm"


def anexar_preco_metrica_campanha(row: Any) -> dict[str, Any]:
    """Igual ao payload de /api/cadu-pi/<id>/campanhas (coluna Preço em Operação/Faturamento)."""
    r = dict(row)
    valor_para_preco = investimento_para_preco_campanha(r) or 0
    vol_kpi = volume_para_preco_campanha(r.get("obj_contratados"), r.get("totalizador_atingido"))
    preco_metrica, modalidade_preco = preco_unitario_por_metrica(
        r.get("objetivo_nome"),
        r.get("obj_contratados"),
        valor_para_preco,
        r.get("nome_campanha"),
        r.get("totalizador_atingido"),
    )
    r["investimento_kpi_brl"] = valor_para_preco if valor_para_preco > 0 else None
    r["volume_kpi"] = vol_kpi
    r["preco_metrica_brl"] = round(preco_metrica, 2) if preco_metrica is not None else None
    r["preco_metrica_modalidade"] = modalidade_preco
    return r


def sigla_metrica_preco(objetivo_nome: Any, modalidade: Any) -> str:
    """Mesma regra que cadu_pi.html / cadu_pi_form (Preço R$ por métrica)."""
    if modalidade == "cpm":
        return "CPM"
    n = (objetivo_nome or "").upper()
    for k in ("CPV", "CPA", "CPC", "CPL", "CPI"):
        if k in n:
            return k
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
