"""Regression checks for public-agent purchase and document finalization boundaries."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest, Forbidden

from aicentralv2.cadu_public_mcp import auth
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.artifacts import service as artifacts
from aicentralv2.cadu_workspace.credit_purchase_service import purchase_extra
from aicentralv2.cadu_workspace.mcp.tools import account as account_tools
from aicentralv2.cadu_workspace.mcp.tools import artifacts as artifact_tools  # noqa: F401
from aicentralv2.cadu_workspace.mcp.registry import ToolForbidden, ToolInputError, registry
from aicentralv2.cadu_workspace.routes import bp as workspace_bp


def _context(project_ref="ci:42"):
    return RequestContext(organization_id=12, client_id=12, user_id=7,
                          conversation_id=None, surface="conversations",
                          project_ref=project_ref, capabilities=("workspace", "artifacts"))


def test_public_credit_purchase_scope_is_admin_only_before_key_is_inserted():
    with patch.object(auth, "_available", return_value=True), \
         patch.object(auth.repository, "actor", return_value={"organization_id": 12}), \
         patch.object(auth.repository, "account_role", return_value="member"), \
         patch.object(auth, "get_db") as database:
        with pytest.raises(auth.PublicMcpAuthError, match="administradores"):
            auth.create_key(client_id=12, user_id=7, label="Agente", client_type="gpt",
                            scopes=["credits:purchase"])
        database.assert_not_called()


def test_credit_purchase_refuses_non_admin_and_unlisted_package_without_writing():
    with patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.actor",
               return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.account_role",
               return_value="member"), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.get_db") as database:
        with pytest.raises(Forbidden):
            purchase_extra(_context(), "Extra Essencial", "prepaid")
        database.assert_not_called()

    with patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.actor",
               return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.account_role",
               return_value="admin"), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.get_db") as database:
        with pytest.raises(BadRequest, match="catálogo"):
            purchase_extra(_context(), "Pacote inventado", "prepaid")
        database.assert_not_called()


def test_credit_purchase_releases_only_catalog_quantity_and_names_requester():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [{"id": 41}, {"id": 72}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.actor",
               return_value={"organization_id": 12, "name": "Ana Silva", "email": "ana@example.com"}), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.account_role",
               return_value="admin"), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.get_db", return_value=connection), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.credit_position",
               return_value={"available": 100_000}), \
         patch("aicentralv2.db.obter_cliente_por_id", return_value={"nome_fantasia": "Agência"}), \
         patch("aicentralv2.email_service.send_email") as send_email:
        result = purchase_extra(_context(), "Extra Essencial", "prepaid", "Solicitado pela equipe")
    assert result["credits_released"] == 100_000
    assert result["requester_name"] == "Ana Silva"
    assert result["credit_lot_id"] == 72
    assert any("Ana Silva" in str(call) for call in send_email.call_args_list)
    insert_lot = [call for call in cursor.execute.call_args_list
                  if "INSERT INTO cadu_credits_extras" in call.args[0]]
    assert len(insert_lot) == 1
    assert insert_lot[0].args[1] == (12, 100_000)
    connection.commit.assert_called_once()


def test_credit_purchase_reports_failed_email_without_reversing_released_credits():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [{"id": 41}, {"id": 72}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    app = Flask(__name__)
    with app.app_context(), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.actor",
               return_value={"organization_id": 12, "name": "Ana", "email": "ana@example.com"}), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.repository.account_role",
               return_value="admin"), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.get_db", return_value=connection), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.credit_position",
               return_value={"available": 100_000}), \
         patch("aicentralv2.db.obter_cliente_por_id", return_value={}), \
         patch("aicentralv2.email_service.send_email", side_effect=[False, True]):
        result = purchase_extra(_context(), "Extra Essencial", "prepaid")
    assert result["notification_sent"] is False
    assert result["credits_released"] == 100_000
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()


def test_external_viewer_cannot_update_project_artifact():
    with patch.object(artifacts, "get_artifact", return_value={
            "id": "artifact-1", "project_ref": "ci:42", "created_by": 8, "status": "draft"}), \
         patch("aicentralv2.cadu_family.repository.project_user_can_view", return_value=True), \
         patch("aicentralv2.cadu_family.repository.actor", return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_family.repository.account_role", return_value="member"), \
         patch("aicentralv2.cadu_family.repository.project_access",
               return_value=[{"user_id": 7, "role": "viewer"}]), \
         patch.object(artifacts, "patch_artifact") as update:
        with pytest.raises(ToolForbidden, match="não pode alterar"):
            registry.execute("artifacts.update_draft", {
                "request_id": "request-123456789", "artifact_id": "artifact-1",
                "expected_version": 1, "content": {"html": "<p>Alteração</p>"},
            }, _context(), exposure="customer_agent")
        update.assert_not_called()

def test_document_finalization_requires_version_and_keeps_manual_html_text():
    assert artifacts._indexable_text({"content": {"html":
        "<h1>Plano revisado</h1><p>Texto editado pela pessoa.</p><script>segredo()</script>"}}) == \
        "Plano revisado\nTexto editado pela pessoa."
    with pytest.raises(BadRequest, match="versão atual"):
        artifacts.finalize_to_project(_context(), "artifact-1", expected_version=None)


def test_refinalizing_replaces_indexed_snapshot_without_inflating_source_count():
    artifact = {"id": "artifact-1", "project_ref": "ci:42", "type": "brief",
                "title": "Briefing", "current_version": 2,
                "content": {"html": "<h1>Briefing revisado</h1><p>Versão manual completa do projeto.</p>"}}
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [None, {"current_version": 2}, None]
    cursor.fetchall.return_value = [{"id": 11}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_family.repository.project_user_can_view", return_value=True), \
         patch("aicentralv2.cadu_family.repository.actor", return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_family.repository.account_role", return_value="admin"), \
         patch("aicentralv2.cadu_family.repository.project_access", return_value=[]), \
         patch.object(artifacts, "get_artifact", return_value=artifact), \
         patch.object(artifacts, "get_db", return_value=connection), \
         patch("aicentralv2.cadu_workspace.project_knowledge.index", return_value=([{"text": "texto"}], 10, "model")), \
         patch("aicentralv2.cadu_skills.repository.charge_project_rag", return_value=10), \
         patch("aicentralv2.cadu_workspace.project_index_service.persist_indexed_source", return_value=99), \
         patch("aicentralv2.cadu_workspace.project_resource_service.notify_change"):
        result = artifacts.finalize_to_project(_context(), "artifact-1", expected_version=2)
    assert result["source_id"] == 99
    assert any("purpose='project_attachment'" in call.args[0] and "superseded" in call.args[0]
               for call in cursor.execute.call_args_list)
    assert any("total_arquivos=GREATEST" in call.args[0] and call.args[1] == (1, "42", 12)
               for call in cursor.execute.call_args_list)
    connection.commit.assert_called_once()


def test_web_credit_purchase_requires_csrf_and_keeps_existing_member_flow():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(workspace_bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, family_csrf="valid", user_type="member",
                       user_name="Ana Silva", user_email="ana@example.com")
    with patch("aicentralv2.cadu_workspace.routes.get_db") as database:
        response = client.post("/workspace/api/creditos/solicitar", json={"package_name":"Extra Essencial"})
        assert response.status_code == 403
        database.assert_not_called()
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [{"id":41}, {"id":72}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_workspace.routes.get_db", return_value=connection), \
         patch("aicentralv2.db.obter_cliente_por_id", return_value={}), \
         patch("aicentralv2.email_service.send_email") as send_email:
        response = client.post("/workspace/api/creditos/solicitar", headers={"X-CSRF-Token":"valid"},
                               json={"package_name":"Extra Essencial", "tokens":100_000,
                                     "price":49, "billing_mode":"prepaid"})
    assert response.status_code == 201
    assert response.get_json()["credit_lot_id"] == 72
    assert send_email.call_count == 2
    assert "Ana Silva" in str(send_email.call_args_list[0])
    assert any("INSERT INTO cadu_credits_extras" in call.args[0] for call in cursor.execute.call_args_list)


def test_web_credit_purchase_does_not_invite_duplicate_retry_when_email_fails():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(workspace_bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, family_csrf="valid", user_type="member",
                       user_name="Ana Silva", user_email="ana@example.com")
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [{"id": 41}, {"id": 72}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_workspace.routes.get_db", return_value=connection), \
         patch("aicentralv2.db.obter_cliente_por_id", return_value={}), \
         patch("aicentralv2.email_service.send_email", return_value=False):
        response = client.post("/workspace/api/creditos/solicitar", headers={"X-CSRF-Token": "valid"},
                               json={"package_name": "Extra Essencial", "tokens": 100_000,
                                     "price": 49, "billing_mode": "prepaid"})
    assert response.status_code == 201
    assert response.get_json()["notification_sent"] is False
    assert response.get_json()["credit_lot_id"] == 72
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()


def test_agency_edit_rejects_invalid_document_and_postal_code_before_operation():
    with patch.object(account_tools, "_admin", return_value={"organization_id":12}), \
         patch.object(account_tools.operations, "execute") as operation:
        with pytest.raises(ToolInputError, match="CPF ou CNPJ"):
            account_tools.update_agency(_context(), {"request_id":"id", "document":"123"})
        with pytest.raises(ToolInputError, match="CEP"):
            account_tools.update_agency(_context(), {"request_id":"id", "postal_code":"123"})
        operation.assert_not_called()
