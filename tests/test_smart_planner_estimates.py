"""Estimativa de impacto: taxas do modelo, valores do executivo, totais e indicador do cliente."""

from aicentralv2.smart_planner import estimates
from aicentralv2.smart_planner.estimates import (
    calculate_estimates,
    format_estimates_for_prompt,
    normalize_indicator,
    normalize_media_params,
    normalize_rates,
    suggest_media_params,
)

SNAP = {
    "objective": {"id": "consideracao", "label": "Consideração"},
    "geography": {"praca": "geolocalizada", "detail": "SP, RJ e BH"},
    "audiences": ["Mulheres AB"],
    "mix": [
        {"id": "interativos", "label": "Interativos", "amount": 150000, "pct": 37.5, "tatica": "impacto", "desc": "x"},
        {"id": "dv360", "label": "Rede de portais e sites", "amount": 250000, "pct": 62.5, "tatica": "remarketing", "desc": "y"},
        {"id": "places", "label": "Places", "amount": 0, "pct": 0},
    ],
    "taticas": [],
}


def test_rates_outside_limits_are_dropped_and_origin_defaults_to_executive():
    rates = normalize_rates({"cpm": "R$ 35,50", "cpc": 900, "ctr": "1,2", "frequencia": 0, "origem": "modelo"})
    assert rates == {"cpm": 35.5, "ctr": 1.2, "origem": "modelo"}
    assert normalize_rates({"cpm": 20})["origem"] == "executivo"


def test_media_params_accepts_legacy_flat_shape_and_keeps_indicator():
    params = normalize_media_params({"dv360": {"cpm": 20, "frequency": 4}, "indicador": {"metrica": "CPC", "meta": "1,5"}}, ["dv360"])
    assert params["canais"]["dv360"]["frequencia"] == 4.0
    assert params["indicador"] == {"metrica": "cpc", "meta": 1.5, "origem": "cliente"}
    assert normalize_indicator({"metrica": "inventada", "meta": 3}) == {}


def test_calculation_from_rates_gives_totals_and_origin_label():
    params = {"canais": {
        "interativos": {"cpm": 50, "ctr": 0.8, "frequencia": 3, "origem": "modelo"},
        "dv360": {"cpm": 25, "cpc": 1.2, "frequencia": 5, "origem": "modelo"}}}
    result = calculate_estimates({**SNAP, "media_params": params})
    assert result["status"] == "available" and result["origin"] == "model_estimate" and not result["reviewed"]
    interativos = next(row for row in result["channels"] if row["id"] == "interativos")
    ref = next(s for s in interativos["scenarios"] if s["scenario"] == "referencia")
    assert ref["impressions"] == 3_000_000 and ref["reach"] == 1_000_000 and ref["clicks"] == 24_000
    totals = result["totals"]
    assert totals["invested"] == 400000 and totals["impressions"] > 3_000_000
    assert totals["impressions_low"] < totals["impressions"] < totals["impressions_high"]
    assert next(row for row in result["channels"] if row["id"] == "places")["status"] == "not_available"
    assert "Estimativa do modelo" in format_estimates_for_prompt(result)


def test_reviewed_flag_changes_the_origin():
    params = {"revisado": True, "canais": {"dv360": {"cpm": 25, "origem": "executivo"}}}
    result = calculate_estimates({**SNAP, "media_params": params})
    assert result["origin"] == "executive_reviewed" and result["reviewed"]
    assert "revisada pelo executivo" in format_estimates_for_prompt(result)


def test_client_indicator_is_compared_with_the_estimate():
    base = {"canais": {"dv360": {"cpm": 25, "cpc": 1.0, "origem": "executivo"}}}
    ok = calculate_estimates({**SNAP, "media_params": {**base, "indicador": {"metrica": "cpc", "meta": 1.5}}})
    assert ok["indicator"]["status"] == "dentro" and ok["indicator"]["estimado"] == 1.0
    over = calculate_estimates({**SNAP, "media_params": {**base, "indicador": {"metrica": "cpc", "meta": 0.5}}})
    assert over["indicator"]["status"] == "acima"
    volume = calculate_estimates({**SNAP, "media_params": {**base, "indicador": {"metrica": "impressoes", "meta": 99_000_000}}})
    assert volume["indicator"]["status"] == "abaixo"
    assert calculate_estimates({**SNAP, "media_params": base})["indicator"] == {}


def test_suggest_only_fills_missing_channels_and_never_touches_executive_values(monkeypatch):
    calls = []

    def fake_chat_json(system, user, **kwargs):
        calls.append(user)
        return {"canais": {
            "interativos": {"cpm": 48, "cpc": 2.1, "ctr": 0.9, "frequencia": 3, "racional": "Portal AB.", "confianca": "media"},
            "dv360": {"cpm": 9999},
            "places": {"cpm": 30}}, "premissas": ["Referência de mercado."]}

    monkeypatch.setattr("aicentralv2.smart_planner.ai.chat_json", fake_chat_json)
    existing = {"canais": {"dv360": {"cpm": 22, "origem": "executivo"}}, "indicador": {"metrica": "cpm", "meta": 30}}
    out = suggest_media_params(SNAP, existing)
    assert out["canais"]["dv360"] == {"cpm": 22.0, "origem": "executivo"}
    assert out["canais"]["interativos"]["origem"] == "modelo" and out["canais"]["interativos"]["cpm"] == 48.0
    # CPC coerente com CPM e CTR: 48 / (0,9 x 10) = 5,33, não o 2,1 que o modelo devolveu
    assert out["canais"]["interativos"]["cpc"] == 5.33
    assert "places" not in out["canais"] and out["revisado"] is False
    assert out["indicador"]["metrica"] == "cpm" and "Referência de mercado." in out["premissas"]
    assert len(calls) == 1 and "places" not in calls[0].lower().split("canais")[-1][:400]
    # nada faltando: não chama o modelo
    again = suggest_media_params(SNAP, out)
    assert len(calls) == 1 and again["canais"] == out["canais"]


def test_params_key_changes_with_channels_and_praca():
    other = {**SNAP, "geography": {"praca": "nacional"}}
    assert estimates.params_key(SNAP) != estimates.params_key(other)
    assert estimates.params_key(SNAP) == estimates.params_key({**SNAP, "audiences": ["Mulheres AB"]})
