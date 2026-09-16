"""Rotas da primeira fase do Creative Analyzer no Studio."""

from urllib.parse import urlparse

from flask import abort, current_app, jsonify, render_template, request, session

from ..creative_modeling_routes import (
    STUDIO_CLIENT_ID,
    studio_or_admin_required,
    studio_or_admin_required_api,
)
from .repository import AnalyzerRepository


def _repository():
    return AnalyzerRepository(legacy_origin=current_app.config.get("CADU_URL"))


def _studio_host():
    configured = urlparse(str(current_app.config.get("STUDIO_URL") or "")).hostname
    return bool(configured and request.host.split(":", 1)[0].lower() == configured.lower())


def _client_id():
    if _studio_host():
        return STUDIO_CLIENT_ID
    value = request.args.get("client_id") or session.get("cliente_id") or session.get("client_id")
    try:
        value = int(value)
    except (TypeError, ValueError):
        abort(400, description="Selecione uma marca válida.")
    if value <= 0:
        abort(400, description="Selecione uma marca válida.")
    return value


@studio_or_admin_required
def analyzer_page(public_id=None):
    return render_template(
        "cadu_studio/analyzer/index.html",
        mc_page="analyzer",
        analysis_id=public_id,
    )


@studio_or_admin_required_api
def analyzer_history():
    try:
        limit = int(request.args.get("limit", "24"))
        offset = int(request.args.get("offset", "0"))
    except ValueError:
        abort(400, description="Paginação inválida.")
    if limit < 1 or limit > 48 or offset < 0 or offset > 100000:
        abort(400, description="Paginação inválida.")
    items, next_offset = _repository().list_history(
        session.get("user_id"), _client_id(), limit=limit, offset=offset
    )
    return jsonify(items=items, next_offset=next_offset, mode="read-only")


def register_api_routes(blueprint):
    blueprint.add_url_rule(
        "/api/analyzer/history",
        endpoint="creative_analyzer_history",
        view_func=analyzer_history,
    )


def register_product_routes(blueprint):
    blueprint.add_url_rule(
        "/analyzer",
        endpoint="studio_analyzer",
        view_func=analyzer_page,
    )
    blueprint.add_url_rule(
        "/analyzer/<uuid:public_id>",
        endpoint="studio_analyzer_result",
        view_func=analyzer_page,
    )
