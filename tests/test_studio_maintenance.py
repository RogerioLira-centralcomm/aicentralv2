from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2.creative_media.studio_maintenance import absolute_studio_url
from aicentralv2.services.cadu_product_emails import send_studio_work_completed, studio_completion_estimates


def test_absolute_studio_url_keeps_remote_and_expands_local_paths():
    assert absolute_studio_url("/static/piece.png", "https://studio.example") == "https://studio.example/static/piece.png"
    assert absolute_studio_url("https://cdn.example/piece.png", "https://studio.example") == "https://cdn.example/piece.png"
    assert absolute_studio_url("", "https://studio.example") == ""


def test_completion_email_uses_dark_studio_template_and_real_metrics():
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "aicentralv2" / "templates"))
    app.config["CADU_PRODUCT_EMAILS_ENABLED"] = True
    captured = {}

    class Sender:
        def enviar_email_com_template(self, **kwargs):
            captured.update(kwargs)
            return {"success": True, "messageId": "mail-1"}

    with app.app_context(), patch(
        "aicentralv2.services.cadu_product_emails.get_brevo_product_service", return_value=Sender()
    ):
        result = send_studio_work_completed(
            recipient_email="person@example.com", recipient_name="Pessoa", title="Campanha",
            asset_url="https://studio.example/static/final.png", studio_url="https://studio.example/criar",
            metrics={"generation_count": 4, "edit_count": 2, "format_count": 3,
                     "handoff_count": 1, "estimated_minutes_saved": 51,
                     "charged_credits": 18420, "provider_tokens": 1360,
                     "internal_cost_usd": "0.1842"},
        )

    assert result["success"] is True
    assert captured["template_name"] == "studio-trabalho-finalizado.html"
    assert captured["params"]["GENERATION_COUNT"] == 4
    assert captured["params"]["ESTIMATED_MINUTES_SAVED"] == 51
    assert captured["params"]["AI_CREDITS_USED"] == "18.420"
    assert captured["params"]["PROVIDER_TOKENS"] == "1.360"
    assert captured["params"]["AI_COST_USD"] == "US$ 0,1842"
    assert captured["params"]["CREDIT_SALE_UNIT_BRL"] == "R$ 8,00"
    assert captured["params"]["CREDIT_SALE_VALUE_BRL"] == "R$ 147.360,00"
    assert captured["params"]["DESIGNER_COST_BRL"] == "R$ 107,28"
    assert captured["params"]["ESTIMATED_MANUAL_TIME"] == "3h 58min"


def test_designer_estimate_has_explicit_configurable_clt_assumptions():
    app = Flask(__name__)
    app.config.update(
        STUDIO_DESIGNER_MONTHLY_SALARY_BRL=3500,
        STUDIO_DESIGNER_MONTHLY_HOURS=220,
        STUDIO_DESIGNER_CLT_FACTOR="1.0",
    )
    with app.app_context():
        result = studio_completion_estimates({"edit_count": 5})

    assert result["manual_minutes"] == 60
    assert result["designer_cost_brl"] == "R$ 15,91"
    assert result["designer_salary_brl"] == "R$ 3.500,00"


def test_worker_source_rechecks_every_reference_before_physical_delete():
    source = (Path(__file__).resolve().parents[1] / "aicentralv2" / "creative_media" / "studio_maintenance.py").read_text(encoding="utf-8")
    assert "cx_studio_session_assets" in source
    assert "cx_studio_finalizations" in source
    assert "cx_studio_project_items" in source
    assert "sa.role IN ('reference','base','accepted','final')" in source
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "updated_at < NOW()-INTERVAL '15 minutes'" in source
    template = (Path(__file__).resolve().parents[1] / "aicentralv2" / "templates" / "emails" / "externos" / "studio-trabalho-finalizado.html").read_text(encoding="utf-8")
    assert "background:#171717" in template
    assert "border-radius:14px" in template
    assert "estimated_minutes_saved" in template
    assert "ai_credits_used" in template
    assert "designer_cost_brl" in template
    assert "brand.logo_url" in template
    assert "credit_sale_value_brl" in template
    assert "fator CLT" in template
