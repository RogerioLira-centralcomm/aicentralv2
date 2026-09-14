"""HTTP do Trocr. Sem rotas da Mesa 15s, Camadas ou Ads."""

from __future__ import annotations

import mimetypes

from flask import request, send_file, session

from ..auth import admin_required_api
from .swap_csrf import trocr_csrf_required


def register_trocr_routes(blueprint):
    from ..creative_media.studio import register_studio_routes
    register_studio_routes(blueprint)
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
        "/api/format-lab/swap/library",
        endpoint="creative_format_lab_swap_library",
        view_func=api_format_lab_swap_library,
        methods=["GET", "POST", "DELETE"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/video-project",
        endpoint="creative_format_lab_video_project",
        view_func=api_format_lab_video_project,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/script",
        endpoint="creative_format_lab_animate_script",
        view_func=api_format_lab_animate_script,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/still/<filename>",
        endpoint="creative_format_lab_swap_still",
        view_func=api_format_lab_swap_still,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/quote",
        endpoint="creative_format_lab_animate_quote",
        view_func=api_format_lab_animate_quote,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate",
        endpoint="creative_format_lab_animate",
        view_func=api_format_lab_animate,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/<job_id>",
        endpoint="creative_format_lab_animate_status",
        view_func=api_format_lab_animate_status,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/<job_id>/retry",
        endpoint="creative_format_lab_animate_retry",
        view_func=api_format_lab_animate_retry,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/<job_id>/cancel",
        endpoint="creative_format_lab_animate_cancel",
        view_func=api_format_lab_animate_cancel,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/layers",
        endpoint="creative_format_lab_animate_layers",
        view_func=api_format_lab_animate_layers,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/map",
        endpoint="creative_format_lab_animate_map",
        view_func=api_format_lab_animate_map,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/preview",
        endpoint="creative_format_lab_animate_preview",
        view_func=api_format_lab_animate_preview,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/swap/animate/<job_id>/recompose",
        endpoint="creative_format_lab_animate_recompose",
        view_func=api_format_lab_animate_recompose,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/media/assets/<asset_id>/content",
        endpoint="creative_media_asset",
        view_func=api_media_asset,
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
                {
                    "client_id": request.args.get("client_id"),
                    "run_id": request.args.get("run_id"),
                    "media": request.args.get("media"),
                },
                session.get("user_id"),
            ))
        )
    return execute(lambda: ok(service().save_format_lab_swap_history(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_swap_library():
    execute, json_body, ok, service = _http()
    if request.method == "GET":
        return execute(
            lambda: ok(service().load_format_lab_swap_library(
                {
                    "client_id": request.args.get("client_id"),
                    "media": request.args.get("media") or "still",
                },
                session.get("user_id"),
            ))
        )
    if request.method == "DELETE":
        return execute(lambda: ok(service().remove_format_lab_swap_library(json_body(), session.get("user_id"))))
    return execute(lambda: ok(service().add_format_lab_swap_library_still(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_video_project():
    execute, json_body, ok, service = _http()
    if request.method == "GET":
        return execute(
            lambda: ok(service().load_format_lab_video_project(
                {"client_id": request.args.get("client_id")},
                session.get("user_id"),
            ))
        )
    return execute(lambda: ok(service().save_format_lab_video_project(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_script():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().script_format_lab_animate(json_body(), session.get("user_id"))))


@admin_required_api
def api_format_lab_swap_still(filename):
    execute, _json_body, _ok, service = _http()

    def _send():
        path = service().serve_format_lab_swap_still(filename)
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        return send_file(path, mimetype=mime, max_age=86400, conditional=True)

    return execute(_send)


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_quote():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().quote_format_lab_animate(json_body())))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().submit_format_lab_animate(json_body(), session.get("user_id"))))


@admin_required_api
def api_format_lab_animate_status(job_id):
    execute, _json_body, ok, service = _http()
    return execute(lambda: ok(service().format_lab_animate_status(job_id)))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_retry(job_id):
    execute, _json_body, ok, service = _http()
    return execute(lambda: ok(service().retry_format_lab_animate(job_id, session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_cancel(job_id):
    execute, _json_body, ok, service = _http()
    return execute(lambda: ok(service().cancel_format_lab_animate(job_id)))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_layers():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().format_lab_animate_layers(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_map():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().map_format_lab_animate_camadas(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_preview():
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().preview_format_lab_animate(json_body(), session.get("user_id"))))


@admin_required_api
@trocr_csrf_required
def api_format_lab_animate_recompose(job_id):
    execute, json_body, ok, service = _http()
    return execute(lambda: ok(service().recompose_format_lab_animate(job_id, json_body(), session.get("user_id"))))


@admin_required_api
def api_media_asset(asset_id):
    execute, _json_body, _ok, service = _http()

    def _send():
        path, mime = service().serve_media_asset(asset_id)
        return send_file(path, mimetype=mime, max_age=86400, conditional=True)

    return execute(_send)
