"""Área autenticada do produto Cadu Agentes."""
from typing import Optional
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
    if request.path.startswith('/connect/api/v1/reports/'):
        return jsonify(error=error.description), error.code
    return error

from .report_workspace import register as register_report_workspace
register_report_workspace(bp)
from .reports_v1 import register as register_reports_v1
register_reports_v1(bp)
from .reports_ingest import register as register_reports_ingest
register_reports_ingest(bp)
from .reports_flow import register as register_reports_flow
register_reports_flow(bp)
from .reports_imports import register as register_reports_imports
register_reports_imports(bp)
from .reports_access import register as register_reports_access
register_reports_access(bp)


@bp.before_request
def route_guest_connect_pages():
    """Use Workspace as the only guest entry for Reports pages."""
    if (
        request.method in {"GET", "HEAD"}
        and not session.get("user_id")
        and not request.path.startswith("/connect/r/")
        and not request.path.startswith("/connect/api/")
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
