"""Rotas da tela de fechamento e do workspace financeiro do PI."""

import logging

from flask import Blueprint, flash, jsonify, make_response, redirect, render_template, request, url_for

from .auth import login_required, login_required_api
from .pi_documento_service import DocumentoIndisponivelError, PiDocumentoService
from .pi_fechamento_service import HandoffBloqueadoError, PiFechamentoService
from .pi_operacao_repository import PiNaoEncontradoError


logger = logging.getLogger(__name__)
bp = Blueprint("pi_financeiro", __name__)


def _service():
    return PiFechamentoService()


def _erro_json(error, status):
    if isinstance(error, HandoffBloqueadoError):
        return jsonify({
            "success": False,
            "message": "PI com pendências de fechamento.",
            "pendencias": error.pendencias,
        }), status
    return jsonify({"success": False, "message": str(error)}), status


@bp.route("/cadu_pi/<int:id_pi>/fechamento")
@login_required
def fechamento(id_pi):
    from . import db

    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi:
        flash("PI não encontrado.", "error")
        return redirect(url_for("cadu_pi_lista", id_sub_status_pi=3))
    if str(pi.get("id_sub_status_pi")) not in {"3", "4"}:
        flash("Este PI ainda não está em fechamento.", "error")
        return redirect(url_for("cadu_pi_editar", id_pi=id_pi))
    if str(pi.get("id_sub_status_pi")) == "4":
        return redirect(url_for("pi_financeiro.workspace", id_pi=id_pi))
    preview = _service().preview(id_pi)
    documentos = PiDocumentoService().listar(preview)
    return render_template(
        "cadu_pi_fechamento.html",
        pi=pi,
        preview=preview,
        documentos=documentos,
        modo="fechamento",
        somente_leitura=False,
        operacao_modo="pi",
    )


@bp.route("/cadu_pi/<int:id_pi>/financeiro")
@login_required
def workspace(id_pi):
    from . import db

    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi:
        flash("PI não encontrado.", "error")
        return redirect(url_for("cadu_pi_lista", id_sub_status_pi=4, origem="operacao"))
    resultado = _service().resultado(id_pi)
    documentos = PiDocumentoService().listar(resultado)
    return render_template(
        "cadu_pi_financeiro.html",
        pi=pi,
        preview=resultado,
        documentos=documentos,
        modo="financeiro",
        somente_leitura=True,
        operacao_modo="pi",
    )


@bp.get("/api/cadu_pi/<int:id_pi>/resultado-fechamento/preview")
@login_required_api
def api_preview(id_pi):
    try:
        return jsonify({"success": True, "data": _service().preview(id_pi)})
    except PiNaoEncontradoError:
        return _erro_json("PI não encontrado", 404)
    except Exception:
        logger.exception("Erro no preview de fechamento do PI %s", id_pi)
        return _erro_json("Erro ao montar preview de fechamento.", 500)


@bp.route("/cadu_pi/<int:id_pi>/financeiro/documento/<tipo>.pdf")
@login_required
def documento_pdf(id_pi, tipo):
    try:
        pdf, filename = PiDocumentoService().gerar(
            id_pi,
            tipo,
            variante=request.args.get("variante") or "cliente",
            id_campanha=request.args.get("id_campanha") or None,
        )
    except DocumentoIndisponivelError as exc:
        flash(str(exc), "error")
        return redirect(url_for("pi_financeiro.workspace", id_pi=id_pi))
    except PiNaoEncontradoError:
        flash("PI não encontrado.", "error")
        return redirect(url_for("cadu_pi_lista", id_sub_status_pi=4, origem="operacao"))
    except Exception:
        logger.exception("Erro ao gerar PDF %s do PI %s", tipo, id_pi)
        flash("Não foi possível gerar o documento.", "error")
        return redirect(url_for("pi_financeiro.workspace", id_pi=id_pi))

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@bp.get("/api/cadu_pi/<int:id_pi>/resultado-fechamento")
@login_required_api
def api_resultado(id_pi):
    try:
        return jsonify({"success": True, "data": _service().resultado(id_pi)})
    except PiNaoEncontradoError:
        return _erro_json("PI não encontrado", 404)
    except Exception:
        logger.exception("Erro ao ler resultado de fechamento do PI %s", id_pi)
        return _erro_json("Erro ao ler resultado de fechamento.", 500)
