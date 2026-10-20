"""Táticas (impacto, remarketing, DCO), formatos por canal e Rede de portais e sites.

Interativos não são canal: são tipos de formato da Rede de portais e sites, com custo agregado.
G1, UOL, CNN e os demais portais são sites da rede.
"""

import json
import time

import pytest

from aicentralv2.smart_planner import formats as fmt
from aicentralv2.smart_planner import generator, portais, repository
from aicentralv2.smart_planner.generator import (
    _material_hash,
    _one_page_payload,
    _repair_page_channels,
    _validate_page,
)
from aicentralv2.smart_planner.helpers import campaign_from_campos
from aicentralv2.smart_planner.places_bridge import apply_places_to_campos, normalize_formatos
from aicentralv2.smart_planner.service import persist_canais
from aicentralv2.smart_planner.snapshot import build_snapshot
from aicentralv2.smart_planner.taticas import (
    dco_channels,
    formats_for_channel,
    hero_scope,
    interactive_formats,
    normalize_taticas,
    primary_format,
    problems,
    tatica_by_channel,
    taticas_for_prompt,
)

HOTSPOT = "interativo-hotspots-shop-the-look"
CARDS = "interativo-cards"
BILLBOARD = "billboard-970x250"
RECTANGLE = "medium-rectangle-300x250"


@pytest.fixture(autouse=True)
def static_catalog():
    """Catálogo fixo: os testes não dependem do banco nem de mudanças no catálogo do Cadu."""
    fmt._CACHE["rows"] = fmt._static_rows()
    fmt._CACHE["at"] = time.monotonic() + 10**6
    yield
    fmt.reset_cache()


CANAIS = ["dv360", "meta_ads"]
RAW = [
    {"tipo": "impacto", "canais": ["dv360"], "formatos": ["Hotspots", "cards"], "segmento": "ab", "peso": 60},
    {"tipo": "remarketing", "canais": ["dv360"], "formatos": ["DCO", "Billboard 970x250"], "peso": 40},
]


# ---------------------------------------------------------------- formatos e migração


def test_network_formats_are_iab_and_interactive_while_social_has_its_own():
    network = {row["id"]: row for row in fmt.formats_for_channel("dv360")}
    assert BILLBOARD in network and HOTSPOT in network
    assert network[HOTSPOT]["aggregated_cost"] and not network[BILLBOARD]["aggregated_cost"]
    assert fmt.formats_for_channel("netflix") == []  # sem formato no catálogo embutido: não inventa
    assert fmt.aggregated_names([HOTSPOT, BILLBOARD, CARDS]) == ["Hotspots (Shop the Look)", "Cards"]


def test_resolve_accepts_legacy_ids_names_and_rejects_unknown():
    allowed = {row["id"] for row in fmt.formats_for_channel("dv360")}
    assert fmt.resolve_id("hotspot", allowed) == HOTSPOT
    assert fmt.resolve_id("Cards", allowed) == CARDS
    assert fmt.resolve_id("Medium Rectangle 300x250", allowed) == RECTANGLE
    assert fmt.resolve_id("inventado", allowed) == ""
    assert fmt.resolve_id(HOTSPOT, {BILLBOARD}) == ""  # fora do que o canal aceita


def test_legacy_plan_becomes_network_channel_with_formats_and_sites():
    old = {
        "canais": ["uol", "g1", "interativos", "dv360", "meta_ads"],
        "mix": {"weights": [{"id": "uol", "pct": 20}, {"id": "g1", "pct": 15}, {"id": "interativos", "pct": 25},
                            {"id": "dv360", "pct": 30}, {"id": "meta_ads", "pct": 10}]},
        "canais_verba": {"uol": 80, "g1": 60, "interativos": 100, "dv360": 120, "meta_ads": 40},
        "interativos": {"formats": ["hotspot", "cartas"]},
        "taticas": [{"tipo": "impacto", "canais": ["uol", "g1", "interativos"], "formatos": ["hotspot"]},
                    {"tipo": "remarketing", "canais": ["dv360"], "formatos": ["dco"]}],
    }
    new = fmt.migrate_campanha(old)
    assert new["canais"] == ["dv360", "meta_ads"]
    assert {row["id"]: row["pct"] for row in new["mix"]["weights"]} == {"dv360": 90, "meta_ads": 10}
    assert new["canais_verba"] == {"dv360": 360, "meta_ads": 40}
    assert new["formatos"] == {"dv360": [HOTSPOT, CARDS]}
    assert new["portais"]["sites_preferidos"] == ["UOL", "G1"]
    assert "interativos" not in new
    assert new["taticas"][0]["canais"] == ["dv360"] and new["taticas"][0]["formatos"] == [HOTSPOT]
    assert fmt.migrate_campanha(new) == new  # idempotente


def test_interativos_never_stay_in_channels_after_review_normalization():
    campos = apply_places_to_campos({"canais": ["meta_ads", "interativos"], "interativos": {"formats": ["quiz"]}}, lock_channel=True)
    assert "interativos" not in campos["canais"] and "dv360" in campos["canais"]
    assert campos["formatos"] == {"dv360": ["interativo-quiz"]}


def test_formats_must_belong_to_the_channel():
    assert normalize_formatos({"meta_ads": [HOTSPOT], "dv360": [HOTSPOT, "x"]}, ["dv360", "meta_ads"]) == {"dv360": [HOTSPOT]}
    assert normalize_formatos({"dv360": [HOTSPOT]}, ["meta_ads"]) == {}


# ---------------------------------------------------------------- táticas


def test_two_fronts_can_share_the_network_with_own_formats_and_weights():
    taticas = normalize_taticas(RAW, CANAIS)
    assert [row["tipo"] for row in taticas] == ["impacto", "remarketing"]
    assert taticas[0]["formatos"] == [HOTSPOT, CARDS] and taticas[0]["segmento"] == "AB"
    assert taticas[1]["formatos"] == ["dco", BILLBOARD]
    assert [row["peso"] for row in taticas] == [60.0, 40.0]
    assert dco_channels(taticas) == ["dv360"]
    assert interactive_formats(taticas) == [HOTSPOT, CARDS]
    assert tatica_by_channel(taticas) == {"dv360": ["impacto", "remarketing"]}
    assert formats_for_channel("dv360", [taticas[0]]) == [HOTSPOT, CARDS]


def test_weights_are_normalized_or_dropped():
    scaled = normalize_taticas([{**RAW[0], "peso": 3}, {**RAW[1], "peso": 1}], CANAIS)
    assert [row["peso"] for row in scaled] == [75.0, 25.0]
    partial = normalize_taticas([RAW[0], {**RAW[1], "peso": None}], CANAIS)
    assert [row["peso"] for row in partial] == [None, None]


def test_normalize_drops_what_the_catalog_and_mix_do_not_support():
    raw = [
        {"tipo": "impacto", "canais": ["dv360", "tiktok"], "formatos": ["Hotspots", "formato inventado", "dco"]},
        {"tipo": "remarketing", "canais": ["ooh"], "formatos": ["dco"]},
        {"tipo": "inventado", "canais": ["dv360"]},
        {"tipo": "impacto", "canais": ["dv360"]},
    ]
    taticas = normalize_taticas(raw, ["dv360", "places"])
    # O tipo vem dos formatos escolhidos: Hotspots é interativo e DCO roda em display.
    assert taticas == [{"tipo": "impacto", "canais": ["dv360"], "formatos": [HOTSPOT, "dco"],
                        "tipos_formato": ["display", "interativo"], "segmento": "", "peso": None}]
    assert normalize_taticas([{"tipo": "impacto", "canais": ["places"], "formatos": ["dco"]}], ["places"])[0]["formatos"] == []


def test_hero_comes_from_the_impact_front_and_primary_format_follows_it():
    taticas = normalize_taticas(RAW, CANAIS)
    assert hero_scope(taticas) == {"dv360"}
    first = primary_format("dv360", taticas)
    assert first["id"] == HOTSPOT and first["surface"] == "portal"
    only_dco = normalize_taticas([{"tipo": "remarketing", "canais": ["dv360"], "formatos": ["dco"]}], CANAIS)
    assert primary_format("dv360", only_dco)["id"] == "dco_dynamic"
    assert primary_format("meta_ads", taticas) is None


def test_prompt_view_uses_own_weight_and_splits_shared_channels_otherwise():
    rows = [{"id": "dv360", "label": "Rede de portais e sites", "pct": 80}, {"id": "meta_ads", "label": "Meta Ads", "pct": 20}]
    with_weight = taticas_for_prompt(normalize_taticas(RAW, CANAIS), rows)
    assert [item["peso_pct"] for item in with_weight] == [60.0, 40.0]
    assert with_weight[0]["recorte_de_portais"] == "classes AB" and with_weight[0]["formatos"][0] == "Hotspots (Shop the Look)"
    no_weight = taticas_for_prompt(normalize_taticas([{**RAW[0], "peso": None}, {**RAW[1], "peso": None}], CANAIS), rows)
    assert [item["peso_pct"] for item in no_weight] == [40.0, 40.0]  # canal dividido por igual


def test_problems_flag_missing_formats_and_network():
    taticas = normalize_taticas([{"tipo": "impacto", "canais": ["meta_ads"], "segmento": "AB"}], CANAIS)
    assert problems(taticas, ["meta_ads"]) == [
        "Impacto: o recorte AB precisa da Rede de portais e sites no mix.",
        "Impacto: escolha os formatos que a frente vai veicular.",
    ]
    assert problems(normalize_taticas(RAW, CANAIS), CANAIS) == []


# ---------------------------------------------------------------- campanha, snapshot e geração


def _row(**campanha):
    base = {"canais": CANAIS, "taticas": RAW,
            "mix": {"method": "manual", "weights": [{"id": "dv360", "pct": 80}, {"id": "meta_ads", "pct": 20}]},
            "portais": {"regioes": ["Sudeste"], "segmento": "AB"}}
    return {"id": 1, "session_token": "tok", "briefing_melhorado": "b", "dados_detectados": {"campanha": {**base, **campanha}}}


def test_campaign_from_campos_stores_formatos_and_portais():
    out = campaign_from_campos({"canais": CANAIS, "formatos": {"dv360": [HOTSPOT]}, "portais": {"segmento": "AB"}})
    assert out["formatos"] == {"dv360": [HOTSPOT]} and out["portais"] == {"segmento": "AB"}
    assert "formatos" not in campaign_from_campos({"canais": CANAIS})


def test_snapshot_merges_front_formats_into_the_channel_and_flags_cost():
    snapshot = build_snapshot(_row())
    assert snapshot["formatos"]["dv360"] == [HOTSPOT, CARDS, BILLBOARD]
    assert snapshot["formatos_com_custo_agregado"] == ["Hotspots (Shop the Look)", "Cards"]
    assert snapshot["portais"] == {"regioes": ["Sudeste"], "segmento": "AB"}
    mix = {row["id"]: row for row in snapshot["mix"]}
    assert mix["dv360"]["taticas"] == ["impacto", "remarketing"] and mix["meta_ads"]["taticas"] == []


def test_snapshot_reads_legacy_plans_in_the_new_model():
    legacy = _row(canais=["g1", "interativos"], interativos={"formats": ["quiz"]}, taticas=[], portais={},
                  mix={"method": "manual", "weights": [{"id": "g1", "pct": 40}, {"id": "interativos", "pct": 60}]})
    snapshot = build_snapshot(legacy)
    assert snapshot["channels"] == ["dv360"] and snapshot["formatos"] == {"dv360": ["interativo-quiz"]}
    assert snapshot["mix"][0]["pct"] == 100.0
    assert snapshot["portais"] == {"sites_preferidos": ["G1"]}


def test_material_hash_changes_with_formats_portals_and_fronts():
    base = _row(taticas=[])
    variants = [
        base,
        _row(taticas=[], formatos={"dv360": [HOTSPOT]}),
        _row(taticas=[], portais={"segmento": "A"}),
        _row(),
        _row(taticas=[{**RAW[0], "segmento": "A"}, RAW[1]]),
    ]
    assert len({_material_hash(item) for item in variants}) == 5


def test_payload_describes_formats_per_channel_front_weight_and_network_sites():
    snapshot = {**build_snapshot(_row()), "client": {"name": "Animale"}}
    snapshot["portais_sites"] = {"total": 13, "sites": [{"name": "Valor Econômico"}, {"name": "Exame"}],
                                 "criterios": {"segmento": "AB"}, "relaxed": ""}
    confirmed = _one_page_payload(snapshot, {}, {})["confirmado"]
    network = next(item for item in confirmed["mix"] if item["canal_id"] == "dv360")
    assert [f["nome"] for f in network["formatos"]] == ["Hotspots (Shop the Look)", "Cards", "Billboard (970x250)"]
    assert network["formatos"][0]["custo_agregado"] and "custo_agregado" not in network["formatos"][2]
    assert network["formato_principal"].startswith("Hotspots") and network["tatica"] == "impacto,remarketing"
    impacto = confirmed["taticas"][0]
    assert impacto["peso_pct"] == 60.0 and impacto["recorte_de_portais"] == "classes AB"
    assert confirmed["formatos_com_custo_agregado"] == ["Hotspots (Shop the Look)", "Cards"]
    assert confirmed["portais"]["maiores_sites"] == ["Valor Econômico", "Exame"]
    assert "interativos" not in confirmed


def test_repair_writes_formats_dco_and_segment_into_roles():
    snapshot = build_snapshot(_row())
    page = {
        "recommendation": {"channel_roles": [{"channel": "Rede de portais e sites", "role": "", "function": "Abre e retoma a audiência."}]},
        "creative_expression": {"channel": "Rede de portais e sites"},
    }
    repairs = _repair_page_channels(page, snapshot)
    role = page["recommendation"]["channel_roles"][0]
    assert "Hotspots (Shop the Look)" in role["function"] and "Cards" in role["function"]
    assert "DCO" in role["function"] and "classes AB" in role["function"]
    assert role["role"] == "intencao" and role["primary_format_id"] == HOTSPOT
    assert page["taticas"][0]["recorte_de_portais"] == "classes AB"
    assert page["formatos"]["dv360"][0]["custo_agregado"] and page["formatos_custo_agregado"]
    assert repairs
    before = json.dumps(page, ensure_ascii=False)
    _repair_page_channels(page, snapshot)
    assert json.dumps(page, ensure_ascii=False) == before  # idempotente


def test_validate_page_accepts_chosen_formats_as_primary():
    snapshot = {**build_snapshot(_row()), "client": {"name": "Animale"}}
    page = {
        "thesis": {"statement": "A coleção de Verão ganha consideração quando é explorada antes de ser comparada."},
        "recommendation": {"summary": "Interativos apresentam e o DCO retoma quem demonstrou interesse.", "channel_roles": []},
        "creative_expression": {"channel": "Rede de portais e sites"},
        "result_estimates": {"status": "not_available"},
    }
    page["creative_plan"] = generator._creative_plan(page, snapshot)
    ids = {row["channel_id"]: row["primary_format_id"] for row in page["creative_plan"]}
    assert ids["dv360"] == HOTSPOT
    _validate_page(page, snapshot, {"status": "not_available"})


def test_channel_with_chosen_formats_but_no_front_uses_the_first_as_primary():
    snapshot = build_snapshot(_row(taticas=[], formatos={"dv360": [BILLBOARD, RECTANGLE]}))
    assert generator._primary_format("dv360", snapshot)["id"] == BILLBOARD


def test_places_never_leads_and_goes_last():
    places = {"id": "places", "label": "Places", "pct": 50, "group": "places"}
    youtube = {"id": "youtube", "label": "YouTube", "pct": 30}
    snapshot = {"mix": [places, youtube]}
    assert [row["id"] for row in generator._hero_rows(snapshot["mix"], snapshot)] == ["youtube"]
    only = {"mix": [places]}
    assert [row["id"] for row in generator._hero_rows(only["mix"], only)] == ["places"]
    built = build_snapshot({"id": 1, "session_token": "t", "dados_detectados": {"campanha": {
        "canais": ["places", "youtube"], "places": [{"slug": "x"}],
        "mix": {"method": "manual", "weights": [{"id": "places", "pct": 50}, {"id": "youtube", "pct": 50}]}}}})
    assert [row["id"] for row in built["mix"]][-1] == "places"


def test_creative_plan_skips_places_when_other_channels_exist():
    snapshot = {"mix": [{"id": "places", "label": "Places", "pct": 40, "group": "places"}, {"id": "youtube", "label": "YouTube", "pct": 60}], "pace": {}}
    plan = generator._creative_plan({"recommendation": {}}, snapshot)
    assert [row["channel_id"] for row in plan] == ["youtube"]


def test_public_fronts_share_the_network_and_keep_unassigned_channels():
    from aicentralv2.smart_planner.public_view import _fronts

    page = {
        "taticas": [{"tipo": "impacto", "tatica": "Impacto", "peso_pct": 60.0, "formatos": ["Hotspots"], "recorte_de_portais": "classes AB", "para_que": "Apresenta."},
                    {"tipo": "remarketing", "tatica": "Remarketing", "peso_pct": 40.0, "formatos": ["DCO · anúncio dinâmico"]}],
        "media_narrative": {"taticas": [{"tipo": "remarketing", "descricao": "Volta a falar com quem visitou o site."}]},
    }
    channels = [{"id": "dv360", "taticas": ["impacto", "remarketing"]}, {"id": "meta_ads", "taticas": []}]
    fronts = _fronts(page, channels)
    assert [front["tipo"] for front in fronts] == ["impacto", "remarketing", "outros"]
    assert [c["id"] for c in fronts[0]["channels"]] == ["dv360"] == [c["id"] for c in fronts[1]["channels"]]
    assert fronts[0]["weight"] == 60.0 and fronts[0]["segment"] == "classes AB"
    assert fronts[1]["text"] == "Volta a falar com quem visitou o site."
    assert [c["id"] for c in fronts[2]["channels"]] == ["meta_ads"]
    assert _fronts({}, channels) == []


def test_public_titles_are_shortened_for_plans_generated_before_the_rule():
    from aicentralv2.smart_planner.public_view import _titled

    long_title = "Usar portais como vitrine editorial e gatilho de retomada para quem já viu a coleção"
    block = _titled({"title": long_title, "body": long_title})
    assert len(block["title"]) <= 64 and block["body"] == long_title
    assert _titled(None) == {}


def test_persist_canais_keeps_saved_fronts_formats_and_portals_when_payload_omits_them(monkeypatch):
    saved = {}
    row = {"session_token": "tok", "dados_detectados": {"campanha": {
        "canais": CANAIS, "taticas": RAW, "formatos": {"dv360": [HOTSPOT]}, "portais": {"segmento": "AB"},
        "verba": "R$ 100.000", "verba_valor": 100000}}}
    monkeypatch.setattr("aicentralv2.smart_planner.service.get_by_token", lambda token: row)
    monkeypatch.setattr(repository, "get_by_token", lambda token: row)
    monkeypatch.setattr(repository, "update_session", lambda token, payload: saved.update(payload) or payload)
    persist_canais("tok", {"canais": CANAIS})
    campanha = saved["dados_detectados"]["campanha"]
    assert [item["tipo"] for item in campanha["taticas"]] == ["impacto", "remarketing"]
    assert campanha["formatos"]["dv360"][0] == HOTSPOT and campanha["portais"] == {"segmento": "AB"}
    persist_canais("tok", {"canais": CANAIS, "taticas": []})
    assert saved["dados_detectados"]["campanha"]["taticas"] == []


# ---------------------------------------------------------------- portais


def test_portais_selection_is_validated():
    out = portais.normalize_portais({
        "categorias": ["Notícias gerais", "", "Notícias gerais"], "regioes": ["Sudeste", "Atlântida"],
        "ufs": ["sp", "ZZ", "SP"], "segmento": "ab", "sites_preferidos": ["G1", "G1"],
    })
    assert out == {"categorias": ["Notícias gerais"], "regioes": ["Sudeste"], "ufs": ["SP"], "segmento": "AB", "sites_preferidos": ["G1"]}
    assert portais.normalize_portais({"segmento": "Z"}) == {}


def test_portais_where_combines_category_region_uf_and_class():
    where, params = portais._where({"categorias": ["Jornalismo online", "Esportes"], "regioes": ["Sul"], "ufs": ["SP"], "segmento": "AB"})
    assert "category LIKE %s" in where and "category = %s" in where and "uf = ANY(%s)" in where and "demographics" in where
    assert params[0] == "Jornalismo online%" and params[1] == "Esportes"
    assert ["PR", "RS", "SC", "SP"] in params and "%· Sul" in params and params[-1] == "A%"


def test_sites_for_relaxes_region_before_class_and_keeps_preferred_sites(monkeypatch):
    calls = []

    def fake_rows(sql, params=None):
        calls.append(sql)
        if sql.startswith("SELECT count"):
            # só o recorte sem região tem resultado
            return [{"n": 0 if "uf = ANY" in sql or "· " in str(params) else 13}]
        return [{"name": "Valor Econômico", "domain": "valor.globo.com", "category": "Economia e negócios", "uf": None, "traffic_tier": "grande"}]

    monkeypatch.setattr("aicentralv2.cadu_family.repository.rows", fake_rows)
    result = portais.sites_for({"regioes": ["Sudeste"], "segmento": "AB", "sites_preferidos": ["Folha"]})
    assert result["total"] == 13 and result["relaxed"] == "regiao"
    assert [site["name"] for site in result["sites"]] == ["Folha", "Valor Econômico"]
    assert result["sites"][0]["preferred"] is True


def test_sites_for_survives_a_missing_database(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("sem banco")

    monkeypatch.setattr("aicentralv2.cadu_family.repository.rows", boom)
    result = portais.sites_for({"sites_preferidos": ["G1"]})
    assert result["total"] == 0 and [site["name"] for site in result["sites"]] == ["G1"]


def test_format_types_are_kept_when_the_channels_accept_them():
    rows = normalize_taticas(
        [{"tipo": "impacto", "canais": ["dv360"], "tipos_formato": ["Vídeo", "áudio", "native", "xyz"], "formatos": []}],
        ["dv360"],
    )
    # A Rede de portais aceita vídeo e native; áudio não está no catálogo dela.
    assert rows[0]["tipos_formato"] == ["video", "native"]
