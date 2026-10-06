import pytest


class FakeCredits:
    """Stands in for the credit connector in Reports tests; records what would have been debited."""
    charges = []

    def ensure_priced(self, client_id):
        return None

    def authorize(self, actor, estimate=1):
        return 10 ** 9

    def authorize_firecrawl(self, actor, operation, **kwargs):
        return 10 ** 9

    def charge_provider(self, **kwargs):
        FakeCredits.charges.append(kwargs)
        return {'charged_tokens': 1}

    def charge_firecrawl(self, **kwargs):
        FakeCredits.charges.append(kwargs)
        return {'charged_tokens': 1}


@pytest.fixture(autouse=True)
def reports_ai_billing(request, monkeypatch):
    """Reports AI helpers bill the client's credits; unit tests of the feature code run without a ledger or a request."""
    name = request.module.__name__
    if 'report' not in name or name.endswith('test_reports_ai_billing'):
        yield
        return
    from aicentralv2.cadu_connect import reports_ai
    from aicentralv2.cadu_credit_connector import CreditActor
    FakeCredits.charges = []
    monkeypatch.setattr(reports_ai, 'CaduCreditConnector', FakeCredits)
    original = reports_ai.actor_for
    monkeypatch.setattr(reports_ai, 'actor_for', lambda selected=None: original(selected) if selected else CreditActor(1, 1))
    yield

@pytest.fixture(autouse=True)
def no_real_database(monkeypatch):
    """A unit test must never open a connection to the database named in .env.

    Tests that do not mock every read used to reach the real server (102 attempts in a
    single Conta test file). The application swallows connection errors, so the tests
    passed anyway, silently touching production. A test that patches ``psycopg.connect``
    itself still wins, because its patch is applied after this one.
    """
    import psycopg

    def refuse(*args, **kwargs):
        raise RuntimeError('Teste tentou abrir conexão real com o banco; simule get_db/psycopg.connect.')

    monkeypatch.setattr(psycopg, 'connect', refuse)
    yield
