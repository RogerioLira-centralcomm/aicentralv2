"""Área autenticada do produto Cadu Agentes."""
from typing import Optional

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..auth import login_required, login_required_api
from ..cadu_skills.repository import customization_targets
from ..services import integration_credentials
from .repository import campaigns_for_client, link_campaign_project, portfolio_for_clients


bp = Blueprint("cadu_connect", __name__, url_prefix="/connect")


def workspace_project_context(client_id: int, projects: list[dict]) -> Optional[dict]:
    """Use the shared selection only when it maps to this Cadu tenant.

    A Family selection can contain projects from other legacy sources. Connect
    campaigns only support cadu_projetos IDs, so every other source is ignored
    instead of being guessed from a name.
    """
    selected = session.get("family_context") or {}
    if selected.get("client_id") != client_id:
        return None
    ref = selected.get("project_ref")
    if not isinstance(ref, str) or not ref.startswith("projects:"):
        return None
    try:
        project_id = int(ref.split(":", 1)[1])
    except ValueError:
        return None
    return next((project for project in projects if project.get("id") == project_id
                 and project.get("client_id") == client_id), None)


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
    requested_client_id = request.args.get("client_id", type=int)
    requested_project_id = request.args.get("project_id", type=int)
    permitted_ids = {int(client["id"]) for client in permitted_clients}
    if is_portfolio_operator and requested_client_id is None:
        client_id = 0
    else:
        client_id = requested_client_id if is_portfolio_operator and requested_client_id in permitted_ids else session_client_id
    active_client = next((client for client in permitted_clients if int(client["id"]) == client_id), None)
    projects = [row for row in targets["projects"] if int(row.get("client_id") or 0) == client_id]
    selected_project = next((project for project in projects if project["id"] == requested_project_id), None)
    if selected_project is None:
        selected_project = workspace_project_context(client_id, projects)
    campaigns = campaigns_for_client(client_id, project_id=selected_project["id"] if selected_project else None)
    accounts = []
    # Integrações globais pertencem à operação interna. Administradores de
    # clientes externos enxergam e gerenciam somente as conexões do Cadu PHP.
    if is_portfolio_operator:
        try:
            accounts = integration_credentials.list_summaries()
        except Exception:
            accounts = []
    # Catálogo de conectores suportados pelo produto. O estado de autorização
    # continua vindo do cofre de integrações; nunca expomos credenciais aqui.
    mcp_catalog = [
        {"name": "Meta Ads", "scope": "Campanhas, conjuntos, criativos e insights", "kind": "MCP", "state": "Disponível", "tone": "meta"},
        {"name": "Google Ads", "scope": "Busca, vídeo, performance e conversões", "kind": "MCP", "state": "Disponível", "tone": "google"},
        {"name": "Google Campaign Manager", "scope": "Veiculação, inventário e relatórios", "kind": "MCP", "state": "Planejado", "tone": "google"},
        {"name": "Display & Video 360", "scope": "Programática, audiência e performance", "kind": "MCP", "state": "Planejado", "tone": "google"},
        {"name": "LinkedIn Ads", "scope": "Campanhas B2B e públicos profissionais", "kind": "MCP", "state": "Planejado", "tone": "linkedin"},
        {"name": "TikTok Ads", "scope": "Campanhas, criativos e métricas", "kind": "MCP", "state": "Planejado", "tone": "tiktok"},
    ]
    return render_template(
        "cadu_portals/connect.html",
        account_name=(active_client or {}).get("name") or session.get("user_name") or "Minha conta",
        active_client=active_client,
        workspace_clients=permitted_clients,
        is_portfolio_operator=is_portfolio_operator,
        portfolio_mode=is_portfolio_operator and requested_client_id is None,
        client_portfolio=portfolio_for_clients(permitted_clients) if is_portfolio_operator else [],
        accounts=accounts, campaigns=campaigns, projects=projects, selected_project=selected_project,
        reports=[row for row in campaigns if row.get("link_dash")],
        mcp_catalog=mcp_catalog,
        connected_count=len([account for account in accounts if account.get("configured")]),
        integrations_url=current_app.config.get("CADU_INTEGRATIONS_URL") or "https://cadu.centralcomm.media/integracoes",
    )


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
