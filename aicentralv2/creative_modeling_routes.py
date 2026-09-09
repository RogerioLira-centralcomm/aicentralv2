"""Rotas HTML/JSON da Modelagem de Criativos."""

import io
import logging
import mimetypes
import zipfile

from flask import Blueprint, abort, jsonify, render_template, request, send_file, session
from werkzeug.utils import secure_filename

from .auth import admin_required, admin_required_api
from .creative_modeling_generation import OpenRouterError
from .creative_modeling_repository import (
    CreativeConflictError,
    CreativeNotFoundError,
)
from .creative_modeling_service import CreativeModelingService
from .creative_modeling_storage import ClientLogoStorage, CreativeAssetStorage


logger = logging.getLogger(__name__)
public_bp = Blueprint(
    "creative_public", __name__, url_prefix="/criativos/publico"
)


def _service():
    return CreativeModelingService()


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
    except CreativeNotFoundError as exc:
        return _error(exc, 404)
    except CreativeConflictError as exc:
        return _error(exc, 409)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 400)
    except Exception:
        logger.exception("Erro na Modelagem de Criativos")
        return _error("Não foi possível concluir a solicitação.", 500)


@admin_required
def modelagem_criativos():
    return render_template("parametros/modelagem_criativos.html")


@admin_required_api
def api_formats():
    return _execute(lambda: _ok(_service().list_formats()))


@admin_required_api
def api_viewer_profiles():
    return _execute(lambda: _ok(_service().list_viewer_profiles()))


@admin_required_api
def api_update_format(format_id):
    return _execute(
        lambda: _ok(_service().update_format_modeling(format_id, _json()))
    )


@admin_required_api
def api_format_modeling_jobs(format_id):
    return _execute(lambda: _ok(_service().list_format_modeling_jobs(format_id)))


@admin_required_api
def api_generate_format_mockup(format_id):
    return _execute(
        lambda: _ok(
            _service().generate_format_mockup(
                format_id,
                request.form.to_dict(),
                request.files.getlist("references"),
                session.get("user_id"),
            ),
            201,
        )
    )


@admin_required_api
def api_refine_format_mockup(job_id):
    return _execute(
        lambda: _ok(
            _service().refine_format_mockup(
                job_id,
                request.form.to_dict(),
                request.files.getlist("references"),
                session.get("user_id"),
            ),
            201,
        )
    )


@admin_required_api
def api_approve_format_mockup(job_id):
    return _execute(
        lambda: _ok(_service().approve_format_mockup(job_id, _json()))
    )


@admin_required_api
def api_archive_format_mockup(job_id):
    def execute():
        _service().archive_format_mockup(job_id)
        return _ok()

    return _execute(execute)


@admin_required_api
def api_clients():
    if request.method == "POST":
        return _execute(lambda: _ok(_service().create_client(_json()), 201))
    return _execute(lambda: _ok(_service().list_clients()))


@admin_required_api
def api_campaign_clients():
    return _execute(lambda: _ok(_service().list_campaign_clients()))


@admin_required_api
def api_analyze_client_brand():
    return _execute(
        lambda: _ok(
            _service().analyze_brand(
                request.form.get("website_url"),
                request.files.get("image"),
            )
        )
    )


@admin_required_api
def api_delete_client(cid):
    def execute():
        service = _service()
        client = service.delete_client(cid)
        ClientLogoStorage().delete(client.get("logo_upload_path"))
        return _ok()

    return _execute(execute)


@admin_required_api
def api_upload_client_logo(cid):
    def execute():
        file_storage = request.files.get("logo")
        storage = ClientLogoStorage()
        new_path = storage.save(file_storage)
        try:
            previous = _service().set_client_logo(cid, new_path)
        except Exception:
            storage.delete(new_path)
            raise
        storage.delete(previous)
        return _ok({"logo_upload_path": new_path})

    return _execute(execute)


@admin_required_api
def api_campaigns():
    if request.method == "POST":
        return _execute(lambda: _ok(_service().create_campaign(_json()), 201))
    return _execute(lambda: _ok(_service().list_campaigns()))


@admin_required_api
def api_campaign_detail(cid):
    return _execute(lambda: _ok(_service().campaign_detail(cid)))


@admin_required_api
def api_create_variation(cid):
    return _execute(
        lambda: _ok(_service().create_variation(cid, _json(optional=True)), 201)
    )


@admin_required_api
def api_variation(vid):
    if request.method == "DELETE":
        def delete():
            _service().delete_variation(vid)
            return _ok()

        return _execute(delete)
    return _execute(lambda: _ok(_service().save_variation(vid, _json())))


@admin_required_api
def api_generate_variation_prompts(vid):
    return _execute(
        lambda: _ok(
            _service().generate_variation_prompts(vid, session.get("user_id"))
        )
    )


@admin_required_api
def api_generate_step_prompt(step_id):
    return _execute(
        lambda: _ok(
            _service().generate_step_prompt(step_id, session.get("user_id")),
            201,
        )
    )


@admin_required_api
def api_review_step_prompt(step_id):
    return _execute(
        lambda: _ok(_service().review_step_prompt(step_id, _json()))
    )


@admin_required_api
def api_generate_step_image(step_id):
    return _execute(
        lambda: _ok(
            _service().generate_step_image(
                step_id,
                request.files.getlist("references"),
                session.get("user_id"),
            ),
            201,
        )
    )


@admin_required_api
def api_generate_step_script(step_id):
    def execute():
        payload = _json()
        return _ok(
            _service().generate_video_script(
                step_id, payload.get("asset_ids"), session.get("user_id")
            ),
            201,
        )

    return _execute(execute)


@admin_required_api
def api_review_step_script(step_id):
    return _execute(
        lambda: _ok(_service().review_step_script(step_id, _json()))
    )


@admin_required_api
def api_prepare_higgsfield(step_id):
    def execute():
        payload = _json()
        return _ok(
            _service().prepare_higgsfield(
                step_id, payload.get("asset_ids"), session.get("user_id")
            ),
            201,
        )

    return _execute(execute)


@admin_required_api
def api_review_asset(asset_id):
    return _execute(lambda: _ok(_service().review_asset(asset_id, _json())))


@admin_required_api
def api_promote_asset(asset_id):
    return _execute(
        lambda: _ok(_service().promote_format_reference(asset_id, _json()))
    )


@admin_required_api
def api_prepare_display_motion(asset_id):
    return _execute(
        lambda: _ok(
            _service().prepare_display_motion(asset_id, session.get("user_id")),
            201,
        )
    )


@admin_required_api
def api_history():
    return _execute(
        lambda: _ok(_service().history(request.args.get("campaign_id")))
    )


@admin_required_api
def api_campaign_assets(cid):
    return _execute(lambda: _ok(_service().campaign_assets(cid)))


@admin_required_api
def api_reorder_campaign_assets(cid):
    return _execute(
        lambda: _ok(_service().reorder_campaign_assets(cid, _json()))
    )


@admin_required_api
def api_campaign_asset(cid, asset_id):
    if request.method == "DELETE":
        def delete():
            _service().delete_campaign_asset(cid, asset_id)
            return _ok()

        return _execute(delete)
    return _execute(
        lambda: _ok(_service().update_campaign_asset(cid, asset_id, _json()))
    )


def _collection_zip(assets, filename):
    memory = io.BytesIO()
    storage = CreativeAssetStorage()
    added = 0
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, asset in enumerate(assets, start=1):
            if asset.get("asset_type") not in ("image", "mockup"):
                continue
            path = storage.absolute_generated_path(asset.get("asset_url"))
            if path is None:
                continue
            label = secure_filename(asset.get("title") or asset.get("format_name") or "criativo")
            archive.write(path, f"{index:02d}_{label or 'criativo'}{path.suffix.lower()}")
            added += 1
    if not added:
        raise ValueError("Nenhuma imagem local está disponível para download.")
    memory.seek(0)
    return send_file(
        memory,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{secure_filename(filename) or 'criativos'}.zip",
    )


@admin_required_api
def api_download_campaign_assets(cid):
    def execute():
        service = _service()
        campaign = service.campaign_detail(cid)
        assets = service.campaign_assets(cid)
        return _collection_zip(assets, campaign["name"])

    return _execute(execute)


@admin_required_api
def api_public_collections(cid):
    if request.method == "POST":
        return _execute(
            lambda: _ok(
                _service().create_public_collection(
                    cid, _json(), session.get("user_id")
                ),
                201,
            )
        )
    return _execute(lambda: _ok(_service().list_public_collections(cid)))


@admin_required_api
def api_revoke_public_collection(cid, collection_id):
    def execute():
        _service().revoke_public_collection(cid, collection_id)
        return _ok()

    return _execute(execute)


@public_bp.get("/<token>")
def public_collection(token):
    try:
        collection = _service().public_collection(token)
    except CreativeNotFoundError:
        abort(404)
    return render_template(
        "public/creative_collection.html",
        collection=collection,
        public_token=token,
    )


@public_bp.get("/<token>/download")
def public_collection_download(token):
    try:
        collection = _service().public_collection(token)
        return _collection_zip(collection["assets"], collection["title"])
    except (CreativeNotFoundError, ValueError):
        abort(404)


@public_bp.get("/<token>/asset/<int:asset_id>")
def public_collection_asset(token, asset_id):
    try:
        asset = _service().public_collection_asset(token, asset_id)
        path = CreativeAssetStorage().absolute_generated_path(asset["asset_url"])
        if path is None:
            abort(404)
        response = send_file(
            path,
            mimetype=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            conditional=True,
        )
        response.headers["Cache-Control"] = "private, max-age=300"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except CreativeNotFoundError:
        abort(404)


def register_creative_modeling_routes(blueprint):
    """Acopla a feature ao blueprint `parametros` antes do primeiro registro."""
    if getattr(blueprint, "_creative_modeling_registered", False):
        return
    blueprint.add_url_rule(
        "/modelagem-criativos",
        endpoint="modelagem_criativos",
        view_func=modelagem_criativos,
    )
    blueprint.add_url_rule(
        "/api/formats", endpoint="creative_formats", view_func=api_formats
    )
    blueprint.add_url_rule(
        "/api/viewer-profiles",
        endpoint="creative_viewer_profiles",
        view_func=api_viewer_profiles,
    )
    blueprint.add_url_rule(
        "/api/formats/<int:format_id>",
        endpoint="creative_update_format",
        view_func=api_update_format,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/formats/<int:format_id>/modeling-jobs",
        endpoint="creative_format_modeling_jobs",
        view_func=api_format_modeling_jobs,
    )
    blueprint.add_url_rule(
        "/api/formats/<int:format_id>/mockups/generate",
        endpoint="creative_generate_format_mockup",
        view_func=api_generate_format_mockup,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-modeling-jobs/<int:job_id>/refine",
        endpoint="creative_refine_format_mockup",
        view_func=api_refine_format_mockup,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-modeling-jobs/<int:job_id>/approve",
        endpoint="creative_approve_format_mockup",
        view_func=api_approve_format_mockup,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/format-modeling-jobs/<int:job_id>",
        endpoint="creative_archive_format_mockup",
        view_func=api_archive_format_mockup,
        methods=["DELETE"],
    )
    blueprint.add_url_rule(
        "/api/clients",
        endpoint="creative_clients",
        view_func=api_clients,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/campaign-clients",
        endpoint="creative_campaign_clients",
        view_func=api_campaign_clients,
    )
    blueprint.add_url_rule(
        "/api/clients/analyze-brand",
        endpoint="creative_analyze_client_brand",
        view_func=api_analyze_client_brand,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>",
        endpoint="creative_delete_client",
        view_func=api_delete_client,
        methods=["DELETE"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>/logo",
        endpoint="creative_client_logo",
        view_func=api_upload_client_logo,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/campaigns",
        endpoint="creative_campaigns",
        view_func=api_campaigns,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>",
        endpoint="creative_campaign_detail",
        view_func=api_campaign_detail,
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/variations",
        endpoint="creative_create_variation",
        view_func=api_create_variation,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/variations/<int:vid>",
        endpoint="creative_variation",
        view_func=api_variation,
        methods=["PUT", "DELETE"],
    )
    blueprint.add_url_rule(
        "/api/variations/<int:vid>/generate-prompts",
        endpoint="creative_generate_variation_prompts",
        view_func=api_generate_variation_prompts,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/steps/<int:step_id>/prompt/generate",
        endpoint="creative_generate_step_prompt",
        view_func=api_generate_step_prompt,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/steps/<int:step_id>/prompt",
        endpoint="creative_review_step_prompt",
        view_func=api_review_step_prompt,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/steps/<int:step_id>/image/generate",
        endpoint="creative_generate_step_image",
        view_func=api_generate_step_image,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/steps/<int:step_id>/script/generate",
        endpoint="creative_generate_step_script",
        view_func=api_generate_step_script,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/steps/<int:step_id>/script",
        endpoint="creative_review_step_script",
        view_func=api_review_step_script,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/steps/<int:step_id>/higgsfield/prepare",
        endpoint="creative_prepare_higgsfield",
        view_func=api_prepare_higgsfield,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/assets/<int:asset_id>/review",
        endpoint="creative_review_asset",
        view_func=api_review_asset,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/assets/<int:asset_id>/promote",
        endpoint="creative_promote_asset",
        view_func=api_promote_asset,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/assets/<int:asset_id>/display-motion/prepare",
        endpoint="creative_prepare_display_motion",
        view_func=api_prepare_display_motion,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/history", endpoint="creative_history", view_func=api_history
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/assets",
        endpoint="creative_campaign_assets",
        view_func=api_campaign_assets,
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/assets/reorder",
        endpoint="creative_reorder_campaign_assets",
        view_func=api_reorder_campaign_assets,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/assets/<int:asset_id>",
        endpoint="creative_campaign_asset",
        view_func=api_campaign_asset,
        methods=["PUT", "DELETE"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/assets/download",
        endpoint="creative_download_campaign_assets",
        view_func=api_download_campaign_assets,
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/public-collections",
        endpoint="creative_public_collections",
        view_func=api_public_collections,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/public-collections/<int:collection_id>/revoke",
        endpoint="creative_revoke_public_collection",
        view_func=api_revoke_public_collection,
        methods=["POST"],
    )
    blueprint._creative_modeling_registered = True
