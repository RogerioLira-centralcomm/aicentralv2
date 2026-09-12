"""Rotas internas e públicas do produto Places."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request, session

from ..auth import login_required, login_required_api
from . import service
from .brand import PUBLIC_TOKENS
from .images import ImageError
from .repository import PlaceConflict, PlaceNotFound, PlacesError
from .research import ResearchError
from .schema import SOURCE_LABELS

logger = logging.getLogger(__name__)

bp = Blueprint("places", __name__, url_prefix="/places")


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _error(message, status=400):
    return jsonify({"success": False, "error": str(message)}), status


def _places_nav(_current_slug=""):
    try:
        catalog = service.public_catalog()
    except Exception:
        catalog = []
    return [
        {
            "slug": item.get("slug"),
            "title": item.get("title"),
            "code": item.get("code") or "",
        }
        for item in catalog
        if item.get("slug")
    ]


def _public_page(place, *, preview=False):
    return render_template(
        "places/public.html",
        place=place,
        brand=PUBLIC_TOKENS,
        source_labels=SOURCE_LABELS,
        preview=preview,
        places_nav=_places_nav(place.get("slug") if place else ""),
    )


def _desk(**extra):
    ctx = service.list_desk(
        city=request.args.get("city") or "",
        place_type=request.args.get("type") or "",
        status=request.args.get("status") or "",
        q=request.args.get("q") or "",
    )
    ctx.update(extra)
    return ctx


@bp.route("/")
@login_required
def index():
    try:
        ctx = _desk()
        ctx["flash_error"] = None
    except Exception:
        logger.exception("Falha ao carregar Places")
        ctx = {
            "rows": [],
            "airports": [],
            "mapping": [],
            "filters": {"city": "", "place_type": "", "status": "", "q": ""},
            "cities": [],
            "types": [],
            "statuses": [],
            "empty_hint": "SP e RJ têm mais pontos a mapear.",
            "flash_error": "Não foi possível carregar os places. Rode a migration add_cx_places.",
        }
    return render_template("places/index.html", **ctx)


@bp.route("/novo")
@login_required
def novo():
    return render_template("places/edit.html", **service.form_context())


@bp.route("/<int:place_id>")
@login_required
def editar(place_id):
    try:
        from .repository import get_by_id

        return render_template("places/edit.html", **service.form_context(get_by_id(place_id)))
    except PlaceNotFound:
        return render_template("places/index.html", **{**_desk(), "flash_error": "Place não encontrado."})


@bp.route("/api")
@login_required_api
def api_list():
    return _ok(_desk())


@bp.route("/api", methods=["POST"])
@login_required_api
def api_create():
    try:
        return _ok(service.save_place(request.get_json(silent=True) or {}), status=201)
    except (ValueError, PlaceConflict, PlacesError) as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao criar place")
        return _error("Não foi possível criar o place.", 500)


@bp.route("/api/<int:place_id>", methods=["GET"])
@login_required_api
def api_get(place_id):
    try:
        from .repository import get_by_id

        return _ok(service.serialize(get_by_id(place_id)))
    except PlaceNotFound as exc:
        return _error(exc, 404)


@bp.route("/api/<int:place_id>", methods=["PUT"])
@login_required_api
def api_update(place_id):
    try:
        return _ok(service.save_place(request.get_json(silent=True) or {}, place_id=place_id))
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except (ValueError, PlaceConflict, PlacesError) as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao salvar place")
        return _error("Não foi possível salvar o place.", 500)


@bp.route("/api/search")
@login_required_api
def api_search():
    try:
        from .research import search_places

        return _ok(search_places(request.args.get("q") or ""))
    except ResearchError as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao buscar lugar")
        return _error("Não foi possível buscar o lugar.", 500)


@bp.route("/api/<int:place_id>/research", methods=["POST"])
@login_required_api
def api_research(place_id):
    try:
        return _ok(service.apply_research(place_id))
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except ResearchError as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao pesquisar região")
        return _error("Não foi possível pesquisar a região.", 500)


@bp.route("/api/<int:place_id>/review", methods=["POST"])
@login_required_api
def api_review(place_id):
    try:
        return _ok(service.apply_review(place_id))
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except ResearchError as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao revisar place")
        return _error("Não foi possível revisar o place.", 500)


@bp.route("/api/<int:place_id>/import", methods=["POST"])
@login_required_api
def api_import(place_id):
    try:
        return _ok(service.apply_import(place_id))
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except ResearchError as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao finalizar importação do place")
        return _error("Não foi possível finalizar a importação.", 500)


@bp.route("/api/<int:place_id>/suggest-points", methods=["POST"])
@login_required_api
def api_suggest_points(place_id):
    try:
        body = request.get_json(silent=True) or {}
        return _ok(service.apply_suggested_points(place_id, body.get("points")))
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except ResearchError as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao sugerir pontos")
        return _error("Não foi possível sugerir pontos.", 500)


@bp.route("/api/<int:place_id>/images", methods=["POST"])
@login_required_api
def api_images(place_id):
    try:
        body = request.get_json(silent=True) or {}
        return _ok(
            service.apply_images(
                place_id,
                kind=body.get("kind") or "both",
                point_id=body.get("point_id") or "",
            )
        )
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except ImageError as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao gerar imagens do place")
        return _error("Não foi possível gerar as imagens.", 500)


@bp.route("/api/<int:place_id>/publish", methods=["POST"])
@login_required_api
def api_publish(place_id):
    try:
        return _ok(service.publish_place(place_id))
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except ValueError as exc:
        return _error(exc, 400)


@bp.route("/api/<int:place_id>/unpublish", methods=["POST"])
@login_required_api
def api_unpublish(place_id):
    try:
        return _ok(service.unpublish_place(place_id))
    except PlaceNotFound as exc:
        return _error(exc, 404)


@bp.route("/p")
def publico_indice():
    try:
        places = service.public_catalog()
    except Exception:
        logger.exception("Falha ao listar places públicos")
        places = []
    return render_template(
        "places/public_index.html",
        places=places,
        brand=PUBLIC_TOKENS,
        source_labels=SOURCE_LABELS,
    )


@bp.route("/p/<slug>")
def publico(slug):
    try:
        place = service.public_place(slug)
    except PlaceNotFound:
        return render_template("erro_publico.html", mensagem="Este place não está disponível."), 404
    except Exception:
        logger.exception("Falha ao abrir place público")
        return render_template("erro_publico.html", mensagem="Este place não está disponível."), 404
    return _public_page(place, preview=False)


@bp.route("/preview/<token>")
def preview(token):
    if "user_id" not in session:
        return render_template("erro_publico.html", mensagem="Prévia restrita."), 404
    try:
        place = service.preview_place(token)
    except PlaceNotFound:
        return render_template("erro_publico.html", mensagem="Prévia não encontrada."), 404
    return _public_page(place, preview=True)


@bp.route("/api/p/<slug>/inquiry", methods=["POST"])
def api_inquiry(slug):
    try:
        return _ok(service.create_inquiry(slug, request.get_json(silent=True) or {}), status=201)
    except PlaceNotFound as exc:
        return _error(exc, 404)
    except PlacesError as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Falha ao gravar interesse de place")
        return _error("Não foi possível enviar o pedido.", 500)
