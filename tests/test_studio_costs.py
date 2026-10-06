from decimal import Decimal
from types import SimpleNamespace

from aicentralv2.creative_media import studio_costs


def test_an_image_costs_what_the_catalog_says_converted_at_the_base_rate(monkeypatch):
    monkeypatch.delenv("CADU_OPENAI_IMAGE_USD_PER_GENERATION", raising=False)
    monkeypatch.delenv("CADU_USD_PER_CREDIT_TOKEN", raising=False)

    assert studio_costs.image_generation_usd() == Decimal("0.22")
    assert studio_costs.image_credits(0) == 22000
    assert studio_costs.image_credits(2) == 27280, "cada referência soma 12%"


def test_media_tokens_are_the_full_cost_at_the_base_rate():
    assert studio_costs.media_tokens_for_cost(0.14) == 14000
    assert studio_costs.media_tokens_for_cost(0.001) == 100
    assert studio_costs.media_tokens_for_cost(None) == 0
    assert studio_costs.media_tokens_for_cost(-1) == 0


def test_a_real_image_is_not_discounted_by_the_provider_usage_tokens():
    """Medido em produção (2026-10-06): custo US$ 0,04413 com 1.966 tokens de uso foi cobrado 2.447 em vez de 4.413."""
    from aicentralv2.creative_modeling_service import CreativeModelingService

    charged = {}

    class Connector:
        def charge_provider(self, **kwargs):
            charged.update(kwargs)

    service = CreativeModelingService.__new__(CreativeModelingService)
    service.credit_connector = Connector()
    service._credits_crm_id = lambda value: value
    service._charge_studio_call(
        client_id=174, user_id=2, idempotency_key="studio:create-image:t", stage="image_generation", media=True,
        provider_result={"model": "gpt-image-2", "actual_cost_usd": 0.04413, "usage": {"input_tokens": 594, "output_tokens": 1372}},
        fallback_cost=Decimal("0"),
    )
    assert charged["media_tokens"] == 4413


def test_a_creation_is_charged_like_the_workspace_estimates_it_not_at_the_plan_token_price():
    from aicentralv2.creative_modeling_service import CreativeModelingService

    charged = {}

    class Connector:
        def charge_provider(self, **kwargs):
            charged.update(kwargs)
            return {"tokens_cobrados": kwargs["media_tokens"]}

    service = CreativeModelingService.__new__(CreativeModelingService)
    service.credit_connector = Connector()
    service._credits_crm_id = lambda value: value

    service._charge_studio_call(
        client_id=25, user_id=2, idempotency_key="studio:create-image:1", stage="image_generation",
        provider_result={"model": "gpt-image-2"}, fallback_cost=Decimal("0.22"), media=True,
    )

    assert charged["media_tokens"] == 22000
    assert charged["provider_result"]["actual_cost_usd"] == 0.22


def test_agent_steps_are_not_converted_as_media():
    from aicentralv2.creative_modeling_service import CreativeModelingService

    charged = {}

    class Connector:
        def charge_provider(self, **kwargs):
            charged.update(kwargs)

    service = CreativeModelingService.__new__(CreativeModelingService)
    service.credit_connector = Connector()
    service._credits_crm_id = lambda value: value

    service._charge_studio_call(
        client_id=25, user_id=2, idempotency_key="studio:directions:1", stage="creative_directions",
        provider_result={"usage": {"total_tokens": 5200}}, fallback_cost=Decimal("0"), media=False,
    )

    assert charged["media_tokens"] is None


def test_an_image_is_charged_by_the_tokens_it_used_not_by_the_flat_catalog_price():
    usage = {"input_tokens": 700, "input_tokens_details": {"text_tokens": 500, "image_tokens": 200}, "output_tokens": 1584}
    cost = studio_costs.usage_cost_usd(usage)
    assert abs(cost - 0.05162) < 1e-6
    assert studio_costs.media_tokens_for_cost(cost) == 5162
    assert studio_costs.usage_cost_usd({}) is None
    assert studio_costs.usage_cost_usd({"input_tokens": 10}) is None


def test_the_desk_estimate_follows_quality_and_is_near_five_thousand_credits_for_standard():
    table = studio_costs.image_credits_by_quality()
    assert 4000 <= table["padrão"] <= 6000
    assert table["econômica"] < table["padrão"] < table["alta"]


def test_the_editor_also_charges_the_full_cost_without_subtracting_provider_usage():
    from aicentralv2.creative_format_lab.service import FormatLabService

    charged = []

    class Connector:
        def charge_provider(self, **kwargs):
            charged.append(kwargs)
            return {}

    service = FormatLabService.__new__(FormatLabService)
    service._billing_identity = lambda payload, user_id: (174, 2)
    service._credit_connector = lambda: Connector()
    service._charge_provider_calls(
        {"request_id": "r1"}, 2, "studio.image", "image_edit",
        [{"model": "gpt-image-2", "actual_cost_usd": 0.04413, "usage": {"input_tokens": 594, "output_tokens": 1372}}],
        media=True,
    )
    assert charged[0]["media_tokens"] == 4413
