"""Rotas HTTP da Camadas V2."""

import logging

from flask import jsonify, render_template, request, session

from .schemas import strip_client_injections

from ..auth import admin_required, admin_required_api
from ..creative_modeling_generation import OpenRouterError
from .repositories import CamadasConflictError, CamadasNotFoundError
from .service import CamadasService

logger = logging.getLogger(__name__)


def _service():
    return CamadasService()


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _error(message, status):
    return jsonify({"success": False, "error": str(message)}), status


def _execute(callback):
    try:
        return callback()
    except CamadasNotFoundError as exc:
        return _error(exc, 404)
    except CamadasConflictError as exc:
        return _error(exc, 409)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Erro na Camadas V2")
        return _error("Não foi possível concluir a solicitação.", 500)


@admin_required_api
def api_creatives_create():
    payload = {
        "brand_id": request.form.get("brand_id") or request.form.get("client_id"),
        "collection_id": request.form.get("collection_id"),
        "name": request.form.get("name") or "",
    }
    return _execute(
        lambda: _ok(
            _service().create_creative(
                request.files.get("file"),
                payload,
                session.get("user_id"),
            )
        )
    )


@admin_required_api
def api_creative_get(creative_id):
    return _execute(lambda: _ok(_service().get_creative(creative_id)))


@admin_required_api
def api_job_get(job_id):
    return _execute(lambda: _ok(_service().get_job(job_id)))


def _json():
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Corpo JSON inválido.")
    return strip_client_injections(payload)


@admin_required_api
def api_segment(creative_id):
    payload = _json()
    return _execute(lambda: _ok(_service().segment_point(creative_id, payload)))


@admin_required_api
def api_refine_mask(element_id):
    payload = _json()
    return _execute(lambda: _ok(_service().refine_element_mask(element_id, payload)))


@admin_required_api
def api_element_patch(element_id):
    payload = _json()
    return _execute(lambda: _ok(_service().patch_element(element_id, payload)))


@admin_required_api
def api_scene_patch(creative_id):
    payload = _json()
    return _execute(lambda: _ok(_service().patch_scene(creative_id, payload)))


@admin_required
def html_stage_page():
    return render_template("parametros/lab/camadas_html_stage.html")


@admin_required_api
def api_brand_assets(brand_id):
    payload = {
        "collection_id": request.args.get("collection_id"),
        "kind": request.args.get("kind"),
        "provenance": request.args.get("provenance"),
        "q": request.args.get("q") or request.args.get("query"),
    }
    return _execute(lambda: _ok(_service().list_brand_library(brand_id, payload)))


@admin_required_api
def api_brand_collections_create(brand_id):
    payload = _json()
    return _execute(lambda: _ok(_service().create_brand_collection(brand_id, payload)))


@admin_required_api
def api_element_publish(element_id):
    payload = _json()
    return _execute(lambda: _ok(_service().publish_element(element_id, payload)))


@admin_required_api
def api_creative_place(creative_id):
    payload = _json()
    return _execute(lambda: _ok(_service().place_asset(creative_id, payload)))


def register_camadas_routes(blueprint):
    if getattr(blueprint, "_camadas_v2_registered", False):
        return
    blueprint.add_url_rule(
        "/api/camadas/v2/creatives",
        endpoint="camadas_v2_creatives_create",
        view_func=api_creatives_create,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/creatives/<creative_id>",
        endpoint="camadas_v2_creative_get",
        view_func=api_creative_get,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/jobs/<job_id>",
        endpoint="camadas_v2_job_get",
        view_func=api_job_get,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/creatives/<creative_id>/segment",
        endpoint="camadas_v2_segment",
        view_func=api_segment,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/elements/<element_id>/mask/refine",
        endpoint="camadas_v2_mask_refine",
        view_func=api_refine_mask,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/elements/<element_id>",
        endpoint="camadas_v2_element_patch",
        view_func=api_element_patch,
        methods=["PATCH"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/creatives/<creative_id>/scene",
        endpoint="camadas_v2_scene_patch",
        view_func=api_scene_patch,
        methods=["PATCH"],
    )
    blueprint.add_url_rule(
        "/camadas/v2/stage",
        endpoint="camadas_v2_html_stage",
        view_func=html_stage_page,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/brands/<brand_id>/assets",
        endpoint="camadas_v2_brand_assets",
        view_func=api_brand_assets,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/brands/<brand_id>/collections",
        endpoint="camadas_v2_brand_collections_create",
        view_func=api_brand_collections_create,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/elements/<element_id>/publish",
        endpoint="camadas_v2_element_publish",
        view_func=api_element_publish,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/camadas/v2/creatives/<creative_id>/place",
        endpoint="camadas_v2_creative_place",
        view_func=api_creative_place,
        methods=["POST"],
    )
    blueprint._camadas_v2_registered = True
