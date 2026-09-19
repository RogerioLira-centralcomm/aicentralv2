from aicentralv2.creative_format_lab.instruction_refine import refine_edit_instruction
from aicentralv2.creative_format_lab.swap import build_optimized_prompt


def test_refiner_keeps_original_and_literal_values():
    def fake(messages, **kwargs):
        assert kwargs["model"].endswith("gpt-5-nano")
        return {"message": {"content": '{"instruction":"Troque o preço para R$ 30; manter TIM."}'}}

    result = refine_edit_instruction("troque preço para R$ 30 manter TIM", text_callable=fake)

    assert result["original_instruction"] == "troque preço para R$ 30 manter TIM"
    assert result["refined_instruction"] == "Troque o preço para R$ 30; manter TIM."


def test_refiner_falls_back_if_a_literal_is_lost():
    def fake(_messages, **_kwargs):
        return {"message": {"content": '{"instruction":"Troque o preço."}'}}

    result = refine_edit_instruction('troque "16GB" por "20GB"', text_callable=fake)

    assert result["refined"] is False
    assert result["refined_instruction"] == 'troque "16GB" por "20GB"'


def test_refiner_rejects_an_invented_brand():
    def fake(_messages, **_kwargs):
        return {"message": {"content": '{"instruction":"Troque o texto do Banco Mercantil para Sicoob."}'}}

    result = refine_edit_instruction("Troque o texto do Banco Mercantil.", text_callable=fake)

    assert result["refined"] is False
    assert result["refined_instruction"] == "Troque o texto do Banco Mercantil."


def test_prompt_names_primary_image_crop_and_user_request_as_sources_of_truth():
    prompt = build_optimized_prompt({
        "reference": "data:image/png;base64,AA==",
        "reference_images": ["data:image/png;base64,BB=="],
        "instruction": "Troque o texto para R$ 30.",
        "original_instruction": "troque o texto para R$ 30",
        "selection_context": {"role": "price", "bbox_px": [10, 20, 110, 80]},
        "force_image": True,
    })

    assert "FIRST attachment is the source creative" in prompt
    assert "pixel crop (10, 20, 110, 80)" in prompt
    assert "Literal user request (source of truth" in prompt
    assert "troque o texto para R$ 30" in prompt


def test_global_composition_reference_guides_layout_without_replacing_the_creative():
    prompt = build_optimized_prompt({
        "reference": "data:image/png;base64,source",
        "reference_images": ["https://studio.example/masks/feed-4x5.png"],
        "reference_inputs": [{
            "image": "https://studio.example/masks/feed-4x5.png",
            "role": "composition_reference",
        }],
        "instruction": "Destaque o produto e preserve a marca.",
    })

    assert "composition system reference" in prompt
    assert "safe margins, hierarchy, negative space, layer order and alignment" in prompt
    assert "Do not recreate its placeholder product" in prompt
