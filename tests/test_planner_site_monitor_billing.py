"""Planner: análise de site passa pelo conector (preço/saldo antes, débito depois)."""
from unittest import mock

import pytest
from werkzeug.exceptions import Conflict

from aicentralv2.cadu_credit_connector import CreditActor
from aicentralv2.cadu_planner import site_monitoring
from aicentralv2.cadu_tool_billing import InsufficientToolCredits

SITE = ['campaign', 'institutional', 'ecommerce', 'publisher', 'app', 'unknown']
GOAL = ['lead', 'purchase', 'engagement', 'signup', 'none']
ANSWERS = {'answers': {
    'site_type': {'type': 'choice', 'choice': 'ecommerce', 'confidence': .9,
                  'probabilities': {k: (1.0 if k == 'ecommerce' else 0.0) for k in SITE}},
    'primary_goal': {'type': 'choice', 'choice': 'purchase', 'confidence': .9,
                     'probabilities': {k: (1.0 if k == 'purchase' else 0.0) for k in GOAL}},
}, 'usage': {'prompt_tokens': 100, 'completion_tokens': 10}, 'model': 'jev-latest'}


def _run(connector, typesafe):
    with mock.patch('aicentralv2.cadu_planner.portals.crawl_public_metadata', return_value={'status': 'ok'}), \
         mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector', return_value=connector), \
         mock.patch('aicentralv2.services.typesafe_service.system_one', typesafe):
        return site_monitoring.analyze_url('https://loja.example.com/', actor=CreditActor(12, 7))


def test_analysis_is_authorized_then_charged():
    connector, typesafe = mock.Mock(), mock.Mock(return_value=ANSWERS)
    analysis = _run(connector, typesafe)
    connector.ensure_priced.assert_called_once_with(12)
    connector.authorize.assert_called_once()
    kwargs = connector.charge_provider.call_args.kwargs
    assert kwargs['actor'] == CreditActor(12, 7) and kwargs['app'] == 'Cadu Planner'
    assert analysis['suggestion']['site_type'] == 'ecommerce'


def test_no_balance_refuses_before_typesafe():
    connector, typesafe = mock.Mock(), mock.Mock(return_value=ANSWERS)
    connector.authorize.side_effect = InsufficientToolCredits('sem saldo')
    with pytest.raises(Conflict):
        _run(connector, typesafe)
    typesafe.assert_not_called()


def test_debit_failure_keeps_answer_and_logs():
    connector, typesafe = mock.Mock(), mock.Mock(return_value=ANSWERS)
    connector.charge_provider.side_effect = RuntimeError('ledger fora')
    with mock.patch.object(site_monitoring.logger, 'error') as log:
        analysis = _run(connector, typesafe)
    assert analysis['suggestion']['site_type'] == 'ecommerce'
    log.assert_called_once()
