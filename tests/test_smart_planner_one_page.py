from pathlib import Path

from aicentralv2.smart_planner.canvas import _row_meta
from aicentralv2.smart_planner.logos import presenter_brand, presenter_options
from aicentralv2.smart_planner.one_page import (
    assemble_from_v2,
    build_media_board,
    build_one_page,
    cards_from_pitch,
    channel_roles_for_one_page,
    match_pitch,
    normalize_one_page,
)
from aicentralv2.smart_planner.images import _default_creative_prompt
from aicentralv2.smart_planner.images import apply_sheet_art
from aicentralv2.smart_planner.theme import compose_theme, density_note_from_pace, hero_party, resolve_market_id


def test_channel_roles_keep_four_card_contract_and_group_portals():
    items = channel_roles_for_one_page({
        "mix": [
            {"id": "serasa", "label": "Serasa"},
            {"id": "g1", "label": "G1"},
            {"id": "uol", "label": "UOL"},
            {"id": "meta_ads", "label": "Meta Ads"},
        ]
    })
    assert len(items) == 3
    assert {item["label"] for item in items} == {"Serasa", "Rede de portais", "Meta Ads"}
    assert all(item["status"] == "confirmed" for item in items)


def test_match_starter_clients():
    assert match_pitch("Montana Grill", "Desafio")["id"] == "montana-grill"
    assert match_pitch("BH Airport", "Filadélfia")["id"] == "bh-airport"
    assert match_pitch("BDMG", "Perfil 252")["id"] == "bdmg"
    assert match_pitch("Minas Máquinas", "StaloIn")["id"] == "minas-maquinas"
    assert match_pitch("Outro", "Nenhuma") is None
    assert match_pitch("BH Airport", "Filadélfia", places=[{"slug": "confins"}]) is None


def test_pitch_cards_follow_joao_shape():
    pitch = match_pitch("Montana Grill", "")
    cards = cards_from_pitch(pitch)
    assert [card["type"] for card in cards] == ["strategy", "creative", "market", "defense"]
    assert cards[1]["surface"] == "ctv"
    assert cards[1]["image_url"].endswith("montana-grill-ctv.png")
    assert "Prime" in cards[1]["body"] or "CTV" in cards[1]["body"]


def test_presenter_centralcomm_is_support():
    brand = presenter_brand("centralcomm")
    assert brand["role"] == "support"
    assert brand["name"] == "CentralComm"
    labels = [item["label"] for item in presenter_options()]
    assert any("apoio" in label for label in labels)
    assert any("Serasa" in label for label in labels)


def test_normalize_keeps_branding():
    plan = normalize_one_page(
        {
            "sections": [{
                "id": "one_page",
                "cards": [
                    {"type": "strategy", "title": "Estratégia", "body": "Universo Amazon"},
                    {"type": "defense", "title": "Defesa", "body": "Atenção exclusiva"},
                ],
            }],
            "branding": {"presenter": {"id": "amazon", "name": "Amazon", "role": "principal"}},
            "meta": {"budget": "R$ 80 mil"},
        },
        {"title": "Montana", "client": "Montana Grill"},
        {"presenter": {"id": "amazon", "name": "Amazon", "role": "principal"}},
    )
    assert plan["schemaVersion"] == 3
    assert plan["branding"]["presenter"]["id"] == "amazon"
    assert plan["sections"][0]["cards"][0]["type"] == "strategy"
    assert plan["meta"]["budget"] == "R$ 80 mil"


def test_principal_brand_removes_centralcomm_from_copy(monkeypatch):
    monkeypatch.setattr(
        "aicentralv2.smart_planner.one_page.resolve_branding",
        lambda client, agency, presenter_id, partners=None, **kwargs: {
            "client": {"name": client, "logo_url": "", "id": 1},
            "agency": {"name": agency, "logo_url": "", "id": 2},
            "presenter": {"id": "serasa", "name": "Serasa Ads", "role": "principal", "logo_url": ""},
            "partners": [],
        },
    )
    plan = build_one_page(
        {"title": "BDMG", "client": "BDMG", "agency": "Perfil 252"},
        "BDMG com Serasa",
        "",
        {},
        "serasa",
    )
    assert plan["meta"]["presenter"] == "serasa"
    assert plan["branding"]["presenter"]["role"] == "principal"
    joined = " ".join(card["body"] for card in plan["sections"][0]["cards"])
    assert "CentralComm" not in joined
    assert plan["theme"]["id"] == "finance"
    assert plan["theme"]["bg_url"].endswith("bg-bdmg-finance.png")
    assert plan["share"]["path"].startswith("/smart-planner/p/")
    assert plan["branding"]["hero"]["source"] == "client"


def test_theme_and_hero_follow_market():
    assert resolve_market_id("Montana Grill", "Desafio") == "food"
    assert resolve_market_id("BH Airport", "Filadélfia") == "travel"
    theme = compose_theme("Minas Máquinas", "StaloIn", "", match_pitch("Minas Máquinas", "StaloIn"))
    assert theme["id"] == "agro"
    assert len(theme["density"]) == 3
    hero = hero_party({"client": {"name": "", "logo_url": ""}, "agency": {"name": "Desafio", "logo_url": "/x.png"}})
    assert hero["source"] == "agency"
    assert hero["name"] == "Desafio"


def test_sheet_art_uses_openrouter_gpt_image_2(monkeypatch, tmp_path):
    monkeypatch.setattr("aicentralv2.smart_planner.images._art_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        "aicentralv2.smart_planner.images.generate_image",
        lambda prompt, **kwargs: {
            "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
            "model": "openai/gpt-image-2",
        },
    )
    plan = {
        "meta": {"client": "Montana Grill"},
        "theme": {"id": "food", "bg_url": "/static/images/smart_planner/bg-montana-food.png", "bg_prompt": "ember wash"},
        "branding": {"hero": {"name": "Montana Grill"}},
        "sections": [{"cards": [{"type": "creative", "surface": "ctv", "image_url": "", "image_prompt": "CTV ad"}]}],
    }
    apply_sheet_art(plan, force=True)
    assert plan["theme"]["bg_url"].startswith("/static/images/smart_planner/generated/")
    assert plan["theme"]["bg_model"] == "openai/gpt-image-2"
    assert plan["sections"][0]["cards"][0]["image_url"].startswith("/static/images/smart_planner/generated/")
    assert plan["sections"][0]["cards"][0]["image_model"] == "openai/gpt-image-2"
    assert list(tmp_path.glob("*.png"))


def test_compose_theme_uses_snapshot_mix_not_market_preset():
    mix = [
        {"id": "ooh", "label": "OOH / Painéis", "pct": 60, "amount_label": "R$ 240.000"},
        {"id": "google_ads", "label": "Google Ads", "pct": 40, "amount_label": "R$ 160.000"},
    ]
    theme = compose_theme(
        "BDMG",
        "Perfil 252",
        "crédito",
        None,
        mix=mix,
        density_note="Começa menor, solta no meio e no fim.",
    )
    assert theme["density_caption"] == "Peso do mix"
    assert [row["label"] for row in theme["density"]] == ["OOH / Painéis", "Google Ads"]
    assert theme["density"][0]["value"] == 60
    assert theme["density"][0]["amount_label"] == "R$ 240.000"
    assert "menor" in theme["density_note"]
    preset = compose_theme("BDMG", "Perfil 252", "crédito")
    assert preset["density"][0]["label"] == "Serasa"


def test_density_note_only_for_multi_month_flight():
    assert density_note_from_pace({"labels": ["Out"], "how": "R$ 10 mil no período"}) == ""
    assert "menor" in density_note_from_pace({
        "labels": ["Out", "Nov", "Dez"],
        "how": "Começa menor, solta no meio e no fim.",
    })


def test_assemble_from_v2_persists_media_board_and_exec_meta():
    page = {
        "thesis": {"statement": "Levar cada demanda de crédito ao canal oficial."},
        "recommendation": {
            "summary": "OOH na praça e busca no serviço.",
            "audience": "Quem busca crédito em Minas",
            "channel_roles": [{"channel": "ooh", "role": "Alcance de rua"}],
        },
        "challenge": {"body": "Parte do público ainda não chega ao autosserviço."},
        "creative_expression": {"headline": "Resolva de onde estiver", "channel": "ooh", "surface": "display"},
        "result_estimates": {"status": "not_available", "summary": "Informe CPM"},
        "commercial_defense": {"why_this_mix": ["OOH leva 60% porque a praça precisa de presença."], "closing_statement": "Aprovar o mix."},
    }
    snapshot = {
        "snapshot_id": "campaign_1",
        "audiences": ["Quem busca crédito em Minas"],
        "budget": {"raw": "R$ 400 mil", "base": "total"},
        "period": {"raw": "outubro a novembro"},
        "objective": {"label": "Tráfego"},
        "geography": {"praca": "geolocalizada"},
        "mix_method": "funil",
        "mix": [
            {"id": "ooh", "label": "OOH / Painéis", "pct": 60, "amount": 240000, "amount_label": "R$ 240.000"},
            {"id": "google_ads", "label": "Google Ads", "pct": 40, "amount": 160000, "amount_label": "R$ 160.000"},
        ],
        "pace": {
            "how": "Começa menor, solta no meio e no fim.",
            "labels": ["Out", "Nov"],
            "keys": ["2026-10", "2026-11"],
            "allocation": {"2026-10": 160000, "2026-11": 240000},
        },
    }
    theme = compose_theme("BDMG", "Perfil 252", "", mix=snapshot["mix"], density_note=density_note_from_pace(snapshot["pace"]))
    media = build_media_board(
        snapshot["mix"],
        method=snapshot["mix_method"],
        pace=snapshot["pace"],
        roles=page["recommendation"]["channel_roles"],
    )
    plan = assemble_from_v2(
        {"title": "BDMG", "client": "BDMG", "agency": "Perfil 252", "market": "Geolocalizada"},
        {"client": {"name": "BDMG"}, "presenter": {"id": "centralcomm"}},
        theme,
        {},
        page,
        snapshot=snapshot,
        media=media,
    )
    assert [row["id"] for row in plan["media"]["channels"]] == ["ooh", "google_ads"]
    assert plan["media"]["channels"][0]["pct"] == 60
    assert plan["media"]["channels"][0]["role"] == "Alcance de rua"
    assert plan["media"]["method_label"] == "Funil do objetivo"
    assert plan["media"]["pace"]["months"][0]["label"] == "Out"
    assert theme["density"][0]["label"] == "OOH / Painéis"
    assert plan["meta"]["publico"] == "Quem busca crédito em Minas"
    assert "2 canais" in plan["meta"]["canais"]
    assert plan["meta"]["ritmo"].startswith("Começa menor")
    assert "60%" in plan["sections"][0]["cards"][3]["body"]


def test_folha_editor_is_enterprise_form_not_pitch_sheet():
    js = Path("aicentralv2/static/js/smart_planner/canvas.js").read_text(encoding="utf-8")
    html = Path("aicentralv2/templates/smart_planner/canvas.html").read_text(encoding="utf-8")
    css = Path("aicentralv2/static/css/smart_planner.css").read_text(encoding="utf-8")
    assert 'data-editor="1"' in html
    assert 'id="sp-folha-form"' in html
    assert "sp-gallery" in html
    assert "Marca apresentadora da folha" in html
    assert "sp-folha-checks" in html
    assert "sp-completo-checks" not in html
    assert "Protótipo visual no canal" in html
    assert "renderPitchSheet" not in js
    assert "shareBlock" not in js
    assert "applyTheme" not in js
    assert "collectEditor" in js
    assert "canvas/imagem" in js
    assert "is-folha" in css
    assert "sp-gallery-item" in css
    # Quadro completo ainda existe fora do editor da folha
    assert "renderBoard" in js
    assert "sp-board" in html


def test_creative_prompt_does_not_invent_a_brand_when_client_is_missing():
    prompt = _default_creative_prompt({"surface": "display", "body": "visitantes no aeroporto"}, {}, {})
    assert "No invented brand" in prompt
    assert "persona" in prompt


def test_row_meta_exposes_audience_and_channel_count():
    meta = _row_meta(
        {"publico_alvo": "Clientes da RMBH", "objetivo": "trafego", "budget": "R$ 400 mil", "prazo": "outubro"},
        {"campanha": {"canais": ["ooh", "google_ads"], "mix": {"method": "funil"}, "praca": "geolocalizada", "verba": "R$ 400 mil"}},
    )
    assert meta["publico"] == "Clientes da RMBH"
    assert "2 canais" in meta["canais"]
    assert meta["mix_method"] == "Funil do objetivo"
    assert meta["objective"] == "Tráfego"
