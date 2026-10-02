"""Área autenticada do produto Cadu Agentes."""
from typing import Optional
from uuid import uuid4
from datetime import date

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from ..auth import login_required, login_required_api
from ..cadu_skills.repository import customization_targets
from ..cadu_family import repository as family_repository
from ..services import integration_credentials
from ..product_domains import workspace_public_url
from .repository import accounts_for_workspace_context, campaigns_for_client, files_for_workspace_context, link_campaign_project


bp = Blueprint("cadu_connect", __name__, url_prefix="/connect")


@bp.errorhandler(HTTPException)
def reports_api_error(error):
    if request.path.startswith(('/connect/api/v1/reports/','/connect/api/v2/reports/')):
        return jsonify(error=error.description,message=error.description,
                       code=getattr(error,'flow_code',f'http_{error.code}'),
                       field_errors=getattr(error,'field_errors',{}),
                       node_ids=getattr(error,'node_ids',[]),edge_ids=getattr(error,'edge_ids',[]),
                       request_id=str(uuid4())), error.code
    return error

from .report_workspace import register as register_report_workspace
register_report_workspace(bp)
from .reports_v1 import register as register_reports_v1
register_reports_v1(bp)
from .reports_ingest import register as register_reports_ingest
register_reports_ingest(bp)
from .reports_ingest_v2 import register as register_reports_ingest_v2
register_reports_ingest_v2(bp)
from .reports_pages import register as register_reports_pages
register_reports_pages(bp)
from .reports_journey import register as register_reports_journey
register_reports_journey(bp)
from .reports_media_performance import register as register_reports_media_performance
register_reports_media_performance(bp)
from .reports_creatives import register as register_reports_creatives
register_reports_creatives(bp)
from .reports_google_ads import register as register_reports_google_ads
register_reports_google_ads(bp)
from .reports_alerts import register as register_reports_alerts
register_reports_alerts(bp)
from .reports_page_captures import register as register_reports_page_captures
register_reports_page_captures(bp)
from .reports_flow import register as register_reports_flow
register_reports_flow(bp)
from .reports_supertag import register as register_reports_supertag
register_reports_supertag(bp)
from .reports_imports import register as register_reports_imports
register_reports_imports(bp)
from .reports_access import register as register_reports_access
register_reports_access(bp)
from .reports_management import register as register_reports_management
register_reports_management(bp)
from .reports_flow_monitor import worker_once_command as reports_flow_monitor_once_command
from .reports_flow_monitor import worker_loop_command as reports_flow_monitor_loop_command
bp.cli.add_command(reports_flow_monitor_once_command)
bp.cli.add_command(reports_flow_monitor_loop_command)


@bp.before_request
def reports_retired_private_contract():
    if request.path.startswith('/connect/api/v1/reports/') and not request.path.startswith(('/connect/api/v1/reports/ingest/', '/connect/api/v1/reports/flow/collect')):
        return jsonify(error='Reports atualizado. Recarregue a página para usar a versão atual.'),410


@bp.before_request
def route_guest_connect_pages():
    """Use Workspace as the only guest entry for Reports pages."""
    if (
        request.method in {"GET", "HEAD"}
        and not session.get("user_id")
        and not request.path.startswith("/connect/r/")
        and not request.path.startswith("/connect/api/")
        and not request.path.startswith("/connect/public/link-tests/")
        and not request.path.startswith("/connect/public/supertag/v1/")
    ):
        return redirect(workspace_public_url(), code=302)


def workspace_project_context(projects: list[dict]) -> Optional[dict]:
    """Use the shared Workspace project when it is available to this user.

    A Family selection can contain projects from other legacy sources. Connect
    Projects are selected by their qualified source reference; campaign links
    remain guarded separately where a legacy numeric ID is required.
    """
    selected = session.get("family_context") or {}
    ref = selected.get("project_ref")
    if not isinstance(ref, str) or ":" not in ref:
        return None
    return next((project for project in projects if project.get("ref") == ref), None)


def attach_workspace_brands(projects: list[dict]) -> list[dict]:
    """Decorate legacy projects with the brands linked in Workspace.

    Workspace owns the relationship between a project and a brand.  Connect
    only reads it here, keeping every product on the same shared context.
    """
    projects_by_client: dict[int, list[dict]] = {}
    for project in projects:
        projects_by_client.setdefault(int(project.get("client_id") or 0), []).append(project)

    for client_id, client_projects in projects_by_client.items():
        if not client_id:
            continue
        try:
            entities = {item.get("ref"): item for item in family_repository.entities(client_id)}
            links = family_repository.project_brand_links(client_id)
        except Exception:
            entities, links = {}, []
        brands_by_project = {project.get("ref") or f"projects:{project['id']}": [] for project in client_projects}
        for link in links:
            project_ref = link.get("project_ref")
            brand = entities.get(link.get("brand_ref"))
            if project_ref in brands_by_project and brand:
                brands_by_project[project_ref].append(brand.get("name"))
        for project in client_projects:
            project["brands"] = brands_by_project.get(project.get("ref") or f"projects:{project['id']}", [])
    return projects


def workspace_projects(client_id: int, legacy_projects: list[dict]) -> list[dict]:
    """Join Cadu PHP, CI and Studio projects by explicit source reference."""
    items = {}
    for row in legacy_projects:
        project = dict(row, ref=f"projects:{row['id']}", source="projects")
        items[project["ref"]] = project
    try:
        for entity in family_repository.entities(client_id):
            if entity.get("kind") == "project" and entity.get("ref"):
                items.setdefault(entity["ref"], {
                    "id": None, "ref": entity["ref"], "name": entity.get("name") or "Projeto sem nome",
                    "source": entity.get("source") or "workspace", "client_id": client_id,
                })
    except Exception:
        pass
    return attach_workspace_brands(list(items.values()))


@bp.get("")
@bp.get("/")
def index():
    # Reports keeps its own authenticated page, but the product family has a
    # single unauthenticated entry point: the public Workspace page.
    if not session.get("user_id"):
        return redirect(workspace_public_url(), code=302)
    return redirect(url_for('cadu_connect.reports_v1_app'), code=302)


@bp.get('/campanhas')
@login_required
def campaigns_board():
    return redirect(url_for('cadu_connect.reports_v1_app') + '#campaigns', code=302)


@bp.post("/api/campaigns/<int:campaign_id>/project")
@login_required_api
def campaign_project(campaign_id):
    data = request.get_json(silent=True) or {}
    try:
        project_id = int(data["project_id"]) if data.get("project_id") else None
        if not link_campaign_project(
            campaign_id, client_id=int(session.get("cliente_id") or 0),
            project_id=project_id, user_id=int(session["user_id"]),
        ):
            return jsonify({"success": False, "error": "Campanha não encontrada para este cliente."}), 404
        return jsonify({"success": True, "message": "Projeto relacionado à campanha."})
    except (ValueError, TypeError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

from .reports_flow_previews import register as register_flow_previews
register_flow_previews(bp)

from .reports_flow_probe import register as register_flow_probe
register_flow_probe(bp)

from .reports_flow_blueprint import register as register_flow_blueprint
register_flow_blueprint(bp)

from .reports_flow_templates import register as register_flow_templates
register_flow_templates(bp)

from .reports_site_pages import register as register_site_pages
register_site_pages(bp)

from .reports_flow_catalog import register as register_flow_catalog
register_flow_catalog(bp)
