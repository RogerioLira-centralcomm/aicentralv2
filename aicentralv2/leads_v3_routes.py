"""Leads v3: mesa de operações de prospecção (React) em ``/leads-v3``.

A tela reaproveita as rotas ``/api/leads/*`` do Leads v2 para detalhe, contatos,
atividades e comunicações. Aqui ficam só a página, a lista da fila e as ações em massa.
Plano em docs/leads-v3-plano.md.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, render_template, request, session

from . import db
from .auth import centralcomm_required, centralcomm_required_api

bp = Blueprint("leads_v3", __name__, url_prefix="/leads-v3")

# Etapas ativas do funil, na ordem da tela (as mesmas do kanban do Leads v2).
STATUS_ATIVOS = (
    ("inbox", "Inbox"),
    ("tentativa_contato", "Tentativa de contato"),
    ("reuniao_agendada", "Reunião agendada"),
    ("nutricao", "Nutrição"),
)
POTENCIAIS = (("alto", "Alto"), ("medio", "Médio"), ("baixo", "Baixo"))
MOTIVOS_DESQUALIFICACAO = (
    ("contato_errado", "Contato errado"),
    ("fora_perfil", "Fora do perfil"),
    ("sem_orcamento", "Sem orçamento"),
    ("duplicado", "Duplicado"),
    ("spam", "Spam / teste"),
    ("outro", "Outro"),
)
MAX_LOTE = 500


def _ok(data, status=200):
    return jsonify({"success": True, "data": data}), status


def _erro(mensagem, status=400):
    return jsonify({"success": False, "error": mensagem}), status


def _json_safe(valor):
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%dT%H:%M")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def _executivos():
    try:
        rows = db.obter_vendedores_centralcomm(incluir_usuario_comercial=True) or []
    except Exception as exc:  # a tela abre mesmo sem a lista de executivos
        current_app.logger.warning("leads-v3: executivos indisponíveis: %s", exc)
        return []
    return [{"id": r["id_contato_cliente"], "nome": r["nome_completo"]} for r in rows]


@bp.route("")
@bp.route("/")
@centralcomm_required
def pagina():
    executivos = _executivos()
    user_id = session.get("user_id")
    eh_executivo = any(e["id"] == user_id for e in executivos)
    boot = {
        "apiRoot": "/leads-v3/api",
        "legacyApiRoot": "/api/leads",
        "user": {"id": user_id, "nome": session.get("user_name") or ""},
        "executivos": executivos,
        "filtroExecutivoInicial": str(user_id) if eh_executivo else "sem",
        "status": [{"value": v, "label": l} for v, l in STATUS_ATIVOS],
        "potenciais": [{"value": v, "label": l} for v, l in POTENCIAIS],
        "motivos": [{"value": v, "label": l} for v, l in MOTIVOS_DESQUALIFICACAO],
        "legacyUrl": "/leads",
    }
    return render_template("leads_v3.html", boot=boot)


@bp.route("/api/leads")
@centralcomm_required_api
def api_listar():
    """Fila: leads ativos. ``executivo`` = id, ``sem`` (sem responsável) ou vazio (todos)."""
    executivo = (request.args.get("executivo") or "").strip()
    filtros = {
        "potencial": request.args.get("potencial") or None,
        "status": request.args.get("status") or None,
        "search": (request.args.get("q") or "").strip() or None,
        "fonte": request.args.get("fonte") or None,
    }
    if executivo == "sem":
        filtros["sem_responsavel"] = True
    elif executivo.isdigit():
        filtros["id_executivo"] = int(executivo)
    try:
        rows = db.obter_leads_dashboard(**filtros)
    except Exception as exc:
        current_app.logger.error("leads-v3 listar: %s", exc)
        return _erro("Não foi possível carregar os leads.", 500)
    leads = [{k: _json_safe(v) for k, v in dict(r).items()} for r in rows]
    return _ok({"leads": leads, "total": len(leads)})


def _ids_do_lote(payload):
    bruto = payload.get("ids")
    if not isinstance(bruto, list) or not bruto:
        raise ValueError("Selecione ao menos um lead.")
    ids = sorted({int(i) for i in bruto if str(i).isdigit()})
    if not ids:
        raise ValueError("Selecione ao menos um lead.")
    if len(ids) > MAX_LOTE:
        raise ValueError(f"No máximo {MAX_LOTE} leads por vez.")
    return ids


def _sql_do_lote(acao, payload):
    """Devolve (SET, parâmetros, condição de mudança, descrição da atividade ou None)."""
    if acao == "status":
        valor = payload.get("valor")
        if valor not in dict(STATUS_ATIVOS):
            raise ValueError("Etapa inválida.")
        label = dict(STATUS_ATIVOS)[valor]
        return "status = %s", [valor], ("l.status IS DISTINCT FROM %s", [valor]), f"Status alterado para {label} (em massa)"
    if acao == "desqualificar":
        motivo = (payload.get("motivo") or "").strip()
        if not motivo:
            raise ValueError("Informe o motivo da desqualificação.")
        motivo = motivo[:100]
        return (
            "status = 'nao_qualificado', motivo_desqualificacao = %s",
            [motivo],
            ("l.status IS DISTINCT FROM 'nao_qualificado'", []),
            f"Lead desqualificado: {motivo} (em massa)",
        )
    if acao == "potencial":
        valor = payload.get("valor")
        if valor not in dict(POTENCIAIS):
            raise ValueError("Potencial inválido.")
        return "potencial = %s", [valor], ("l.potencial IS DISTINCT FROM %s", [valor]), None
    if acao == "responsavel":
        valor = payload.get("valor")
        if valor in (None, "", 0, "0", "sem"):
            return "id_executivo = NULL", [], ("l.id_executivo IS NOT NULL", []), None
        if not str(valor).isdigit():
            raise ValueError("Responsável inválido.")
        exec_id = int(valor)
        return "id_executivo = %s", [exec_id], ("l.id_executivo IS DISTINCT FROM %s", [exec_id]), None
    raise ValueError("Ação desconhecida.")


@bp.route("/api/leads/lote", methods=["POST"])
@centralcomm_required_api
def api_lote():
    """Ação em massa numa única transação: status, desqualificar, potencial ou responsável."""
    payload = request.get_json(silent=True) or {}
    try:
        ids = _ids_do_lote(payload)
        set_sql, set_params, (cond_sql, cond_params), descricao = _sql_do_lote(payload.get("acao"), payload)
    except ValueError as exc:
        return _erro(str(exc))

    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE cadu_leads l
                   SET {set_sql}, updated_at = CURRENT_TIMESTAMP
                 WHERE l.id = ANY(%s) AND {cond_sql}
             RETURNING l.id
                """,
                [*set_params, ids, *cond_params],
            )
            alterados = [row["id"] for row in cursor.fetchall()]
            if descricao and alterados:
                cursor.execute(
                    """
                    INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_usuario, usuario_nome)
                    SELECT unnest(%s::int[]), 'status_change', %s, %s, %s
                    """,
                    [alterados, descricao, session.get("user_id"), session.get("user_name")],
                )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        current_app.logger.error("leads-v3 lote %s: %s", payload.get("acao"), exc)
        return _erro("Não foi possível aplicar a ação aos leads selecionados.", 500)
    return _ok({"alterados": alterados, "ignorados": len(ids) - len(alterados)})
