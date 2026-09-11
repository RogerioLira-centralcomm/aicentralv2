from aicentralv2.smart_planner.brand import (
    apply_pistas,
    brand_prompt_block,
    briefing_pistas,
    map_plate_channels,
    preserve_seed,
    seed_parties,
    snapshot_brand,
)
from aicentralv2.smart_planner.helpers import session_title
from aicentralv2.smart_planner.logos import resolve_branding
from aicentralv2.smart_planner.repository import serialize_list_row


def test_map_plate_channels_keeps_only_catalog_ids():
    mapped = map_plate_channels({
        "feed-1x1": ["instagram"],
        "ctv-15": ["prime_video"],
        "portal-home": ["portal"],
        "g1": ["g1"],
        "unknown": ["xyz"],
    })
    assert mapped == ["meta_ads", "prime_video", "g1"]


def test_snapshot_brand_is_compact():
    snap = snapshot_brand({
        "id": 3,
        "name": "BDMG",
        "tone_of_voice": "institucional",
        "logo_url": "/static/images/smart_planner/bdmg-serasa-app.png",
        "brand_profile": {
            "brand_summary": "Banco de desenvolvimento",
            "target_audience": "PJ mineira",
            "products_services": ["Crédito"],
            "campaign_opportunities": ["Abertura de conta"],
            "plate_channels": {"feed-1x1": ["instagram"], "foo": ["portal"]},
        },
    })
    assert snap["name"] == "BDMG"
    assert snap["has_identity"] is True
    assert snap["target_audience"] == "PJ mineira"
    assert "meta_ads" in snap["canais"]
    assert "portal" not in snap["canais"]
    assert "brand_dna" not in snap


def test_apply_pistas_keeps_confirmed_client():
    merged = apply_pistas(
        {"cliente": "Outro", "agencia": "", "publico": "do briefing", "canais": ["g1"]},
        {
            "cliente": "Montana Grill",
            "agencia": "Desafio",
            "publico": "quem janta fora",
            "canais": ["prime_video"],
        },
    )
    assert merged["cliente"] == "Montana Grill"
    assert merged["agencia"] == "Desafio"
    assert merged["publico"] == "do briefing"
    assert merged["canais"] == ["prime_video", "g1"]


def test_briefing_pistas_from_brand():
    pistas = briefing_pistas({
        "cliente": "BDMG",
        "agencia": "Perfil 252",
        "brand": {
            "brand_summary": "Crédito para PJ",
            "target_audience": "empresas de MG",
            "campaign_opportunities": ["Conta PJ"],
            "canais": ["serasa"],
        },
        "campanha": {},
    })
    assert pistas["cliente"] == "BDMG"
    assert pistas["publico"] == "empresas de MG"
    assert "Crédito para PJ" in pistas["contexto"]
    assert pistas["canais"] == ["serasa"]


def test_preserve_seed_keeps_ids_and_brand():
    current = {
        "plan_mode": "one_page",
        "cliente_id": 44,
        "agencia_id": 8,
        "cx_client_id": 3,
        "brand": {"name": "BDMG"},
        "cliente": "BDMG",
    }
    merged = preserve_seed(current, {"cliente": "BDMG", "objetivo": "leads", "campanha": {}})
    assert merged["cliente_id"] == 44
    assert merged["brand"]["name"] == "BDMG"
    assert merged["objetivo"] == "leads"
    assert merged["plan_mode"] == "one_page"


def test_seed_parties_requires_client():
    try:
        seed_parties({})
    except ValueError as exc:
        assert "anunciante" in str(exc)
    else:
        raise AssertionError("esperava ValueError")


def test_seed_parties_free_name_has_no_brand():
    seed = seed_parties({"cliente": "Marca Livre", "agencia": "Casa"})
    assert seed["cliente"] == "Marca Livre"
    assert seed["agencia"] == "Casa"
    assert seed["cliente_id"] is None
    assert seed["brand"] == {}


def test_resolve_branding_prefers_brand_snapshot():
    branding = resolve_branding(
        "Outro nome",
        "",
        "centralcomm",
        brand={"id": 3, "name": "Montana Grill", "logo_url": "/static/x.png"},
    )
    assert branding["client"]["name"] == "Montana Grill"
    assert branding["client"]["source"] == "marcas"
    assert branding["client"]["logo_url"] == "/static/x.png"


def test_history_row_uses_seeded_client():
    row = serialize_list_row({
        "id": 1,
        "session_token": "tok-brand",
        "cliente": "Montana Grill",
        "dados_detectados": {
            "plan_mode": "one_page",
            "cliente": "Montana Grill",
            "cliente_id": 99,
            "brand": {"name": "Montana Grill"},
            "campanha": {},
        },
        "plan_content": {},
        "briefing_melhorado": "",
    })
    assert row["titulo"] == "Montana Grill"
    assert row["cliente"] == "Montana Grill"
    assert row["href"] == "/smart-planner/tok-brand/briefing"


def test_session_title_from_seed():
    assert session_title(
        {"cliente": "BDMG"},
        {"campanha": {"canais": ["serasa"]}, "cliente": "BDMG"},
    ) == "BDMG"


def test_brand_prompt_block_omits_empty():
    block = brand_prompt_block({
        "name": "BDMG",
        "target_audience": "PJ",
        "products_services": [],
        "canais": ["serasa"],
    })
    assert block["nome"] == "BDMG"
    assert block["publico"] == "PJ"
    assert block["canais"] == ["serasa"]
