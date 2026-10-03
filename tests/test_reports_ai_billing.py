import pytest
from werkzeug.exceptions import Conflict, Forbidden

from aicentralv2.cadu_connect import reports_ai
from aicentralv2.cadu_tool_billing import InsufficientToolCredits


class Ledger:
    def __init__(self, balance=100):
        self.balance, self.authorized, self.charged = balance, [], []

    def authorize(self, actor, estimate=1):
        self.authorized.append(actor)
        if self.balance < estimate:
            raise InsufficientToolCredits('Saldo insuficiente')
        return self.balance

    def authorize_firecrawl(self, actor, operation, **kwargs):
        return self.authorize(actor, 1)

    def charge_provider(self, **kwargs):
        self.charged.append(kwargs)
        return {}

    def charge_firecrawl(self, **kwargs):
        self.charged.append(kwargs)
        return {}


@pytest.fixture
def ledger(monkeypatch):
    ledger = Ledger()
    monkeypatch.setattr(reports_ai, 'CaduCreditConnector', lambda: ledger)
    return ledger


def selected(client=7, role='member', scope='all'):
    return {'client_id': client, 'user_id': 3, 'role': role, 'access_scope': scope}


def test_chat_debits_the_selected_client_not_another(ledger):
    reply = {'message': {'content': '{}'}, 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}, 'model': 'm'}
    out = reports_ai.chat('google_ads_negatives_review', [{'role': 'user', 'content': 'x'}], call=lambda messages, **kw: reply,
                          selected=selected(client=7))
    assert out is reply
    charge = ledger.charged[0]
    assert (charge['actor'].client_id, charge['actor'].user_id) == (7, 3)
    assert charge['app'] == 'Cadu Reports' and charge['stage'] == 'google_ads_negatives_review'
    assert charge['idempotency_key'].startswith('reports-ai:google_ads_negatives_review:')


def test_each_call_gets_its_own_idempotency_key(ledger):
    for _ in range(2):
        reports_ai.chat('flow_briefing', [], call=lambda messages, **kw: {'usage': {}}, selected=selected())
    assert len({item['idempotency_key'] for item in ledger.charged}) == 2


def test_typesafe_debits_usage(ledger):
    result = {'answers': {}, 'model': 'jev', 'usage': {'input_tokens': 4, 'output_tokens': 2}}
    assert reports_ai.typesafe('report_plan', {}, {}, call=lambda state, questions, **kw: result, selected=selected(client=9)) is result
    assert ledger.charged[0]['actor'].client_id == 9 and ledger.charged[0]['provider_result']['usage'] == result['usage']


def test_no_balance_blocks_before_calling_the_provider(ledger):
    ledger.balance = 0
    called = []
    with pytest.raises(Conflict):
        reports_ai.chat('flow_briefing', [], call=lambda *a, **k: called.append(1), selected=selected())
    assert not called and not ledger.charged


@pytest.mark.parametrize('chosen', [selected(scope='shared'), selected(role='viewer')])
def test_guests_and_viewers_cannot_spend_credits(ledger, chosen):
    called = []
    with pytest.raises(Forbidden):
        reports_ai.chat('flow_briefing', [], call=lambda *a, **k: called.append(1), selected=chosen)
    assert not called and not ledger.charged


def test_provider_error_is_not_charged(ledger):
    def boom(*args, **kwargs):
        raise RuntimeError('provider down')
    with pytest.raises(RuntimeError):
        reports_ai.chat('flow_briefing', [], call=boom, selected=selected())
    assert not ledger.charged


def test_billing_failure_does_not_lose_the_answer(monkeypatch):
    class Broken(Ledger):
        def charge_provider(self, **kwargs):
            raise RuntimeError('ledger down')
    monkeypatch.setattr(reports_ai, 'CaduCreditConnector', lambda: Broken())
    assert reports_ai.chat('flow_briefing', [], call=lambda *a, **k: {'ok': 1}, selected=selected()) == {'ok': 1}


def test_firecrawl_is_billed_as_one_page(ledger):
    assert reports_ai.firecrawl_scrape('page_capture', 'https://example.com/a', call=lambda url, **kw: {'screenshot': 'x'},
                                       selected=selected(client=5)) == {'screenshot': 'x'}
    charge = ledger.charged[0]
    assert charge['actor'].client_id == 5 and charge['pages'] == 1 and charge['operation'] == 'scrape'


def test_priority_review_degrades_when_credits_are_out(monkeypatch):
    """The rule-based findings must still reach the person when the AI step cannot be paid for."""
    from aicentralv2.cadu_connect import report_agents
    monkeypatch.setattr(reports_ai, 'actor_for', lambda selected=None: (_ for _ in ()).throw(Forbidden('Seu acesso não permite usar IA neste cliente.')))
    findings = [{'code': 'a', 'severity': 'high', 'title': 'A', 'evidence': ''}, {'code': 'b', 'severity': 'low', 'title': 'B', 'evidence': ''}]
    result = report_agents.prioritize(findings)
    assert result['status'] == 'unavailable' and 'IA' in result['reason']
