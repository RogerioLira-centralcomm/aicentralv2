"""Rotas HTML/JSON da Modelagem de Criativos."""

import io
import json
import logging
import mimetypes
import zipfile
from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from .auth import admin_required, admin_required_api, login_required, login_required_api
from .creative_media.studio_csrf import get_or_create_token as studio_csrf_token
from .creative_media.studio import _studio_reference_masks
from .creative_format_lab.swap_routes import register_trocr_routes
from .creative_format_lab.swap_csrf import get_or_create_token as trocr_csrf_token
from .creative_modeling_generation import OpenRouterError
from .creative_format_registry import catalog_entries
from .cadu_tool_billing import InsufficientToolCredits
from .cadu_skills.repository import credit_position
from .creative_modeling_repository import (
    CreativeConflictError,
    CreativeNotFoundError,
)
from .creative_modeling_service import CreativeModelingService
from .creative_modeling_storage import ClientLogoStorage, CreativeAssetStorage
from .product_domains import product_url, workspace_public_url


logger = logging.getLogger(__name__)
STUDIO_CLIENT_ID = 174
public_bp = Blueprint(
    "creative_public", __name__, url_prefix="/criativos/publico"
)


def _service():
    return CreativeModelingService()


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _error(message, status, extra=None):
    payload = {"success": False, "error": str(message)}
    if extra:
        payload.update(extra)
    return jsonify(payload), status


def _run_extra(exc):
    run = getattr(exc, "run", None)
    if not run:
        return None
    return {"data": {"run": run}}


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
        return _error(exc, 404, _run_extra(exc))
    except CreativeConflictError as exc:
        return _error(exc, 409, _run_extra(exc))
    except InsufficientToolCredits as exc:
        return _error(exc, 402, {"workspace_credits_url": product_url('workspace', '/workspace/app/creditos')})
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 400, _run_extra(exc))
    except Exception as exc:
        logger.exception("Erro na Modelagem de Criativos")
        return _error("Não foi possível concluir a solicitação.", 500, _run_extra(exc))


def _configured_product_host(product):
    key = {'centralx': 'CENTRALX_URL', 'studio': 'STUDIO_URL', 'workspace': 'WORKSPACE_URL'}[product]
    return (urlparse(str(current_app.config.get(key) or '')).hostname or '').lower()


def _host_redirect(product):
    """Move legacy HTML entrypoints without touching API or persisted content."""
    destination = _configured_product_host(product)
    current = (request.host.split(':', 1)[0] or '').lower()
    if not destination or current == destination:
        return None
    query = ('?' + request.query_string.decode('utf-8')) if request.query_string else ''
    return redirect(product_url(product, request.path) + query, code=302)


def _studio_client_scope():
    """Restrict the standalone Studio to its contracted brand profile."""
    return STUDIO_CLIENT_ID if (
        (request.host.split(':', 1)[0] or '').lower() == _configured_product_host('studio')
    ) else None


def _workspace_brand_scope():
    """Whether a creative API call is mounted inside the Workspace product."""
    return request.blueprint == "workspace_brand_api"


def _workspace_brand_ids():
    """Return only brands owned by the organization in the current session."""
    if not _workspace_brand_scope():
        return None
    tenant_id = int(session.get("cliente_id") or 0)
    if not tenant_id:
        return set()
    from .db import get_db
    with get_db().cursor() as cursor:
        cursor.execute("SELECT id FROM cx_clients WHERE crm_client_id = %s", (tenant_id,))
        return {int(row["id"]) for row in cursor.fetchall()}


def studio_or_admin_required(view):
    """Cadu Studio has its own login; CentralX keeps the internal guard."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if (
            request.method in {"GET", "HEAD"}
            and not session.get("user_id")
            and (_studio_client_scope() or _workspace_brand_scope())
        ):
            return redirect(workspace_public_url(), code=302)
        guard = login_required if (_studio_client_scope() or _workspace_brand_scope()) else admin_required
        return guard(view)(*args, **kwargs)
    return wrapped


def studio_or_admin_required_api(view):
    """Apply the product login on Studio without widening CentralX APIs."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        guard = login_required_api if (_studio_client_scope() or _workspace_brand_scope()) else admin_required_api
        return guard(view)(*args, **kwargs)
    return wrapped


def studio_brand_required(view):
    """The standalone Studio must never accept another brand profile."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        client_id = kwargs.get("client_id", kwargs.get("cid", args[0] if args else None))
        if _studio_client_scope() and str(client_id) != str(STUDIO_CLIENT_ID):
            return _error("Esta marca não está disponível neste Studio.", 403)
        if _workspace_brand_scope():
            try:
                allowed = int(client_id) in _workspace_brand_ids()
            except (TypeError, ValueError):
                allowed = False
            if not allowed:
                return _error("Esta marca não pertence à sua organização.", 403)
        return view(*args, **kwargs)
    return wrapped


MC_DESKS = {
    "criar": {
        "title": "Criar uma peça",
        "lead": "O projeto traz o contexto. Você define a direção e leva a peça para o editor.",
        "panel": "",
        "studio": False,
        "page_js": "js/mc-studio-create.js",
    },
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
        "title": "Studio",
        "lead": "Roteiro, referências, cenas e animação.",
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
        "title": "Cadu Media Studio®",
        "lead": "Ajuste a peça. Cada tentativa fica no histórico da marca.",
        "panel": "parametros/_mc_trocar.html",
        "studio": False,
        "page_js": "js/mc-trocar.js",
    },
    "video": {
        "title": "Cadu Media Studio®",
        "lead": "Duas a trinta cenas da biblioteca viram um clipe.",
        "panel": "parametros/_mc_video.html",
        "studio": False,
        "page_js": "js/mc-cadu-video.js",
    },
    "design-system": {
        "title": "Design System Ads",
        "lead": "Sistema da marca, melhoria por intenção e montagem IAB.",
        "panel": "parametros/_mc_design_system.html",
        "studio": False,
        "page_js": "js/mc-design-system.js",
    },
}

# The Studio owns its host, so product-facing URLs stay short. The older
# ``/studio/modelagem-criativos/...`` routes remain as compatibility entries.
STUDIO_SHORT_ROUTES = {
    "modelagem_criar": "criar",
    "modelagem_trocar": "imagem",
    "modelagem_video": "video",
    "modelagem_camadas": "camadas",
    "modelagem_biblioteca": "formatos",
    "modelagem_bancada": "bancada",
    "modelagem_historico": "historico",
    "modelagem_preparar": "roteiro",
    "modelagem_produzir": "producao",
    "modelagem_desdobrar": "desdobrar",
    "modelagem_mesa": "mesa",
    "modelagem_placas": "placas",
}


@studio_or_admin_required
def modelagem_criativos():
    if request.blueprint == "studio" and request.endpoint == "studio.modelagem_criativos":
        return redirect(url_for("studio_product.studio_home"), code=302)
    redirected = _host_redirect('studio')
    if redirected:
        return redirected
    response = make_response(render_template(
        "cadu_studio/home.html",
        mc_page="hub",
        mc_title="A peça na mesa",
        mc_trocr_csrf=studio_csrf_token(),
    ))
    response.headers['Cache-Control'] = 'no-store, private'
    return response


CADU_RETIRED_DESKS = {"extrair", "revisao", "lab"}


@studio_or_admin_required
def modelagem_desk(page):
    # ``/formatos`` is also a product-owned Planner route.  Flask registers
    # the Studio shortcut first, so route it explicitly when this request is
    # on the Planner host instead of redirecting the user to Studio.
    planner_host = (urlparse(str(current_app.config.get('PLANNER_URL') or '')).hostname or '').lower()
    if page == 'biblioteca' and (request.host.split(':', 1)[0] or '').lower() == planner_host:
        return current_app.view_functions['cadu_family.page']('planner', 'formatos')
    # Brand guidance belongs to Workspace, where the brand itself and its
    # governance live. Keep legacy Studio URLs as a direct compatibility hop.
    if page in {"marcas", "design-system"}:
        brand_id = request.args.get('creative_client_id') or request.args.get('brand_id')
        path = f'/workspace/app/marcas/{brand_id}' if str(brand_id or '').isdigit() else '/workspace/app/marcas'
        query = ('?' + request.query_string.decode('utf-8')) if request.query_string else ''
        return redirect(
            product_url('workspace', path) + query,
            code=302,
        )
    if request.blueprint == "studio" and request.endpoint == f"studio.modelagem_{page}":
        return redirect(url_for(f"studio_product.studio_{page}"), code=302)
    if page in CADU_RETIRED_DESKS:
        return redirect(url_for(".modelagem_criativos"))
    spec = MC_DESKS.get(page)
    if not spec:
        abort(404)
    redirected = _host_redirect('studio')
    if redirected:
        return redirected
    if page == "trocar" and request.args.get("ws") == "video":
        args = request.args.to_dict(flat=True)
        args.pop("ws", None)
        return redirect(url_for(".modelagem_video", **args))
    panel = spec["panel"]
    page_js = spec.get("page_js")
    if page == "camadas" and current_app.config.get("CAMADAS_V2_ENABLED"):
        panel = "parametros/_mc_camadas_v2.html"
        page_js = "js/camadas/index.js"
    studio_credit = {}
    if page == "trocar":
        try:
            studio_credit = credit_position(int(session.get('cliente_id') or 0)) or {}
        except Exception:
            logger.warning('Nao foi possivel carregar o saldo do Studio', exc_info=True)
    # Creative Modeling is a Studio product surface. Every desk uses the same
    # standalone frame, so its navigation and work area never inherit CentralX.
    template = (
        "cadu_studio/create.html" if page == "criar"
        else "cadu_studio/trocr.html" if page == "trocar"
        else "cadu_studio/desk.html"
    )
    response = make_response(render_template(
        template,
        mc_page=page,
        mc_title=spec["title"],
        mc_lead=spec["lead"],
        panel=panel,
        mc_studio_js=spec["studio"],
        mc_page_js=page_js,
        # The Trocr routes validate their own CSRF token. Studio/video routes
        # keep using the Studio token, even though both use the same header.
        mc_trocr_csrf=(
            trocr_csrf_token() if page == "trocar"
            else studio_csrf_token() if page in {"criar", "video"}
            else ""
        ),
        mc_workspace_brands=page == 'marcas' and _configured_product_host('workspace') == (request.host.split(':', 1)[0] or '').lower(),
        mc_format_catalog=catalog_entries(),
        mc_reference_masks=_studio_reference_masks() if page == "criar" else [],
        studio_credit=studio_credit,
    ))
    if page in {"criar", "video"}:
        response.headers['Cache-Control'] = 'no-store, private'
    return response


@studio_or_admin_required_api
def api_format_lab_formats():
    return _execute(lambda: _ok(_service().format_lab_formats()))


@studio_or_admin_required_api
def api_format_lab_campaigns():
    return _execute(lambda: _ok(_service().format_lab_campaigns()))


@studio_or_admin_required_api
def api_format_lab_campaign(slug):
    return _execute(lambda: _ok(_service().format_lab_campaign(slug)))


@studio_or_admin_required_api
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
def api_prototype_quote():
    return _execute(lambda: _ok(_service().prototype_quote(_json())))


@admin_required_api
def api_prototype_script():
    return _execute(lambda: _ok(_service().prototype_script(_json(), session.get("user_id"))))


@admin_required_api
def api_prototype_refs():
    return _execute(lambda: _ok(_service().prototype_refs(_json(), session.get("user_id"))))


@admin_required_api
def api_prototype_scenes():
    return _execute(lambda: _ok(_service().prototype_scenes(_json(), session.get("user_id"))))


@admin_required_api
def api_prototype_animate():
    return _execute(lambda: _ok(_service().prototype_animate(_json(), session.get("user_id"))))


@admin_required_api
def api_prototype_video():
    return _execute(lambda: _ok(_service().prototype_video(_json(), session.get("user_id"))))


@admin_required_api
def api_prototype_video_status(job_id):
    return _execute(
        lambda: _ok(
            _service().prototype_video_status(job_id, request.args.get("polling_url"))
        )
    )


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
    from aicentralv2.creative_format_lab.camadas_lab import strip_client_injections

    payload = strip_client_injections(_json())
    return _execute(
        lambda: _ok(_service().split_format_lab_layers(payload, session.get("user_id")))
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
def api_format_registry():
    return _execute(lambda: _ok(_service().format_registry_catalog()))


@admin_required_api
def api_format_registry_entry(key):
    return _execute(lambda: _ok(_service().format_registry_entry(key)))


@admin_required_api
def api_format_lab_train():
    return _execute(lambda: _ok(_service().train_format(_json())))


@admin_required_api
def api_format_assets_resolve():
    return _execute(lambda: _ok(_service().resolve_format_assets(_json())))


@admin_required_api
def api_format_revision():
    if request.method == "GET":
        return _execute(
            lambda: _ok(_service().list_format_revisions(request.args.get("variant_id")))
        )
    return _execute(lambda: _ok(_service().create_format_revision(_json())))


@admin_required_api
def api_format_revision_approve():
    return _execute(lambda: _ok(_service().approve_format_revision(_json())))


@admin_required_api
def api_format_revision_showcase():
    return _execute(lambda: _ok(_service().showcase_format_revision(_json())))


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
def api_viewer_templates():
    return _execute(lambda: _ok(_service().list_viewer_templates()))


@admin_required_api
def api_viewer_template(slug):
    if request.method == "GET":
        return _execute(lambda: _ok(_service().get_viewer_template(slug)))
    return _execute(lambda: _ok(_service().update_viewer_template(slug, _json())))


@admin_required_api
def api_viewer_template_formats(slug):
    return _execute(lambda: _ok(_service().assign_viewer_formats(slug, _json())))


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


@studio_or_admin_required_api
def api_brand_sources():
    if _workspace_brand_scope():
        # The legacy directory spans multiple organizations. New brands are
        # created by the tenant-scoped native Workspace form instead.
        return _ok([])
    return _execute(lambda: _ok(_service().list_brand_sources()))


@studio_or_admin_required_api
def api_clients():
    if request.method == "POST":
        if _studio_client_scope() or _workspace_brand_scope():
            return _error("Cadastre novas marcas pela página Marcas do Workspace.", 403)
        return _execute(lambda: _ok(_service().create_client(_json()), 201))
    def list_scoped_clients():
        clients = _service().list_clients()
        scoped_client_id = _studio_client_scope()
        if scoped_client_id:
            clients = [item for item in clients if int(item.get("id") or 0) == scoped_client_id]
        workspace_ids = _workspace_brand_ids()
        if workspace_ids is not None:
            clients = [item for item in clients if int(item.get("id") or 0) in workspace_ids]
        return _ok(clients)
    return _execute(list_scoped_clients)


@studio_or_admin_required_api
@studio_brand_required
def api_brand_design_system(client_id):
    if request.method == "POST":
        from .design_system_ads.commands import parse_optional_revision

        command = parse_optional_revision(_json(optional=True))
        return _execute(
            lambda: _ok(
                _service().ensure_brand_design_system(
                    client_id, expected_revision=command.expected_revision
                )
            )
        )
    return _execute(lambda: _ok(_service().get_brand_design_system(client_id)))


@studio_or_admin_required_api
@studio_brand_required
def api_refine_brand_design_system(client_id):
    from .design_system_ads.commands import parse_refine_brand

    command = parse_refine_brand(_json(optional=True))
    return _execute(
        lambda: _ok(
            _service().refine_brand_design_system(
                client_id,
                command.attempts or 4,
                intent=command.intent,
                expected_revision=command.expected_revision,
            )
        )
    )


@studio_or_admin_required_api
@studio_brand_required
def api_approve_brand_design_system(client_id):
    from .design_system_ads.commands import parse_approve_brand

    command = parse_approve_brand(_json(optional=True))
    return _execute(
        lambda: _ok(
            _service().approve_brand_design_system(
                client_id, expected_revision=command.expected_revision
            )
        )
    )


@studio_or_admin_required_api
@studio_brand_required
def api_patch_brand_design_system(client_id):
    from .design_system_ads.commands import parse_patch_brand

    command = parse_patch_brand(_json(optional=True))
    return _execute(
        lambda: _ok(
            _service().patch_brand_design_system(
                client_id,
                tokens=command.tokens,
                ad_copy=command.ad_copy,
                dna=command.dna,
                archetype=command.archetype,
                expected_revision=command.expected_revision,
            )
        )
    )


@studio_or_admin_required_api
@studio_brand_required
def api_compose_brand_design_system(client_id):
    from .design_system_ads.commands import parse_optional_revision

    command = parse_optional_revision(_json(optional=True))
    return _execute(
        lambda: _ok(
            _service().compose_brand_design_system(
                client_id, expected_revision=command.expected_revision
            )
        )
    )


@studio_or_admin_required_api
@studio_brand_required
def api_loop_brand_design_system(client_id):
    from .design_system_ads.commands import parse_optional_revision

    command = parse_optional_revision(_json(optional=True))
    return _execute(
        lambda: _ok(
            _service().loop_brand_design_system(
                client_id, expected_revision=command.expected_revision
            )
        )
    )


@studio_or_admin_required_api
@studio_brand_required
def api_generate_brand_track(client_id, track_id):
    from .design_system_ads.commands import parse_optional_revision

    command = parse_optional_revision(_json(optional=True))
    return _execute(
        lambda: _ok(
            _service().generate_brand_track(
                client_id,
                track_id,
                extra=command.extra or "",
                expected_revision=command.expected_revision,
            )
        )
    )


@studio_or_admin_required_api
@studio_brand_required
def api_validate_brand_design_system_render(client_id):
    from .design_system_ads.commands import parse_validate_render

    command = parse_validate_render(_json(optional=True))
    format_key = command.format or request.args.get("format")
    layers = command.layers if command.layers is not None else request.args.get("layers")
    return _execute(
        lambda: _ok(
            _service().validate_brand_design_system_render(
                client_id, format_key, layers
            )
        )
    )


@studio_or_admin_required_api
@studio_brand_required
def api_adapt_brand_design_system(client_id):
    from .design_system_ads.commands import parse_adapt

    command = parse_adapt(_json(optional=True))
    format_key = command.format or request.args.get("format")
    layers = command.layers if command.layers is not None else request.args.get("layers")
    swaps = command.swaps if isinstance(command.swaps, list) else None
    return _execute(
        lambda: _ok(
            _service().adapt_brand_design_system(
                client_id,
                format_key,
                layers,
                swaps=swaps,
                archetype=command.archetype,
                expected_revision=command.expected_revision,
            )
        )
    )


@admin_required_api
def api_campaign_design_system(campaign_id):
    if request.method == "POST":
        from .design_system_ads.commands import parse_campaign_compose

        command = parse_campaign_compose(_json(optional=True))
        return _execute(
            lambda: _ok(
                _service().ensure_campaign_design_system(
                    campaign_id, expected_revision=command.expected_revision
                )
            )
        )
    return _execute(lambda: _ok(_service().get_campaign_design_system(campaign_id)))


@admin_required_api
def api_validate_campaign_design_system_render(campaign_id):
    from .design_system_ads.commands import parse_validate_render

    command = parse_validate_render(_json(optional=True))
    format_key = command.format or request.args.get("format")
    layers = command.layers if command.layers is not None else request.args.get("layers")
    return _execute(
        lambda: _ok(
            _service().validate_campaign_design_system_render(
                campaign_id, format_key, layers
            )
        )
    )


@admin_required_api
def api_adapt_campaign_design_system(campaign_id):
    from .design_system_ads.commands import parse_adapt

    command = parse_adapt(_json(optional=True))
    format_key = command.format or request.args.get("format")
    layers = command.layers if command.layers is not None else request.args.get("layers")
    swaps = command.swaps if isinstance(command.swaps, list) else None
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


@studio_or_admin_required_api
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


@studio_or_admin_required_api
@studio_brand_required
def api_delete_client(cid):
    if request.method == "PUT":
        return _execute(lambda: _ok(_service().update_client(cid, _json())))
    if _workspace_brand_scope():
        return _error("A exclusão de marcas não está disponível. Preserve o histórico da organização.", 403)

    def execute():
        service = _service()
        client = service.delete_client(cid)
        ClientLogoStorage().delete(client.get("logo_upload_path"))
        return _ok()

    return _execute(execute)


@studio_or_admin_required_api
@studio_brand_required
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


@studio_or_admin_required_api
@studio_brand_required
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


@studio_or_admin_required_api
@studio_brand_required
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


@studio_or_admin_required_api
@studio_brand_required
def api_primary_client_brand_asset(cid, asset_id):
    return _execute(
        lambda: _ok(_service().set_primary_brand_asset(cid, asset_id))
    )


@studio_or_admin_required_api
@studio_brand_required
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


@studio_or_admin_required_api
def api_image_credits():
    client_id = request.args.get("client_id")
    if _studio_client_scope() and str(client_id) != str(STUDIO_CLIENT_ID):
        return _error("Esta marca não está disponível neste Studio.", 403)
    return _execute(lambda: _ok(_service().image_credits(
        session.get("user_id"),
        client_id,
    )))


@admin_required_api
def api_create_variation(cid):
    def create():
        created = _service().create_variation(cid, _json(optional=True))
        try:
            from .services.cadu_product_emails import send_piece_ready
            send_piece_ready(
                recipient_email=str(session.get("user_email") or ""),
                recipient_name=str(session.get("user_name") or ""),
                title=str(created.get("name") or created.get("notes") or "Nova peça"),
                url=product_url("studio", "/studio/modelagem-criativos/trocar"), kind="piece",
            )
        except Exception:
            logger.exception("Não enviou a notificação da nova peça")
        return _ok(created, 201)
    return _execute(create)


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
    redirected = _host_redirect('studio')
    if redirected:
        return redirected
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
    redirected = _host_redirect('studio')
    if redirected:
        return redirected
    try:
        collection = _service().public_collection(token)
        return _collection_zip(collection["assets"], collection["title"])
    except (CreativeNotFoundError, ValueError):
        abort(404)


@public_bp.get("/<token>/asset/<int:asset_id>")
def public_collection_asset(token, asset_id):
    redirected = _host_redirect('studio')
    if redirected:
        return redirected
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
    # Mantém compatibilidade com clientes antigos que ainda usam o prefixo
    # ``/parametros`` na chamada do laboratório de camadas.
    blueprint.add_url_rule(
        "/parametros/api/format-lab/layers/split",
        endpoint="creative_format_lab_layers_split_legacy",
        view_func=api_format_lab_layers_split,
        methods=["POST"],
    )
    register_trocr_routes(blueprint)
    blueprint.add_url_rule(
        "/api/format-lab/quote",
        endpoint="creative_format_lab_quote",
        view_func=api_format_lab_quote,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/prototype/quote",
        endpoint="creative_prototype_quote",
        view_func=api_prototype_quote,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/prototype/script",
        endpoint="creative_prototype_script",
        view_func=api_prototype_script,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/prototype/refs",
        endpoint="creative_prototype_refs",
        view_func=api_prototype_refs,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/prototype/scenes",
        endpoint="creative_prototype_scenes",
        view_func=api_prototype_scenes,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/prototype/animate",
        endpoint="creative_prototype_animate",
        view_func=api_prototype_animate,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/prototype/video",
        endpoint="creative_prototype_video",
        view_func=api_prototype_video,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-lab/prototype/video/<job_id>",
        endpoint="creative_prototype_video_status",
        view_func=api_prototype_video_status,
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
        "/api/design-system/brand/<client_id>/validate-render",
        endpoint="creative_design_system_brand_validate_render",
        view_func=api_validate_brand_design_system_render,
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
        "/api/design-system/campaign/<campaign_id>/validate-render",
        endpoint="creative_design_system_campaign_validate_render",
        view_func=api_validate_campaign_design_system_render,
        methods=["POST"],
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
        "/api/format-registry",
        endpoint="creative_format_registry",
        view_func=api_format_registry,
    )
    blueprint.add_url_rule(
        "/api/format-registry/<key>",
        endpoint="creative_format_registry_entry",
        view_func=api_format_registry_entry,
    )
    blueprint.add_url_rule(
        "/api/format-lab/train",
        endpoint="creative_format_lab_train",
        view_func=api_format_lab_train,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-assets/resolve",
        endpoint="creative_format_assets_resolve",
        view_func=api_format_assets_resolve,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-revisions",
        endpoint="creative_format_revisions",
        view_func=api_format_revision,
        methods=["GET", "POST"],
    )
    blueprint.add_url_rule(
        "/api/format-revisions/approve",
        endpoint="creative_format_revisions_approve",
        view_func=api_format_revision_approve,
        methods=["POST"],
    )
    blueprint.add_url_rule(
        "/api/format-revisions/showcase",
        endpoint="creative_format_revisions_showcase",
        view_func=api_format_revision_showcase,
        methods=["POST"],
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
        "/api/viewer-templates",
        endpoint="creative_viewer_templates",
        view_func=api_viewer_templates,
    )
    blueprint.add_url_rule(
        "/api/viewer-templates/<slug>",
        endpoint="creative_viewer_template",
        view_func=api_viewer_template,
        methods=["GET", "PUT"],
    )
    blueprint.add_url_rule(
        "/api/viewer-templates/<slug>/formats",
        endpoint="creative_viewer_template_formats",
        view_func=api_viewer_template_formats,
        methods=["PUT"],
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
        "/api/brand-sources",
        endpoint="creative_brand_sources",
        view_func=api_brand_sources,
        methods=["GET"],
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


def register_studio_product_routes(blueprint):
    """Register short, product-owned workspace URLs on the Studio host."""
    blueprint.add_url_rule("/", endpoint="studio_home", view_func=modelagem_criativos)
    blueprint.add_url_rule("/audio", endpoint="studio_audio", view_func=studio_audio)
    blueprint.add_url_rule(
        "/direcao-de-marca",
        endpoint="studio_workspace_brand",
        view_func=lambda: modelagem_desk("design-system"),
    )
    from .creative_media.studio_delivery import public_player, public_video
    blueprint.add_url_rule("/public/<token>", endpoint="studio_public_video", view_func=public_player)
    blueprint.add_url_rule("/public/<token>/video", endpoint="studio_public_video_file", view_func=public_video)
    for endpoint, path in STUDIO_SHORT_ROUTES.items():
        page = endpoint.removeprefix("modelagem_")
        blueprint.add_url_rule(
            f"/{path}", endpoint=f"studio_{page}",
            view_func=lambda page=page: modelagem_desk(page),
        )


@studio_or_admin_required
def studio_audio():
    """Audio Studio interface prototype on the product host."""
    redirected = _host_redirect('studio')
    if redirected:
        return redirected
    try:
        studio_credit = credit_position(int(session.get('cliente_id') or 0)) or {}
    except Exception:
        logger.warning('Nao foi possivel carregar o saldo do Studio Audio', exc_info=True)
        studio_credit = {}
    response = make_response(render_template(
        'cadu_studio/audio.html',
        studio_credit=studio_credit,
    ))
    response.headers['Cache-Control'] = 'no-store, private'
    return response


@admin_required
def modeling_ux_states():
    return render_template("parametros/mesa/states.html")


@admin_required
def trocr_ux_states():
    return render_template("parametros/trocr/states.html")


@admin_required
def modeling_ux_templates():
    return render_template("parametros/lab/templates.html")


@admin_required
def modeling_ux_template_edit(slug):
    return render_template("parametros/lab/template_edit.html", template_slug=slug)


@studio_or_admin_required
@studio_brand_required
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
        "/lab/templates",
        endpoint="modeling_ux_templates",
        view_func=modeling_ux_templates,
    )
    app.add_url_rule(
        "/lab/templates/<slug>",
        endpoint="modeling_ux_template_edit",
        view_func=modeling_ux_template_edit,
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
