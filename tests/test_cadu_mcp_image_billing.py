from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from aicentralv2.cadu_workspace import media_creation_service as service
from aicentralv2.cadu_workspace.mcp.registry import ToolInputError
from aicentralv2.creative_media import studio_create
from aicentralv2.creative_media.studio_costs import media_tokens_for_cost
from aicentralv2.creative_modeling_service import CreativeModelingService

REQUEST = "11111111-1111-4111-8111-111111111111"


@pytest.mark.parametrize("client_id,user_id", [(0, 3), (7, 0), (None, 3), (7, None)])
def test_generation_is_refused_without_a_payer(client_id, user_id):
    context = SimpleNamespace(client_id=client_id, user_id=user_id, project_ref="")
    with pytest.raises(ToolInputError):
        service.generate_studio_image(context, {"request_id": REQUEST, "prompt": "uma imagem"})


def test_failed_ledger_write_is_retried_with_the_same_idempotency_key():
    keys = []

    def charge(**kwargs):
        keys.append(kwargs["idempotency_key"])
        if len(keys) < 3:
            raise RuntimeError("ledger indisponível")
        return {"tokens_cobrados": 4800}

    charged = studio_create.charge_image_with_retry(charge, request_id=REQUEST, idempotency_key="studio:create-image:x")
    assert charged["tokens_cobrados"] == 4800
    assert keys == ["studio:create-image:x"] * 3


def test_persistent_ledger_failure_still_raises_for_reconciliation():
    charge = MagicMock(side_effect=RuntimeError("ledger fora do ar"))
    with pytest.raises(RuntimeError):
        studio_create.charge_image_with_retry(charge, request_id=REQUEST, idempotency_key="k")
    assert charge.call_count == studio_create.IMAGE_CHARGE_ATTEMPTS


def test_studio_image_charge_debits_the_full_provider_cost():
    modeling = CreativeModelingService.__new__(CreativeModelingService)
    modeling.credit_connector = MagicMock()
    modeling._credits_crm_id = lambda client_id: None
    modeling._charge_studio_call(
        client_id=7, user_id=3, idempotency_key="studio:create-image:x", stage="image_generation",
        provider_result={"actual_cost_usd": 0.05, "model": "gpt-image-2"}, fallback_cost=0.22, media=True)
    debit = modeling.credit_connector.charge_provider.call_args.kwargs
    assert debit["media_tokens"] == media_tokens_for_cost(0.05) > 0
    assert debit["media_tokens"] == 5000  # US$ 0,05 a US$ 10 por milhão de créditos, sem desconto de tokens do provedor


def test_image_quote_follows_the_chosen_quality():
    from aicentralv2.creative_media.studio_costs import QUALITY_LABELS, image_estimate_usd
    from aicentralv2.cadu_tool_billing import cost_token_equivalent

    quotes = {label: cost_token_equivalent(image_estimate_usd(quality), margin_multiplier=1)
              for label, quality in QUALITY_LABELS.items()}
    assert quotes["econômica"] < quotes["padrão"] < quotes["alta"]


def test_rag_credit_estimate_matches_the_charge_margin(monkeypatch):
    from aicentralv2.cadu_skills.repository import project_rag_credits

    monkeypatch.delenv("CADU_PROJECT_RAG_TOKEN_MARGIN", raising=False)
    assert project_rag_credits(1000) == 1200
    monkeypatch.setenv("CADU_PROJECT_RAG_TOKEN_MARGIN", "abc")
    assert project_rag_credits(1000) == 1200


def test_queued_brand_audit_kicks_the_queue_without_a_worker(monkeypatch):
    from flask import Flask
    from aicentralv2.cadu_workspace import routes as workspace_routes, brand_audit_jobs

    app = Flask(__name__)
    processed = []
    monkeypatch.setattr(brand_audit_jobs, "process_one", lambda: processed.append(1) or len(processed) < 2)
    started = []

    class Immediate:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            started.append(1)
            self.target()

    monkeypatch.setattr(workspace_routes.threading, "Thread", Immediate)
    workspace_routes._kick_brand_audit_queue(app)
    assert started and processed == [1, 1]
