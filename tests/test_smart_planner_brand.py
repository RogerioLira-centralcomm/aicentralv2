from aicentralv2.smart_planner.brand import (
    apply_pistas,
    brand_prompt_block,
    briefing_pistas,
    map_plate_channels,
    preserve_seed,
    search_parties,
    seed_parties,
    snapshot_brand,
)
from aicentralv2.smart_planner.editor import editor_context
from aicentralv2.smart_planner.helpers import name_leaks_in, redact_advertiser, session_title
from aicentralv2.smart_planner.logos import resolve_branding
from aicentralv2.smart_planner.repository import serialize_list_row


def test_editor_context_checklist_and_brand_cta():
    view = editor_context(
        {
            "session_token": "tok-edit",
            "plan_content": {"sections": []},
            "dados_detectados": {
                "plan_mode": "one_page",
                "cliente_id": 44,
                "folha": {
                    "meta": {"client": "BDMG"},
                    "branding": {
                        "client": {"name": "BDMG", "logo_url": ""},
                        "agency": {"name": "Perfil 252", "logo_url": ""},
                        "presenter": {"id": "centralcomm", "role": "support", "name": "CentralComm"},
                    },
                    "theme": {},
                    "media": {"channels": [{"id": "ooh", "label": "OOH", "pct": 40}], "pace": {"months": []}},
                    "share": {"url": "https://example.com/smart-planner/p/abc"},
                    "sections": [{
                        "id": "one_page",
                        "cards": [
                            {"type": "strategy", "title": "Tese", "body": "Tese pronta."},
                            {"type": "creative", "title": "Criativo", "body": "Peça no canal.", "channel": "ooh"},
                            {"type": "market", "stat": "12%", "stat_label": "cobertura"},
                            {"type": "defense", "body": "Porque aprovar."},
                        ],
                    }],
                },
            },
        },
        share_url="https://example.com/smart-planner/p/abc",
    )
    assert view["editor_mode"] == "one_page"
    assert any(item["id"] == "strategy" and item["done"] for item in view["folha_checks"])
    assert any(item["id"] == "compose" and item["state"] == "planned" for item in view["completo_checks"])
    assert "modelagem-criativos/marcas" in view["brand_panel"]["marcas_url"]
    assert "crm_client_id=44" in view["brand_panel"]["create_url"]


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
    assert seed["anunciante_confidencial"] is False


def test_name_leaks_uses_word_boundary():
    assert name_leaks_in("COPASA", "A COPASA precisa do app.")
    assert not name_leaks_in("COPASA", "A copasaica não é a marca.")
    assert "COPASA" not in redact_advertiser("A COPASA precisa do app.", "COPASA")


def test_create_session_persists_confidential(monkeypatch):
    from aicentralv2.smart_planner.repository import create_session

    captured = {}

    class Cursor:
        def execute(self, sql, params):
            captured["params"] = params

        def fetchone(self):
            return {"session_token": "tok", "dados_detectados": captured["params"][4]}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Conn:
        def cursor(self):
            return Cursor()

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr("aicentralv2.smart_planner.repository.get_db", lambda: Conn())
    row = create_session(
        {"user_id": 1, "user_email": "a@b.com", "user_name": "A"},
        "one_page",
        {"cliente": "COPASA", "anunciante_confidencial": True},
    )
    dados = captured["params"][4]
    if hasattr(dados, "obj"):
        dados = dados.obj
    assert dados["anunciante_confidencial"] is True
    assert row["session_token"] == "tok"


def test_seed_parties_keeps_confidential_flag():
    seed = seed_parties({"cliente": "COPASA", "anunciante_confidencial": True})
    assert seed["anunciante_confidencial"] is True


def test_preserve_seed_keeps_confidential_flag():
    merged = preserve_seed(
        {"anunciante_confidencial": True, "cliente": "COPASA", "plan_mode": "one_page"},
        {"cliente": "COPASA", "objetivo": "conversao"},
    )
    assert merged["anunciante_confidencial"] is True


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
    assert session_title(
        {"cliente": "COPASA"},
        {"anunciante_confidencial": True, "cliente": "COPASA"},
    ) == "Anunciante"
    assert session_title(
        {"nome_campanha": "COPASA Digital", "cliente": "COPASA"},
        {"anunciante_confidencial": True, "cliente": "COPASA", "nome_campanha": "COPASA Digital"},
    ) == "Anunciante"
    assert session_title(
        {"nome_campanha": "Campanha digital", "cliente": "COPASA"},
        {"anunciante_confidencial": True, "cliente": "COPASA", "nome_campanha": "Campanha digital"},
    ) == "Campanha digital"


def test_search_parties_lists_recent_with_logo(monkeypatch):
    captured = {}

    class Cursor:
        def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return [
                {"id_cliente": 44, "nome": "BDMG", "logo_url": "/static/images/marcas/bdmg.png"},
                {"id_cliente": 8, "nome": "Montana Grill", "logo_url": ""},
            ]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Conn:
        def cursor(self):
            return Cursor()

        def rollback(self):
            return None

    monkeypatch.setattr("aicentralv2.smart_planner.brand.get_db", lambda: Conn())
    rows = search_parties("", "cliente", limit=10)
    assert captured["params"] == [10]
    assert "data_modificacao" in captured["sql"]
    assert "cx_clients" in captured["sql"]
    assert rows[0]["name"] == "BDMG"
    assert rows[0]["logo_url"] == "/static/images/marcas/bdmg.png"
    assert rows[1]["logo_url"] == ""


def test_search_parties_filters_when_query_has_two_letters(monkeypatch):
    captured = {}

    class Cursor:
        def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return [{"id_cliente": 2, "nome": "BDMG", "logo_url": ""}]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Conn:
        def cursor(self):
            return Cursor()

        def rollback(self):
            return None

    monkeypatch.setattr("aicentralv2.smart_planner.brand.get_db", lambda: Conn())
    rows = search_parties("bd", "agencia")
    assert captured["params"][0] == "%bd%"
    assert "a.key = TRUE" in captured["sql"]
    assert rows[0]["id"] == 2


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
