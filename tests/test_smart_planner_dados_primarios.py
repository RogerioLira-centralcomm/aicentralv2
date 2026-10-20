from aicentralv2.smart_planner import dados_primarios as dp
from aicentralv2.smart_planner.public_slides import build_slides


def test_normalize_reads_aliases_and_keeps_catalog_order():
    data = dp.normalize({"fontes": ["Pixel", "lista de clientes", "xyz"], "usos": ["Lookalike", "retargeting"], "observacao": "  base do e-commerce "})
    assert data == {"fontes": ["crm", "pixel"], "usos": ["remarketing", "lookalike"], "observacao": "base do e-commerce"}


def test_uses_need_a_source_and_campaign_interactions_only_allow_remarketing():
    assert dp.normalize({"usos": ["remarketing"]}) == {}
    only_campaign = dp.normalize({"fontes": ["interacoes"], "usos": ["remarketing", "lookalike", "exclusao"]})
    assert only_campaign["usos"] == ["remarketing"]


def test_problems_flag_remarketing_without_audience_and_use_without_front():
    taticas = [{"tipo": "remarketing", "canais": ["dv360"]}]
    assert any("precisa de uma audiência" in p for p in dp.problems({}, taticas))
    assert any("não tem a frente de remarketing" in p for p in dp.problems({"fontes": ["crm"], "usos": ["remarketing"]}, []))
    assert dp.problems({"fontes": ["crm"], "usos": ["remarketing"]}, taticas) == []


def test_prompt_block_names_sources_and_forbids_promised_numbers():
    block = dp.for_prompt({"fontes": ["crm"], "usos": ["lookalike"]})
    assert block["fontes"] == ["Lista de clientes (CRM)"] and block["usos"] == ["Lookalike"]
    assert "taxa de match" in block["regra"]
    assert dp.for_prompt({}) is None


def test_snapshot_carries_first_party_data():
    from aicentralv2.smart_planner.snapshot import build_snapshot

    row = {"id": 1, "cliente": "Animale", "objetivo": "consideracao", "dados_detectados": {"campanha": {
        "canais": ["dv360"], "dados_primarios": {"fontes": ["pixel"], "usos": ["remarketing"]}}}}
    assert build_snapshot(row)["dados_primarios"] == {"fontes": ["pixel"], "usos": ["remarketing"], "observacao": ""}


def test_slide_only_appears_with_sources_and_links_remarketing_to_the_front():
    base = {"title": "Plano", "overview": "Uma tese.", "fronts": [{"tipo": "remarketing", "label": "Remarketing"}]}
    assert not any(s["type"] == "first_party" for s in build_slides(base))
    view = {**base, "first_party": dp.public_view({"fontes": ["crm", "pixel"], "usos": ["remarketing", "exclusao"]})}
    slide = next(s for s in build_slides(view) if s["type"] == "first_party")
    assert [s["label"] for s in slide["sources"]] == ["Lista de clientes (CRM)", "Visitantes do site (pixel)"]
    assert slide["uses"][0]["where"] == "Frente de remarketing"
