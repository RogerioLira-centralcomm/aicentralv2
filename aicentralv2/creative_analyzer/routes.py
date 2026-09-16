"""Rotas da primeira fase do Creative Analyzer no Studio."""

from urllib.parse import urlparse
from pathlib import Path
import re

from flask import abort, current_app, jsonify, render_template, request, send_file, session

from ..creative_modeling_routes import (
    STUDIO_CLIENT_ID,
    studio_or_admin_required,
    studio_or_admin_required_api,
)
from ..creative_format_lab.swap_csrf import get_or_create_token, trocr_csrf_required
from ..services.openrouter_service import OpenRouterError
from .repository import AnalyzerRepository
from .service import AnalyzerService
from .storage import AnalyzerStorage

PUBLIC_TOKEN = re.compile(r"^[A-Za-z0-9_-]{40,80}$")


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
        analyzer_csrf=get_or_create_token(),
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
    return jsonify(items=items, next_offset=next_offset, mode="unified")


def _private_payload(row):
    if not row:
        abort(404)
    data = dict(row)
    for key, value in list(data.items()):
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
    data.pop("error_message", None)
    return data


@studio_or_admin_required_api
@trocr_csrf_required
def analyzer_create():
    upload = request.files.get("file")
    if not upload:
        return jsonify(error="Escolha uma imagem."), 400
    repository = _repository()
    try:
        service = AnalyzerService(repository)
        extension = Path(upload.filename or "").suffix.lower()
        method = service.analyze_video if extension in {".mp4", ".mov", ".webm"} else service.analyze_image
        row = method(upload, user_id=session.get("user_id"), client_id=_client_id(), context=request.form.get("context", ""))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except OpenRouterError as exc:
        return jsonify(error=str(exc)), 502
    except Exception:
        current_app.logger.exception("Falha ao analisar imagem no Studio")
        try:
            repository.connection.rollback()
        except Exception:
            pass
        return jsonify(error="Não foi possível analisar o criativo."), 500
    return jsonify(analysis=_private_payload(row)), 201


@studio_or_admin_required_api
def analyzer_detail(public_id):
    row = _repository().get_analysis(str(public_id), _client_id())
    return jsonify(analysis=_private_payload(row))


@studio_or_admin_required_api
def analyzer_asset(public_id, kind):
    if kind not in {"source", "thumbnail", "frame-0", "frame-1", "frame-2", "frame-3"}:
        abort(404)
    if not _repository().get_analysis(str(public_id), _client_id()):
        abort(404)
    path, mime = AnalyzerStorage().read(str(public_id), kind)
    if path is None:
        abort(404)
    response = send_file(path, mimetype=mime, conditional=True)
    response.headers["Cache-Control"] = "private, max-age=300"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noimageindex"
    return response


@studio_or_admin_required_api
@trocr_csrf_required
def analyzer_share(public_id):
    repository = _repository()
    if request.method == "DELETE":
        if not repository.revoke_share(str(public_id), _client_id()):
            abort(404)
        return jsonify(revoked=True)
    share = repository.create_share(str(public_id), _client_id(), session.get("user_id"))
    if not share:
        abort(404)
    from ..product_domains import product_url

    return jsonify(url=product_url("studio", f"/analyzer/public/{share['token']}"), expires_at=None), 201


def _public_analysis(token):
    if not PUBLIC_TOKEN.fullmatch(str(token or "")):
        abort(404)
    row = _repository().public_analysis(token)
    if not row:
        abort(404)
    return row


def analyzer_public(token):
    response = current_app.make_response(render_template(
        "cadu_studio/analyzer/public.html",
        analysis=_private_payload(_public_analysis(token)),
        public_token=token,
    ))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def analyzer_public_asset(token, kind):
    if kind not in {"source", "thumbnail", "frame-0", "frame-1", "frame-2", "frame-3"}:
        abort(404)
    analysis = _public_analysis(token)
    path, mime = AnalyzerStorage().read(str(analysis["public_id"]), kind)
    if path is None:
        abort(404)
    response = send_file(path, mimetype=mime, conditional=True)
    response.headers["Cache-Control"] = "private, max-age=300"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noimageindex"
    return response


def register_api_routes(blueprint):
    blueprint.add_url_rule(
        "/api/analyzer/history",
        endpoint="creative_analyzer_history",
        view_func=analyzer_history,
    )
    blueprint.add_url_rule(
        "/api/analyzer/analyses",
        endpoint="creative_analyzer_create",
        view_func=analyzer_create,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/analyzer/analyses/<uuid:public_id>",
        endpoint="creative_analyzer_detail",
        view_func=analyzer_detail,
    )
    blueprint.add_url_rule(
        "/api/analyzer/assets/<uuid:public_id>/<kind>",
        endpoint="creative_analyzer_asset",
        view_func=analyzer_asset,
    )
    blueprint.add_url_rule(
        "/api/analyzer/analyses/<uuid:public_id>/share",
        endpoint="creative_analyzer_share",
        view_func=analyzer_share,
        methods=["POST", "DELETE"],
    )


def register_product_routes(blueprint):
    blueprint.add_url_rule(
        "/analyzer",
        endpoint="studio_analyzer",
        view_func=analyzer_page,
    )
    blueprint.add_url_rule(
        "/analyzer/public/<token>",
        endpoint="studio_analyzer_public",
        view_func=analyzer_public,
    )
    blueprint.add_url_rule(
        "/analyzer/public/<token>/assets/<kind>",
        endpoint="studio_analyzer_public_asset",
        view_func=analyzer_public_asset,
    )
    blueprint.add_url_rule(
        "/analyzer/<uuid:public_id>",
        endpoint="studio_analyzer_result",
        view_func=analyzer_page,
    )
