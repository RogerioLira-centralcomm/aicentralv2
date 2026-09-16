"""Rotas HTML e API do Smart Planner no CentralX."""

from __future__ import annotations

import logging
import os

from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request, url_for

from ..auth import centralcomm_required, centralcomm_required_api
from ..services.openrouter_service import OpenRouterError
from . import canvas as canvas_mod
from . import planner
from . import processor
from .logos import presenter_options
from .public_view import public_view
from .share import HOUSE, public_sheet_url, qr_svg
from .catalog import (
    CHANNEL_CATALOG,
    CHANNEL_GROUPS,
    DEVICE_OPTIONS,
    OBJETIVO_OPTIONS,
    PLAN_MODE_LABELS,
    PRACA_OPTIONS,
    WIZARD_STEPS,
    channels_by_group,
    plan_mode_label,
)
from .helpers import as_dict, as_list, session_public_token
from .materials import save_upload
from .references import capture_file, capture_search, capture_url, discover_campaigns
from .brand import brand_for_client, search_parties
from .editor import editor_context
from .images import regenerate_creative
from .logos import lookup_agency_for_client
from .repository import SessionNotFound, SmartPlannerError, get_by_public_token, merge_dados
from .service import (
    delete_plan,
    history_payload,
    load_owned,
    persist_canais,
    persist_review,
    ritmo_from_payload,
    recent_plans,
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
        "recent_plans": recent_plans(),
    }
    ctx.update(extra)
    return ctx


@bp.route("/")
@centralcomm_required
def index():
    try:
        payload = history_payload()
        flash_error = None
    except Exception:
        logger.exception("Falha ao carregar histórico do Smart Planner")
        payload = {
            "rows": [],
            "total_user": 0,
            "total_base": 0,
            "custo_total": "",
            "custo_total_brl": 0,
        }
        flash_error = "Não foi possível carregar o histórico."
    return render_template(
        "smart_planner/index.html",
        rows=payload["rows"],
        total_user=payload["total_user"],
        total_base=payload["total_base"],
        custo_total=payload.get("custo_total") or "",
        custo_total_brl=payload.get("custo_total_brl") or 0,
        flash_error=flash_error,
        **_page_ctx(),
    )


@bp.route("/novo")
@centralcomm_required
def novo():
    return render_template("smart_planner/start.html", **_page_ctx())


@bp.route("/<token>/briefing")
@centralcomm_required
def briefing(token):
    row = load_owned(token)
    return render_template("smart_planner/wizard.html", **_page_ctx(**wizard_context(row, "briefing")))


@bp.route("/<token>/revisao")
@centralcomm_required
def revisao(token):
    row = load_owned(token)
    return render_template("smart_planner/wizard.html", **_page_ctx(**wizard_context(row, "revisao")))


@bp.route("/<token>/canais")
@centralcomm_required
def canais(token):
    load_owned(token)
    return redirect(url_for("smart_planner.revisao", token=token))


@bp.route("/<token>/gerar")
@centralcomm_required
def gerar(token):
    load_owned(token)
    return redirect(url_for("smart_planner.revisao", token=token))


@bp.route("/<token>/conclusao")
@centralcomm_required
def conclusao(token):
    row = load_owned(token)
    return render_template("smart_planner/wizard.html", **_page_ctx(**wizard_context(row, "conclusao")))


@bp.route("/p/<public_token>")
def publico(public_token):
    row = get_by_public_token(public_token)
    if not row:
        raise SessionNotFound("Este planejamento não está no ar.")
    view = public_view(row)
    view["share_url"] = view.get("share_url") or public_sheet_url(public_token)
    return render_template("smart_planner/public.html", **view)


def _public_document(public_token: str, document: str):
    row = get_by_public_token(public_token)
    if not row:
        raise SessionNotFound("Este planejamento não está no ar.")
    view = public_view(row, document=document)
    if document == "proposal" and not view.get("tem_folha"):
        raise SessionNotFound("Esta proposta comercial não está publicada.")
    if document == "full_plan" and not view.get("tem_completo"):
        raise SessionNotFound("Este planejamento completo não está publicado.")
    view["share_url"] = view.get("document_url")
    return render_template("smart_planner/public_document.html", **view)


@bp.route("/p/<public_token>/proposta")
def publico_proposta(public_token):
    return _public_document(public_token, "proposal")


@bp.route("/p/<public_token>/plano")
def publico_plano(public_token):
    return _public_document(public_token, "full_plan")


@bp.route("/api/p/<public_token>")
def api_publico(public_token):
    row = get_by_public_token(public_token)
    if not row:
        return _error("Este planejamento não está no ar.", 404)
    view = public_view(row)
    view["share_url"] = view.get("share_url") or public_sheet_url(public_token)
    return _ok(view)


@bp.route("/api/p/<public_token>/qr.svg")
def api_publico_qr(public_token):
    row = get_by_public_token(public_token)
    if not row:
        return _error("Quadro público não encontrado.", 404)
    svg = qr_svg(public_sheet_url(public_token))
    if not svg:
        return _error("QR indisponível.", 503)
    return Response(svg, mimetype="image/svg+xml")


def _render_canvas(row, *, force_folha: bool = False):
    ctx = wizard_context(row, "canvas")
    want_folha = force_folha or (request.args.get("folha") or "").strip().lower() in {"1", "true", "folha"}
    dados = as_dict(row.get("dados_detectados"))
    folha = as_dict(dados.get("folha"))
    mode = ctx.get("plan_mode") or "one_page"
    if want_folha or mode == "one_page":
        plan = folha if as_list(folha.get("sections")) else as_dict(row.get("plan_content"))
        ctx["plan_mode"] = "one_page"
        ctx["plan_mode_label"] = plan_mode_label("one_page")
        ctx.update(editor_context(row, ctx.get("share_url") or ""))
        return render_template(
            "smart_planner/canvas.html",
            plan=plan,
            editor=True,
            **_page_ctx(**ctx),
        )
    plan = as_dict(row.get("plan_content"))
    return render_template(
        "smart_planner/canvas.html",
        plan=plan,
        editor=False,
        **_page_ctx(**ctx),
    )


@bp.route("/p/<public_token>/editar")
@centralcomm_required
def canvas_editar(public_token):
    found = get_by_public_token(public_token)
    if not found:
        raise SessionNotFound("Este planejamento não está no ar.")
    return _render_canvas(load_owned(found["session_token"]), force_folha=True)


@bp.route("/<token>/canvas")
@centralcomm_required
def canvas(token):
    row = load_owned(token)
    dados = as_dict(row.get("dados_detectados"))
    mode = (dados.get("plan_mode") or "").strip().lower()
    want_folha = (request.args.get("folha") or "").strip().lower() in {"1", "true", "folha"}
    public = session_public_token(row)
    # Página única (ou ?folha=1) → editor enterprise em /editar.
    if public and (want_folha or mode != "completo"):
        dest = {"public_token": public}
        if want_folha:
            dest["folha"] = "1"
        return redirect(url_for("smart_planner.canvas_editar", **dest))
    # Plano completo: quadro neste path (não cai no form da folha).
    return _render_canvas(row, force_folha=False)


@bp.route("/api/partes")
@centralcomm_required_api
def api_partes():
    kind = (request.args.get("kind") or "cliente").strip().lower()
    if kind not in {"cliente", "agencia"}:
        kind = "cliente"
    rows = search_parties(request.args.get("q") or "", kind, limit=10)
    return _ok({"rows": rows})


@bp.route("/api/marca")
@centralcomm_required_api
def api_marca():
    cliente_id = request.args.get("cliente_id")
    try:
        cliente_id = int(cliente_id) if cliente_id else None
    except (TypeError, ValueError):
        cliente_id = None
    brand = brand_for_client(cliente_id) if cliente_id else {}
    agency = lookup_agency_for_client(cliente_id) if cliente_id else {}
    return _ok({
        "brand": brand,
        "agency": {
            "id": agency.get("id"),
            "name": agency.get("name") or "",
            "logo_url": agency.get("logo_url") or "",
        } if agency.get("name") else {},
    })


@bp.route("/api/criar", methods=["POST"])
@centralcomm_required_api
def api_criar():
    try:
        payload = request.get_json(silent=True) or {}
        row = start_plan(payload.get("plan_mode"), payload)
        token = row["session_token"]
        return _ok({
            "session_token": token,
            "redirect": f"/smart-planner/{token}/briefing",
        })
    except ValueError as exc:
        return _error(exc, 400)


@bp.route("/api/<token>/referencia", methods=["POST"])
@centralcomm_required_api
def api_referencia(token):
    try:
        load_owned(token)
        if request.files:
            uploaded = request.files.get("file")
            if not uploaded or not uploaded.filename:
                return _error("Envie um arquivo.", 400)
            dest = os.path.join(current_app.static_folder, "uploads", "smart_planner")
            path, original = save_upload(uploaded, dest)
            captured = capture_file(path, original)
            return _ok(captured)
        payload = request.get_json(silent=True) or {}
        kind = (payload.get("kind") or "").strip().lower()
        if kind == "url":
            captured = capture_url(payload.get("url") or "")
        elif kind == "search":
            captured = capture_search(
                payload.get("query") or "",
                payload.get("briefing") or "",
                payload.get("scope") or "briefing",
            )
        else:
            return _error("Escolha URL, arquivo ou busca online.", 400)
        return _ok(captured)
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao capturar referência")
        return _error("Não foi possível capturar a referência.", 500)


@bp.route("/api/<token>/campanhas/pesquisa", methods=["POST"])
@centralcomm_required_api
def api_campaign_discovery(token):
    try:
        load_owned(token)
        payload = request.get_json(silent=True) or {}
        return _ok(discover_campaigns(payload.get("query") or "", payload.get("briefing") or ""))
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao pesquisar campanhas")
        return _error("Não foi possível pesquisar campanhas agora.", 500)


@bp.route("/api/<token>/processar", methods=["POST"])
@centralcomm_required_api
def api_processar(token):
    try:
        load_owned(token)
        references = []
        text_in = ""
        if request.files:
            text_in = (request.form.get("text") or "").strip()
            url = (request.form.get("url") or "").strip()
            if url:
                references.append(capture_url(url))
            uploaded = request.files.get("file")
            if uploaded and uploaded.filename:
                dest = os.path.join(current_app.static_folder, "uploads", "smart_planner")
                path, original = save_upload(uploaded, dest)
                references.append(capture_file(path, original))
        else:
            payload = request.get_json(silent=True) or {}
            text_in = (payload.get("text") or "").strip()
            references.extend(item for item in as_list(payload.get("references")) if isinstance(item, dict))
            url = (payload.get("url") or "").strip()
            if url:
                references.append(capture_url(url))
        return _ok(processor.start_processing(token, text_in, references))
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao processar briefing")
        return _error("Não foi possível processar o briefing.", 500)


@bp.route("/api/<token>/processar/status", methods=["GET"])
@centralcomm_required_api
def api_processar_status(token):
    try:
        return _ok(processor.processing_view(load_owned(token)))
    except SessionNotFound as exc:
        return _error(exc, 404)


@bp.route("/api/<token>/revisao", methods=["POST"])
@centralcomm_required_api
def api_revisao(token):
    try:
        load_owned(token)
        persist_review(token, request.get_json(silent=True) or {})
        return _ok({"saved": True, "redirect": f"/smart-planner/{token}/revisao"})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except Exception:
        logger.exception("Falha ao salvar revisão")
        return _error("Não foi possível salvar a revisão.", 500)


@bp.route("/api/<token>/rebrief", methods=["POST"])
@centralcomm_required_api
def api_rebrief(token):
    try:
        load_owned(token)
        persist_review(token, request.get_json(silent=True) or {})
        result = processor.rewrite_from_plan(token)
        return _ok({"briefing": result["briefing"]})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao reescrever briefing")
        return _error("Não foi possível reescrever o briefing.", 500)


@bp.route("/api/<token>/canais", methods=["POST"])
@centralcomm_required_api
def api_canais(token):
    try:
        load_owned(token)
        persist_canais(token, request.get_json(silent=True) or {})
        return _ok({"redirect": f"/smart-planner/{token}/revisao"})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except ValueError as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao salvar canais")
        return _error("Não foi possível salvar canais e verba.", 500)


@bp.route("/api/<token>/ritmo", methods=["POST"])
@centralcomm_required_api
def api_ritmo(token):
    try:
        load_owned(token)
        return _ok(ritmo_from_payload(request.get_json(silent=True) or {}))
    except SessionNotFound as exc:
        return _error(exc, 404)
    except Exception:
        logger.exception("Falha ao calcular ritmo")
        return _error("Não foi possível calcular o voo da campanha.", 500)


@bp.route("/api/<token>/gerar/status", methods=["GET"])
@centralcomm_required_api
def api_gerar_status(token):
    try:
        row = load_owned(token)
        from .progress import progress_view
        from .skills import decorate_step, generation_steps
        view = progress_view(row)
        if not view.get("steps"):
            mode = (request.args.get("mode") or "").strip() or as_dict(row.get("dados_detectados")).get("plan_mode")
            view["steps"] = [decorate_step(item) for item in generation_steps(mode or "one_page")]
            view["mode"] = mode or view.get("mode") or "one_page"
        return _ok(view)
    except SessionNotFound as exc:
        return _error(exc, 404)


@bp.route("/api/<token>/gerar", methods=["POST"])
@centralcomm_required_api
def api_gerar(token):
    try:
        load_owned(token)
        payload = request.get_json(silent=True) or {}
        data = planner.start_generation(token, payload.get("plan_mode"))
        return _ok(data)
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao gerar planejamento")
        return _error("Não foi possível gerar o planejamento.", 500)


@bp.route("/api/<token>/canvas", methods=["GET"])
@centralcomm_required_api
def api_canvas_get(token):
    try:
        row = load_owned(token)
        want_folha = (request.args.get("folha") or "").strip().lower() in {"1", "true", "folha"}
        dados = as_dict(row.get("dados_detectados"))
        folha = as_dict(dados.get("folha"))
        if want_folha or (dados.get("plan_mode") or "").strip().lower() != "completo":
            plan = folha if as_list(folha.get("sections")) else as_dict(row.get("plan_content"))
            if not as_list(plan.get("sections")):
                generated = canvas_mod.generate_canvas(token)
                plan = generated["plan"]
            return _ok({"plan": plan, "editor": editor_context(row)})
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
@centralcomm_required_api
def api_canvas_save(token):
    try:
        load_owned(token)
        payload = request.get_json(silent=True) or {}
        folha = bool(payload.get("folha")) or (request.args.get("folha") or "").strip() in {"1", "true", "folha"}
        canvas_mod.save_plan(token, payload.get("plan") or payload, folha=folha)
        return _ok({"saved": True})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except Exception:
        logger.exception("Falha ao salvar canvas")
        return _error("Não foi possível salvar o canvas.", 500)


@bp.route("/api/<token>/canvas/gerar", methods=["POST"])
@centralcomm_required_api
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


@bp.route("/api/<token>/canvas/imagem", methods=["POST"])
@centralcomm_required_api
def api_canvas_imagem(token):
    try:
        from .cost import bound_session
        from .repository import update_session

        row = load_owned(token)
        dados = as_dict(row.get("dados_detectados"))
        folha = as_dict(dados.get("folha")) or as_dict(row.get("plan_content"))
        if not as_list(folha.get("sections")):
            generated = canvas_mod.generate_canvas(token)
            folha = generated["plan"]
        with bound_session(token):
            folha = regenerate_creative(folha)
        merge_dados(token, {"folha": folha})
        if (dados.get("plan_mode") or "").strip().lower() != "completo":
            update_session(token, {"plan_content": folha})
        return _ok({"plan": folha, "editor": editor_context(load_owned(token))})
    except SessionNotFound as exc:
        return _error(exc, 404)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 422)
    except Exception:
        logger.exception("Falha ao gerar imagem da folha")
        return _error("Não foi possível gerar a imagem.", 500)


@bp.route("/api/<int:session_id>/excluir", methods=["POST"])
@centralcomm_required_api
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
    if request.path.startswith("/smart-planner/p/"):
        return render_template(
            "smart_planner/public_error.html",
            house=HOUSE,
            mensagem=str(exc) or "Este planejamento não está no ar.",
        ), 404
    try:
        payload = history_payload()
    except Exception:
        payload = {
            "rows": [],
            "total_user": 0,
            "total_base": 0,
            "custo_total": "",
            "custo_total_brl": 0,
        }
    return render_template(
        "smart_planner/index.html",
        rows=payload["rows"],
        total_user=payload["total_user"],
        total_base=payload["total_base"],
        custo_total=payload.get("custo_total") or "",
        custo_total_brl=payload.get("custo_total_brl") or 0,
        flash_error=str(exc),
        **_page_ctx(),
    ), 404
