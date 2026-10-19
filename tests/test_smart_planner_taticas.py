"""Táticas da campanha: impacto e remarketing, DCO, interativos e recorte de portais AB."""

import json

from aicentralv2.smart_planner import generator, repository
from aicentralv2.smart_planner.generator import (
    _material_hash,
    _one_page_payload,
    _repair_page_channels,
    _validate_page,
)
from aicentralv2.smart_planner.helpers import campaign_from_campos
from aicentralv2.smart_planner.places_bridge import apply_places_to_campos, normalize_interativos
from aicentralv2.smart_planner.service import persist_canais
from aicentralv2.smart_planner.snapshot import build_snapshot
from aicentralv2.smart_planner.taticas import (
    dco_channels,
    hero_scope,
    interativos_from_taticas,
    normalize_taticas,
    primary_format,
    problems,
    taticas_for_prompt,
)

CANAIS = ["uol", "g1", "interativos", "dv360"]
RAW = [
    {"tipo": "impacto", "canais": ["uol", "g1", "interativos"], "formatos": ["hotspot", "cartas"], "segmento": "ab"},
    {"tipo": "remarketing", "canais": ["dv360"], "formatos": ["DCO"]},
]


def test_normalize_keeps_both_fronts_formats_and_segment():
    taticas = normalize_taticas(RAW, CANAIS)
    assert [row["tipo"] for row in taticas] == ["impacto", "remarketing"]
    assert taticas[0]["formatos"] == ["hotspot", "cartas"]
    assert taticas[0]["segmento"] == "AB"
    assert taticas[1]["formatos"] == ["dco"]
    assert dco_channels(taticas) == ["dv360"]
    assert interativos_from_taticas(taticas) == ["hotspot", "cartas"]


def test_normalize_drops_what_the_mix_does_not_support():
    raw = [
        {"tipo": "impacto", "canais": ["uol", "tiktok"], "formatos": ["hotspot", "dco"], "segmento": "ZZ"},
        {"tipo": "remarketing", "canais": ["ooh"], "formatos": ["dco"]},
        {"tipo": "remarketing", "canais": ["dv360"]},
        {"tipo": "inventado", "canais": ["uol"]},
        {"tipo": "impacto", "canais": ["g1"]},
    ]
    taticas = normalize_taticas(raw, ["uol", "dv360"])
    # tiktok não está no mix; hotspot exige o canal interativos; OOH nunca roda DCO.
    assert taticas[0] == {"tipo": "impacto", "canais": ["uol"], "formatos": ["dco"], "segmento": ""}
    assert [row["tipo"] for row in taticas] == ["impacto", "remarketing"]
    assert taticas[1]["canais"] == ["dv360"]


def test_dco_is_never_applied_to_interativos_or_ooh():
    taticas = normalize_taticas([{"tipo": "impacto", "canais": ["interativos", "uol"], "formatos": ["dco"]}], ["interativos", "uol"])
    assert dco_channels(taticas) == ["uol"]
    only = normalize_taticas([{"tipo": "impacto", "canais": ["interativos"], "formatos": ["dco"]}], ["interativos", "uol"])
    assert only[0]["formatos"] == []


def test_dv360_counts_as_portal_for_interativos():
    assert normalize_interativos({"formats": ["hotspot"]}, ["dv360", "interativos"]) == {"formats": ["hotspot"]}
    assert normalize_interativos({"formats": ["hotspot"]}, ["meta_ads", "interativos"]) == {"formats": []}


def test_apply_places_syncs_interativos_from_taticas():
    campos = apply_places_to_campos({"canais": CANAIS, "taticas": RAW, "interativos": {"formats": ["quiz"]}}, lock_channel=True)
    assert campos["interativos"] == {"formats": ["hotspot", "cartas"]}
    assert campos["taticas"][0]["segmento"] == "AB"


def test_apply_places_does_not_touch_taticas_when_absent():
    campos = apply_places_to_campos({"canais": CANAIS}, lock_channel=True)
    assert "taticas" not in campos


def test_removed_channel_leaves_the_tatica():
    campos = apply_places_to_campos({"canais": ["uol", "dv360"], "taticas": RAW}, lock_channel=True)
    assert [row["canais"] for row in campos["taticas"]] == [["uol"], ["dv360"]]
    assert campos["taticas"][0]["formatos"] == []


def test_campaign_from_campos_stores_taticas():
    assert campaign_from_campos({"canais": CANAIS, "taticas": RAW})["taticas"] == RAW
    assert "taticas" not in campaign_from_campos({"canais": CANAIS})


def _row(**campanha):
    base = {"canais": CANAIS, "taticas": RAW, "interativos": {"formats": ["hotspot", "cartas"]},
            "mix": {"method": "manual", "weights": [
                {"id": "uol", "pct": 20}, {"id": "g1", "pct": 15}, {"id": "interativos", "pct": 25}, {"id": "dv360", "pct": 40}]}}
    return {"id": 1, "session_token": "tok", "briefing_melhorado": "b", "dados_detectados": {"campanha": {**base, **campanha}}}


def test_snapshot_tags_channels_with_their_tatica():
    snapshot = build_snapshot(_row())
    tags = {row["id"]: row["tatica"] for row in snapshot["mix"]}
    assert tags == {"uol": "impacto", "g1": "impacto", "interativos": "impacto", "dv360": "remarketing"}
    assert [row["tipo"] for row in snapshot["taticas"]] == ["impacto", "remarketing"]


def test_hero_comes_from_the_impact_front_not_the_biggest_channel():
    snapshot = build_snapshot(_row())
    assert hero_scope(snapshot["taticas"]) == {"uol", "g1", "interativos"}
    heroes = generator._hero_rows(generator._mix_rows(snapshot), snapshot)
    assert [row["id"] for row in heroes] == ["interativos"]  # dv360 pesa 40%, mas é remarketing
    plain = build_snapshot(_row(taticas=[]))
    assert [row["id"] for row in generator._hero_rows(generator._mix_rows(plain), plain)] == ["dv360"]


def test_material_hash_changes_with_taticas():
    without = _row(taticas=[])
    with_taticas = _row()
    swapped = _row(taticas=[{**RAW[0], "segmento": "A"}, RAW[1]])
    assert len({_material_hash(item) for item in (without, with_taticas, swapped)}) == 3


def test_primary_format_follows_dco_and_chosen_interativo():
    taticas = normalize_taticas(RAW, CANAIS)
    assert primary_format("dv360", taticas)["id"] == "dco_dynamic"
    assert primary_format("interativos", taticas)["id"] == "hotspot"
    taticas = normalize_taticas([{**RAW[0], "formatos": ["cartas", "hotspot"]}], CANAIS)
    assert primary_format("interativos", taticas)["id"] == "cartas"
    assert primary_format("uol", taticas) is None


def test_payload_exposes_fronts_with_weight_dco_and_segment():
    snapshot = {**build_snapshot(_row()), "client": {"name": "Animale"}}
    confirmed = _one_page_payload(snapshot, {}, {})["confirmado"]
    impacto, remarketing = confirmed["taticas"]
    assert impacto["peso_no_mix_pct"] == 60 and impacto["recorte_de_portais"] == "classes AB"
    assert impacto["formatos"] == ["Hotspot", "Cartas"]
    assert remarketing["formatos"] == ["DCO · anúncio dinâmico"]
    assert confirmed["mix_heroi"] == "Interativos"
    dv = next(item for item in confirmed["mix"] if item["canal_id"] == "dv360")
    assert dv["formato_principal"].startswith("DCO") and dv["tatica"] == "remarketing"


def test_repair_writes_dco_formats_and_segment_into_roles():
    snapshot = build_snapshot(_row())
    page = {
        "recommendation": {"channel_roles": [
            {"channel": "Interativos", "role": "intencao", "function": "Aprofunda a consideração."},
            {"channel": "Rede de portais e sites", "role": "", "function": "Volta a falar com quem interagiu."},
        ]},
        "creative_expression": {"channel": "Rede de portais e sites"},
    }
    repairs = _repair_page_channels(page, snapshot)
    roles = {row["channel"]: row for row in page["recommendation"]["channel_roles"]}
    assert "Hotspot e Cartas" in roles["Interativos"]["function"]
    assert "classes AB" in roles["Interativos"]["function"]
    dv = roles["Rede de portais e sites"]
    assert "DCO" in dv["function"] and dv["role"] == "acao" and dv["primary_format_id"] == "dco_dynamic"
    assert {"UOL", "G1"} <= set(roles)  # canais da frente de impacto ganham papel
    assert page["creative_expression"]["channel"] == "Interativos"
    assert page["taticas"][0]["recorte_de_portais"] == "classes AB"
    assert repairs
    # idempotente: rodar de novo não duplica texto
    before = json.dumps(page, ensure_ascii=False)
    _repair_page_channels(page, snapshot)
    assert json.dumps(page, ensure_ascii=False).count("Hotspot e Cartas") == before.count("Hotspot e Cartas")


def test_validate_page_accepts_dco_and_interativo_primary_formats():
    snapshot = build_snapshot(_row())
    snapshot["client"] = {"name": "Animale"}
    page = {
        "thesis": {"statement": "A coleção de Verão ganha consideração quando é explorada antes de ser comparada."},
        "recommendation": {"summary": "Interativos apresentam e o DCO retoma quem demonstrou interesse.", "channel_roles": []},
        "creative_expression": {"channel": "Interativos"},
        "result_estimates": {"status": "not_available"},
    }
    page["creative_plan"] = generator._creative_plan(page, snapshot)
    ids = {row["channel_id"]: row["primary_format_id"] for row in page["creative_plan"]}
    assert ids["dv360"] == "dco_dynamic" and ids["interativos"] == "hotspot"
    _validate_page(page, snapshot, {"status": "not_available"})


def test_problems_warn_about_missing_interativo_formats():
    taticas = normalize_taticas([{"tipo": "impacto", "canais": ["interativos", "uol"]}], CANAIS)
    assert problems(taticas, CANAIS) == ["Impacto: escolha os formatos interativos."]
    assert problems(normalize_taticas(RAW, CANAIS), CANAIS) == []


def test_taticas_for_prompt_uses_labels_and_rounds_weight():
    rows = [{"id": "uol", "label": "UOL", "pct": 20.04}, {"id": "dv360", "label": "Rede de portais e sites", "pct": 40}]
    out = taticas_for_prompt(normalize_taticas([{"tipo": "impacto", "canais": ["uol"]}], ["uol", "dv360"]), rows)
    assert out[0]["canais"] == ["UOL"] and out[0]["peso_no_mix_pct"] == 20.0


def test_persist_canais_keeps_saved_taticas_when_payload_omits_them(monkeypatch):
    saved = {}
    row = {"session_token": "tok", "dados_detectados": {"campanha": {"canais": CANAIS, "taticas": RAW, "verba": "R$ 100.000", "verba_valor": 100000}}}
    monkeypatch.setattr("aicentralv2.smart_planner.service.get_by_token", lambda token: row)
    monkeypatch.setattr(repository, "get_by_token", lambda token: row)
    monkeypatch.setattr(repository, "update_session", lambda token, payload: saved.update(payload) or payload)
    persist_canais("tok", {"canais": CANAIS})
    campanha = saved["dados_detectados"]["campanha"]
    assert [item["tipo"] for item in campanha["taticas"]] == ["impacto", "remarketing"]
    persist_canais("tok", {"canais": CANAIS, "taticas": []})
    assert saved["dados_detectados"]["campanha"]["taticas"] == []


def test_public_fronts_group_channels_and_keep_unassigned_ones():
    from aicentralv2.smart_planner.public_view import _fronts

    page = {
        "taticas": [{"tipo": "impacto", "tatica": "Impacto", "peso_no_mix_pct": 60.0, "formatos": ["Hotspot"], "recorte_de_portais": "classes AB", "para_que": "Apresenta."},
                    {"tipo": "remarketing", "tatica": "Remarketing", "peso_no_mix_pct": 40.0, "formatos": ["DCO · anúncio dinâmico"]}],
        "media_narrative": {"taticas": [{"tipo": "remarketing", "descricao": "Volta a falar com quem visitou o site."}]},
    }
    channels = [{"id": "uol", "tatica": "impacto"}, {"id": "dv360", "tatica": "remarketing"}, {"id": "meta_ads", "tatica": ""}]
    fronts = _fronts(page, channels)
    assert [front["tipo"] for front in fronts] == ["impacto", "remarketing", "outros"]
    assert fronts[0]["segment"] == "classes AB" and fronts[0]["text"] == "Apresenta."
    assert fronts[1]["text"] == "Volta a falar com quem visitou o site."
    assert [c["id"] for c in fronts[2]["channels"]] == ["meta_ads"]
    assert _fronts({}, channels) == []


def test_public_titles_are_shortened_for_plans_generated_before_the_rule():
    from aicentralv2.smart_planner.public_view import _titled

    long_title = "Usar portais como vitrine editorial e gatilho de retomada para quem já viu a coleção"
    block = _titled({"title": long_title, "body": long_title})
    assert len(block["title"]) <= 64 and block["body"] == long_title
    assert _titled(None) == {}


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
