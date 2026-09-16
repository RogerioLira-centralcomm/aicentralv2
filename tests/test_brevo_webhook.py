from unittest.mock import patch

from flask import Flask

from aicentralv2.brevo_webhook_routes import bp


def _client():
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app.test_client()


def test_brevo_webhook_requires_token():
    with patch(
        "aicentralv2.brevo_webhook_routes.resolve_brevo_webhook_token",
        return_value="webhook-test-token",
    ):
        response = _client().post("/api/brevo/webhook", json={"event": "delivered"})
    assert response.status_code == 401


def test_brevo_webhook_accepts_bearer_token_and_batch():
    with patch(
        "aicentralv2.brevo_webhook_routes.resolve_brevo_webhook_token",
        return_value="webhook-test-token",
    ):
        response = _client().post(
            "/api/brevo/webhook",
            headers={"Authorization": "Bearer webhook-test-token"},
            json=[{"event": "delivered"}, {"event": "uniqueOpened"}],
        )
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "received": 2}
