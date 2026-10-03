"""Creative Lab: adaptation plans, brand readiness, evaluation math and access gating (no network)."""

import json
from pathlib import Path

import pytest
from PIL import Image

from aicentralv2.creative_lab import adapter, brands, evaluation
from aicentralv2.creative_lab.catalog import MODELS_DIR


def manifest(key):
    return json.loads((MODELS_DIR / f"{key}.json").read_text(encoding="utf-8"))


CAPS = {
    "qwen-image-3-pro": {"available": True, "max_references": 4, "aspect_ratios": ["1:1", "3:4", "4:5", "16:9"],
                         "resolutions": ["1K", "2K"], "qualities": [], "backgrounds": [], "parameters": ["aspect_ratio", "resolution", "seed"],
                         "passthrough": [], "pricing": [{"billable": "input_image", "unit": "image", "cost_usd": 0.003},
                                                        {"billable": "output_image", "unit": "image", "cost_usd": 0.04, "variant": "1k"},
                                                        {"billable": "output_image", "unit": "image", "cost_usd": 0.075, "variant": "2k"}]},
    "recraft-v4.1": {"available": True, "max_references": 1, "aspect_ratios": ["1:1", "4:3", "3:4", "16:9", "9:16", "auto"],
                     "resolutions": [], "qualities": [], "backgrounds": [], "parameters": ["aspect_ratio", "n", "input_references"],
                     "passthrough": ["style", "controls", "text_layout"],
                     "pricing": [{"billable": "output_image", "unit": "image", "cost_usd": 0.035}]},
    "gpt-image-2--openrouter": {"available": True, "max_references": 16,
                                "aspect_ratios": ["1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9", "auto"],
                                "resolutions": [], "qualities": ["auto", "low", "medium", "high"], "backgrounds": ["auto", "opaque"],
                                "parameters": ["aspect_ratio", "quality", "background", "n", "input_references", "output_compression"],
                                "passthrough": ["moderation"],
                                "pricing": [{"billable": "input_image", "unit": "token", "cost_usd": 8e-06},
                                            {"billable": "input_text", "unit": "token", "cost_usd": 5e-06},
                                            {"billable": "output_image", "unit": "token", "cost_usd": 3e-05}]},
}
REFS = [{"ref_id": 1, "role": "PERSON", "label": "Modelo"}, {"ref_id": 2, "role": "PRODUCT", "label": "Colar"},
        {"ref_id": 3, "role": "LOGO", "label": "Logo"}]


def spec(**overrides):
    base = {"task": "generate", "instruction": "Campanha", "aspect_ratio": "4:5", "quality": "standard",
            "logo_mode": "composer", "must_include_text": ["Brilho que é seu"], "objective": "ad"}
    return {**base, **overrides}


def test_every_manifest_is_complete_and_unique():
    keys = set()
    for path in sorted(Path(MODELS_DIR).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert path.stem == data["model_key"]
        for field in ("label", "provider", "provider_model_id", "catalog_id", "adapter", "quality_map",
                      "reference_policy", "prompt_profile", "notes", "profile_version"):
            assert field in data, (path.name, field)
        assert data["provider"] in ("openrouter", "openai_direct")
        assert "output_compression" not in data.get("fixed_params", {}), "OpenRouter rejects it with png output"
        keys.add(data["model_key"])
    assert {"gpt-image-2--openai", "gpt-image-2--openrouter", "gpt-image-2.5-sunburst--openai",
            "gpt-image-2.5-sunburst--openrouter", "qwen-image-3-pro", "recraft-v4.1"} <= keys


def test_recraft_sends_one_reference_and_describes_the_rest():
    plan = adapter.plan(spec(), manifest("recraft-v4.1"), CAPS["recraft-v4.1"], REFS)
    assert [ref["role"] for ref in plan["sent"]] == ["PRODUCT"]  # manifest order puts PRODUCT before PERSON
    assert [ref["role"] for ref in plan["converted_to_text"]] == ["PERSON"]
    assert [ref["role"] for ref in plan["post_processed"]] == ["LOGO", "FORMAT"]  # 4:5 is cropped from 3:4
    assert plan["parameters"]["applied"]["aspect_ratio"] == "3:4"
    assert plan["parameters"]["transformed"][0]["from"] == "4:5"


def test_native_logo_goes_to_the_model_and_none_drops_it():
    native = adapter.plan(spec(logo_mode="native"), manifest("qwen-image-3-pro"), CAPS["qwen-image-3-pro"], REFS)
    assert "LOGO" in [ref["role"] for ref in native["sent"]] and not native["post_processed"]
    dropped = adapter.plan(spec(logo_mode="none"), manifest("qwen-image-3-pro"), CAPS["qwen-image-3-pro"], REFS)
    assert dropped["dropped"][0]["role"] == "LOGO"


def test_edit_is_blocked_for_models_without_image_input():
    caps = {**CAPS["recraft-v4.1"], "max_references": 0}
    plan = adapter.plan(spec(task="edit"), manifest("recraft-v4.1"), caps, [{"ref_id": 9, "role": "BASE", "label": "Peça"}])
    assert plan["blocked"]


def test_unavailable_catalog_entry_blocks_without_breaking():
    plan = adapter.plan(spec(), manifest("qwen-image-3-pro"), {"available": False, "reason": "sumiu"}, [])
    assert plan["blocked"] == "sumiu"


def test_openai_direct_uses_exact_size_and_keeps_quality():
    plan = adapter.plan(spec(aspect_ratio="3:4"), manifest("gpt-image-2--openai"), CAPS["gpt-image-2--openrouter"], [])
    assert plan["parameters"]["applied"] == {"size": "1152x1536", "quality": "medium"}


def test_unsupported_values_are_reported_as_dropped():
    caps = {**CAPS["gpt-image-2--openrouter"], "backgrounds": ["auto"]}
    plan = adapter.plan(spec(aspect_ratio="1:1"), manifest("gpt-image-2--openrouter"), caps, [])
    assert {"param": "background", "value": "opaque", "reason": "valor fora do catálogo"} in plan["parameters"]["dropped"]


def test_cost_estimates_per_image_and_per_token():
    qwen = adapter.plan(spec(), manifest("qwen-image-3-pro"), CAPS["qwen-image-3-pro"], REFS)
    estimate = adapter.estimate_cost(qwen, CAPS["qwen-image-3-pro"], "prompt")
    assert estimate == {"usd": 0.046, "variable": False, "basis": "preço por imagem do catálogo"}
    gpt = adapter.plan(spec(aspect_ratio="1:1"), manifest("gpt-image-2--openrouter"), CAPS["gpt-image-2--openrouter"], [])
    token = adapter.estimate_cost(gpt, CAPS["gpt-image-2--openrouter"], "x" * 1000)
    assert token["variable"] and 0.03 < token["usd"] < 0.04


def test_model_prompt_respects_budget_and_keeps_the_text_requirement():
    director = adapter.director_prompt(spec(), {"name": "Vivara", "palette": ["#000000"], "creative_guidelines": "x" * 900,
                                                "visual_motifs": ["a"], "tone_of_voice": "t", "mandatory_elements": ["m"]})
    plan = adapter.plan(spec(), manifest("recraft-v4.1"), CAPS["recraft-v4.1"], REFS)
    prompt = adapter.model_prompt(director, plan, manifest("recraft-v4.1"))
    assert len(prompt) <= manifest("recraft-v4.1")["prompt_profile"]["max_chars"]
    assert '"Brilho que é seu"' in prompt
    assert "Image 1 (PRODUCT" in prompt


def test_plain_reads_python_repr_strings_from_the_audit():
    assert brands.plain("[{'value': 'Institucional', 'source_url': 'x'}, {'value': 'Serviços'}]") == "Institucional; Serviços"
    assert brands.plain_list("[{'label': 'Clientes'}]") == ["Clientes"]


def test_readiness_requires_logo_palette_summary_and_audit():
    snapshot = {"logo_url": "", "palette": [{"hex": "#000000"}], "text": {"brand_summary": ""}, "lists": {},
                "fields": {}, "assets": [], "audit": None}
    result = brands.readiness(snapshot)
    assert result["level"] == "needs_audit"
    assert "logo oficial" in result["summary"].lower()
    ready = brands.readiness({"logo_url": "https://x/logo.png", "palette": [{"hex": "#000000"}, {"hex": "#FFFFFF"}],
                              "text": {"brand_summary": "s", "tone_of_voice": "t", "creative_guidelines": "g"},
                              "lists": {"forbidden_elements": ["f"]}, "assets": [{"role": "reference"}],
                              "fields": {f"f{i}": {"status": "verified"} for i in range(6)},
                              "audit": {"created_at": "2099-01-01T00:00:00+00:00"}})
    assert ready["level"] == "ready"


def test_payload_policy_filters_by_audit_status():
    snapshot = {"name": "M", "palette": [], "fonts": [], "text": {"brand_summary": "s", "tone_of_voice": "t"},
                "lists": {}, "fields": {"brand_summary": {"status": "verified"}, "tone_of_voice": {"status": "blocked"}}}
    assert "tone_of_voice" not in brands.payload_fields(snapshot, "verified_only")
    assert "tone_of_voice" in brands.payload_fields(snapshot, "all")


def test_text_check_is_exact_and_detects_lost_accents():
    result = evaluation.text_check(["Mídia que chega."], ["Midia que chega."])
    assert result["items"][0] == {"text": "Mídia que chega.", "exact": False, "accent_lost": True}
    assert evaluation.text_check(["Fale com a gente"], ["FALE COM A GENTE"])["all_exact"] is True


def test_palette_check_measures_distance_to_brand_colors():
    image = Image.new("RGB", (64, 64), "#4FFF82")
    result = evaluation.palette_check(image, ["#4FFF82", "#000000"])
    assert result["brand_distances"][0]["distance"] < 5
    assert result["brand_coverage"][0]["share"] == 1.0 and result["adherence"] == 1.0
    half = Image.new("RGB", (64, 64), "#FFFFFF")
    half.paste(Image.new("RGB", (64, 16), "#4FFF82"), (0, 0))
    assert evaluation.palette_check(half, ["#4FFF82"])["coverage_total"] == 0.25


def test_summary_combines_typed_answers():
    scores = evaluation._summarize({
        "instruction_fidelity": {"type": "score", "score": 3.0},
        "text_exact": {"type": "noul", "noul": 1.0},
        "forbidden_present": {"type": "noul", "noul": 0.0},
        "primary_failure": {"type": "choice", "choice": "none", "confidence": 0.9},
    })
    assert scores["overall"] == 100 and scores["primary_failure"]["choice"] == "none"


def test_score_questions_use_list_criteria():
    questions = evaluation._questions(spec(), True, True)
    assert isinstance(questions["instruction_fidelity"]["criteria"], list)
    assert isinstance(questions["brand_fit"]["criteria"], list)
    assert set(questions["primary_failure"]["criteria"]) == set(evaluation.FAILURES)


@pytest.fixture()
def lab_client(monkeypatch):
    from flask import Flask
    from aicentralv2.creative_lab import access
    app = Flask(__name__)
    app.secret_key = "test"

    @app.get("/lab")
    @access.lab_required
    def page():
        return "ok"

    @app.get("/lab/api/state")
    @access.lab_required
    def state():
        return {"ok": True}

    return app.test_client()


@pytest.mark.parametrize("session_data,status", [({}, 404), ({"user_id": 5, "cliente_id": 236}, 404),
                                                 ({"user_id": 5, "cliente_id": 174}, 200)])
def test_lab_exists_only_for_allowed_organizations(lab_client, session_data, status):
    with lab_client.session_transaction() as session:
        session.update(session_data)
    assert lab_client.get("/lab").status_code == status
    assert lab_client.get("/lab/api/state").status_code == status


def test_director_v2_diagrams_by_archetype_and_format():
    brief = {"archetype": "oferta-heroi", "format_key": "story-9x16",
             "copy": {"kicker": "TIM PRÉ", "highlight": "29GB", "cta": "Recarregar"},
             "casting": ["jovem negra agachada fazendo selfie"]}
    spec_v2 = spec(aspect_ratio="9:16", brief=brief)
    text = adapter.director_prompt(spec_v2, {"name": "TIM", "palette": ["#0026D9", "#FFB000", "#FFFFFF"]})
    assert "LAYOUT (Oferta com número herói)" in text
    assert "keep 0–6% clear for app UI" in text
    assert 'HERO (2–4× the headline size, in the ACCENT color): "29GB"' in text
    assert "background #0026D9" in text and "hero/accent #FFB000" in text
    assert adapter.copy_strings(brief) == ["TIM PRÉ", "29GB", "Recarregar"]


def test_reformat_edit_keeps_copy_and_relayouts():
    text = adapter.director_prompt(spec(task="edit", aspect_ratio="16:9", brief={"format_key": "wide-16x9"}), None)
    assert text.startswith("TASK: Recompose the supplied ad") and "KEEP IDENTICAL" in text and "copy column on the left" in text


def test_fit_to_ratio_center_crops_only_when_needed():
    import io
    from aicentralv2.creative_lab.runner import fit_to_ratio
    buffer = io.BytesIO()
    Image.new("RGB", (1200, 900), "red").save(buffer, "PNG")
    cropped, info = fit_to_ratio(buffer.getvalue(), "1:1")
    assert info["to"] == [900, 900] and Image.open(io.BytesIO(cropped)).size == (900, 900)
    same, none = fit_to_ratio(buffer.getvalue(), "4:3")
    assert none is None and same == buffer.getvalue()
