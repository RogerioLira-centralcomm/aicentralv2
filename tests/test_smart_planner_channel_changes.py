"""Troca de canais, mix sem verba e remontagem do one page no Smart Planner."""

import json

from aicentralv2.smart_planner import generator, repository
from aicentralv2.smart_planner.generator import (
    _fit_json,
    _material_hash,
    _pack,
    _repair_page_channels,
    _usable_market,
    _validate_page,
)
from aicentralv2.smart_planner.mix import normalize_mix
from aicentralv2.smart_planner.snapshot import build_snapshot, mix_shares


def _row(campanha, **dados):
    return {"id": 1, "session_token": "tok", "dados_detectados": {"campanha": campanha, **dados}}


def test_mix_without_budget_keeps_user_weights():
    mix = normalize_mix(
        {"method": "manual", "locked": True, "weights": [{"id": "meta_ads", "pct": 70}, {"id": "youtube", "pct": 30}]},
        ["meta_ads", "youtube"],
        "vendas",
    )
    snapshot = build_snapshot(_row({"canais": ["meta_ads", "youtube"], "mix": mix}))
    assert [(row["id"], row["pct"]) for row in snapshot["mix"]] == [("meta_ads", 70.0), ("youtube", 30.0)]
    assert all(not row["amount"] for row in snapshot["mix"])


def test_mix_with_budget_uses_weights_for_money():
    shares, split = mix_shares(
        {
            "verba": "R$ 100.000",
            "verba_valor": 100000,
            "canais_verba": {"google_ads": 80000, "meta_ads": 20000},
            "mix": {"weights": [{"id": "meta_ads", "pct": 40}, {"id": "youtube", "pct": 60}]},
        },
        ["meta_ads", "youtube"],
    )
    assert shares == {"meta_ads": 40.0, "youtube": 60.0}
    assert split == {"meta_ads": 40000, "youtube": 60000}


def test_stale_split_ignores_removed_channels():
    shares, split = mix_shares({"canais_verba": {"google_ads": 80000, "meta_ads": 20000}}, ["meta_ads", "youtube"])
    assert "google_ads" not in split and "google_ads" not in shares
    assert shares == {"meta_ads": 100.0}


def _save(monkeypatch, stored, campos):
    saved = {}
    monkeypatch.setattr(repository, "get_by_token", lambda token: {"session_token": token, "dados_detectados": stored})
    monkeypatch.setattr(repository, "update_session", lambda token, payload: saved.update(payload) or payload)
    repository.save_campos("tok", campos)
    return saved["dados_detectados"]["campanha"]


def test_save_campos_prunes_removed_channel_money(monkeypatch):
    stored = {"campanha": {
        "canais": ["google_ads", "meta_ads"],
        "canais_verba": {"google_ads": 80000, "meta_ads": 20000},
        "verba": "R$ 100.000",
        "verba_valor": 100000,
    }}
    campanha = _save(monkeypatch, stored, {"canais": ["youtube", "meta_ads"], "verba": "R$ 100.000"})
    assert campanha["canais"] == ["youtube", "meta_ads"]
    assert campanha["canais_verba"] == {"meta_ads": 20000}


def test_save_campos_allows_clearing_budget_and_praca(monkeypatch):
    stored = {"campanha": {
        "canais": ["meta_ads"],
        "canais_verba": {"meta_ads": 100000},
        "verba": "R$ 100.000",
        "verba_valor": 100000,
        "verba_alocacao": {"2027-03": 100000},
        "praca": "sp",
        "dispositivos": ["mobile"],
    }}
    campanha = _save(monkeypatch, stored, {"canais": ["meta_ads"], "verba": "", "praca": ""})
    assert campanha["verba"] == ""
    assert campanha["verba_valor"] == 0
    assert campanha["canais_verba"] == {}
    assert campanha["verba_alocacao"] == {}
    assert campanha["praca"] == ""
    # Campo que o formulário não enviou continua como estava.
    assert campanha["dispositivos"] == ["mobile"]


def test_material_hash_changes_with_mix_places_and_interativos():
    base = {"canais": ["meta_ads", "youtube"], "mix": {"method": "funil", "weights": [{"id": "meta_ads", "pct": 50}, {"id": "youtube", "pct": 50}]}}
    row = {"briefing_melhorado": "b", "dados_detectados": {"campanha": base}}
    rebalanced = {"briefing_melhorado": "b", "dados_detectados": {"campanha": {**base, "mix": {"method": "manual", "weights": [{"id": "meta_ads", "pct": 80}, {"id": "youtube", "pct": 20}]}}}}
    with_place = {"briefing_melhorado": "b", "dados_detectados": {"campanha": {**base, "places": [{"slug": "shopping-x"}]}}}
    with_interativos = {"briefing_melhorado": "b", "dados_detectados": {"campanha": {**base, "interativos": {"formats": ["quiz"]}}}}
    hashes = {_material_hash(item) for item in (row, rebalanced, with_place, with_interativos)}
    assert len(hashes) == 4


def test_market_research_redone_when_praca_changes():
    row = {"briefing_melhorado": "b", "dados_detectados": {"campanha": {"praca": "sp"}}}
    moved = {"briefing_melhorado": "b", "dados_detectados": {"campanha": {"praca": "rj"}}}
    key = generator._market_key(row)
    assert key != generator._market_key(moved)
    assert _usable_market({"market_research": "x", "market_research_key": key}, key, "h")
    assert not _usable_market({"market_research": "x", "market_research_key": key}, generator._market_key(moved), "h")
    # Pesquisa antiga sem chave vale só enquanto o material é o mesmo.
    assert _usable_market({"market_research": "x", "material_hash": "h"}, key, "h")
    assert not _usable_market({"market_research": "x", "material_hash": "old"}, key, "h")


SNAPSHOT = {
    "client": {"name": "Marca"},
    "channels": ["meta_ads", "youtube"],
    "mix": [
        {"id": "youtube", "label": "YouTube", "pct": 60},
        {"id": "meta_ads", "label": "Meta Ads", "pct": 40},
    ],
}


def test_repair_moves_creative_to_hero_and_adds_hero_role():
    page = {
        "thesis": {"statement": "A marca precisa ganhar lembrança entre jovens da capital."},
        "recommendation": {"summary": "Vídeo abre, social sustenta.", "channel_roles": [{"channel": "Meta Ads", "role": "acao"}, {"channel": "TikTok"}]},
        "creative_expression": {"channel": "Meta Ads", "headline": "Oi"},
    }
    repairs = _repair_page_channels(page, SNAPSHOT)
    channels = [role["channel"] for role in page["recommendation"]["channel_roles"]]
    assert channels == ["YouTube", "Meta Ads"]
    assert page["creative_expression"]["channel"] == "YouTube"
    assert page["creative_expression"]["headline"] == "Oi"
    assert len(repairs) == 3


def test_validate_page_no_longer_fails_on_creative_outside_hero():
    page = {
        "thesis": {"statement": "A marca precisa ganhar lembrança entre jovens da capital."},
        "recommendation": {"summary": "Vídeo abre, social sustenta.", "channel_roles": [{"channel": "Meta Ads"}]},
        "creative_expression": {"channel": "Meta Ads"},
        "creative_plan": [],
    }
    _validate_page(page, SNAPSHOT, {"status": "not_available"})
    assert page["creative_expression"]["channel"] == "YouTube"


def test_pack_stays_valid_json_when_too_big():
    huge = "x" * 60000
    packed = _pack(
        {"client": {"name": "Marca"}, "briefing": huge, "conteudo_capturado": huge, "market_research": huge},
        {"briefing": huge, "conteudo_capturado": huge, "market_research": huge, "user_briefing": huge},
        {"central_thesis": "Tese"},
    )
    data = json.loads(packed)
    assert len(packed) <= 36000
    assert data["strategy_core"]["central_thesis"] == "Tese"


def test_fit_json_never_cuts_mid_string():
    payload = {"snapshot": {"briefing": "é" * 50000, "client": {"name": "Marca"}}, "evidence": {}}
    dumped = _fit_json(payload, 20000)
    assert json.loads(dumped)["snapshot"]["client"]["name"] == "Marca"
    assert payload["snapshot"]["briefing"] == "é" * 50000  # o original não muda


def test_market_research_survives_channel_swap():
    row = {"briefing_melhorado": "b", "dados_detectados": {"campanha": {"praca": "sp", "canais": ["meta_ads"]}}}
    swapped = {"briefing_melhorado": "b", "dados_detectados": {"campanha": {"praca": "sp", "canais": ["youtube"]}}}
    assert generator._market_key(row) == generator._market_key(swapped)
