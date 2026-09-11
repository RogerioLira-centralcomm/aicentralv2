"""Rotas HTML e API da mesa de assinaturas."""

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..auth import login_required, login_required_api
from ..services.d4sign_client import D4SignError
from . import service
from .repository import DocumentoNaoEncontrado


bp = Blueprint("assinaturas", __name__, url_prefix="/assinaturas")


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _error(message, status=400):
    return jsonify({"success": False, "error": str(message)}), status


def _user_email():
    return str(session.get("user_email") or "").strip().lower()


@bp.route("/")
@login_required
def mesa():
    return render_template(
        "assinaturas/mesa.html",
        integracao_pronta=service.integration_ready(),
        pendencias=service.badge_count(_user_email()),
    )


@bp.route("/novo")
@login_required
def novo():
    return render_template(
        "assinaturas/novo.html",
        integracao_pronta=service.integration_ready(),
    )


@bp.route("/<int:id_documento>")
@login_required
def viewer(id_documento):
    try:
        payload = service.viewer_payload(
            id_documento,
            _user_email(),
            session.get("user_fullname") or session.get("user_name") or "",
        )
    except DocumentoNaoEncontrado:
        return render_template("assinaturas/mesa.html", integracao_pronta=service.integration_ready()), 404
    except service.IntegracaoPendente as exc:
        return render_template(
            "assinaturas/viewer.html",
            documento={"id": id_documento, "titulo": "Documento", "status": "rascunho",
                       "status_label": "Integração pendente", "signatarios": []},
            embed_url="",
            pode_assinar=False,
            sou_signatario=False,
            erro=str(exc),
        )
    return render_template(
        "assinaturas/viewer.html",
        documento=payload["documento"],
        embed_url=payload["embed_url"],
        pode_assinar=payload["pode_assinar"],
        sou_signatario=payload["sou_signatario"],
        erro="",
    )


@bp.route("/api")
@login_required_api
def api_listar():
    try:
        filtros = {
            "status": request.args.get("status"),
            "tipo_vinculo": request.args.get("tipo_vinculo"),
            "id_vinculo": request.args.get("id_vinculo"),
            "q": request.args.get("q"),
            "minhas": request.args.get("eixo") == "minhas",
            "email": _user_email(),
            "enviados_por": session.get("user_id") if request.args.get("eixo") == "enviados" else None,
        }
        return _ok(service.listar_documentos(filtros))
    except Exception:
        current_app.logger.exception("Falha ao listar documentos da mesa")
        return _error("Não foi possível carregar a mesa de assinaturas.", 500)


@bp.route("/api/badge")
@login_required_api
def api_badge():
    return _ok({"count": service.badge_count(_user_email())})


@bp.route("/api/vinculos")
@login_required_api
def api_vinculos():
    return _ok(service.listar_vinculos(request.args.get("tipo"), request.args.get("q") or ""))


@bp.route("/api", methods=["POST"])
@login_required_api
def api_criar():
    try:
        import json

        raw_signers = request.form.get("signatarios") or "[]"
        signatarios = json.loads(raw_signers) if isinstance(raw_signers, str) else raw_signers
        documento = service.criar_documento(
            request.form.get("titulo"),
            request.files.get("arquivo"),
            signatarios,
            tipo_vinculo=request.form.get("tipo_vinculo") or "interno",
            id_vinculo=request.form.get("id_vinculo") or None,
            vinculo_nome=request.form.get("vinculo_nome") or "",
            workflow=1 if request.form.get("workflow") in {"1", "true", "on"} else 0,
            autor_id=session.get("user_id"),
        )
        return _ok(documento, 201)
    except (service.AssinaturaError, D4SignError, ValueError) as exc:
        return _error(str(exc))
    except Exception:
        current_app.logger.exception("Falha ao criar documento na D4Sign")
        return _error("Não foi possível enviar o documento para assinatura.", 500)


@bp.route("/api/<int:id_documento>")
@login_required_api
def api_detalhe(id_documento):
    try:
        return _ok(service.viewer_payload(
            id_documento,
            _user_email(),
            session.get("user_fullname") or session.get("user_name") or "",
        ))
    except DocumentoNaoEncontrado:
        return _error("Documento não encontrado.", 404)
    except (service.AssinaturaError, D4SignError) as exc:
        return _error(str(exc))


@bp.route("/api/<int:id_documento>/cancelar", methods=["POST"])
@login_required_api
def api_cancelar(id_documento):
    try:
        return _ok(service.cancelar(id_documento))
    except DocumentoNaoEncontrado:
        return _error("Documento não encontrado.", 404)
    except (service.AssinaturaError, D4SignError) as exc:
        return _error(str(exc))


@bp.route("/api/webhook", methods=["POST"])
def api_webhook():
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        result = service.processar_webhook(payload, request.args.get("secret") or "")
        return _ok(result)
    except service.AssinaturaError as exc:
        return _error(str(exc), 401 if "autorização" in str(exc) else 400)
    except Exception:
        current_app.logger.exception("Falha no webhook D4Sign")
        return _error("Não foi possível processar o webhook.", 500)
