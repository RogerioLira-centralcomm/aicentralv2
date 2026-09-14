from datetime import date

from aicentralv2.smart_planner.catalog import WIZARD_STEPS
from aicentralv2.smart_planner.helpers import campaign_from_campos
from aicentralv2.smart_planner.pace import (
    allocate_months,
    campaign_pace,
    campaign_verba,
    distribute_budget,
    format_money,
    learn_release_weights,
    pace_payload,
    parse_money,
    parse_periodo,
)
from aicentralv2.smart_planner.planner import _campaign_block


HOJE = date(2026, 9, 12)


def test_parse_money_reads_brazilian_and_monthly():
    assert parse_money("R$ 100.000")["valor"] == 100000
    assert parse_money("R$ 100.000")["base"] == "total"
    parsed = parse_money("80 mil por mês")
    assert parsed["valor"] == 80000
    assert parsed["base"] == "mensal"


def test_parse_periodo_six_months_from_today():
    parsed = parse_periodo("6 meses", HOJE)
    assert parsed["parseou"] is True
    assert parsed["meses"] == 6
    assert parsed["chaves"][0] == "2026-09"
    assert parsed["chaves"][-1] == "2027-02"


def test_parse_periodo_named_range_crosses_year():
    parsed = parse_periodo("set a fev", HOJE)
    assert parsed["meses"] == 6
    assert parsed["helper"].startswith("6 meses")


def test_ten_days_opens_weekly_columns():
    pace = campaign_pace({
        "verba": "R$ 20.000",
        "verba_valor": 20000,
        "verba_base": "total",
        "periodo": "10 dias",
    }, HOJE)
    assert pace["parseou"] is True
    assert pace["granularidade"] == "semana"
    assert pace["editavel"] is True
    assert 2 <= len(pace["chaves"]) <= 3
    assert sum(pace["alocacao"].values()) == 20000
    payload = pace_payload(pace)
    assert payload["granularidade"] == "semana"
    assert "inicio" in payload
    assert "fim" in payload


def test_thirty_days_opens_weekly_channel_plan():
    pace = campaign_pace({
        "verba": "R$ 40.000",
        "verba_valor": 40000,
        "verba_base": "total",
        "periodo": "30 dias",
    }, HOJE)
    assert pace["dias"] == 30
    assert pace["granularidade"] == "semana"
    assert pace["editavel"] is True
    assert pace["visivel"] is True
    assert 4 <= len(pace["chaves"]) <= 5
    assert sum(pace["alocacao"].values()) == 40000
    first = pace["alocacao"][pace["chaves"][0]]
    last = pace["alocacao"][pace["chaves"][-1]]
    assert first < last
    assert "semana" in pace["helper"]


def test_one_month_campaign_opens_weekly_columns():
    pace = campaign_pace({
        "verba": "R$ 40.000",
        "verba_valor": 40000,
        "verba_base": "total",
        "periodo": "1 mês",
    }, HOJE)
    assert pace["meses"] == 1
    assert pace["granularidade"] == "semana"
    assert pace["editavel"] is True
    assert len(pace["chaves"]) >= 4
    assert sum(pace["alocacao"].values()) == 40000


def test_named_month_opens_weekly_columns():
    pace = campaign_pace({
        "verba": "R$ 40.000",
        "verba_valor": 40000,
        "verba_base": "total",
        "periodo": "outubro de 2026",
    }, HOJE)
    assert pace["meses"] == 1
    assert pace["granularidade"] == "semana"
    assert pace["editavel"] is True
    assert sum(pace["alocacao"].values()) == 40000


def test_learn_release_starts_smaller_and_ends_larger():
    keys = ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02"]
    alocacao = allocate_months(keys, 100000)
    values = [alocacao[key] for key in keys]
    assert sum(values) == 100000
    assert values[0] < values[2] < values[-1]
    assert values[0] < values[-1]
    weights = learn_release_weights(6)
    assert weights[0] < weights[-1]


def test_saved_month_split_is_kept():
    keys = ["2026-09", "2026-10"]
    alocacao = allocate_months(keys, 100000, {"2026-09": 20000, "2026-10": 80000})
    assert alocacao["2026-09"] == 20000
    assert alocacao["2026-10"] == 80000


def test_long_campaign_columns_are_editable():
    pace = campaign_pace({
        "verba": "R$ 100.000 no total",
        "verba_valor": 100000,
        "verba_base": "total",
        "periodo": "6 meses",
    }, HOJE)
    assert pace["editavel"] is True
    assert pace["granularidade"] == "mes"
    assert pace["total"] == 100000
    first = pace["alocacao"][pace["chaves"][0]]
    last = pace["alocacao"][pace["chaves"][-1]]
    assert first < last


def test_channel_split_keeps_user_values():
    split = distribute_budget(["prime_video", "spotify"], 100000, {"prime_video": 50000})
    assert split["prime_video"] == 50000
    assert split["spotify"] == 50000


def test_campaign_verba_formats_text():
    verba = campaign_verba({"verba_valor": 100000, "verba_base": "total"})
    assert verba["texto"] == format_money(100000) + " no total"


def test_campaign_fields_keep_flight():
    campanha = campaign_from_campos({
        "canais": ["prime_video"],
        "verba": "R$ 100.000 no total",
        "verba_valor": 100000,
        "verba_base": "total",
        "verba_alocacao": {"2026-09": 12000},
        "canais_verba": {"prime_video": 100000},
        "periodo": "6 meses",
        "praca": "geolocalizada",
    })
    assert campanha["verba_alocacao"]["2026-09"] == 12000
    assert campanha["canais_verba"]["prime_video"] == 100000
    assert campanha["verba_base"] == "total"


def test_plan_prompt_includes_monthly_flight():
    block = _campaign_block({
        "canais": ["prime_video", "spotify"],
        "canais_verba": {"prime_video": 50000, "spotify": 50000},
        "verba": "R$ 100.000 no total",
        "verba_valor": 100000,
        "verba_base": "total",
        "periodo": "6 meses",
        "praca": "nacional",
    })
    assert "Voo mensal" in block
    assert "Prime Video" in block
    assert "50%" in block


def test_progress_calendar_shifts_toward_conversion():
    from aicentralv2.smart_planner.mix import progress_calendar, should_progress
    from aicentralv2.smart_planner.pace import campaign_pace

    assert should_progress(1) is False
    assert should_progress(6) is True
    assert should_progress(6, {"progress": False}) is False
    assert should_progress(18) is False

    pace = campaign_pace({
        "verba": "R$ 120.000 no total",
        "verba_valor": 120000,
        "verba_base": "total",
        "periodo": "6 meses",
    }, HOJE)
    calendar = progress_calendar(
        ["google_ads", "meta_ads", "netflix", "g1"],
        "vendas",
        "funil",
        pace,
        {"method": "funil", "progress": True},
        True,
    )
    assert calendar["progress"] is True
    assert calendar["months"] == 6
    google = next(row for row in calendar["rows"] if row["id"] == "google_ads")
    netflix = next(row for row in calendar["rows"] if row["id"] == "netflix")
    assert google["cells"][0]["pct"] < google["cells"][-1]["pct"]
    assert netflix["cells"][0]["pct"] > netflix["cells"][-1]["pct"]
    assert sum(cell["valor"] for cell in google["cells"]) > 0


def test_wizard_has_three_synced_steps():
    ids = [item["id"] for item in WIZARD_STEPS]
    assert ids == ["briefing", "revisao", "conclusao"]
    assert WIZARD_STEPS[1]["title"] == "Revisar briefing"
