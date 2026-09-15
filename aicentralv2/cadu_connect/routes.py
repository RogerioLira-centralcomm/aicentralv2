"""Área autenticada do produto Cadu Agentes."""

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..auth import login_required, login_required_api
from ..cadu_skills.repository import customization_targets
from ..services import integration_credentials
from .repository import campaigns_for_client, link_campaign_project


bp = Blueprint("cadu_connect", __name__, url_prefix="/connect")


@bp.get("")
@bp.get("/")
@login_required
def index():
    client_id = int(session.get("cliente_id") or 0)
    campaigns = campaigns_for_client(client_id)
    targets = customization_targets()
    projects = [row for row in targets["projects"] if int(row.get("client_id") or 0) == client_id]
    accounts = []
    # Integrações globais pertencem à operação interna. Administradores de
    # clientes externos enxergam e gerenciam somente as conexões do Cadu PHP.
    if session.get("is_centralcomm") or session.get("user_type") == "superadmin":
        try:
            accounts = integration_credentials.list_summaries()
        except Exception:
            accounts = []
    return render_template(
        "cadu_portals/connect.html",
        account_name=session.get("user_name") or "Minha conta",
        accounts=accounts, campaigns=campaigns, projects=projects,
        reports=[row for row in campaigns if row.get("link_dash")],
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
