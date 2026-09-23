from unittest.mock import MagicMock, patch

from flask import Flask

from aicentralv2.cadu_workspace import brand_audit_jobs
from aicentralv2.services.cadu_product_emails import send_brand_audit_ready


def _app(enabled=True):
    app = Flask(__name__)
    app.config.update(TESTING=True, CADU_PRODUCT_EMAILS_ENABLED=enabled)
    return app


def test_brand_audit_email_records_disabled_delivery_as_skipped():
    with _app(enabled=False).app_context(), \
         patch.dict("os.environ", {"CADU_PRODUCT_EMAILS_ENABLED": "0"}), \
         patch("aicentralv2.email_service.record_workspace_email_event") as record:
        result = send_brand_audit_ready(
            recipient_email="pessoa@example.com", recipient_name="Pessoa",
            brand_name="Marca", summary="Resumo", differentiators=[],
            url="https://workspace.example/marcas/81", client_id=12,
        )

    assert result == {
        "success": True, "skipped": True, "reason": "product_emails_disabled",
    }
    record.assert_called_once()
    assert record.call_args.kwargs["client_id"] == 12
    assert record.call_args.kwargs["result"]["skipped"] is True


def test_brand_audit_email_uses_vault_key_when_env_key_is_absent():
    sender = MagicMock()
    sender.enviar_email_com_template.return_value = {"success": True, "messageId": "message-1"}
    with _app(enabled=False).app_context(), \
         patch.dict("os.environ", {}, clear=True), \
         patch("aicentralv2.services.integration_credentials.resolve_brevo_api_key", return_value="vault-key"), \
         patch("aicentralv2.services.cadu_email_connector.get_brevo_product_service", return_value=sender), \
         patch("aicentralv2.email_service.record_workspace_email_event"):
        result = send_brand_audit_ready(
            recipient_email="pessoa@example.com", recipient_name="Pessoa",
            brand_name="Marca", summary="Resumo", differentiators=[],
            url="https://workspace.example/marcas/81", client_id=12,
        )

    assert result["success"] is True
    sender.enviar_email_com_template.assert_called_once()


def test_brand_audit_email_records_provider_failure():
    sender = MagicMock()
    sender.enviar_email_com_template.return_value = {
        "success": False, "error": "provider rejected",
    }
    with _app(enabled=True).app_context(), \
         patch("aicentralv2.services.cadu_email_connector.get_brevo_product_service", return_value=sender), \
         patch("aicentralv2.email_service.record_workspace_email_event") as record:
        result = send_brand_audit_ready(
            recipient_email="pessoa@example.com", recipient_name="Pessoa",
            brand_name="Marca", summary="Resumo", differentiators=[],
            url="https://workspace.example/marcas/81", client_id=12,
        )

    assert result["success"] is False
    record.assert_called_once()
    assert record.call_args.kwargs["event_type"] == "workspace.brand_audit_ready"
    assert record.call_args.kwargs["result"]["error"] == "provider rejected"


def test_brand_audit_job_persists_requester_columns():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    with patch("aicentralv2.cadu_workspace.brand_audit_jobs.repository.get_db", return_value=connection):
        brand_audit_jobs.enqueue({
            "job_id": "job-1", "client_id": 12, "brand_id": 81, "user_id": 7,
            "analysis_mode": "deep", "request_reason": "chat", "images": [],
        })

    sql, params = cursor.execute.call_args.args
    assert "requested_by" in sql
    assert "analysis_mode" in sql
    assert params[-3:] == ("deep", "chat", 7)
    connection.commit.assert_called_once_with()
