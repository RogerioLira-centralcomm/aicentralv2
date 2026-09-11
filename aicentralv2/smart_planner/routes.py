"""Rotas HTML e API do Smart Planner no CentralX."""

from __future__ import annotations

import logging
import os

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from ..auth import login_required, login_required_api
from ..services.openrouter_service import OpenRouterError
from . import canvas as canvas_mod
from . import planner
from . import processor
from .logos import presenter_options
from .share import public_sheet_url, qr_svg
from .catalog import (
    CHANNEL_CATALOG,
    CHANNEL_GROUPS,
    DEVICE_OPTIONS,
    OBJETIVO_OPTIONS,
    PLAN_MODE_LABELS,
    PRACA_OPTIONS,
    WIZARD_STEPS,
    channels_by_group,
)
from .helpers import as_dict
from .materials import extract_pdf, save_upload, scrape_url
from .repository import SessionNotFound, SmartPlannerError, get_by_public_token
from .service import (
    delete_plan,
    history_payload,
    load_owned,
    persist_canais,
    persist_review,
    start_plan,
    wizard_context,
)

logger = logging.getLogger(__name__)

bp = Blueprint("smart_planner", __name__, url_prefix="/smart-planner")


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _error(message, status=400):
    return jsonify({"success": False, "error": str(message)}), status


def _page_ctx(**extra):
    ctx = {
        "channels": CHANNEL_CATALOG,
        "channel_groups": CHANNEL_GROUPS,
        "channel_sections": channels_by_group(),
        "pracas": PRACA_OPTIONS,
        "devices": DEVICE_OPTIONS,
        "objetivos": OBJETIVO_OPTIONS,
        "wizard_steps": WIZARD_STEPS,
        "plan_mode_labels": PLAN_MODE_LABELS,
        "presenter_options": presenter_options(),
        "presenter_brand": "centralcomm",
    }
    ctx.update(extra)
    return ctx


@bp.route("/")
@login_required
def index():
    payload = history_payload()
    return render_template(
        "smart_planner/index.html",
        rows=payload["rows"],
        total_user=payload["total_user"],
        total_base=payload["total_base"],
        **_page_ctx(),
    )


@bp.route("/novo")
@login_required
def novo():
    return render_template("smart_planner/start.html", **_page_ctx())


@bp.route("/<token>/briefing")
@login_required
def briefing(token):
    row = load_owned(token)
    return render_template("smart_planner/wizard.html", **_page_ctx(**wizard_context(row, "briefing")))


@bp.route("/<token>/revisao")
@login_required
def revisao(token):
    row = load_owned(token)
    return render_template("smart_planner/wizard.html", **_page_ctx(**wizard_context(row, "revisao")))


@bp.route("/<token>/canais")
@login_required
def canais(token):
    row = load_owned(token)
    return render_template("smart_planner/wizard.html", **_page_ctx(**wizard_context(row, "canais")))


@bp.route("/<token>/gerar")
@login_required
def gerar(token):
    row = load_owned(token)
    return render_template("smart_planner/wizard.html", **_page_ctx(**wizard_context(row, "gerar")))


@bp.route("/p/<public_token>")
def publico(public_token):
    row = get_by_public_token(public_token)
    if not row:
        raise SessionNotFound("Quadro público não encontrado.")
    plan = as_dict(row.get("plan_content"))
    if not plan.get("sections"):
        generated = canvas_mod.generate_canvas(row["session_token"])
        plan = generated["plan"]
    share = as_dict(plan.get("share"))
    share["url"] = share.get("url") or public_sheet_url(public_token)
    plan["share"] = share
    return render_template(
        "smart_planner/public.html",
        plan=plan,
        token=public_token,
        titulo=share.get("title") or (plan.get("meta") or {}).get("client") or "Página única",
        plan_mode="one_page",
        readonly=True,
    )


@bp.route("/api/p/<public_token>")
def api_publico(public_token):
    row = get_by_public_token(public_token)
    if not row:
        return _error("Quadro público não encontrado.", 404)
    plan = as_dict(row.get("plan_content"))
    if not plan.get("sections"):
        generated = canvas_mod.generate_canvas(row["session_token"])
        plan = generated["plan"]
    share = as_dict(plan.get("share"))
    share["url"] = share.get("url") or public_sheet_url(public_token)
    plan["share"] = share
    return _ok({"plan": plan})


@bp.route("/api/p/<public_token>/qr.svg")
def api_publico_qr(public_token):
    row = get_by_public_token(public_token)
    if not row:
        return _error("Quadro público não encontrado.", 404)
    svg = qr_svg(public_sheet_url(public_token))
    if not svg:
        return _error("QR indisponível.", 503)
    return Response(svg, mimetype="image/svg+xml")


@bp.route("/<token>/canvas")
@login_required
def canvas(token):
    row = load_owned(token)
    plan = as_dict(row.get("plan_content"))
    return render_template(
        "smart_planner/canvas.html",
        plan=plan,
        **_page_ctx(**wizard_context(row, "canvas")),
    )


@bp.route("/api/criar", methods=["POST"])
@login_required_api
def api_criar():
    try:
        payload = request.get_json(silent=True) or {}
        row = start_plan(payload.get("plan_mode"))
        token = row["session_token"]
        return _ok({
            "session_token": token,
            "redirect": f"/smart-planner/{token}/briefing",
        })
    except ValueError as exc:
        return _error(exc, 400)


@bp.route("/api/<token>/processar", methods=["POST"])
@login_required_api
def api_processar(token):
    try:
        load_owned(token)
        references = []
        text_in = ""
        if request.files:
            text_in = (request.form.get("text") or "").strip()
            url = (request.form.get("url") or "").strip()
            if url:
                references.append({"kind": "url", "url": url, "text": scrape_url(url)})
            uploaded = request.files.get("file")
            if uploaded and uploaded.filename:
                dest = os.path.join(current_app.static_folder, "uploads", "smart_planner")
                path, original = save_upload(uploaded, dest)
                references.append({
                    "kind": "pdf",
                    "name": original,
                    "text": extract_pdf(path),
                })
        else:
            payload = request.get_json(silent=True) or {}
            text_in = (payload.get("text") or "").strip()
            url = (payload.get("url") or "").strip()
            if url:
                references.append({"kind": "url", "url": url, "text": scrape_url(url)})
        result = processor.process_briefing(token, text_in, references)
        return _ok({
            "redirect": f"/smart-planner/{token}/revisao",
            "score": result["score"],
        })
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao processar briefing")
        return _error("Não foi possível processar o briefing.", 500)


@bp.route("/api/<token>/revisao", methods=["POST"])
@login_required_api
def api_revisao(token):
    try:
        load_owned(token)
        persist_review(token, request.get_json(silent=True) or {})
        return _ok({"redirect": f"/smart-planner/{token}/canais"})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except Exception:
        logger.exception("Falha ao salvar revisão")
        return _error("Não foi possível salvar a revisão.", 500)


@bp.route("/api/<token>/canais", methods=["POST"])
@login_required_api
def api_canais(token):
    try:
        load_owned(token)
        persist_canais(token, request.get_json(silent=True) or {})
        return _ok({"redirect": f"/smart-planner/{token}/gerar"})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except Exception:
        logger.exception("Falha ao salvar canais")
        return _error("Não foi possível salvar canais e verba.", 500)


@bp.route("/api/<token>/gerar", methods=["POST"])
@login_required_api
def api_gerar(token):
    try:
        load_owned(token)
        planner.run_generation(token)
        canvas_mod.generate_canvas(token)
        return _ok({"redirect": f"/smart-planner/{token}/canvas"})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao gerar planejamento")
        return _error("Não foi possível gerar o planejamento.", 500)


@bp.route("/api/<token>/canvas", methods=["GET"])
@login_required_api
def api_canvas_get(token):
    try:
        row = load_owned(token)
        plan = as_dict(row.get("plan_content"))
        if not plan.get("sections"):
            generated = canvas_mod.generate_canvas(token)
            plan = generated["plan"]
        return _ok({"plan": plan})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao carregar canvas")
        return _error("Não foi possível carregar o canvas.", 500)


@bp.route("/api/<token>/canvas", methods=["POST"])
@login_required_api
def api_canvas_save(token):
    try:
        load_owned(token)
        payload = request.get_json(silent=True) or {}
        canvas_mod.save_plan(token, payload.get("plan") or payload)
        return _ok({"saved": True})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except Exception:
        logger.exception("Falha ao salvar canvas")
        return _error("Não foi possível salvar o canvas.", 500)


@bp.route("/api/<token>/canvas/gerar", methods=["POST"])
@login_required_api
def api_canvas_gerar(token):
    try:
        load_owned(token)
        payload = request.get_json(silent=True) or {}
        generated = canvas_mod.generate_canvas(token, payload.get("presenter"))
        return _ok({"plan": generated["plan"]})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao gerar canvas")
        return _error("Não foi possível gerar o canvas.", 500)


@bp.route("/api/<int:session_id>/excluir", methods=["POST"])
@login_required_api
def api_excluir(session_id):
    try:
        if not delete_plan(session_id):
            return _error("Plano não encontrado ou sem permissão.", 404)
        return _ok({"deleted": True})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except SmartPlannerError as exc:
        return _error(exc, 400)


@bp.app_errorhandler(SessionNotFound)
def _handle_not_found(exc):
    if request.path.startswith("/smart-planner/api/"):
        return _error(exc, 404)
    return render_template("smart_planner/index.html", rows=[], total_user=0, total_base=0, flash_error=str(exc), **_page_ctx()), 404
