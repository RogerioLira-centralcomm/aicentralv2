import copy
import unittest
from decimal import Decimal

from aicentralv2.cadu_tool_billing import (
    InsufficientToolCredits,
    ToolCharge,
    ToolTokenLedger,
    cost_token_equivalent,
    estimated_credit_tokens,
    usage_tokens,
)


class FakeLedgerDb:
    def __init__(self, lots):
        self.lots = {row["id"]: dict(row) for row in lots}
        self.usage = {}
        self.next_id = 1

    def connect(self):
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, db):
        self.db = db
        self.before = (copy.deepcopy(db.lots), copy.deepcopy(db.usage), db.next_id)

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        self.before = (copy.deepcopy(self.db.lots), copy.deepcopy(self.db.usage), self.db.next_id)

    def rollback(self):
        self.db.lots, self.db.usage, self.db.next_id = copy.deepcopy(self.before)


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.one = None
        self.many = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.one, self.many = None, []
        if compact.startswith("SELECT COALESCE(SUM(tokens_amount - tokens_used)"):
            client = params[0]
            self.one = {"available": sum(
                row["tokens_amount"] - row["tokens_used"]
                for row in self.db.lots.values()
                if row["id_cliente"] == client and row["status"] == "active"
            )}
        elif compact.startswith("INSERT INTO cadu_tools_token_usage"):
            key = params[0]
            if key in self.db.usage:
                return
            ident = self.db.next_id
            self.db.next_id += 1
            row = {
                "id": ident, "idempotency_key": key, "id_cliente": params[1],
                "id_contato_cliente": params[2], "ferramenta": params[3],
                "etapa": params[4], "modelo": params[5], "tokens_entrada": params[6],
                "tokens_saida": params[7], "total_tokens": params[8],
                "tokens_cobrados": params[9], "status": "pending",
            }
            self.db.usage[key] = row
            self.one = {"id": ident}
        elif "FROM cadu_credits_extras" in compact and "FOR UPDATE" in compact:
            client = params[0]
            self.many = [dict(row) for row in sorted(self.db.lots.values(), key=lambda row: row["id"])
                         if row["id_cliente"] == client and row["status"] == "active"
                         and row["tokens_used"] < row["tokens_amount"]]
        elif compact.startswith("UPDATE cadu_credits_extras"):
            used, ident = params
            self.db.lots[ident]["tokens_used"] += used
        elif compact.startswith("UPDATE cadu_tools_token_usage"):
            _metadata, ident = params
            row = next(row for row in self.db.usage.values() if row["id"] == ident)
            row["status"] = "charged"
            self.one = dict(row)
        elif compact.startswith("SELECT * FROM cadu_tools_token_usage"):
            row = self.db.usage.get(params[0])
            self.one = dict(row) if row else None
        else:
            raise AssertionError(compact)

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


def charge(key="run-1", tokens=120):
    return ToolCharge(
        idempotency_key=key,
        client_id=10,
        user_id=7,
        tool="studio.image",
        stage="generation",
        model="openai/gpt-image-2",
        input_tokens=10,
        output_tokens=20,
        provider_total_tokens=30,
        charged_tokens=tokens,
        internal_cost_usd=Decimal("0.14"),
    )


class ToolTokenLedgerTest(unittest.TestCase):
    def test_usage_and_media_cost_are_expressed_as_tokens(self):
        self.assertEqual(usage_tokens({"prompt_tokens": 10, "completion_tokens": 4}), (10, 4, 14))
        self.assertEqual(cost_token_equivalent("0.14", usd_per_credit_token="0.00001"), 14000)
        self.assertEqual(estimated_credit_tokens(provider_tokens=14, media_tokens=100), 114)

    def test_margin_multiplier_protects_media_and_text_costs(self):
        self.assertEqual(cost_token_equivalent("0.22", usd_per_credit_token="0.00001", margin_multiplier=8), 176000)
        self.assertEqual(cost_token_equivalent("0.02", usd_per_credit_token="0.00001", margin_multiplier=12), 24000)

    def test_media_equivalent_can_include_provider_tokens_without_double_charge(self):
        provider_tokens = usage_tokens({"input_tokens": 10, "output_tokens": 4})[2]
        total_equivalent = cost_token_equivalent("0.001", usd_per_credit_token="0.00001")
        additional_media_tokens = max(0, total_equivalent - provider_tokens)
        self.assertEqual(
            estimated_credit_tokens(provider_tokens=provider_tokens, media_tokens=additional_media_tokens),
            total_equivalent,
        )

    def test_charge_consumes_lots_fifo_and_is_idempotent(self):
        db = FakeLedgerDb([
            {"id": 1, "id_cliente": 10, "tokens_amount": 50, "tokens_used": 0, "status": "active"},
            {"id": 2, "id_cliente": 10, "tokens_amount": 100, "tokens_used": 0, "status": "active"},
        ])
        ledger = ToolTokenLedger(db.connect)
        first = ledger.charge(charge())
        replay = ledger.charge(charge())
        self.assertEqual(first["status"], "charged")
        self.assertEqual(replay["id"], first["id"])
        self.assertEqual(db.lots[1]["tokens_used"], 50)
        self.assertEqual(db.lots[2]["tokens_used"], 70)
        self.assertEqual(len(db.usage), 1)

    def test_insufficient_balance_rolls_back_usage_and_lots(self):
        db = FakeLedgerDb([
            {"id": 1, "id_cliente": 10, "tokens_amount": 20, "tokens_used": 0, "status": "active"},
        ])
        ledger = ToolTokenLedger(db.connect)
        with self.assertRaises(InsufficientToolCredits):
            ledger.charge(charge(tokens=21))
        self.assertEqual(db.lots[1]["tokens_used"], 0)
        self.assertEqual(db.usage, {})


if __name__ == "__main__":
    unittest.main()
