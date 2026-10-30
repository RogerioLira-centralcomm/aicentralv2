"""Rotas HTTP da trilha Representação Comercial."""

from __future__ import annotations

import os
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from aicentralv2 import db
from aicentralv2.auth import login_required
from aicentralv2.representacao_comercial.domain import eh_representacao_comercial
from aicentralv2.representacao_comercial.parceiros import sincronizar_trilha_cotacao
from aicentralv2.representacao_comercial.repository import (
    checklist_cotacao_representacao,
    criar_nf_comissao_mes,
    criar_relatorio_pi,
    listar_nf_comissao,
    listar_relatorios_pi,
    marcar_proposta_representacao_pronta,
    marcar_relatorio_enviado_cliente,
    metricas_gestao_representacao,
    registrar_recebimento_nf,
    _upload_dir_pi_rep,
)

bp = Blueprint("representacao_comercial", __name__, url_prefix="/representacao")


@bp.route("/nf-comissao")
@login_required
def nf_comissao_lista():
    id_parceiro = request.args.get("id_parceiro", type=int)
    notas = listar_nf_comissao(id_parceiro)
    return render_template(
        "representacao_comercial/nf_comissao_lista.html",
        notas=notas,
        id_parceiro_filtro=id_parceiro,
    )


@bp.route("/api/cotacoes/<int:cotacao_id>/checklist")
@login_required
def api_checklist_cotacao(cotacao_id):
    return jsonify(checklist_cotacao_representacao(cotacao_id))


@bp.route("/api/cotacoes/<int:cotacao_id>/proposta-pronta", methods=["POST"])
@login_required
def api_proposta_pronta(cotacao_id):
    pronta = request.json.get("pronta", True) if request.is_json else True
    ok = marcar_proposta_representacao_pronta(cotacao_id, bool(pronta))
    return jsonify({"success": ok})


@bp.route("/api/cadu_pi/<int:id_pi>/relatorios", methods=["GET"])
@login_required
def api_listar_relatorios_pi(id_pi):
    return jsonify({"relatorios": listar_relatorios_pi(id_pi)})


@bp.route("/api/cadu_pi/<int:id_pi>/relatorios", methods=["POST"])
@login_required
def api_criar_relatorio_pi(id_pi):
    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi or pi.get("modo_operacao") != "representacao":
        return jsonify({"error": "PI não é de representação comercial."}), 400
    f = request.files.get("arquivo")
    path = nome = None
    if f and f.filename:
        nome = secure_filename(f.filename)
        path = os.path.join(_upload_dir_pi_rep(), f"{id_pi}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{nome}")
        f.save(path)
        path = os.path.relpath(path, current_app.static_folder).replace("\\", "/")
    rid = criar_relatorio_pi(
        id_pi,
        tipo=(request.form.get("tipo") or "parcial").strip(),
        periodo_inicio=request.form.get("periodo_inicio") or None,
        periodo_fim=request.form.get("periodo_fim") or None,
        arquivo_path=path,
        arquivo_nome=nome,
        observacoes=(request.form.get("observacoes") or "").strip() or None,
        created_by=session.get("user_id"),
    )
    return jsonify({"success": True, "id": rid})


@bp.route("/api/relatorios/<int:rel_id>/repassar-cliente", methods=["POST"])
@login_required
def api_repassar_relatorio(rel_id):
    ok = marcar_relatorio_enviado_cliente(rel_id)
    return jsonify({"success": ok})


@bp.route("/api/nf-comissao", methods=["POST"])
@login_required
def api_criar_nf():
    data = request.get_json(force=True, silent=True) or {}
    id_parceiro = data.get("id_parceiro")
    competencia_str = data.get("competencia")
    id_pis = data.get("id_pis") or []
    if not id_parceiro or not competencia_str:
        return jsonify({"error": "id_parceiro e competencia são obrigatórios."}), 400
    comp = date.fromisoformat(str(competencia_str)[:10])
    nf_id = criar_nf_comissao_mes(int(id_parceiro), comp, [int(x) for x in id_pis])
    return jsonify({"success": True, "id": nf_id})


@bp.route("/api/nf-comissao/<int:nf_id>/recebimento", methods=["POST"])
@login_required
def api_recebimento_nf(nf_id):
    data = request.get_json(force=True, silent=True) or {}
    valor = float(data.get("valor_recebido") or 0)
    result = registrar_recebimento_nf(nf_id, valor)
    status = 200 if result.get("ok") else 404
    return jsonify(result), status


@bp.route("/api/gestao/metricas")
@login_required
def api_metricas_gestao():
    return jsonify(metricas_gestao_representacao())


def sincronizar_trilha_apos_salvar_cotacao(cotacao_id: int) -> None:
    cotacao = db.obter_cotacao_por_id(cotacao_id)
    if not cotacao or not eh_representacao_comercial(cotacao):
        return
    patch = sincronizar_trilha_cotacao(cotacao)
    db.atualizar_cotacao(cotacao_id, **patch)


@bp.route("/api/cadu_pi/<int:id_pi>/encerramento", methods=["POST"])
@login_required
def api_encerramento_representacao(id_pi):
    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi or pi.get("modo_operacao") != "representacao":
        return jsonify({"error": "PI não é de representação comercial."}), 400
    data = request.get_json(force=True, silent=True) or {}
    obs = (data.get("observacoes") or "").strip()
    prefix = "[Encerramento representação] "
    atual = (pi.get("obs_operacao") or "").strip()
    nova_obs = f"{prefix}{obs}\n{atual}".strip() if obs else atual
    db.atualizar_cadu_pi(id_pi, obs_operacao=nova_obs, id_sub_status_pi=4)
    return jsonify({"success": True})
