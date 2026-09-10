"""Rotas HTML/JSON do Studio de Treinamentos."""

import logging

from flask import jsonify, render_template, request, session

from ..auth import admin_required, admin_required_api
from ..services.openrouter_service import OpenRouterError
from .repository import TrainingConflictError, TrainingNotFoundError
from .service import TrainingStudioService


logger = logging.getLogger(__name__)


def _service():
    return TrainingStudioService()


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _error(message, status):
    return jsonify({"success": False, "error": str(message)}), status


def _json(optional=False):
    payload = request.get_json(silent=True)
    if payload is None and optional:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Corpo JSON inválido.")
    return payload


def _execute(callback):
    try:
        return callback()
    except TrainingNotFoundError as exc:
        return _error(exc, 404)
    except TrainingConflictError as exc:
        return _error(exc, 409)
    except (ValueError, OpenRouterError, RuntimeError) as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Erro no Studio de Treinamentos")
        return _error("Não foi possível concluir a solicitação.", 500)


@admin_required
def treinamentos_page():
    return render_template("parametros/treinamentos.html")


@admin_required_api
def api_bootstrap():
    return _execute(lambda: _ok(_service().bootstrap(session.get("user_id"))))


@admin_required_api
def api_treinamento(treinamento_id):
    if request.method == "PATCH":
        return _execute(
            lambda: _ok(_service().update_treinamento(treinamento_id, _json()))
        )
    return _execute(lambda: _ok(_service().get_treinamento(treinamento_id)))


@admin_required_api
def api_sessao(sessao_id):
    if request.method == "PATCH":
        return _execute(lambda: _ok(_service().update_sessao(sessao_id, _json())))
    return _execute(lambda: _ok(_service().get_sessao(sessao_id)))


@admin_required_api
def api_import_url(sessao_id):
    return _execute(lambda: _ok(_service().import_url(sessao_id, _json().get("url"))))


@admin_required_api
def api_apply_fonte(sessao_id, fonte_id):
    return _execute(lambda: _ok(_service().apply_fonte(sessao_id, fonte_id)))


@admin_required_api
def api_agent(sessao_id):
    payload = _json()
    message = str(payload.get("message") or "").strip()
    action = str(payload.get("action") or "").strip()
    selection = str(payload.get("selection") or "")
    document = str(payload.get("document") or "")
    instrucao = str(payload.get("instrucao") or "")
    prompt = str(payload.get("prompt") or "")

    def run():
        if action:
            return _ok(
                _service().run_action(
                    sessao_id,
                    action,
                    selection=selection,
                    document=document,
                    instrucao=instrucao,
                    prompt=prompt,
                )
            )
        if not message:
            raise ValueError("Escreva uma instrução ou escolha uma ação.")
        return _ok(
            _service().run_chat(
                sessao_id, message, selection=selection, document=document
            )
        )

    return _execute(run)


@admin_required_api
def api_sessao_imagens(sessao_id):
    if request.method == "GET":
        return _execute(lambda: _ok(_service().list_imagens(sessao_id)))
    payload = _json()
    return _execute(
        lambda: _ok(
            _service().run_action(
                sessao_id,
                "gerar_imagem",
                selection=str(payload.get("selection") or ""),
                document=str(payload.get("document") or ""),
                prompt=str(payload.get("prompt") or ""),
            )
        )
    )


@admin_required_api
def api_consumo(sessao_id):
    return _execute(lambda: _ok(_service().consumo(sessao_id)))


@admin_required_api
def api_pesquisar_canais(treinamento_id):
    return _execute(lambda: _ok(_service().enrich_channels(treinamento_id)))


def register_training_studio_routes(blueprint):
    if getattr(blueprint, "_training_studio_registered", False):
        return
    blueprint.add_url_rule(
        "/treinamentos",
        endpoint="treinamentos",
        view_func=treinamentos_page,
    )
    blueprint.add_url_rule(
        "/api/treinamentos/bootstrap",
        endpoint="treinamentos_bootstrap",
        view_func=api_bootstrap,
    )
    blueprint.add_url_rule(
        "/api/treinamentos/<int:treinamento_id>",
        endpoint="treinamento_item",
        view_func=api_treinamento,
        methods=["GET", "PATCH"],
    )
    blueprint.add_url_rule(
        "/api/sessoes/<int:sessao_id>",
        endpoint="sessao_item",
        view_func=api_sessao,
        methods=["GET", "PATCH"],
    )
    blueprint.add_url_rule(
        "/api/sessoes/<int:sessao_id>/importar-url",
        endpoint="sessao_import_url",
        view_func=api_import_url,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/sessoes/<int:sessao_id>/fontes/<int:fonte_id>/aplicar",
        endpoint="sessao_apply_fonte",
        view_func=api_apply_fonte,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/sessoes/<int:sessao_id>/agente",
        endpoint="sessao_agente",
        view_func=api_agent,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/sessoes/<int:sessao_id>/imagens",
        endpoint="sessao_imagens",
        view_func=api_sessao_imagens,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/sessoes/<int:sessao_id>/consumo",
        endpoint="sessao_consumo",
        view_func=api_consumo,
    )
    blueprint.add_url_rule(
        "/api/treinamentos/<int:treinamento_id>/pesquisar-canais",
        endpoint="treinamento_pesquisar_canais",
        view_func=api_pesquisar_canais,
        methods=["POST"],
    )
    blueprint._training_studio_registered = True
