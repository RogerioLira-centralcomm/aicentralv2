import json
from pathlib import Path

from aicentralv2.creative_media.studio_prompt import optimize_prompt, protected_literals
from aicentralv2.creative_format_lab.service import FormatLabService


def response(payload):
    return {"message": {"content": json.dumps(payload, ensure_ascii=False)}}


def test_optimizer_translates_operations_and_preserves_high_risk_literals():
    original = 'Não altere Apolo Lira nem Casa Baanko. Troque apenas "3 HORAS" por "9h30" e adicione 14/10.'

    def fake(messages, **kwargs):
        assert kwargs["temperature"] == 0
        request = json.loads(messages[1]["content"])
        assert request["protected_literals"] == protected_literals(original)
        return response({
            "optimized_prompt": (
                'Edit only the requested visible text. Preserve Apolo Lira and Casa Baanko exactly. '
                'Replace literal "3 HORAS" with literal "9h30" and add literal 14/10. Preserve everything else.'
            ),
            "detected_language": "pt-BR",
            "preserved_literals": request["protected_literals"],
        })

    result = optimize_prompt(original, mode="edit", text_callable=fake)
    assert result["optimized"] is True
    assert result["detected_language"] == "pt-BR"
    for literal in protected_literals(original):
        assert literal in result["optimized_prompt"]


def test_optimizer_falls_back_when_a_literal_is_changed_or_removed():
    original = 'Manter "3 HORAS", 14/10, 9h30 e Casa Baanko.'

    def unsafe(*_args, **_kwargs):
        return response({"optimized_prompt": "Change the event details.", "detected_language": "pt-BR"})

    result = optimize_prompt(original, mode="edit", text_callable=unsafe)
    assert result["optimized"] is False
    assert result["optimized_prompt"] == original


def test_optimizer_falls_back_when_provider_is_unavailable():
    original = "Crie uma peça institucional limpa."

    def unavailable(*_args, **_kwargs):
        raise ValueError("offline")

    result = optimize_prompt(original, text_callable=unavailable)
    assert result["optimized_prompt"] == original
    assert result["optimized"] is False


def test_both_trocr_entry_points_request_model_optimization():
    root = Path(__file__).resolve().parents[1] / "aicentralv2" / "static" / "js"
    agent = (root / "mc-trocar.js").read_text(encoding="utf-8")
    element = (root / "trocr" / "workspace.js").read_text(encoding="utf-8")
    assert "optimize_for_model: true" in agent
    assert "optimize_for_model:true" in element


def test_trocr_service_exposes_optimized_instruction_without_losing_original():
    original = 'Troque somente "3 HORAS" por "9h30".'

    def fake(_messages, **_kwargs):
        return response({
            "optimized_prompt": 'Replace only literal "3 HORAS" with literal "9h30". Preserve everything else.',
            "detected_language": "pt-BR",
        })

    service = object.__new__(FormatLabService)
    service._assert_tool_balance = lambda *_args, **_kwargs: None
    service._metered_text_callable = lambda _payload, _calls: fake
    service._charge_provider_calls = lambda *_args, **_kwargs: None

    result = service.refine_swap_instruction({
        "instruction": original, "optimize_for_model": True,
    }, user_id=7)
    assert result["original_instruction"] == original
    assert result["refined_instruction"].startswith("Replace only")
    assert result["prompt_version"] == "studio-prompt-v1"
