"""Limite de projetos/marcas ativos: enterprise sem limite, pro 10, demais 1; mesma regra para marca e projeto."""
import pytest

from aicentralv2.cadu_family import repository


def test_plan_entity_limit_by_plan():
    assert repository.plan_entity_limit('enterprise') is None
    assert repository.plan_entity_limit('pro') == 10
    assert repository.plan_entity_limit('') == 1
    assert repository.plan_entity_limit('free') == 1


@pytest.mark.parametrize('plan, count, blocked', [('enterprise', 500, False), ('pro', 9, False), ('pro', 10, True), ('', 1, True)])
def test_assert_entity_capacity(monkeypatch, plan, count, blocked):
    monkeypatch.setattr(repository, 'entity_limit', lambda client_id: repository.plan_entity_limit(plan))
    monkeypatch.setattr(repository, 'active_entity_count', lambda client_id: count)
    if blocked:
        with pytest.raises(ValueError, match='O plano permite'):
            repository.assert_entity_capacity(174)
    else:
        repository.assert_entity_capacity(174)


def test_mcp_brand_create_checks_capacity_before_inspecting_site(monkeypatch):
    from werkzeug.exceptions import BadRequest
    from aicentralv2.cadu_workspace import brand_mcp_service as service

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, *args): pass
        def fetchone(self): return None

    class Db:
        def cursor(self): return Cursor()

    monkeypatch.setattr(service, '_require_admin', lambda context: None)
    monkeypatch.setattr(service, 'get_db', lambda: Db())
    monkeypatch.setattr(repository, 'assert_entity_capacity', lambda client_id: (_ for _ in ()).throw(ValueError('O plano permite 10 projeto(s)/marca(s) ativos.')))
    monkeypatch.setattr(service, 'inspect_site', lambda *args: pytest.fail('não deve inspecionar o site sem vaga no plano'))
    context = type('Ctx', (), {'client_id': 174, 'user_id': 2})()
    with pytest.raises(BadRequest, match='O plano permite'):
        service.create_brand(context, request_id='6f1c7f0e-5b7a-4f43-9b7e-0c4d1a2e3f10', name='Cadu Studio',
                             website_url='https://workspace.centralcomm.media', sector='Tecnologia')
