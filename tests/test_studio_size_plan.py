from types import SimpleNamespace

from aicentralv2.creative_media import ad_masks, size_plan
from aicentralv2.services import openrouter_service


def test_every_studio_format_gets_a_valid_provider_size():
    for _, (label, width, height, _) in ad_masks.FORMATS.items():
        plan = size_plan.plan(width, height)
        gw, gh = plan["generation"]
        assert gw % 16 == 0 and gh % 16 == 0, label
        assert gw * gh >= size_plan.MIN_PIXELS and max(gw, gh) <= size_plan.MAX_SIDE, label
        assert 1 / 3 <= gw / gh <= 3, label
        if 1 / 3 <= width / height <= 3:
            assert plan["strategy"] == "native", label
            assert abs(gw / gh - width / height) / (width / height) < 0.01, label
        else:
            assert plan["strategy"] == "composed", label


def test_generation_is_never_smaller_than_what_is_delivered():
    story = size_plan.plan(1080, 1920)
    assert story["generation"][0] >= 1080 and story["generation"][1] >= 1920
    medium = size_plan.plan(300, 250)
    assert medium["delivery_2x"] == (600, 500) and medium["weight_budget_kb"] == 150
    assert medium["generation"][0] >= 600
    assert size_plan.plan(1080, 1350)["delivery_2x"] is None


def test_openai_route_receives_the_planned_size(monkeypatch):
    sent = {}

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"b64_json": "aGk="}], "model": "gpt-image-2"}

    def post(url, **kwargs):
        sent.update(kwargs.get("json") or {})
        return Response()

    monkeypatch.setattr(openrouter_service, "resolve_openai_api_key", lambda: "k")
    openrouter_service._openai_generate_image(
        {"prompt": "x", "aspect_ratio": "9:16"}, image_model="openai/gpt-image-2",
        output_format="png", timeout=30, http_client=SimpleNamespace(post=post), size="1152x2048",
    )
    assert sent["size"] == "1152x2048"
    assert openrouter_service._openai_size({"aspect_ratio": "9:16"}, "bad") == "1024x1536"


def test_image_quota_waits_and_retries(monkeypatch):
    calls = []
    monkeypatch.setattr(openrouter_service.time, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    responses = iter([SimpleNamespace(status_code=429, headers={"retry-after": "3"}), SimpleNamespace(status_code=200, headers={})])
    result = openrouter_service._post_with_rate_retry(SimpleNamespace(post=lambda url, **kw: next(responses)), "u")
    assert result.status_code == 200 and calls == [("sleep", 3.0)]
