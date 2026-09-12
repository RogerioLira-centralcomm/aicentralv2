"""HTTP do Trocr. Sem rotas da Mesa 15s, Camadas ou Ads."""

from __future__ import annotations

import mimetypes

from flask import request, send_file, session

from ..auth import admin_required_api
from .swap_csrf import trocr_csrf_required


def register_trocr_routes(blueprint):
    blueprint.add_url_rule(
        "/api/format-lab/swap",
        endpoint="creative_format_lab_swap",
        view_func=api_format_lab_swap,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/read",
        endpoint="creative_format_lab_swap_read",
        view_func=api_format_lab_swap_read,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/prompt",
        endpoint="creative_format_lab_swap_prompt",
        view_func=api_format_lab_swap_prompt,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/history",
        endpoint="creative_format_lab_swap_history",
        view_func=api_format_lab_swap_history,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/still/<filename>",
        endpoint="creative_format_lab_swap_still",
        view_func=api_format_lab_swap_still,
        methods=["GET"],
    )


def _http():
    from ..creative_modeling_routes import _execute, _json, _ok, _service

    return _execute, _json, _ok, _service


@admin_required_api
@trocr_csrf_required
def api_format_lab_swap():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().swap_format_lab(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_swap_read():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().read_format_lab_swap(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_swap_prompt():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().preview_format_lab_swap(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_swap_history():
    execute, json_body, ok, service = _http()
    if request.method == "GET":
        return execute(
            lambda: ok(service().load_format_lab_swap_history(
                {"client_id": request.args.get("client_id")},
                session.get("user_id"),
            ))
        )
    return execute(lambda: ok(service().save_format_lab_swap_history(json_body(), session.get("user_id"))))


@admin_required_api
def api_format_lab_swap_still(filename):
    execute, _json_body, _ok, service = _http()

    def _send():
        path = service().serve_format_lab_swap_still(filename)
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        return send_file(path, mimetype=mime, max_age=86400, conditional=True)

    return execute(_send)
