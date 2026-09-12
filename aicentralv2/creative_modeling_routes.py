"""Rotas HTML/JSON da Modelagem de Criativos."""

import io
import json
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


MC_DESKS = {
    "preparar": {
        "title": "Roteiro da campanha",
        "lead": "Marca, brief, formato e batidas. O HTML fecha a peça.",
        "panel": "parametros/_mc_gerador.html",
        "studio": True,
    },
    "produzir": {
        "title": "Montar a peça",
        "lead": "A IA gera a foto. Headline, CTA e logo entram no HTML.",
        "panel": "parametros/_mc_variacoes.html",
        "studio": True,
    },
    "bancada": {
        "title": "Bancada 2.0",
        "lead": "Camadas da peça no retângulo. O canal entra no fim.",
        "panel": "parametros/_mc_bancada.html",
        "studio": False,
        "page_js": "js/mc-bancada.js",
    },
    "desdobrar": {
        "title": "Desdobrar o KV",
        "lead": "O mesmo anúncio nos retângulos de mídia.",
        "panel": "parametros/_mc_desdobrar.html",
        "studio": True,
    },
    "biblioteca": {
        "title": "Formatos",
        "lead": "Retângulo, mecânica e referência visual de cada inventário.",
        "panel": "parametros/_mc_biblioteca.html",
        "studio": True,
    },
    "marcas": {
        "title": "Sistema da marca",
        "lead": "Logo, paleta, fontes, peças e regras. Sem oferta de campanha.",
        "panel": "parametros/_mc_clientes.html",
        "studio": True,
    },
    "historico": {
        "title": "Histórico de custo",
        "lead": "O que já foi gasto nesta mesa.",
        "panel": "parametros/_mc_historico.html",
        "studio": True,
    },
    "extrair": {
        "title": "Extrair o template",
        "lead": "Um criativo de referência vira o mapa HTML. Copy fica de fora.",
        "panel": "parametros/_mc_extrair.html",
        "studio": False,
        "page_js": "js/mc-extrair.js",
    },
    "revisao": {
        "title": "Revisar a peça",
        "lead": "Passou ou volta. Sem reescrever copy ou foto.",
        "panel": "parametros/_mc_revisao.html",
        "studio": False,
        "page_js": "js/mc-revisao.js",
    },
    "mesa": {
        "title": "Mesa de Conceito",
        "lead": "Conceito, base, cena, fecha e aprova — nesta ordem.",
        "panel": "parametros/_mc_mesa.html",
        "studio": False,
        "page_js": "js/mc-mesa.js",
    },
    "lab": {
        "title": "Lab de conceito 15s",
        "lead": "Still de aprovação. O chrome do canal fica para depois.",
        "panel": "parametros/_mc_lab.html",
        "studio": False,
    },
    "placas": {
        "title": "Placas da marca",
        "lead": "A marca entra. Os retângulos aparecem juntos. Você liga cada um ao canal.",
        "panel": "parametros/_mc_placas.html",
        "studio": False,
        "page_js": "js/mc-placas.js",
    },
    "camadas": {
        "title": "Camadas do still",
        "lead": "Pessoa só se o recorte for fiel. Papel vira wash. Headline e CTA ficam no HTML.",
        "panel": "parametros/_mc_camadas.html",
        "studio": False,
        "page_js": "js/mc-camadas.js",
    },
    "trocar": {
        "title": "Editar criativo com IA",
        "lead": "Envie um criativo, ajuste o que deseja alterar e gere novas versões sem perder as anteriores.",
        "panel": "parametros/_mc_trocar.html",
        "studio": False,
        "page_js": "js/mc-trocar.js",
    },
    "design-system": {
        "title": "Design System Ads",
        "lead": "Sistema da marca, melhoria por intenção e montagem IAB.",
        "panel": "parametros/_mc_design_system.html",
        "studio": False,
        "page_js": "js/mc-design-system.js",
    },
}


@admin_required
def modelagem_criativos():
    return render_template(
        "parametros/modelagem_criativos.html",
        mc_page="hub",
        mc_title="A peça na mesa",
    )


@admin_required
def modelagem_desk(page):
    spec = MC_DESKS.get(page)
    if not spec:
        abort(404)
    return render_template(
        "parametros/modelagem_desk.html",
        mc_page=page,
        mc_title=spec["title"],
        mc_lead=spec["lead"],
        panel=spec["panel"],
        mc_studio_js=spec["studio"],
        mc_page_js=spec.get("page_js"),
    )


@admin_required_api
def api_format_lab_formats():
    return _execute(lambda: _ok(_service().format_lab_formats()))


@admin_required_api
def api_format_lab_campaigns():
    return _execute(lambda: _ok(_service().format_lab_campaigns()))


@admin_required_api
def api_format_lab_campaign(slug):
    return _execute(lambda: _ok(_service().format_lab_campaign(slug)))


@admin_required_api
def api_format_lab_sessions():
    if request.method == "GET":
        def _list_sessions():
            try:
                return _ok(
                    _service().list_format_lab_sessions({
                        "client_id": request.args.get("client_id"),
                        "format": request.args.get("format") or request.args.get("format_key"),
                        "campaign_slug": request.args.get("campaign_slug"),
                    })
                )
            except Exception:
                logger.exception("GET format-lab/sessions falhou")
                return _ok({"sessions": [], "active": None, "history": []})

        return _execute(_list_sessions)

    def _create_session():
        try:
            return _ok(
                _service().create_format_lab_session(_json(), session.get("user_id")),
                201,
            )
        except (CreativeNotFoundError, CreativeConflictError, ValueError, OpenRouterError):
            raise
        except Exception:
            logger.exception("POST format-lab/sessions falhou")
            raise CreativeConflictError("Não montou a sessão da Mesa. Tente de novo.")

    return _execute(_create_session)


@admin_required_api
def api_format_lab_session(session_id):
    return _execute(lambda: _ok(_service().get_format_lab_session(session_id)))


@admin_required_api
def api_format_lab_quote():
    return _execute(lambda: _ok(_service().format_lab_quote(_json())))


@admin_required_api
def api_format_lab_storyboard(session_id):
    return _execute(
        lambda: _ok(
            _service().storyboard_format_lab_session(
                session_id, _json(), session.get("user_id")
            )
        )
    )


@admin_required_api
def api_format_lab_mockup(session_id):
    return _execute(
        lambda: _ok(
            _service().mockup_format_lab_session(
                session_id, _json(), session.get("user_id")
            )
        )
    )


@admin_required_api
def api_format_lab_run(session_id):
    return _execute(
        lambda: _ok(
            _service().run_format_lab_session(
                session_id, _json(), session.get("user_id")
            )
        )
    )


@admin_required_api
def api_format_lab_patch(session_id):
    return _execute(
        lambda: _ok(
            _service().patch_format_lab_session(
                session_id, _json(), session.get("user_id")
            )
        )
    )


@admin_required_api
def api_format_lab_plates():
    if request.method == "GET":
        return _execute(
            lambda: _ok(_service().list_format_lab_plates(request.args.get("client_id")))
        )
    return _execute(
        lambda: _ok(_service().format_lab_plates(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_plates_item(kit_id):
    return _execute(lambda: _ok(_service().get_format_lab_plates(kit_id)))


@admin_required_api
def api_format_lab_plates_patch():
    return _execute(
        lambda: _ok(_service().patch_format_lab_plates(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_plates_bind():
    return _execute(
        lambda: _ok(_service().bind_format_lab_plates(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_layers_example():
    return _execute(
        lambda: _ok(_service().example_format_lab_layers(session.get("user_id")))
    )


@admin_required_api
def api_format_lab_layers_split():
    return _execute(
        lambda: _ok(_service().split_format_lab_layers(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_swap():
    return _execute(
        lambda: _ok(_service().swap_format_lab(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_swap_read():
    return _execute(
        lambda: _ok(_service().read_format_lab_swap(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_swap_prompt():
    return _execute(
        lambda: _ok(_service().preview_format_lab_swap(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_swap_history():
    if request.method == "GET":
        return _execute(
            lambda: _ok(_service().load_format_lab_swap_history(
                {"client_id": request.args.get("client_id")},
                session.get("user_id"),
            ))
        )
    return _execute(
        lambda: _ok(_service().save_format_lab_swap_history(_json(), session.get("user_id")))
    )


@admin_required_api
def api_format_lab_close(session_id):
    return _execute(
        lambda: _ok(
            _service().close_format_lab_session(
                session_id, _json(), session.get("user_id")
            )
        )
    )


@admin_required_api
def api_format_lab_handoff(session_id):
    return _execute(lambda: _ok(_service().handoff_format_lab_session(session_id)))


@admin_required_api
def api_creative_agent(name):
    return _execute(
        lambda: _ok(_service().run_creative_agent(name, _json()), 200)
    )


@admin_required_api
def api_formats():
    return _execute(lambda: _ok(_service().list_formats()))


@admin_required_api
def api_compose_library():
    return _execute(
        lambda: _ok(
            _service().list_compose_library(
                request.args.get("family"),
                request.args.get("client_id", type=int),
            )
        )
    )


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
def api_brand_design_system(client_id):
    if request.method == "POST":
        return _execute(lambda: _ok(_service().ensure_brand_design_system(client_id)))
    return _execute(lambda: _ok(_service().get_brand_design_system(client_id)))


@admin_required_api
def api_refine_brand_design_system(client_id):
    payload = _json(optional=True)
    return _execute(
        lambda: _ok(
            _service().refine_brand_design_system(
                client_id,
                payload.get("attempts") or 4,
                intent=payload.get("intent"),
            )
        )
    )


@admin_required_api
def api_approve_brand_design_system(client_id):
    return _execute(lambda: _ok(_service().approve_brand_design_system(client_id)))


@admin_required_api
def api_patch_brand_design_system(client_id):
    payload = _json(optional=True)
    return _execute(
        lambda: _ok(
            _service().patch_brand_design_system(
                client_id,
                tokens=payload.get("tokens") if isinstance(payload.get("tokens"), dict) else None,
                ad_copy=payload.get("ad_copy") if isinstance(payload.get("ad_copy"), dict) else None,
                dna=payload.get("dna") if isinstance(payload.get("dna"), dict) else None,
                archetype=payload.get("archetype"),
            )
        )
    )


@admin_required_api
def api_compose_brand_design_system(client_id):
    return _execute(lambda: _ok(_service().compose_brand_design_system(client_id)))


@admin_required_api
def api_loop_brand_design_system(client_id):
    return _execute(lambda: _ok(_service().loop_brand_design_system(client_id)))


@admin_required_api
def api_generate_brand_track(client_id, track_id):
    payload = _json(optional=True)
    return _execute(
        lambda: _ok(
            _service().generate_brand_track(
                client_id, track_id, extra=payload.get("extra") or ""
            )
        )
    )


@admin_required_api
def api_adapt_brand_design_system(client_id):
    payload = _json(optional=True)
    format_key = payload.get("format") or request.args.get("format")
    layers = payload.get("layers") or request.args.get("layers")
    swaps = payload.get("swaps") if isinstance(payload.get("swaps"), list) else None
    return _execute(
        lambda: _ok(
            _service().adapt_brand_design_system(
                client_id,
                format_key,
                layers,
                swaps=swaps,
                archetype=payload.get("archetype"),
            )
        )
    )


@admin_required_api
def api_campaign_design_system(campaign_id):
    if request.method == "POST":
        return _execute(lambda: _ok(_service().ensure_campaign_design_system(campaign_id)))
    return _execute(lambda: _ok(_service().get_campaign_design_system(campaign_id)))


@admin_required_api
def api_adapt_campaign_design_system(campaign_id):
    payload = _json(optional=True)
    format_key = payload.get("format") or request.args.get("format")
    layers = payload.get("layers") or request.args.get("layers")
    swaps = payload.get("swaps") if isinstance(payload.get("swaps"), list) else None
    return _execute(
        lambda: _ok(
            _service().adapt_campaign_design_system(
                campaign_id, format_key, layers, swaps=swaps
            )
        )
    )


@admin_required_api
def api_campaign_clients():
    return _execute(lambda: _ok(_service().list_campaign_clients()))


@admin_required_api
def api_analyze_client_brand():
    images = request.files.getlist("images") or request.files.getlist("image")
    return _execute(
        lambda: _ok(
            _service().analyze_brand(
                request.form.get("website_url"),
                images,
            )
        )
    )


@admin_required_api
def api_enhance_campaign_brief():
    return _execute(lambda: _ok(_service().enhance_campaign_brief(_json())))


@admin_required_api
def api_read_campaign_pack():
    def execute():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = request.form.to_dict()
        files = request.files.getlist("images") or request.files.getlist("image")
        return _ok(_service().read_campaign_pack(payload, files))

    return _execute(execute)


@admin_required_api
def api_delete_client(cid):
    if request.method == "PUT":
        return _execute(lambda: _ok(_service().update_client(cid, _json())))

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
def api_upload_client_brand_assets(cid):
    role = request.form.get("role") or "reference"
    return _execute(
        lambda: _ok(
            _service().upload_client_brand_assets(
                cid,
                request.files.getlist("images"),
                request.form.get("primary_logo") == "true",
                role,
            ),
            201,
        )
    )


@admin_required_api
def api_learn_client_creative_line(cid):
    return _execute(
        lambda: _ok(
            _service().learn_client_creative_line(
                cid,
                request.files.getlist("creatives"),
                request.files.get("logo"),
                request.form.get("logo_url"),
            )
        )
    )


@admin_required_api
def api_primary_client_brand_asset(cid, asset_id):
    return _execute(
        lambda: _ok(_service().set_primary_brand_asset(cid, asset_id))
    )


@admin_required_api
def api_delete_client_brand_asset(cid, asset_id):
    def execute():
        _service().delete_brand_asset(cid, asset_id)
        return _ok()

    return _execute(execute)


@admin_required_api
def api_campaigns():
    if request.method == "POST":
        return _execute(lambda: _ok(_service().create_campaign(_json()), 201))
    return _execute(
        lambda: _ok(_service().list_campaigns(request.args.get("flow_kind")))
    )


@admin_required_api
def api_production_plans():
    return _execute(
        lambda: _ok(_service().create_production_plan(_json()), 201)
    )


@admin_required_api
def api_production_detail(production_id):
    return _execute(lambda: _ok(_service().production_detail(production_id)))


@admin_required_api
def api_generate_scene(scene_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict()
    return _execute(
        lambda: _ok(
            _service().generate_scene(
                scene_id,
                request.files.getlist("references"),
                session.get("user_id"),
                payload.get("render_mode"),
                "draft",
                payload.get("source_asset_id"),
            ),
            201,
        )
    )


@admin_required_api
def api_generate_scene_prompt(scene_id):
    return _execute(
        lambda: _ok(
            _service().generate_scene_prompt(
                scene_id, session.get("user_id"), _json(optional=True)
            ),
            201,
        )
    )


@admin_required_api
def api_refine_scene_asset(scene_id, asset_id):
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form.to_dict()
    return _execute(
        lambda: _ok(
            _service().refine_scene_asset(
                scene_id,
                asset_id,
                payload if isinstance(payload, dict) else {},
                request.files.getlist("references"),
                session.get("user_id"),
            ),
            201,
        )
    )


@admin_required_api
def api_review_scene_prompt(scene_id):
    return _execute(
        lambda: _ok(_service().review_scene_prompt(scene_id, _json()))
    )


@admin_required_api
def api_select_scene_preview_asset(scene_id):
    return _execute(
        lambda: _ok(_service().select_scene_preview_asset(scene_id, _json()))
    )


@admin_required_api
def api_review_scene(scene_id):
    return _execute(lambda: _ok(_service().review_scene(scene_id, _json())))


@admin_required_api
def api_select_simulation_asset(production_id):
    return _execute(
        lambda: _ok(
            _service().select_simulation_asset(production_id, _json())
        )
    )


@admin_required_api
def api_campaign_detail(cid):
    return _execute(lambda: _ok(_service().campaign_detail(cid)))


@admin_required_api
def api_campaign_bancada(cid):
    return _execute(lambda: _ok(_service().save_bancada_document(cid, _json())))


@admin_required_api
def api_campaign_html5(cid):
    def execute():
        memory, filename = _service().html5_package(cid)
        return send_file(
            memory,
            mimetype="application/zip",
            as_attachment=True,
            download_name=secure_filename(filename) or "criativo-html5.zip",
        )

    return _execute(execute)


@admin_required_api
def api_image_credits():
    return _execute(lambda: _ok(_service().image_credits(session.get("user_id"))))


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
def api_unfoldings():
    if request.method != "POST":
        return _execute(lambda: _ok(_service().list_campaigns("unfold")))

    def execute():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = request.form.to_dict()
        for key in (
            "format_ids", "format_template_ids", "locks", "kv_notes",
            "items", "construct_path",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value[:1] in "[{":
                try:
                    payload[key] = json.loads(value)
                except ValueError:
                    pass
        files = request.files.getlist("kv") or request.files.getlist("file")
        created = _service().create_unfolding(
            payload, files, session.get("user_id")
        )
        if str(payload.get("generate") or "").lower() in {"1", "true", "yes"}:
            created = _service().generate_unfolding(
                created["campaign"]["id"],
                session.get("user_id"),
                payload,
            )
        return _ok(created, 201)

    return _execute(execute)


@admin_required_api
def api_example_kv():
    return _execute(lambda: _ok(_service().create_example_kv(), 201))


@admin_required_api
def api_read_kv():
    def execute():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = request.form.to_dict()
        files = request.files.getlist("kv") or request.files.getlist("file")
        return _ok(_service().read_kv(payload, files))

    return _execute(execute)


@admin_required_api
def api_generate_unfolding(cid):
    return _execute(
        lambda: _ok(
            _service().generate_unfolding(
                cid, session.get("user_id"), _json(optional=True)
            )
        )
    )


@admin_required_api
def api_quote_unfolding():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.args.to_dict()
    return _execute(lambda: _ok(_service().quote_unfolding(payload)))


@admin_required_api
def api_unfold_paths():
    return _execute(lambda: _ok(_service().list_unfold_paths()))


@admin_required_api
def api_image_tiers():
    return _execute(lambda: _ok(_service().list_image_tiers()))


@admin_required_api
def api_campaign_publish_quote(cid):
    raw = request.args.get("asset_ids") or ""
    asset_ids = [item for item in raw.split(",") if item.strip()] or None
    return _execute(lambda: _ok(_service().quote_campaign_publish(cid, asset_ids)))


@admin_required_api
def api_campaign_publish(cid):
    return _execute(
        lambda: _ok(
            _service().publish_campaign(
                cid, _json(optional=True), session.get("user_id")
            )
        )
    )


@admin_required_api
def api_prepare_campaign_video(cid):
    return _execute(lambda: _ok(_service().prepare_campaign_video(cid)))


@admin_required_api
def api_publish_scene_asset(scene_id, asset_id):
    payload = _json(optional=True) or {}
    return _execute(
        lambda: _ok(
            _service().publish_scene_asset(
                scene_id,
                asset_id,
                session.get("user_id"),
                payload.get("render_mode"),
            ),
            201,
        )
    )


@admin_required_api
def api_history():
    return _execute(
        lambda: _ok(_service().history(
            request.args.get("campaign_id"),
            request.args.get("flow_kind"),
        ))
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
    for slug in MC_DESKS:
        blueprint.add_url_rule(
            f"/modelagem-criativos/{slug}",
            endpoint=f"modelagem_{slug}",
            view_func=lambda page=slug: modelagem_desk(page),
        )
    blueprint.add_url_rule(
        "/api/format-lab/formats",
        endpoint="creative_format_lab_formats",
        view_func=api_format_lab_formats,
    )
    blueprint.add_url_rule(
        "/api/format-lab/campaigns",
        endpoint="creative_format_lab_campaigns",
        view_func=api_format_lab_campaigns,
    )
    blueprint.add_url_rule(
        "/api/format-lab/campaigns/<slug>",
        endpoint="creative_format_lab_campaign",
        view_func=api_format_lab_campaign,
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions",
        endpoint="creative_format_lab_sessions",
        view_func=api_format_lab_sessions,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions/<session_id>",
        endpoint="creative_format_lab_session",
        view_func=api_format_lab_session,
    )
    blueprint.add_url_rule(
        "/api/format-lab/plates",
        endpoint="creative_format_lab_plates",
        view_func=api_format_lab_plates,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/plates/bind",
        endpoint="creative_format_lab_plates_bind",
        view_func=api_format_lab_plates_bind,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/plates/patch",
        endpoint="creative_format_lab_plates_patch",
        view_func=api_format_lab_plates_patch,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/plates/<int:kit_id>",
        endpoint="creative_format_lab_plates_item",
        view_func=api_format_lab_plates_item,
    )
    blueprint.add_url_rule(
        "/api/format-lab/layers/example",
        endpoint="creative_format_lab_layers_example",
        view_func=api_format_lab_layers_example,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/layers/split",
        endpoint="creative_format_lab_layers_split",
        view_func=api_format_lab_layers_split,
        methods=["POST"],
    )
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
        "/api/format-lab/quote",
        endpoint="creative_format_lab_quote",
        view_func=api_format_lab_quote,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions/<session_id>/storyboard",
        endpoint="creative_format_lab_storyboard",
        view_func=api_format_lab_storyboard,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions/<session_id>/mockup",
        endpoint="creative_format_lab_mockup",
        view_func=api_format_lab_mockup,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions/<session_id>/run",
        endpoint="creative_format_lab_run",
        view_func=api_format_lab_run,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions/<session_id>/patch",
        endpoint="creative_format_lab_patch",
        view_func=api_format_lab_patch,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions/<session_id>/close",
        endpoint="creative_format_lab_close",
        view_func=api_format_lab_close,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/sessions/<session_id>/handoff",
        endpoint="creative_format_lab_handoff",
        view_func=api_format_lab_handoff,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/agents/<name>",
        endpoint="creative_agent_run",
        view_func=api_creative_agent,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>",
        endpoint="creative_design_system_brand",
        view_func=api_brand_design_system,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>/refine",
        endpoint="creative_design_system_brand_refine",
        view_func=api_refine_brand_design_system,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>/approve",
        endpoint="creative_design_system_brand_approve",
        view_func=api_approve_brand_design_system,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>/tokens",
        endpoint="creative_design_system_brand_tokens",
        view_func=api_patch_brand_design_system,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>/compose",
        endpoint="creative_design_system_brand_compose",
        view_func=api_compose_brand_design_system,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>/loop",
        endpoint="creative_design_system_brand_loop",
        view_func=api_loop_brand_design_system,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>/tracks/<track_id>",
        endpoint="creative_design_system_brand_track",
        view_func=api_generate_brand_track,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/brand/<client_id>/adapt",
        endpoint="creative_design_system_brand_adapt",
        view_func=api_adapt_brand_design_system,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/campaign/<campaign_id>",
        endpoint="creative_design_system_campaign",
        view_func=api_campaign_design_system,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/design-system/campaign/<campaign_id>/adapt",
        endpoint="creative_design_system_campaign_adapt",
        view_func=api_adapt_campaign_design_system,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/formats", endpoint="creative_formats", view_func=api_formats
    )
    blueprint.add_url_rule(
        "/api/compose-library",
        endpoint="creative_compose_library",
        view_func=api_compose_library,
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
        "/api/campaigns/enhance-brief",
        endpoint="creative_enhance_campaign_brief",
        view_func=api_enhance_campaign_brief,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/read-pack",
        endpoint="creative_read_campaign_pack",
        view_func=api_read_campaign_pack,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>",
        endpoint="creative_delete_client",
        view_func=api_delete_client,
        methods=["PUT", "DELETE"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>/logo",
        endpoint="creative_client_logo",
        view_func=api_upload_client_logo,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>/brand-assets",
        endpoint="creative_client_brand_assets_upload",
        view_func=api_upload_client_brand_assets,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>/creative-line/analyze",
        endpoint="creative_client_line_analyze",
        view_func=api_learn_client_creative_line,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>/brand-assets/<int:asset_id>/primary",
        endpoint="creative_client_brand_asset_primary",
        view_func=api_primary_client_brand_asset,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/clients/<int:cid>/brand-assets/<int:asset_id>",
        endpoint="creative_client_brand_asset_delete",
        view_func=api_delete_client_brand_asset,
        methods=["DELETE"],
    )
    blueprint.add_url_rule(
        "/api/campaigns",
        endpoint="creative_campaigns",
        view_func=api_campaigns,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/production-plans",
        endpoint="creative_production_plans",
        view_func=api_production_plans,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/productions/<int:production_id>",
        endpoint="creative_production_detail",
        view_func=api_production_detail,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/generate",
        endpoint="creative_generate_scene",
        view_func=api_generate_scene,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/prompt/generate",
        endpoint="creative_generate_scene_prompt",
        view_func=api_generate_scene_prompt,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/prompt",
        endpoint="creative_review_scene_prompt",
        view_func=api_review_scene_prompt,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/image/generate",
        endpoint="creative_generate_scene_image",
        view_func=api_generate_scene,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/assets/<int:asset_id>/refine",
        endpoint="creative_refine_scene_asset",
        view_func=api_refine_scene_asset,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/assets/<int:asset_id>/publish",
        endpoint="creative_publish_scene_asset",
        view_func=api_publish_scene_asset,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/image-tiers",
        endpoint="creative_image_tiers",
        view_func=api_image_tiers,
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/publish-quote",
        endpoint="creative_campaign_publish_quote",
        view_func=api_campaign_publish_quote,
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/publish",
        endpoint="creative_campaign_publish",
        view_func=api_campaign_publish,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/video/prepare",
        endpoint="creative_prepare_campaign_video",
        view_func=api_prepare_campaign_video,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/preview-asset",
        endpoint="creative_select_scene_preview_asset",
        view_func=api_select_scene_preview_asset,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/scenes/<int:scene_id>/review",
        endpoint="creative_review_scene",
        view_func=api_review_scene,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/productions/<int:production_id>/simulation-asset",
        endpoint="creative_select_simulation_asset",
        view_func=api_select_simulation_asset,
        methods=["PUT"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>",
        endpoint="creative_campaign_detail",
        view_func=api_campaign_detail,
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/bancada",
        endpoint="creative_campaign_bancada",
        view_func=api_campaign_bancada,
        methods=["PATCH"],
    )
    blueprint.add_url_rule(
        "/api/campaigns/<int:cid>/html5",
        endpoint="creative_campaign_html5",
        view_func=api_campaign_html5,
    )
    blueprint.add_url_rule(
        "/api/image-credits",
        endpoint="creative_image_credits",
        view_func=api_image_credits,
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
        "/api/unfoldings",
        endpoint="creative_unfoldings",
        view_func=api_unfoldings,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/unfoldings/example-kv",
        endpoint="creative_example_kv",
        view_func=api_example_kv,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/unfoldings/read-kv",
        endpoint="creative_read_kv",
        view_func=api_read_kv,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/unfoldings/quote",
        endpoint="creative_quote_unfolding",
        view_func=api_quote_unfolding,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/unfoldings/paths",
        endpoint="creative_unfold_paths",
        view_func=api_unfold_paths,
    )
    blueprint.add_url_rule(
        "/api/unfoldings/<int:cid>/generate",
        endpoint="creative_generate_unfolding",
        view_func=api_generate_unfolding,
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


@admin_required
def modeling_ux_states():
    return render_template("parametros/mesa/states.html")


@admin_required
def trocr_ux_states():
    return render_template("parametros/trocr/states.html")


@admin_required
def design_system_brand_specimen(client_id):
    try:
        html = _service().render_brand_design_system(
            client_id,
            request.args.get("format"),
            request.args.get("layers"),
            highlight=request.args.get("highlight"),
        )
    except CreativeNotFoundError:
        abort(404)
    except ValueError:
        abort(400)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@admin_required
def design_system_campaign_specimen(campaign_id):
    try:
        html = _service().render_campaign_design_system(
            campaign_id,
            request.args.get("format"),
            request.args.get("layers"),
            highlight=request.args.get("highlight"),
        )
    except CreativeNotFoundError:
        abort(404)
    except ValueError:
        abort(400)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def register_modeling_ux_lab(app):
    """Rotas de validação visual — fora de MC_DESKS para não entrar no nav."""
    if getattr(app, "_modeling_ux_lab_registered", False):
        return
    app.add_url_rule(
        "/lab/modelagem/states",
        endpoint="modeling_ux_states",
        view_func=modeling_ux_states,
    )
    app.add_url_rule(
        "/lab/trocr/states",
        endpoint="trocr_ux_states",
        view_func=trocr_ux_states,
    )
    app.add_url_rule(
        "/lab/design-system/marca/<client_id>",
        endpoint="design_system_brand_specimen",
        view_func=design_system_brand_specimen,
    )
    app.add_url_rule(
        "/lab/design-system/campanha/<campaign_id>",
        endpoint="design_system_campaign_specimen",
        view_func=design_system_campaign_specimen,
    )
    app._modeling_ux_lab_registered = True
