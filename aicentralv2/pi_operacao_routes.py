"""API JSON da Operação do PI."""

import logging
from functools import wraps

from flask import Blueprint, jsonify, request, session

from .auth import login_required_api
from .pi_operacao_repository import (
    PiNaoEncontradoError,
    PropriedadeInvalidaError,
)
from .pi_operacao_service import PiOperacaoService


logger = logging.getLogger(__name__)
bp = Blueprint("pi_operacao", __name__, url_prefix="/api/cadu_pi")


def operacao_required_api(f):
    """Restringe a operação de PI aos usuários internos da CentralComm."""
    @login_required_api
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_centralcomm"):
            return _erro("Acesso restrito à equipe CentralComm.", 403)
        return f(*args, **kwargs)

    return decorated


def _service():
    return PiOperacaoService()


def _ok(data, status=200):
    return jsonify({"success": True, "data": data}), status


def _erro(error, status):
    if isinstance(error, dict):
        message = error.get("message") or "Não foi possível concluir a solicitação."
        details = {key: value for key, value in error.items() if key != "message"}
        payload = {"success": False, "error": message}
        if details:
            payload["data"] = details
        return jsonify(payload), status
    return jsonify({"success": False, "error": str(error)}), status


def _json(opcional=False):
    payload = request.get_json(silent=True)
    if payload is None and opcional:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Corpo JSON inválido.")
    return payload


def _executar(callback):
    try:
        return callback()
    except PiNaoEncontradoError as exc:
        return _erro(exc, 404)
    except PropriedadeInvalidaError as exc:
        return _erro(exc, 400)
    except ValueError as exc:
        return _erro(exc, 400)
    except LookupError as exc:
        return _erro(exc, 404)
    except Exception:
        logger.exception("Erro na API de Operação do PI")
        return _erro("Erro interno ao processar a operação do PI.", 500)


@bp.get("/<int:id_pi>/operacao")
@operacao_required_api
def obter_operacao(id_pi):
    return _executar(lambda: _ok(_service().estado_completo(id_pi)))


@bp.get("/<int:id_pi>/operacao/campanhas/<int:id_campanha>")
@operacao_required_api
def obter_operacao_campanha(id_pi, id_campanha):
    return _executar(
        lambda: _ok(_service().estado_campanha(id_pi, id_campanha))
    )


@bp.get("/<int:id_pi>/operacao/comunicacoes/catalogo")
@bp.get("/<int:id_pi>/operacao/comunicacoes")
@operacao_required_api
def obter_catalogo_comunicacoes(id_pi):
    return _executar(lambda: _ok(_service().catalogo(id_pi)))


@bp.put("/<int:id_pi>/operacao/destinatarios")
@operacao_required_api
def salvar_destinatarios(id_pi):
    def executar():
        payload = _json()
        destinatarios = payload.get("destinatarios")
        if not isinstance(destinatarios, list):
            raise ValueError("destinatarios deve ser uma lista.")
        return _ok(
            _service().salvar_destinatarios(
                id_pi, destinatarios, session["user_id"]
            )
        )

    return _executar(executar)


@bp.post("/<int:id_pi>/operacao/checklist/gerar")
@operacao_required_api
def gerar_checklist(id_pi):
    return _executar(
        lambda: _ok(
            _service().gerar_checklist(
                id_pi, _json(opcional=True), session["user_id"]
            ),
            201,
        )
    )


@bp.patch("/<int:id_pi>/operacao/checklist/<int:item_id>")
@operacao_required_api
def atualizar_checklist(id_pi, item_id):
    def executar():
        payload = _json()
        if "concluido" not in payload or not isinstance(payload["concluido"], bool):
            raise ValueError("concluido deve ser booleano.")
        return _ok(
            _service().atualizar_item(
                id_pi, item_id, payload["concluido"], session["user_id"]
            )
        )

    return _executar(executar)


@bp.post("/<int:id_pi>/operacao/interacoes")
@operacao_required_api
def criar_interacao(id_pi):
    return _executar(
        lambda: _ok(
            _service().criar_interacao(id_pi, _json(), session["user_id"]),
            201,
        )
    )


@bp.post("/<int:id_pi>/operacao/email/preview")
@operacao_required_api
def preview_email(id_pi):
    return _executar(lambda: _ok(_service().preview_email(id_pi, _json())))


@bp.post("/<int:id_pi>/operacao/email/enviar")
@operacao_required_api
def enviar_email(id_pi):
    def executar():
        resultado = _service().enviar_email(
            id_pi, _json(), session["user_id"]
        )
        if not resultado["success"]:
            return _erro(
                {
                    "message": "Um ou mais e-mails não foram enviados.",
                    "envios": resultado["enviados"],
                },
                502,
            )
        return _ok(resultado)

    return _executar(executar)
