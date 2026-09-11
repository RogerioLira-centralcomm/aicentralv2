from aicentralv2.smart_planner.cost import apply_charge, cost_from_dados, format_brl, usage_usd
from aicentralv2.smart_planner.repository import serialize_list_row


def test_format_brl_uses_brazilian_reais():
    assert format_brl(0) == ""
    assert format_brl(12.4) == "R$ 12,40"
    assert format_brl(1234.5) == "R$ 1.234,50"
    assert format_brl(0, usd=0.002) == "R$ 0,01"


def test_usage_usd_reads_openrouter_cost():
    assert usage_usd({"cost": 0.042}) == 0.042
    assert usage_usd({"total_cost": "1.5"}) == 1.5
    assert usage_usd({"tokens": 12}) is None
    assert usage_usd(None) is None


def test_apply_charge_sums_usd_then_converts():
    first = apply_charge({}, {"cost": 1}, kind="chat", model="x", rate=5.5, source="test")
    second = apply_charge(first, {"cost": 0.5}, kind="image", model="y", rate=5.5, source="test")
    assert second["usd"] == 1.5
    assert second["brl"] == 8.25
    assert second["rate"] == 5.5
    assert len(second["items"]) == 2
    assert second["items"][1]["kind"] == "image"


def test_cost_from_dados_formats_label():
    info = cost_from_dados({"cost": {"usd": 2, "brl": 11}})
    assert info["brl"] == 11
    assert info["label"] == "R$ 11,00"
    assert cost_from_dados({})["label"] == ""


def test_history_row_exposes_custo_in_reais():
    row = serialize_list_row({
        "id": 11,
        "session_token": "tok-cost",
        "cliente": "BDMG",
        "budget": "R$ 80 mil",
        "dados_detectados": {
            "plan_mode": "one_page",
            "campanha": {"canais": ["g1"]},
            "cost": {"usd": 1.2, "brl": 6.6, "items": []},
        },
        "plan_content": {},
        "briefing_melhorado": "Briefing",
    })
    assert row["verba"] == "R$ 80 mil"
    assert row["custo"] == "R$ 6,60"
    assert row["custo_brl"] == 6.6
