from aicentralv2.smart_planner.logos import presenter_brand, presenter_options
from aicentralv2.smart_planner.one_page import (
    build_one_page,
    cards_from_pitch,
    match_pitch,
    normalize_one_page,
)


def test_match_starter_clients():
    assert match_pitch("Montana Grill", "Desafio")["id"] == "montana-grill"
    assert match_pitch("BH Airport", "Filadélfia")["id"] == "bh-airport"
    assert match_pitch("BDMG", "Perfil 252")["id"] == "bdmg"
    assert match_pitch("Minas Máquinas", "StaloIn")["id"] == "minas-maquinas"
    assert match_pitch("Outro", "Nenhuma") is None


def test_pitch_cards_follow_joao_shape():
    pitch = match_pitch("Montana Grill", "")
    cards = cards_from_pitch(pitch)
    assert [card["type"] for card in cards] == ["strategy", "creative", "market", "defense"]
    assert cards[1]["surface"] == "ctv"
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
        },
        {"title": "Montana", "client": "Montana Grill"},
        {"presenter": {"id": "amazon", "name": "Amazon", "role": "principal"}},
    )
    assert plan["schemaVersion"] == 3
    assert plan["branding"]["presenter"]["id"] == "amazon"
    assert plan["sections"][0]["cards"][0]["type"] == "strategy"


def test_principal_brand_removes_centralcomm_from_copy(monkeypatch):
    monkeypatch.setattr(
        "aicentralv2.smart_planner.one_page.resolve_branding",
        lambda client, agency, presenter_id, partners=None: {
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
