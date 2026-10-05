import itertools
from types import SimpleNamespace

from aicentralv2.creative_media import studio_create, studio_review

from tests.test_studio_create_directions import image_data


def _modeling(calls, saved, sent=None):
    sent = [] if sent is None else sent
    colors = itertools.cycle(["blue", "green", "red"])

    class Generator:
        def generate_image(self, prompt, references, **kwargs):
            calls.append(prompt)
            sent.append(list(references or []))
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
    calls, saved, sent = [], [], []
    rejected = {**REJECTED, "observation": {"visible_text": ["Saiba mas"], "unrequested_elements": ["selo"]},
                "required_text": ["Saiba mais"]}
    _verdicts(monkeypatch, rejected, APPROVED)
    result = _generate(_modeling(calls, saved, sent))
    assert len(calls) == 2
    # The fix edits the first image: it goes first among the references, and the prompt names what to change.
    assert calls[1].startswith("EDIT THE FIRST IMAGE") and "EDIT THE FIRST IMAGE" not in calls[0]
    assert '"Saiba mas"' in calls[1] and '"Saiba mais"' in calls[1]
    # Never ask the editor to delete what the reviewer listed as extra: it removed scene props and copy in tests.
    assert "selo" not in calls[1] and "Do not delete, add or reword any text" in calls[1]
    assert sent[1] and sent[1][0].startswith("data:image/") and result["review"]["fix"] == "edit"
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
    _verdicts(monkeypatch, {**REJECTED, "score": 50}, {**REJECTED, "score": 20}, {**REJECTED, "score": 30})
    result = _generate(_modeling(calls, saved))
    # Every edit starts from the best version so far and the best one is delivered.
    assert len(calls) == studio_review.MAX_ATTEMPTS == 3 and result["review"]["delivered"] == "first"
    assert [item["best"] for item in result["review"]["attempts"][1:]] == [False, False]


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


def test_official_logo_is_never_an_added_element():
    assert studio_review._is_brand_mark("CEMIG brand mark (top right)", "Cemig")
    assert studio_review._is_brand_mark("Cemig logo", "Cemig")
    assert not studio_review._is_brand_mark("WhatsApp icon", "Cemig")
    assert "never list it" in studio_review.eyes_instruction("Cemig", "composed", True)


def test_lab_refines_until_the_target_score_within_five_versions(monkeypatch):
    calls, saved = [], []
    scores = [{**APPROVED, "score": value} for value in (60, 72, 70, 91)]
    _verdicts(monkeypatch, *scores)
    modeling = _modeling(calls, saved)
    modeling.review_attempts, modeling.refine_target = 5, 90
    result = _generate(modeling)
    assert len(calls) == 4 and result["review"]["delivered_version"] == 4 and result["review"]["score"] == 91


def test_margin_violation_rejects_and_costs_points():
    observation = {"visible_text": ["Chame agora"], "boxes": [
        {"kind": "cta", "label": "Chame agora", "box": [60, 80, 97, 93]},
        {"kind": "face", "label": "rosto", "box": [0, 10, 40, 90]}]}
    verdict = studio_review.judge({"overall": 80}, observation, {}, [])
    assert verdict["reason"] == "margin" and verdict["score"] == 70
    assert verdict["margin"] == ["Chame agora (right)"]
    prompt = studio_review.edit_prompt({**verdict, "observation": observation}, "6:5")
    assert "Chame agora (right)" in prompt and "8% from every edge" in prompt


def test_edits_chain_from_the_latest_version_and_the_best_score_is_delivered(monkeypatch):
    calls, saved, sent = [], [], []
    scores = [{**APPROVED, "score": value} for value in (60, 80, 70, 75, 72)]
    _verdicts(monkeypatch, *scores)
    modeling = _modeling(calls, saved, sent)
    modeling.review_attempts, modeling.refine_target = 5, 90
    result = _generate(modeling)
    assert len(calls) == 5 and result["review"]["delivered_version"] == 2 and result["review"]["score"] == 80
    # Version 4 edits version 3 (the latest), not version 2 (the best).
    assert sent[3][0] != sent[2][0]


def test_edit_prompt_follows_what_the_piece_has():
    observation = {"improvements": ["Make the CTA button larger", "Move the logo up", "Increase headline contrast"]}
    bare = studio_review.edit_prompt({"observation": observation, "piece": {"palette": ["#C4FF3F"], "logo_mode": "none", "has_cta": False}})
    assert "CTA button larger" not in bare and "Move the logo" not in bare and "headline contrast" in bare
    assert "Do not add any button" in bare and "do not add any logo" in bare and "#C4FF3F" in bare
    full = studio_review.edit_prompt({"observation": observation, "piece": {"palette": ["#C4FF3F"], "logo_mode": "composed", "has_cta": True}})
    assert "CTA button larger" in full and "applied afterwards" in full and "CTA button)" in full
    assert "no CTA" in studio_review.eyes_instruction("Cemig", "composed", False)


def test_reframe_factor_brings_every_box_inside_the_safe_margin():
    observation = {"boxes": [{"kind": "cta", "box": [2, 80, 30, 93]}, {"kind": "face", "box": [0, 0, 50, 100]}]}
    factor = studio_review.reframe_factor(observation)
    # The CTA's left edge at 2% sits 48% from the centre; 42% is needed, so the picture shrinks to ~0.86.
    assert 0.85 <= factor <= 0.875 and 50 - 48 * factor >= 8
    assert studio_review.reframe_factor({"boxes": [{"kind": "cta", "box": [20, 20, 80, 80]}]}) is None


def test_margin_rejection_is_fixed_by_shrinking_and_outpainting(monkeypatch):
    calls, saved, sent = [], [], []
    margin = {**REJECTED, "reason": "margin", "margin": ["CTA (left)"],
              "observation": {"boxes": [{"kind": "cta", "label": "CTA", "box": [2, 80, 30, 93]}]}}
    _verdicts(monkeypatch, margin, APPROVED)
    result = _generate(_modeling(calls, saved, sent))
    assert calls[1].startswith("OUTPAINT THE BORDER") and len(sent[1]) == 1
    assert result["review"]["delivered_version"] == 2


def test_shrink_into_border_keeps_the_canvas_and_paints_the_edge_color():
    import base64, io
    from PIL import Image
    image = Image.new("RGB", (200, 100), "#123456")
    out = io.BytesIO(); image.save(out, "PNG")
    url = studio_create.shrink_into_border(base64.b64encode(out.getvalue()).decode(), 0.8)
    result = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert result.size == (200, 100) and result.getpixel((1, 1)) == (0x12, 0x34, 0x56)


def test_text_free_banner_edits_never_ask_for_text():
    verdict = {"reason": "text_mismatch", "required_text": ["Saiba mais"],
               "observation": {"visible_text": ["Saiba"], "improvements": ["Make the headline bolder", "Warmer light"]},
               "piece": {"palette": [], "logo_mode": "composed", "has_cta": True, "text_free": True}}
    prompt = studio_review.edit_prompt(verdict)
    assert "TEXT-FREE IMAGE" in prompt and '"Saiba mais"' not in prompt
    assert "headline bolder" not in prompt and "Warmer light" in prompt


def test_two_pass_drafts_at_low_quality_then_finishes_on_the_draft(monkeypatch):
    calls, saved, sent, qualities = [], [], [], []
    verdicts = [{**APPROVED, "score": 70, "observation": {"unrequested_elements": ["selo"], "cut_off": []}}, APPROVED]
    _verdicts(monkeypatch, *verdicts)
    modeling = _modeling(calls, saved, sent)
    original = modeling.generator.generate_image

    def tracked(prompt, references, **kwargs):
        qualities.append(kwargs.get("quality"))
        return original(prompt, references, **kwargs)

    modeling.generator.generate_image = tracked
    modeling.two_pass = True
    result = _generate(modeling)
    assert len(calls) == 2 and qualities[0] == "low"
    assert calls[0].startswith("DRAFT PASS") and "EDIT THE FIRST IMAGE" in calls[1] and "selo" in calls[1]
    assert sent[1][0].startswith("data:image/") and result["passes"] == ["draft", "finish"]


def test_variation_edits_a_finished_piece_and_skips_the_draft(monkeypatch):
    calls, saved, sent = [], [], []
    _verdicts(monkeypatch, APPROVED)
    modeling = _modeling(calls, saved, sent)
    modeling.two_pass = True
    modeling.storage.generated_as_data_url = lambda url: "data:image/png;base64," + image_data("blue").split(",", 1)[1]
    result = studio_create.create_image({"prompt": "Anúncio com botão Saiba mais.", "aspect_ratio": "1:1",
                                         "variation_base": "/static/uploads/creative_generated/a@base.png",
                                         "request_id": "variation-1"}, modeling, 10, 20)
    assert len(calls) == 1 and calls[0].startswith("VARIATION OF THE FIRST IMAGE") and result["passes"] == ["variation"]
    assert studio_create.variation_reference({"variation_base": "https://evil.example/x.png"}, modeling) is None


def test_numbers_the_request_never_wrote_reject_the_piece():
    observation = {"visible_text": ["Sua conta de luz", "R$ 184,90", "289 kWh", "Chame agora"]}
    verdict = studio_review.judge({"overall": 80}, observation, {}, ["Sua conta de luz", "Chame agora"],
                                  allowed_text="Título: Sua conta de luz Botão: Chame agora")
    assert verdict["reason"] == "invented_data"
    offer = {"visible_text": ["Outlet com +20% EXTRA"]}
    assert studio_review.judge({"overall": 80}, offer, {}, [], allowed_text="Título: Outlet com +20% EXTRA")["approved"]
    prompt = studio_review.edit_prompt({**verdict, "observation": observation})
    assert "R$ 184,90" in prompt and "abstract interface shapes" in prompt


def test_text_the_studio_did_not_typeset_rejects_a_text_free_piece():
    observation = {"visible_text": ["Outlet com +20% EXTRA", "Outlet com", "COMPRAR AGORA", "Use o cupom DIADOCLIENTE"]}
    piece = {"text_free": True, "logo_mode": "composed", "brand_name": "Reserva"}
    verdict = studio_review.judge({"overall": 80}, observation, {}, ["Outlet com +20% EXTRA", "COMPRAR AGORA"], piece)
    assert verdict["reason"] == "stray_text"
    clean = studio_review.judge({"overall": 80}, {"visible_text": ["Outlet com +20% EXTRA", "COMPRAR AGORA", "RESERVA", "reserva.com.br"]}, {},
                                ["Outlet com +20% EXTRA", "COMPRAR AGORA"], piece)
    assert clean["approved"]


def test_scene_prompt_of_a_typeset_piece_loses_the_sentences_that_quote_the_copy():
    from aicentralv2.creative_media.studio_playbook import scene_only
    scene = "Homem com camiseta bege em estúdio. Título Outlet com +20% EXTRA no topo. Luz suave."
    assert scene_only(scene, ["Outlet com +20% EXTRA"]) == "Homem com camiseta bege em estúdio. Luz suave."


def test_a_layout_by_position_is_used_as_is_and_its_sketch_goes_to_the_model(monkeypatch):
    from aicentralv2.creative_media import banner_compose, export
    monkeypatch.setattr(export, "save_sibling", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(banner_compose, "save_layers", lambda *_args, **_kwargs: None)
    calls, saved, sent = [], [], []
    _verdicts(monkeypatch, APPROVED)
    modeling = _modeling(calls, saved, sent)
    result = studio_create.create_image({"prompt": "Cena da campanha.", "original_prompt": "Título: Outlet com +20% EXTRA\nBotão: Comprar agora",
                                         "aspect_ratio": "6:5", "width": 300, "height": 250, "position_layout": "pessoa-circulo",
                                         "request_id": "review-request-pos"}, modeling, 10, 20)
    assert "LAYOUT BY POSITION" in calls[0] and "TEXT-FREE IMAGE" in calls[0]
    assert any(str(item).startswith("data:image/png") for item in sent[0]), "the sketch goes embedded"
    assert result


def test_required_copy_follows_the_transcription_and_the_wordmark_is_not_extra_text():
    from aicentralv2.creative_media.studio_review import as_transcribed
    required = ["SUA CONTA DE LUZ", "NA PALMA DA MÃO", "Acesse agora"]
    visible = ["SUA CONTA DE LUZ", "NA", "PALMA DA MÃO", "Acesse agora", "CEMIG"]
    assert as_transcribed(required, visible, "Cemig") == (visible[:4], visible[:4])
    assert as_transcribed(["OUTLET COM", "+20% EXTRA"], ["OUTLET.COM", "+20% EXTRA"], "Reserva")[0] == ["OUTLET COM", "+20% EXTRA"]
