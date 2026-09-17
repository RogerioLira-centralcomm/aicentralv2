from unittest import TestCase
from unittest.mock import Mock

from aicentralv2.cadu_credit_connector import CaduCreditConnector, CreditActor, firecrawl_credit_cost
from aicentralv2.cadu_tool_billing import ToolTokenLedger, estimated_credit_tokens


class CreditConnectorTest(TestCase):
    def test_actor_requires_a_client_and_user(self):
        self.assertEqual(CreditActor.from_values('174', '32'), CreditActor(174, 32))
        with self.assertRaises(ValueError):
            CreditActor.from_values(174, None)

    def test_authorization_is_bound_to_the_client_account(self):
        ledger = Mock(spec=ToolTokenLedger, unsafe=True)
        ledger.assert_available.return_value = 2499988
        connector = CaduCreditConnector(ledger)
        balance = connector.authorize(CreditActor(174, 32), 12)
        self.assertEqual(balance, 2499988)
        ledger.assert_available.assert_called_once_with(174, 12)

    def test_provider_charge_uses_the_actor_identity(self):
        ledger = Mock(spec=ToolTokenLedger, unsafe=True)
        connector = CaduCreditConnector(ledger)
        connector.charge_provider(
            actor=CreditActor(174, 32), idempotency_key='chat:run-1',
            app='Cadu Chat', stage='conversa',
            provider_result={'usage': {'prompt_tokens': 10, 'completion_tokens': 2}},
        )
        charge = ledger.charge.call_args.args[0]
        self.assertEqual((charge.client_id, charge.user_id), (174, 32))
        self.assertEqual(charge.idempotency_key, 'chat:run-1')

    def test_firecrawl_standard_units_are_explicit(self):
        self.assertEqual(firecrawl_credit_cost('scrape'), 1)
        self.assertEqual(firecrawl_credit_cost('crawl', pages=4), 4)
        self.assertEqual(firecrawl_credit_cost('search', results=10), 2)
        self.assertEqual(firecrawl_credit_cost('search', results=11), 4)

    def test_firecrawl_standard_scrape_converts_to_cadu_tokens(self):
        connector = CaduCreditConnector(Mock(spec=ToolTokenLedger, unsafe=True))
        self.assertEqual(connector.estimate_firecrawl_tokens('scrape'), 250)

    def test_commercial_margin_applies_to_measured_provider_usage(self):
        self.assertEqual(
            estimated_credit_tokens(provider_tokens=25, margin_multiplier=12),
            300,
        )
