"""Dados da Área do Cliente. Cada PI é um projeto.

Regra da casa: nada de custo, margem, fee ou valor de PI. Só períodos,
status, metas, atingido e percentuais, como na página pública do PI.
"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

SUB_STATUS_CANCELADO = 6
SUB_STATUS_ATIVOS = (2, 3)  # Em configuração, Em andamento
STATUS_CAMPANHA_NO_AR = ("ativa", "ativo", "em andamento")

ETAPAS_CLIENTE = {
    "dados_validados": "PI aprovado e dados validados",
    "campanhas_configuradas": "Campanhas configuradas nas plataformas",
    "materiais_recebidos": "Materiais recebidos",
    "campanha_iniciada": "Campanha no ar",
    "otimizacao_enviada": "Otimização aplicada",
    "fechamento_comunicado": "Fechamento comunicado",
    "enviado_financeiro": "Enviado ao faturamento",
}


def _db():
    from .. import db
    return db


def _fetch(sql, params):
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
    except Exception:
        conn.rollback()
        raise


def _iso(value):
    if not value:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _pi_label(row):
    return row.get("codigo_pi_cc") or row.get("codigo_pi_ag") or f"PI #{row['id_pi']}"


def listar_projetos(cliente_id, busca: str = "") -> list[dict]:
    """PIs do cliente (como cliente final ou como agência), sem os cancelados."""
    params: list = [cliente_id, cliente_id, SUB_STATUS_CANCELADO]
    filtro = ""
    termo = (busca or "").strip()
    if termo:
        filtro = "AND (pi.titulo_pi ILIKE %s OR pi.codigo_pi_cc ILIKE %s OR pi.codigo_pi_ag ILIKE %s)"
        params += [f"%{termo}%"] * 3
    rows = _fetch(
        f"""
        SELECT pi.id_pi, pi.codigo_pi_cc, pi.codigo_pi_ag, pi.titulo_pi,
               pi.periodo_inicio, pi.periodo_fim, pi.updated_at, pi.created_at,
               pi.id_sub_status_pi, ss.display AS sub_status,
               cli.nome_fantasia AS cliente_nome
          FROM cadu_pi pi
          LEFT JOIN cadu_pi_sub_status ss ON ss.key = pi.id_sub_status_pi
          LEFT JOIN tbl_cliente cli ON cli.id_cliente = pi.id_cliente
         WHERE (pi.id_cliente = %s OR pi.id_agencia = %s)
           AND COALESCE(pi.id_sub_status_pi, 0) <> %s
           {filtro}
         ORDER BY COALESCE(pi.periodo_inicio, pi.created_at::date) DESC NULLS LAST, pi.id_pi DESC
        """,
        tuple(params),
    )
    campanhas = campanhas_dos_pis([r["id_pi"] for r in rows])
    projetos = []
    for row in rows:
        das_campanhas = [c for c in campanhas if c["id_pi"] == row["id_pi"]]
        pcts = [c["pct"] for c in das_campanhas if c["pct"] is not None]
        projetos.append({
            "id": row["id_pi"],
            "titulo": row["titulo_pi"] or _pi_label(row),
            "pi": _pi_label(row),
            "cliente": row["cliente_nome"] or "",
            "status": row["sub_status"] or "Em preparação",
            "status_id": row["id_sub_status_pi"],
            "ativo": row["id_sub_status_pi"] in SUB_STATUS_ATIVOS,
            "periodo": {"inicio": _iso(row["periodo_inicio"]), "fim": _iso(row["periodo_fim"])},
            "atualizado_em": _iso(row["updated_at"] or row["created_at"]),
            "n_campanhas": len(das_campanhas),
            "plataformas": sorted({c["plataforma"] for c in das_campanhas if c["plataforma"]}),
            "pct": round(sum(pcts) / len(pcts)) if pcts else None,
            "campanhas": das_campanhas,
        })
    return projetos


def campanhas_dos_pis(ids_pi) -> list[dict]:
    """Entregas por campanha (meta, atingido, %), no formato da página do PI."""
    ids = [int(i) for i in ids_pi or []]
    if not ids:
        return []
    from ..campanha_acompanhamento_publico import _resultado_campanha

    rows = _fetch(
        """
        SELECT c.id_campanha, c.id_pi, c.nome_campanha, c.obj_contratados,
               c.totalizador_atingido, c.periodo_inicio, c.periodo_fim,
               c.link_dash, c.link_dash_incorporar, c.updated_at,
               plt.descricao AS plataforma_nome, obj.descricao AS objetivo_nome,
               st.descricao AS status_nome
          FROM cadu_pi_campanha c
          LEFT JOIN cadu_pi_camp_plataforma plt ON plt.id_plataforma = c.id_plataforma
          LEFT JOIN cadu_pi_camp_objetivos obj ON obj.id_objetivos_campanha = c.id_objetivos_campanha
          LEFT JOIN cadu_pi_camp_status st ON st.id = c.id_status
         WHERE c.id_pi = ANY(%s)
         ORDER BY c.periodo_inicio DESC NULLS LAST, c.id_campanha
        """,
        (ids,),
    )
    saida = []
    for row in rows:
        resultado = _resultado_campanha(row, 0)
        resultado["id_pi"] = row["id_pi"]
        resultado["no_ar"] = (resultado["status"] or "").strip().lower() in STATUS_CAMPANHA_NO_AR
        saida.append(resultado)
    return saida


def atividades_recentes(ids_pi, projetos_por_id, limite=8) -> list[dict]:
    """Etapas concluídas da operação, com rótulos para o cliente."""
    ids = [int(i) for i in ids_pi or []]
    if not ids:
        return []
    try:
        rows = _fetch(
            """
            SELECT id_pi, etapa, concluida_em
              FROM cadu_pi_operacao_etapa
             WHERE id_pi = ANY(%s) AND concluida_em IS NOT NULL
             ORDER BY concluida_em DESC
             LIMIT %s
            """,
            (ids, limite),
        )
    except Exception:
        logger.warning("Etapas da operação indisponíveis.", exc_info=True)
        return []
    saida = []
    for row in rows:
        projeto = projetos_por_id.get(row["id_pi"]) or {}
        saida.append({
            "titulo": ETAPAS_CLIENTE.get(row["etapa"], "Atualização da operação"),
            "projeto": projeto.get("titulo") or f"PI #{row['id_pi']}",
            "projeto_id": row["id_pi"],
            "em": row["concluida_em"],
        })
    return saida


def resumo_inicio(cliente_id) -> dict:
    """Tudo o que a tela Início mostra, em uma chamada."""
    projetos = listar_projetos(cliente_id)
    campanhas = [c for p in projetos for c in p["campanhas"]]
    pcts = [c["pct"] for c in campanhas if c["no_ar"] and c["pct"] is not None]
    performance = sorted(
        (c for c in campanhas if c["meta"]),
        key=lambda c: (not c["no_ar"], c["periodo"]["fim"] or ""),
    )[:6]
    destaque = sorted(projetos, key=lambda p: (not p["ativo"], p["periodo"]["fim"] or ""))[:4]
    return {
        "kpis": {
            "projetos_ativos": sum(1 for p in projetos if p["ativo"]),
            "projetos_total": len(projetos),
            "campanhas_no_ar": sum(1 for c in campanhas if c["no_ar"]),
            "campanhas_total": len(campanhas),
            "entrega_media": round(sum(pcts) / len(pcts)) if pcts else None,
            "dashboards": sum(1 for c in campanhas if c["dash_abrir"]),
        },
        "performance": performance,
        "atividades": atividades_recentes([p["id"] for p in projetos], {p["id"]: p for p in projetos}),
        "destaque": destaque,
        "hoje": date.today(),
    }


def projeto_do_cliente(cliente_id, id_pi) -> dict | None:
    """Payload 360° do PI, só se o PI for deste cliente e não estiver cancelado."""
    rows = _fetch(
        """
        SELECT id_pi FROM cadu_pi
         WHERE id_pi = %s AND (id_cliente = %s OR id_agencia = %s)
           AND COALESCE(id_sub_status_pi, 0) <> %s
        """,
        (id_pi, cliente_id, cliente_id, SUB_STATUS_CANCELADO),
    )
    if not rows:
        return None
    from ..campanha_acompanhamento_publico import contexto_pagina, montar_payload_acompanhamento_pi

    try:
        payload = montar_payload_acompanhamento_pi(id_pi)
    except LookupError:
        return {"vazio": True, "id_pi": id_pi}
    return {"vazio": False, "payload": payload, "ctx": contexto_pagina(payload)}
