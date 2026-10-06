"""Catálogo comercial único e resumo de uso pelo ledger (funções puras)."""
from datetime import date

import pytest

from aicentralv2 import cadu_billing_catalog as catalog


def test_plural_handles_singular_and_plural():
    assert catalog.plural(1, "token", "tokens") == "token"
    assert catalog.plural(0, "token", "tokens") == "tokens"
    assert catalog.plural(2, "pessoa", "pessoas") == "pessoas"


def test_package_lookup_accepts_slug_and_name_without_accent():
    assert catalog.package_by_key("extra-agencia")["tokens"] == 1_000_000
    assert catalog.package_by_key("Extra Agência")["price_brl"] == 299.0
    assert catalog.package_by_key("extra agencia")["slug"] == "extra-agencia"
    assert catalog.package_by_key("Equipe") is None  # planos não são vendidos como pacote


def test_packages_from_rows_falls_back_to_code_when_table_is_empty():
    assert catalog.packages_from_rows([]) == catalog.public_packages()
    rows = [{"slug": "extra-x", "name": "Extra X", "credits": 10, "price": "5.00", "kind": "tokens"},
            {"slug": "gb-10", "name": "10 GB", "credits": 1, "price": 9, "kind": "storage"}]
    assert catalog.packages_from_rows(rows) == [
        {"slug": "extra-x", "name": "Extra X", "tokens": 10, "price_brl": 5.0, "description": ""}]


def test_finance_recipients_default_and_env(monkeypatch):
    monkeypatch.delenv("CADU_FINANCE_EMAILS", raising=False)
    assert catalog.finance_recipients() == [
        "apolo@centralcomm.media", "financeiro@centralcomm.media", "alexandre@centralcomm.media"]
    monkeypatch.setenv("CADU_FINANCE_EMAILS", "a@x.com; b@x.com")
    assert catalog.finance_recipients() == ["a@x.com", "b@x.com"]


def test_commercial_plans_do_not_invent_allowance_and_mark_current(monkeypatch):
    monkeypatch.delenv("CADU_PLAN_CATALOG_JSON", raising=False)
    plans = catalog.commercial_plans([], {"plan_definition_name": "Equipe"})
    assert [plan["slug"] for plan in plans] == ["essencial", "equipe", "agencia"]
    assert all(plan["tokens_monthly"] is None and plan["storage_gb"] is None for plan in plans)
    assert all(plan["users_unlimited"] for plan in plans)
    equipe = plans[1]
    assert equipe["current"] and equipe["cta"] == "current" and equipe["price_monthly"] == 697.0


def test_commercial_plans_include_current_internal_plan_with_commercial_name():
    plans = catalog.commercial_plans(
        [{"id": 9, "plan_type": "beta_tester", "plan_name": "Beta Tester", "tokens_monthly_limit": 50000}],
        {"plan_type": "beta_tester", "plan_definition_name": "Beta Tester", "id_plan_definition": 9})
    assert plans[0]["name"] == "Acesso antecipado"
    assert plans[0]["current"] and plans[0]["tokens_monthly"] == 50000


def test_commercial_plans_env_override(monkeypatch):
    monkeypatch.setenv("CADU_PLAN_CATALOG_JSON", '{"equipe": {"tokens_monthly": 3000000, "storage_gb": 50}}')
    equipe = catalog.commercial_plans()[1]
    assert equipe["tokens_monthly"] == 3_000_000 and equipe["storage_gb"] == 50


@pytest.mark.parametrize("today,anchor,expected", [
    (date(2026, 10, 6), 1, (date(2026, 10, 1), date(2026, 10, 31))),
    (date(2026, 2, 28), 31, (date(2026, 2, 28), date(2026, 3, 30))),
    (date(2026, 3, 10), 15, (date(2026, 2, 15), date(2026, 3, 14))),
    (date(2026, 1, 3), 20, (date(2025, 12, 20), date(2026, 1, 19))),
])
def test_current_cycle(today, anchor, expected):
    assert catalog.current_cycle(today, anchor) == expected


def test_group_interactions_merges_steps_of_one_execution():
    rows = [
        {"ferramenta": "studio", "amount": 1, "created_at": "2026-10-05T10:00:00"},
        {"ferramenta": "studio", "amount": 900, "created_at": "2026-10-05T10:03:00"},
        {"ferramenta": "chat", "amount": 50, "created_at": "2026-10-05T10:04:00"},
        {"ferramenta": "studio", "amount": 10, "created_at": "2026-10-05T11:00:00"},
    ]
    groups = catalog.group_interactions(rows)
    assert [(g["tool"], g["tokens"], g["steps"]) for g in groups] == [
        ("Studio", 10, 1), ("Chat", 50, 1), ("Studio", 901, 2)]


def test_usage_summary_reads_ledger_not_dead_plan_counter():
    plan = {"pd_tokens_monthly_limit": 2_000_000, "tokens_used_current_month": 0}
    rows = [{"ferramenta": "studio", "amount": 120_000, "created_at": "2026-10-02T09:00:00"},
            {"ferramenta": "chat", "amount": 60_000, "created_at": "2026-10-03T09:00:00"},
            {"ferramenta": "chat", "amount": 99, "created_at": "2026-09-30T09:00:00"}]  # ciclo anterior
    lots = [{"id": 1, "tokens_amount": 500_000, "tokens_used": 180_000, "status": "active"}]
    summary = catalog.usage_summary(plan=plan, usage_rows=rows, lots=lots, today=date(2026, 10, 6))
    assert summary["cycle_tokens"] == 180_000
    assert summary["allowance"] == {"active": False, "granted": 2_000_000, "used": 180_000,
                                    "available": 1_820_000, "percentage": 9.0}
    assert summary["extras"] == {"available": 320_000, "lots": 1}
    assert summary["cycle"]["renews_on"] == "2026-11-01"
    assert summary["by_tool"][0] == {"tool": "Studio", "tokens": 120_000, "interactions": 1}


def test_usage_summary_splits_allowance_and_extras_when_enabled():
    rows = [{"ferramenta": "chat", "amount": 300, "created_at": "2026-10-02T09:00:00",
             "metadata": {"allocations": [{"lot_id": 10, "tokens": 200}, {"lot_id": 11, "tokens": 100}]}}]
    lots = [{"id": 10, "source": "plan_allowance", "tokens_amount": 200, "tokens_used": 200,
             "expires_at": "2026-11-01T00:00:00", "status": "active"},
            {"id": 11, "source": "purchase", "tokens_amount": 1000, "tokens_used": 100, "status": "active"}]
    summary = catalog.usage_summary(plan={}, usage_rows=rows, lots=lots, today=date(2026, 10, 6),
                                    allowance_enabled=True)
    assert summary["allowance"]["active"] is True
    assert summary["allowance"]["available"] == 0
    assert summary["extras_used_in_cycle"] == 100
    assert summary["extras"]["available"] == 900
