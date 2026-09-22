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
from aicentralv2.cadu_credit_connector import CaduCreditConnector, CreditActor


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
            claim = len(params) == 7
            row = {
                "id": ident, "idempotency_key": key, "id_cliente": params[1],
                "id_contato_cliente": params[2], "ferramenta": params[3],
                "etapa": params[4], "modelo": params[5],
                "tokens_entrada": 0 if claim else params[6],
                "tokens_saida": 0 if claim else params[7],
                "total_tokens": 0 if claim else params[8],
                "tokens_cobrados": 0 if claim else params[9], "status": "pending",
                "metadata": {"ai_generation_claim": True} if claim else {},
            }
            self.db.usage[key] = row
            self.one = dict(row) if "RETURNING *" in compact else {"id": ident}
        elif "FROM cadu_credits_extras" in compact and "FOR UPDATE" in compact:
            client = params[0]
            self.many = [dict(row) for row in sorted(self.db.lots.values(), key=lambda row: row["id"])
                         if row["id_cliente"] == client and row["status"] == "active"
                         and row["tokens_used"] < row["tokens_amount"]]
        elif compact.startswith("UPDATE cadu_credits_extras"):
            used, ident = params
            self.db.lots[ident]["tokens_used"] += used
        elif compact.startswith("UPDATE cadu_tools_token_usage") and "SET modelo=" in compact:
            model, incoming, outgoing, total, charged, _internal, _additional, _metadata, ident = params
            row = next(row for row in self.db.usage.values() if row["id"] == ident)
            row.update(modelo=model, tokens_entrada=incoming, tokens_saida=outgoing,
                       total_tokens=total, tokens_cobrados=charged)
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

    def test_generation_claim_is_finalized_without_a_second_usage_row(self):
        db = FakeLedgerDb([
            {"id": 1, "id_cliente": 10, "tokens_amount": 200, "tokens_used": 0, "status": "active"},
        ])
        ledger = ToolTokenLedger(db.connect)
        claimed = ledger.claim_generation(charge(tokens=0))
        completed = ledger.charge(charge(tokens=120))

        self.assertTrue(claimed["claim_acquired"])
        self.assertEqual(completed["status"], "charged")
        self.assertEqual(len(db.usage), 1)
        self.assertEqual(db.lots[1]["tokens_used"], 120)

    def test_insufficient_balance_rolls_back_usage_and_lots(self):
        db = FakeLedgerDb([
            {"id": 1, "id_cliente": 10, "tokens_amount": 20, "tokens_used": 0, "status": "active"},
        ])
        ledger = ToolTokenLedger(db.connect)
        with self.assertRaises(InsufficientToolCredits):
            ledger.charge(charge(tokens=21))
        self.assertEqual(db.lots[1]["tokens_used"], 0)
        self.assertEqual(db.usage, {})

    def test_connector_owns_fixed_token_debits_for_cadu_apps(self):
        db = FakeLedgerDb([
            {"id": 1, "id_cliente": 10, "tokens_amount": 200, "tokens_used": 0, "status": "active"},
        ])
        connector = CaduCreditConnector(ToolTokenLedger(db.connect))

        result = connector.charge_tokens(
            actor=CreditActor.from_values(10, 7),
            idempotency_key="analyzer:reservation:1",
            app="Cadu Analyzer",
            stage="image_analysis",
            model="creative-analyzer",
            charged_tokens=120,
        )

        self.assertEqual(result["tokens_cobrados"], 120)
        self.assertEqual(db.lots[1]["tokens_used"], 120)
        self.assertEqual(db.usage["analyzer:reservation:1"]["ferramenta"], "Cadu Analyzer")

    def test_cadu_products_do_not_write_directly_to_the_token_ledger(self):
        root = __import__("pathlib").Path(__file__).resolve().parents[1] / "aicentralv2"
        product_files = [
            root / "creative_analyzer" / "service.py",
            root / "creative_format_lab" / "animate.py",
            root / "creative_format_lab" / "service.py",
            root / "creative_media" / "studio_create.py",
        ]
        sources = "\n".join(path.read_text(encoding="utf-8") for path in product_files)

        self.assertNotIn("ToolTokenLedger", sources)
        self.assertNotIn("charge_from_provider", sources)
        self.assertNotIn(".charge(ToolCharge", sources)


if __name__ == "__main__":
    unittest.main()
