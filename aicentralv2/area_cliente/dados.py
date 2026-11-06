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


def _limpo(valor):
    """Texto do cadastro sem lixo: vazio, "None" ou "null" gravados como texto viram None."""
    texto = str(valor).strip() if valor is not None else ""
    return None if texto.lower() in ("", "none", "null") else texto


def _pi_label(row):
    return _limpo(row.get("codigo_pi_cc")) or _limpo(row.get("codigo_pi_ag")) or f"PI #{row['id_pi']}"


def _pi_titulo(row):
    return _limpo(row.get("titulo_pi")) or _pi_label(row)


def listar_projetos(cliente_id, busca: str = "", id_pi=None) -> list[dict]:
    """PIs do cliente (como cliente final ou como agência), sem os cancelados."""
    params: list = [cliente_id, cliente_id, SUB_STATUS_CANCELADO]
    filtro = ""
    if id_pi is not None:
        filtro += " AND pi.id_pi = %s"
        params.append(int(id_pi))
    termo = (busca or "").strip()
    if termo:
        filtro += " AND (pi.titulo_pi ILIKE %s OR pi.codigo_pi_cc ILIKE %s OR pi.codigo_pi_ag ILIKE %s)"
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
            "titulo": _pi_titulo(row),
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
               st.descricao AS status_nome, resp.nome_completo AS responsavel_nome
          FROM cadu_pi_campanha c
          LEFT JOIN tbl_contato_cliente resp ON resp.id_contato_cliente = c.id_responsavel_operacao
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
        resultado["responsavel"] = row.get("responsavel_nome") or ""
        from .plataformas import iniciais, logo
        resultado["plataforma_logo"] = logo(resultado["plataforma"])
        resultado["plataforma_iniciais"] = iniciais(resultado["plataforma"])
        saida.append(resultado)
    return saida


def atividades_recentes(ids_pi, projetos_por_id, limite=6) -> list[dict]:
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


def resumo_projeto(cliente_id, id_pi) -> dict | None:
    """Cartão-resumo de um PI do cliente (mesmo formato da lista)."""
    projetos = listar_projetos(cliente_id, id_pi=id_pi)
    return projetos[0] if projetos else None


def _media(valores):
    return round(sum(valores) / len(valores)) if valores else None


def _ritmo(pct, tempo):
    """Mesma régua das campanhas: adiantado, no ritmo ou atenção."""
    if pct is None or not tempo:
        return ""
    return "adiantado" if pct >= tempo + 5 else "no_ritmo" if pct >= tempo - 10 else "atencao"


def resumo_inicio(cliente_id) -> dict:
    """Tudo o que a tela Início mostra, em uma chamada."""
    projetos = listar_projetos(cliente_id)
    campanhas = [c for p in projetos for c in p["campanhas"]]
    pcts = [c["pct"] for c in campanhas if c["no_ar"] and c["pct"] is not None]
    performance = sorted(
        (c for c in campanhas if c["meta"]),
        key=lambda c: (not c["no_ar"], c["periodo"]["fim"] or ""),
    )[:6]
    ativos = [p for p in projetos if p["ativo"]]
    destaque = (ativos or projetos)[:4]
    resumo = {
        "kpis": {
            "projetos_ativos": sum(1 for p in projetos if p["ativo"]),
            "projetos_total": len(projetos),
            "campanhas_no_ar": sum(1 for c in campanhas if c["no_ar"]),
            "campanhas_total": len(campanhas),
            "entrega_media": round(sum(pcts) / len(pcts)) if pcts else None,
            "tempo_medio": _media([c["tempo_pct"] for c in campanhas if c["no_ar"] and c["tempo_pct"] is not None]),
            "dashboards": sum(1 for c in campanhas if c["dash_abrir"] and c["no_ar"]),
        },
        "performance": performance,
        "atividades": atividades_recentes([p["id"] for p in projetos], {p["id"]: p for p in projetos}),
        "destaque": destaque,
        "destaque_ativos": bool(ativos),
        "hoje": date.today(),
    }
    k = resumo["kpis"]
    k["ritmo"] = _ritmo(k["entrega_media"], k["tempo_medio"])
    return resumo


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


# ---------- PIs: histórico, faturamento e notas fiscais (só valores de venda) ----------

ETAPAS_PI = ("Em aprovação", "Em configuração", "Em andamento", "Em faturamento", "Finalizado")


def _brl(valor):
    from flask import current_app
    if valor in (None, ""):
        return None
    parse = current_app.jinja_env.filters["parse_brl"]
    numero = parse(valor) if isinstance(valor, str) else float(valor)
    return numero


def listar_pis(cliente_id, id_pi=None) -> list[dict]:
    """PIs do cliente com valores de venda e o resumo das notas fiscais."""
    filtro_pi = "AND pi.id_pi = %s" if id_pi is not None else ""
    params = (cliente_id, cliente_id, SUB_STATUS_CANCELADO) + ((int(id_pi),) if id_pi is not None else ())
    rows = _fetch(
        f"""
        SELECT pi.id_pi, pi.codigo_pi_cc, pi.codigo_pi_ag, pi.titulo_pi, pi.periodo_inicio, pi.periodo_fim,
               pi.created_at, pi.updated_at, pi.id_sub_status_pi, ss.display AS sub_status,
               pi.vr_bruto_pi, pi.vr_cms_agencia, pi.vr_liquido_pi, pi.pi_tem_agencia,
               pi.googled_pi_princ, pi.googled_pi_pecas, pi.googled_pi_arq_ass,
               cli.nome_fantasia AS cliente_nome, ag.nome_fantasia AS agencia_nome,
               COUNT(nf.id) AS n_notas,
               COUNT(nf.id) FILTER (WHERE nf.data_pag_realizado IS NOT NULL OR nfs.descricao ILIKE 'pagamento%%') AS n_pagas
          FROM cadu_pi pi
          LEFT JOIN cadu_pi_sub_status ss ON ss.key = pi.id_sub_status_pi
          LEFT JOIN tbl_cliente cli ON cli.id_cliente = pi.id_cliente
          LEFT JOIN tbl_cliente ag ON ag.id_cliente = pi.id_agencia
          LEFT JOIN cadu_pi_nota_fiscal nf ON nf.id_pi = pi.id_pi
          LEFT JOIN cadu_pi_nota_fiscal_status nfs ON nfs.id = nf.status
         WHERE (pi.id_cliente = %s OR pi.id_agencia = %s)
           AND COALESCE(pi.id_sub_status_pi, 0) <> %s
           {filtro_pi}
         GROUP BY pi.id_pi, ss.display, cli.nome_fantasia, ag.nome_fantasia
         ORDER BY COALESCE(pi.periodo_inicio, pi.created_at::date) DESC NULLS LAST, pi.id_pi DESC
        """,
        params,
    )
    return [_pi_resumo(r) for r in rows]


def _pi_resumo(r) -> dict:
    return {
        "id": r["id_pi"],
        "pi": _pi_label(r),
        "titulo": _pi_titulo(r),
        "status": r["sub_status"] or "Em preparação",
        "status_id": r["id_sub_status_pi"],
        "periodo": {"inicio": _iso(r["periodo_inicio"]), "fim": _iso(r["periodo_fim"])},
        "cliente": r.get("cliente_nome") or "",
        "agencia": r.get("agencia_nome") if r.get("pi_tem_agencia") else "",
        "bruto": _brl(r["vr_bruto_pi"]),
        "comissao": _brl(r["vr_cms_agencia"]) if r.get("pi_tem_agencia") else None,
        "liquido": _brl(r["vr_liquido_pi"]),
        "n_notas": int(r.get("n_notas") or 0),
        "n_pagas": int(r.get("n_pagas") or 0),
        "atualizado_em": _iso(r["updated_at"] or r["created_at"]),
        "documentos": [{"titulo": t, "url": u} for t, u in (
            ("PI e pasta principal", r.get("googled_pi_princ")), ("Plano de mídia e peças", r.get("googled_pi_pecas")),
            ("Documentos assinados", r.get("googled_pi_arq_ass"))) if u and str(u).startswith(("http://", "https://"))],
    }


def pi_do_cliente(cliente_id, id_pi) -> dict | None:
    """Um PI do cliente: valores de venda, notas fiscais e histórico da operação."""
    encontrados = listar_pis(cliente_id, id_pi=id_pi)
    if not encontrados:
        return None
    resumo = encontrados[0]
    notas = _fetch(
        """
        SELECT nf.numero_nota, nf.data_emissao, nf.valor, nf.valor_liquido, nf.mes_ref_comp,
               nf.data_pag_prevista, nf.data_pag_realizado, nfs.descricao AS status
          FROM cadu_pi_nota_fiscal nf
          LEFT JOIN cadu_pi_nota_fiscal_status nfs ON nfs.id = nf.status
         WHERE nf.id_pi = %s
         ORDER BY COALESCE(nf.data_emissao, nf.created_at) DESC
        """,
        (int(id_pi),),
    )
    resumo["notas"] = [{
        "numero": n["numero_nota"] or "—",
        "emissao": _iso(n["data_emissao"]),
        "valor": _brl(n["valor"]),
        "liquido": _brl(n["valor_liquido"]),
        "competencia": n["mes_ref_comp"] or "",
        "prevista": _iso(n["data_pag_prevista"]),
        "pago_em": _iso(n["data_pag_realizado"]),
        "status": n["status"] or ("Pagamento realizado" if n["data_pag_realizado"] else "NF emitida"),
    } for n in notas]
    resumo["faturado"] = sum(n["valor"] or 0 for n in resumo["notas"]) or None
    resumo["pago"] = sum((n["valor"] or 0) for n in resumo["notas"] if n["pago_em"] or "pagamento" in n["status"].lower()) or None
    try:
        etapas = _fetch(
            "SELECT etapa, concluida_em FROM cadu_pi_operacao_etapa WHERE id_pi = %s AND concluida_em IS NOT NULL ORDER BY concluida_em",
            (int(id_pi),),
        )
    except Exception:
        logger.warning("Etapas da operação indisponíveis.", exc_info=True)
        etapas = []
    historico = [{"titulo": ETAPAS_CLIENTE.get(e["etapa"], "Atualização da operação"), "em": _iso(e["concluida_em"])} for e in etapas]
    historico += [{"titulo": f"Nota fiscal {n['numero']} emitida", "em": n["emissao"]} for n in resumo["notas"] if n["emissao"]]
    historico += [{"titulo": f"Pagamento da nota {n['numero']} realizado", "em": n["pago_em"]} for n in resumo["notas"] if n["pago_em"]]
    resumo["historico"] = sorted((h for h in historico if h["em"]), key=lambda h: h["em"], reverse=True)
    atual = resumo["status"]
    resumo["etapas"] = [{"titulo": t, "estado": "done" if ETAPAS_PI.index(t) < ETAPAS_PI.index(atual) else ("current" if t == atual else "todo")}
                        for t in ETAPAS_PI] if atual in ETAPAS_PI else []
    return resumo


# ---------- Campanhas por status ----------

GRUPOS_CAMPANHA = {
    "andamento": ("Em andamento", ("ativa", "ativo", "em andamento")),
    "aguardando": ("Aguardando criativos", ("aguardando",)),
    "parada": ("Paradas", ("parada",)),
    "finalizadas": ("Finalizadas", ("finalizada", "finalizado", "encerrada", "encerrado")),
}


def listar_campanhas(cliente_id, projetos=None) -> dict:
    """Todas as campanhas dos PIs do cliente, agrupadas por status (canceladas ficam de fora)."""
    projetos = listar_projetos(cliente_id) if projetos is None else projetos
    grupos = {chave: [] for chave in GRUPOS_CAMPANHA}
    for p in projetos:
        for c in p["campanhas"]:
            status = (c["status"] or "").strip().lower()
            chave = next((k for k, (_r, valores) in GRUPOS_CAMPANHA.items() if status in valores), None)
            if chave is None:
                continue
            grupos[chave].append({**c, "projeto": p["titulo"], "projeto_id": p["id"], "pi": p["pi"]})
    return grupos


def ritmo_campanhas(cliente_id) -> dict:
    """Painel de campanhas no espírito da "Central de ritmo" interna, sem gasto nem previsto."""
    grupos = listar_campanhas(cliente_id)
    no_ar = grupos["andamento"]
    pcts = [c["pct"] for c in no_ar if c["pct"] is not None]
    return {
        "grupos": grupos,
        "kpis": {
            "no_ar": len(no_ar),
            "aguardando": len(grupos["aguardando"]),
            "encerram_7d": sum(1 for c in no_ar if c["dias_restantes"] is not None and 0 <= c["dias_restantes"] <= 7),
            "entrega_media": round(sum(pcts) / len(pcts)) if pcts else None,
            "tempo_medio": _media([c["tempo_pct"] for c in no_ar if c["tempo_pct"] is not None]),
            "finalizadas": len(grupos["finalizadas"]),
        },
    }


# ---------- Relatórios: só PIs e campanhas em andamento ----------

SUB_STATUS_ABERTOS = (1, 2, 3, 4)  # Em aprovação, configuração, andamento, faturamento


def relatorios(cliente_id) -> list[dict]:
    """Por PI em aberto: link público de acompanhamento, prestação de contas e dashboards no ar."""
    from datetime import datetime
    projetos = [p for p in listar_projetos(cliente_id) if p["status_id"] in SUB_STATUS_ABERTOS]
    if not projetos:
        return []
    rows = _fetch(
        """
        SELECT id_pi, link_publico_token, link_publico_ativo, link_publico_expires_at, googled_pi_financ
          FROM cadu_pi WHERE id_pi = ANY(%s)
        """,
        ([p["id"] for p in projetos],),
    )
    extras = {r["id_pi"]: r for r in rows}
    saida = []
    for p in projetos:
        e = extras.get(p["id"]) or {}
        expira = e.get("link_publico_expires_at")
        link = ""
        if e.get("link_publico_token") and e.get("link_publico_ativo") and not (expira and expira < datetime.now()):
            link = f"/campanha/p/{e['link_publico_token']}"
        financ = _limpo(e.get("googled_pi_financ"))
        dashboards = [c for c in p["campanhas"] if c["dash_abrir"] and c["no_ar"]]
        saida.append({**p, "link_publico": link,
                      "prestacao": financ if financ and financ.startswith(("http://", "https://")) else "",
                      "dashboards": dashboards})
    return saida


_CACHE_CONTAGEM: dict = {}


def campanhas_em_andamento(cliente_id) -> int:
    """Contagem para o selo do menu (cache de 60 s por cliente)."""
    import time
    agora = time.time()
    em, n = _CACHE_CONTAGEM.get(cliente_id, (0.0, 0))
    if agora - em < 60:
        return n
    try:
        n = sum(1 for p in listar_projetos(cliente_id) for c in p["campanhas"] if c["no_ar"])
    except Exception:
        logger.warning("Contagem de campanhas indisponível.", exc_info=True)
        n = 0
    _CACHE_CONTAGEM[cliente_id] = (agora, n)
    return n
