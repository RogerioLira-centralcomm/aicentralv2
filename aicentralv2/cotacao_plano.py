"""Família de versões do mesmo briefing — o comercial não vê estes nomes.

Uma cotação sozinha já é um plano e já conta nos relatórios.
Duplicar herda o grupo; só a marcada como principal entra em valor.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from .cotacao_tipos import COTACAO_TIPOS, normalizar_tipo_comercial, rotulo_tipo_comercial

DASHBOARD_TIPOS = (
    ("midia", "Mídia", "#0369a1"),
    ("parceiros", "Parceiros", "#6d28d9"),
    ("formatos_interativos", "Formatos interativos", "#c2410c"),
    ("dados", "Dados", "#047857"),
)

STATUS_ABERTAS = frozenset({
    "rascunho",
    "enviada",
    "em-acompanhamento",
    "em_acompanhamento",
    "proximo-de-aprovar",
    "proximo_de_aprovar",
    "pendente",
    "negociação",
    "negociacao",
})
STATUS_APROVADAS = frozenset({"aprovada", "ganha", "fechada"})
STATUS_MORTAS = frozenset({"rejeitada", "expirada", "perdida"})


def sql_eh_principal(alias: str = "c") -> str:
    return f"COALESCE({alias}.eh_principal, TRUE)"


def sql_valor_que_conta(alias: str = "c", campo: str = "valor_total_proposta") -> str:
    return (
        f"CASE WHEN {sql_eh_principal(alias)} "
        f"THEN COALESCE({alias}.{campo}, 0) ELSE 0 END"
    )


def parse_alvo_id(value) -> int:
    if value in (None, ""):
        raise ValueError("Escolha outra proposta para ligar.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("Escolha outra proposta para ligar.")


def cotacao_conta_em_relatorio(cotacao: Optional[Dict[str, Any]]) -> bool:
    if not cotacao:
        return False
    flag = cotacao.get("eh_principal")
    if flag is None:
        return True
    return bool(flag)


def slug_tipo_dashboard(valor: Any) -> str:
    slug = normalizar_tipo_comercial(valor, estrito=False)
    return slug if slug in COTACAO_TIPOS else "midia"


def rotulo_tipo_dashboard(valor: Any) -> str:
    return rotulo_tipo_comercial(slug_tipo_dashboard(valor))


def cor_tipo_dashboard(valor: Any) -> str:
    slug = slug_tipo_dashboard(valor)
    for key, _label, color in DASHBOARD_TIPOS:
        if key == slug:
            return color
    return DASHBOARD_TIPOS[0][2]


def _grupo_id(cotacao: Dict[str, Any]) -> str:
    raw = cotacao.get("grupo_plano_id") or cotacao.get("id") or ""
    return str(raw)


def metricas_por_plano(
    cotacoes: Sequence[Dict[str, Any]],
    *,
    aberta_fn=None,
    aprovada_fn=None,
    valor_fn=None,
) -> Dict[str, Any]:
    """Uma oportunidade por briefing; valor só da que o comercial marcou."""

    def _aberta(item):
        if aberta_fn:
            return aberta_fn(item)
        slug = str(item.get("status") or "").strip().casefold().replace(" ", "-")
        return slug in STATUS_ABERTAS

    def _aprovada(item):
        if aprovada_fn:
            return aprovada_fn(item)
        slug = str(item.get("status") or "").strip().casefold().replace(" ", "-")
        return slug in STATUS_APROVADAS

    def _valor(item):
        if valor_fn:
            return float(valor_fn(item) or 0)
        try:
            return float(item.get("valor_total_proposta") or item.get("valor_total") or 0)
        except (TypeError, ValueError):
            return 0.0

    pipeline = 0.0
    faturamento = 0.0
    oportunidades = 0
    aprovadas = 0
    for item in cotacoes:
        if not cotacao_conta_em_relatorio(item):
            continue
        valor = _valor(item)
        if _aberta(item):
            oportunidades += 1
            pipeline += valor
        if _aprovada(item):
            aprovadas += 1
            faturamento += valor
    return {
        "oportunidades": oportunidades,
        "pipeline": pipeline,
        "faturamento": faturamento,
        "aprovadas": aprovadas,
    }


def plano_sem_principal_viva(irmas: Sequence[Dict[str, Any]], *, viva_fn=None) -> bool:
    """True quando o grupo tem irmãs e nenhuma que conta está aberta/aprovada."""
    if len(irmas) < 2:
        return False

    def _viva(item):
        if viva_fn:
            return viva_fn(item)
        slug = str(item.get("status") or "").strip().casefold().replace(" ", "-")
        return slug not in STATUS_MORTAS

    principais = [item for item in irmas if cotacao_conta_em_relatorio(item)]
    if not principais:
        return True
    return not any(_viva(item) for item in principais)


def serializar_irma(cotacao: Dict[str, Any], atual_id=None) -> Dict[str, Any]:
    cid = cotacao.get("id")
    tipo = slug_tipo_dashboard(cotacao.get("tipo_comercial"))
    try:
        valor = float(cotacao.get("valor_total_proposta") or cotacao.get("valor_total") or 0)
    except (TypeError, ValueError):
        valor = 0.0
    return {
        "id": cid,
        "numero_cotacao": cotacao.get("numero_cotacao") or "",
        "nome_campanha": cotacao.get("nome_campanha") or "",
        "status": cotacao.get("status_display") or cotacao.get("status_label") or cotacao.get("status") or "",
        "tipo_comercial": tipo,
        "tipo_comercial_label": rotulo_tipo_dashboard(tipo),
        "valor_total": valor,
        "eh_principal": cotacao_conta_em_relatorio(cotacao),
        "atual": str(cid) == str(atual_id) if atual_id is not None else False,
        "grupo_plano_id": _grupo_id(cotacao),
    }


def payload_haste(
    cotacao: Optional[Dict[str, Any]],
    irmas: Iterable[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    irmas_list = [serializar_irma(item, cotacao.get("id") if cotacao else None) for item in irmas]
    if cotacao and not any(item["atual"] for item in irmas_list):
        irmas_list.insert(0, serializar_irma(cotacao, cotacao.get("id")))
    principal = next((item for item in irmas_list if item["eh_principal"]), None)
    return {
        "grupo_plano_id": _grupo_id(cotacao) if cotacao else "",
        "eh_principal": cotacao_conta_em_relatorio(cotacao) if cotacao else True,
        "tem_irmas": len(irmas_list) > 1,
        "aviso_sem_principal": plano_sem_principal_viva(irmas_list),
        "principal_numero": (principal or {}).get("numero_cotacao") or "",
        "irmas": irmas_list,
    }


def agregar_semanas_por_tipo(rows: Sequence[Dict[str, Any]], week_starts: Sequence[Any]) -> List[Dict[str, Any]]:
    """Agrega linhas SQL semanais (tipo + qtd + valor) no shape do gráfico."""
    weeks = []
    for week_start in week_starts:
        tipos = {}
        for slug, _label, _color in DASHBOARD_TIPOS:
            matching = [
                row for row in rows
                if row.get("semana") == week_start
                and slug_tipo_dashboard(row.get("tipo_comercial")) == slug
            ]
            tipos[slug] = {
                "quantidade": sum(int(row.get("total") or 0) for row in matching),
                "valor_total": sum(float(row.get("valor_total") or 0) for row in matching),
            }
        weeks.append({
            "inicio": week_start.isoformat() if hasattr(week_start, "isoformat") else str(week_start),
            "rotulo": week_start.strftime("%d/%m") if hasattr(week_start, "strftime") else str(week_start),
            "total": sum(item["quantidade"] for item in tipos.values()),
            "valor_total": sum(item["valor_total"] for item in tipos.values()),
            "tipos": tipos,
        })
    return weeks


def agregar_trimestres_por_tipo(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    quarters = []
    for quarter in range(1, 5):
        quarter_rows = [
            row for row in rows
            if ((int(str(row.get("mes") or "0000-00")[5:7]) - 1) // 3) + 1 == quarter
        ]
        tipos = {}
        for slug, _label, _color in DASHBOARD_TIPOS:
            tipo_rows = [
                row for row in quarter_rows
                if slug_tipo_dashboard(row.get("tipo_comercial")) == slug
            ]
            tipos[slug] = {
                "quantidade": sum(int(row.get("total") or 0) for row in tipo_rows),
                "valor_total": sum(float(row.get("valor_total") or 0) for row in tipo_rows),
            }
        quarters.append({
            "trimestre": quarter,
            "total": sum(int(row.get("total") or 0) for row in quarter_rows),
            "valor_total": sum(float(row.get("valor_total") or 0) for row in quarter_rows),
            "tipos": tipos,
        })
    return quarters
