from flask import Flask, session

from aicentralv2.cadu_family.routes import _apply_requested_context

SELECTED = {'organization_id': 12, 'client_id': 12, 'client_name': 'Agência', 'role': 'admin'}


def bar():
    return {'brands': [{'ref': 'studio:3', 'name': 'Marca', 'related_refs': []}],
            'projects': [{'ref': 'ci:abc', 'name': 'Projeto', 'related_refs': ['studio:3']}],
            'brand_ref': None, 'project_ref': None}


def apply(query):
    app = Flask(__name__)
    app.secret_key = 'test'
    with app.test_request_context('/planos?' + query):
        context_bar = bar()
        _apply_requested_context(SELECTED, context_bar)
        return context_bar, dict(session.get('family_context') or {})


def test_valid_refs_select_brand_and_project_and_persist():
    context_bar, saved = apply('create=1&project_ref=ci:abc&brand_ref=studio:3')
    assert (context_bar['brand_ref'], context_bar['project_ref']) == ('studio:3', 'ci:abc')
    assert saved['project_ref'] == 'ci:abc' and saved['client_id'] == 12


def test_project_alone_brings_its_related_brand():
    context_bar, _ = apply('project_ref=ci:abc')
    assert context_bar['brand_ref'] == 'studio:3'


def test_unknown_refs_are_ignored_without_error():
    context_bar, saved = apply('project_ref=ci:other&brand_ref=studio:99')
    assert context_bar['brand_ref'] is None and context_bar['project_ref'] is None
    assert saved == {}


def test_brand_only_keeps_project_empty():
    context_bar, _ = apply('brand_ref=studio:3')
    assert context_bar['brand_ref'] == 'studio:3' and context_bar['project_ref'] is None
