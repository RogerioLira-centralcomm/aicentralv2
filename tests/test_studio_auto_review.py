from types import SimpleNamespace

from aicentralv2.creative_media import studio_create, studio_review

from tests.test_studio_create_directions import image_data


def _modeling(calls, saved):
    colors = iter(["blue", "green", "red"])

    class Generator:
        def generate_image(self, prompt, references, **kwargs):
            calls.append(prompt)
            return {"b64_json": image_data(next(colors)).split(",", 1)[1], "model": "test-image", "output_format": "png"}

    class Storage:
        def save_generated_base64(self, encoded, _format):
            saved.append(encoded)
            return "/static/uploads/creative_generated/result.png"

    return SimpleNamespace(
        generator=Generator(), storage=Storage(), auto_review=True,
        _estimate=lambda *_args: .01, _charge_studio_call=lambda **_kwargs: {"tokens_cobrados": 5},
        _credits_crm_id=lambda value: value,
        credit_ledger=SimpleNamespace(assert_available=lambda *_a: 1000, available=lambda _c: 900),
    )


def _generate(modeling):
    return studio_create.create_image({"prompt": "Anúncio com botão Saiba mais.", "aspect_ratio": "1:1",
                                       "request_id": "review-request-1"}, modeling, 10, 20)


def _verdicts(monkeypatch, *items):
    queue = list(items)
    monkeypatch.setattr(studio_review, "review", lambda **_kwargs: queue.pop(0))


REJECTED = {"reviewed": True, "approved": False, "score": 40, "reason": "text_mismatch",
            "reason_text": "o texto saiu diferente do pedido"}
APPROVED = {"reviewed": True, "approved": True, "score": 80, "reason": "", "reason_text": ""}


def test_rejected_first_version_triggers_a_second_with_the_fix(monkeypatch):
    calls, saved = [], []
    _verdicts(monkeypatch, REJECTED, APPROVED)
    result = _generate(_modeling(calls, saved))
    assert len(calls) == 2
    assert "REVIEW FIX" in calls[1] and "REVIEW FIX" not in calls[0]
    assert result["review"]["retried"] and result["review"]["delivered"] == "second"
    assert result["review"]["reason_text"] == "o texto saiu diferente do pedido"


def test_approved_first_version_is_delivered_without_retry(monkeypatch):
    calls, saved = [], []
    _verdicts(monkeypatch, APPROVED)
    result = _generate(_modeling(calls, saved))
    assert len(calls) == 1
    assert result["review"]["retried"] is False and result["review"]["delivered"] == "first"


def test_worse_second_version_keeps_the_first(monkeypatch):
    calls, saved = [], []
    _verdicts(monkeypatch, {**REJECTED, "score": 50}, {**REJECTED, "score": 20})
    result = _generate(_modeling(calls, saved))
    assert len(calls) == 2 and result["review"]["delivered"] == "first"


def test_unavailable_reviewer_never_blocks_delivery(monkeypatch):
    calls, saved = [], []
    _verdicts(monkeypatch, {"reviewed": False, "approved": True, "score": None, "reason": "", "reason_text": ""})
    result = _generate(_modeling(calls, saved))
    assert len(calls) == 1 and result["image_url"].endswith("result.png")


def test_second_generation_failure_delivers_the_first(monkeypatch):
    calls, saved = [], []
    _verdicts(monkeypatch, REJECTED)
    modeling = _modeling(calls, saved)
    original = modeling.generator.generate_image

    def flaky(prompt, references, **kwargs):
        if calls:
            raise RuntimeError("provider down")
        return original(prompt, references, **kwargs)

    modeling.generator.generate_image = flaky
    result = _generate(modeling)
    assert result["review"]["retry_failed"] is True and result["image_url"].endswith("result.png")


def test_review_is_off_for_services_that_do_not_opt_in(monkeypatch):
    calls, saved = [], []
    modeling = _modeling(calls, saved)
    modeling.auto_review = False
    result = _generate(modeling)
    assert "review" not in result and len(calls) == 1


def test_judge_rejects_only_objective_failures():
    ok = {"overall": 58, "primary_failure": {"choice": "palette_off", "confidence": 0.9}}
    assert studio_review.judge(ok, {}, {}, [])["approved"]
    bad = {"overall": 70, "primary_failure": {"choice": "logo_redrawn", "confidence": 0.8}}
    assert studio_review.judge(bad, {}, {}, [])["reason"] == "logo_redrawn"
    unsure = {"overall": 70, "primary_failure": {"choice": "logo_redrawn", "confidence": 0.3}}
    assert studio_review.judge(unsure, {}, {}, [])["approved"]
    wrong_text = studio_review.judge({"overall": 70}, {"visible_text": ["Saiba mas"]}, {"text": {"all_exact": False}}, ["Saiba mais"])
    assert wrong_text["reason"] == "text_mismatch"
