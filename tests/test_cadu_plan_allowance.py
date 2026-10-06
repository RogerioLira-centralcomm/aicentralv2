"""Franquia do plano como lote: ciclo, expiração, ordem de débito e idempotência."""
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from aicentralv2 import cadu_plan_allowance as allowance


def test_switch_is_off_by_default(monkeypatch):
    monkeypatch.delenv("CADU_PLAN_ALLOWANCE_ENABLED", raising=False)
    assert allowance.allowance_enabled() is False
    cursor = MagicMock()
    assert allowance.ensure_plan_allowance(cursor, 12) is None
    cursor.execute.assert_not_called()
    assert allowance.debit_order_sql(cursor) == "ORDER BY expires_at NULLS LAST, purchased_at, id"


def test_new_cycle_grants_allowance_and_expires_previous():
    lots = [{"id": 5, "source": "plan_allowance", "cycle_start": date(2026, 9, 1), "status": "active"},
            {"id": 6, "source": "purchase", "status": "active"}]
    actions = allowance.plan_allowance_actions(today=date(2026, 10, 6), anchor_day=1,
                                               tokens_monthly=2_000_000, lots=lots)
    assert actions["expire"] == [5]  # extras nunca expiram por aqui
    assert actions["grant"] == {"tokens": 2_000_000, "cycle_start": date(2026, 10, 1),
                                "expires_at": datetime(2026, 11, 1)}


def test_grant_is_idempotent_within_the_cycle():
    lots = [{"id": 7, "source": "plan_allowance", "cycle_start": "2026-10-01", "status": "active"}]
    actions = allowance.plan_allowance_actions(today=date(2026, 10, 20), anchor_day=1,
                                               tokens_monthly=2_000_000, lots=lots)
    assert actions["grant"] is None and actions["expire"] == []


def test_no_allowance_configured_grants_nothing():
    actions = allowance.plan_allowance_actions(today=date(2026, 10, 6), anchor_day=1, tokens_monthly=0, lots=[])
    assert actions["grant"] is None


def test_debit_uses_allowance_before_extras_even_if_extra_expires_sooner():
    lots = [
        {"id": 1, "source": "purchase", "tokens_amount": 1000, "tokens_used": 0, "expires_at": datetime(2026, 10, 10)},
        {"id": 2, "source": "purchase", "tokens_amount": 1000, "tokens_used": 0, "expires_at": None},
        {"id": 3, "source": "plan_allowance", "tokens_amount": 500, "tokens_used": 100, "expires_at": datetime(2026, 11, 1)},
    ]
    assert allowance.allocate_debit(lots, 1500) == [
        {"lot_id": 3, "tokens": 400}, {"lot_id": 1, "tokens": 1000}, {"lot_id": 2, "tokens": 100}]


def test_debit_with_insufficient_balance_raises_without_allocating():
    with pytest.raises(allowance.InsufficientAllowanceBalance, match="Saldo insuficiente"):
        allowance.allocate_debit([{"id": 1, "tokens_amount": 10, "tokens_used": 5}], 6)


def test_balance_from_rows_off_keeps_current_total(monkeypatch):
    monkeypatch.delenv("CADU_PLAN_CATALOG_JSON", raising=False)
    lots = [{"id": 1, "tokens_amount": 1000, "tokens_used": 400}]
    balance = allowance.balance_from_rows(plan={"plan_type": "pro", "tokens_monthly_limit": 2_000_000},
                                          lots=lots, today=date(2026, 10, 6), enabled=False)
    assert balance["total_available"] == 600
    assert balance["franchise"]["active"] is False
    assert balance["franchise"]["renews_on"] == "2026-11-01"


def test_balance_from_rows_on_sums_franchise_and_extras():
    lots = [{"id": 1, "source": "purchase", "tokens_amount": 1000, "tokens_used": 400},
            {"id": 2, "source": "plan_allowance", "cycle_start": "2026-10-01", "tokens_amount": 500, "tokens_used": 50}]
    balance = allowance.balance_from_rows(plan={}, lots=lots, today=date(2026, 10, 6), enabled=True)
    assert balance["franchise"]["available"] == 450
    assert balance["extras"] == {"available": 600, "lots": 1}
    assert balance["total_available"] == 1050


def test_ensure_plan_allowance_inserts_grant_and_expires_old(monkeypatch):
    monkeypatch.setenv("CADU_PLAN_ALLOWANCE_ENABLED", "1")
    monkeypatch.setattr(allowance, "_SOURCE_COLUMN", {"value": True})
    cursor = MagicMock()
    cursor.fetchone.return_value = {"client_plan_id": 3, "plan_type": "pro", "plan_name": "Pro",
                                    "plan_definition_name": "Pro", "tokens_monthly_limit": 1000}
    cursor.fetchall.return_value = [{"id": 5, "source": "plan_allowance", "cycle_start": date(2026, 9, 1), "status": "active"}]
    actions = allowance.ensure_plan_allowance(cursor, 12, today=date(2026, 10, 6))
    sql = " ".join(call.args[0] for call in cursor.execute.call_args_list)
    assert actions["expire"] == [5] and actions["grant"]["tokens"] == 1000
    assert "SET status = 'expired'" in sql and "ON CONFLICT DO NOTHING" in sql
    assert "RELEASE SAVEPOINT" in sql


def test_ensure_plan_allowance_rolls_back_savepoint_on_error(monkeypatch):
    monkeypatch.setenv("CADU_PLAN_ALLOWANCE_ENABLED", "1")
    monkeypatch.setattr(allowance, "_SOURCE_COLUMN", {"value": True})
    cursor = MagicMock()
    cursor.fetchone.side_effect = RuntimeError("boom")
    assert allowance.ensure_plan_allowance(cursor, 12, today=date(2026, 10, 6)) is None
    assert "ROLLBACK TO SAVEPOINT" in cursor.execute.call_args_list[-1].args[0]
