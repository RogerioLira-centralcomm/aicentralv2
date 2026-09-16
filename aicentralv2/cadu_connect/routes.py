"""Área autenticada do produto Cadu Agentes."""
from typing import Optional

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..auth import login_required, login_required_api
from ..cadu_skills.repository import customization_targets
from ..cadu_family import repository as family_repository
from ..services import integration_credentials
from .repository import accounts_for_workspace_context, campaigns_for_client, files_for_workspace_context, link_campaign_project


bp = Blueprint("cadu_connect", __name__, url_prefix="/connect")


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
@login_required
def index():
    targets = customization_targets()
    is_portfolio_operator = bool(session.get("is_centralcomm") or session.get("user_type") == "superadmin")
    session_client_id = int(session.get("cliente_id") or 0)
    permitted_clients = targets["clients"] if is_portfolio_operator else [
        client for client in targets["clients"] if int(client.get("id") or 0) == session_client_id
    ]
    requested_project_id = request.args.get("project_id", type=int)
    permitted_ids = {int(client["id"]) for client in permitted_clients}
    # A temporary client-directory failure must not discard projects that are
    # already scoped to the signed-in organization.
    if not is_portfolio_operator and not permitted_ids and session_client_id:
        permitted_ids.add(session_client_id)
    legacy_projects = [dict(row) for row in targets["projects"] if int(row.get("client_id") or 0) in permitted_ids]
    projects = workspace_projects(session_client_id, legacy_projects)
    selected_project = next((project for project in projects if project.get("ref") == request.args.get("project_ref")), None)
    if selected_project is None:
        selected_project = next((project for project in projects if project.get("id") == requested_project_id), None)
    if selected_project is None:
        selected_project = workspace_project_context(projects)
    active_client_id = int(selected_project.get("client_id") or 0) if selected_project else session_client_id
    active_client = next((client for client in permitted_clients if int(client["id"]) == active_client_id), None)
    campaigns = campaigns_for_client(active_client_id, project_id=(selected_project or {}).get("id")) if active_client_id else []
    accounts = accounts_for_workspace_context(
        int(session.get("organization_id") or session_client_id or 0), workspace_client_id=active_client_id,
        workspace_project_ref=(selected_project or {}).get("ref"),
    ) if active_client_id else []
    # Integrações globais pertencem à operação interna. Administradores de
    # clientes externos enxergam e gerenciam somente as conexões do Cadu PHP.
    if is_portfolio_operator:
        try:
            accounts = accounts or integration_credentials.list_summaries()
        except Exception:
            accounts = []
    # Catálogo de conectores suportados pelo produto. O estado de autorização
    # continua vindo do cofre de integrações; nunca expomos credenciais aqui.
    mcp_catalog = [
        {"name": "Meta Ads", "scope": "Campanhas, conjuntos, criativos e insights", "kind": "MCP", "state": "Disponível", "tone": "meta"},
        {"name": "Google Ads", "scope": "Busca, vídeo, performance e conversões", "kind": "MCP", "state": "Disponível", "tone": "google"},
    ]
    page_context = dict(
        account_name=(selected_project or {}).get("name") or "Projetos",
        active_client=active_client,
        is_portfolio_operator=is_portfolio_operator,
        accounts=accounts, campaigns=campaigns, projects=projects, selected_project=selected_project,
        files=files_for_workspace_context(active_client_id),
        reports=[row for row in campaigns if row.get("link_dash")],
        mcp_catalog=mcp_catalog,
        connected_count=len([account for account in accounts if account.get("configured")]),
        integrations_url=current_app.config.get("CADU_INTEGRATIONS_URL") or "https://cadu.centralcomm.media/integracoes",
    )
    try:
        return render_template("cadu_connect/entry.html", **page_context)
    except Exception:
        # Connect não pode indisponibilizar a operação caso a entrada editorial
        # ainda esteja incompatível com uma dependência do servidor em produção.
        current_app.logger.exception("Falha ao renderizar a entrada do Connect; usando a tela operacional.")
        return render_template("cadu_portals/connect.html", **page_context)


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
