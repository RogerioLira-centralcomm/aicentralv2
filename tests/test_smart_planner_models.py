from aicentralv2.smart_planner.canvas import folha_text
from aicentralv2.smart_planner.models import (
    COMPLETO_SECTIONS,
    ONE_PAGE_SECTIONS,
    generation_map,
    preview_cost,
    preview_steps,
    resolve_role,
)
from aicentralv2.smart_planner.planner import FINAL_PROMPT, IMPROVE_PROMPT, PLAN_PROMPT


def test_roles_use_gpt5_family():
    extract = resolve_role("extract")
    final = resolve_role("final")
    assert "gpt-5" in extract["model"]
    assert "gpt-5" in final["model"]
    assert final["temperature"] <= 0.15


def test_one_page_map_has_four_pieces():
    mapped = generation_map("one_page")
    assert [item["id"] for item in mapped["sections"]] == ["strategy", "creative", "market", "defense"]
    assert len(mapped["passes"]) == 2
    assert mapped["passes"][1]["role"] == "sheet"
    assert not mapped["board"]


def test_completo_map_has_plan_and_board():
    mapped = generation_map("completo")
    assert len(mapped["sections"]) == 12
    assert [item["id"] for item in mapped["board"]] == ["context", "strategy", "media", "execution"]
    assert any(item["id"] == "voo" for item in COMPLETO_SECTIONS)
    assert any(item["id"] == "defense" for item in ONE_PAGE_SECTIONS)


def test_preview_costs_documents_without_images():
    one = preview_steps("one_page")
    full = preview_steps("completo")
    assert not any("Imagem" in item["label"] for item in one + full)
    assert any("página única" in item["label"].lower() or "defesa" in item["label"].lower() for item in one)
    assert any("quadro" in item["label"].lower() for item in full)
    assert any("Passagem 3" in item["label"] or "Núcleo" in item["label"] for item in full)
    one_cost = preview_cost("one_page")
    full_cost = preview_cost("completo")
    assert full_cost["usd"] > one_cost["usd"]
    assert "página única" in full_cost["note"]


def test_prompts_name_the_three_passes():
    assert "Estratégia e Mix" in PLAN_PROMPT
    assert "voo mensal" in IMPROVE_PROMPT
    assert "versão final" in FINAL_PROMPT


def test_folha_text_joins_cards():
    body = folha_text({
        "sections": [{"cards": [
            {"title": "Estratégia", "body": "Ir de CTV."},
            {"title": "", "body": ""},
            {"type": "defense", "body": "O anunciante já vende ali."},
        ]}]
    })
    assert "### Estratégia" in body
    assert "Ir de CTV." in body
    assert "O anunciante já vende ali." in body
