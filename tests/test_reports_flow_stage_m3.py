from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


path = Path(__file__).resolve().parents[1] / 'aicentralv2/cadu_connect/reports_flow_stage.py'
spec = spec_from_file_location('reports_flow_stage', path)
module = module_from_spec(spec)
spec.loader.exec_module(module)


def test_stage_sets_x_but_preserves_y_and_legacy_role():
    original = {'type': 'page', 'stage': 'intent', 'x': 9, 'y': 431, 'role': 'form', 'locked': True}
    moved = module.normalize_stage_position(original)
    assert moved == {**original, 'x': 1040}
    assert original['x'] == 9


def test_only_page_in_legacy_source_stage_is_migrated():
    assert module.normalize_stage_position({'type': 'page', 'stage': 'source', 'path': '/'})['stage'] == 'entry'
    assert module.normalize_stage_position({'type': 'page', 'stage': 'source', 'path': '/a'})['stage'] == 'exploration'
    assert module.normalize_stage_position({'type': 'event', 'stage': 'source'})['stage'] == 'source'
    assert module.normalize_stage_position({'type': 'source', 'stage': 'intent'})['stage'] == 'source'


def test_draft_normalization_preserves_page_type_and_legacy_role():
    from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config

    config = {'nodes': [{'id': 'p', 'type': 'page', 'title': 'Contato', 'path': '/contato',
                         'stage': 'source', 'role': 'intent', 'pageType': 'contact',
                         'x': 80, 'y': 120}], 'edges': []}
    normalized, _ = _normalize_flow_config(config, 'example.com')
    node = normalized['nodes'][0]
    assert (node['stage'], node['pageType'], node['role'], node['x'], node['y']) == (
        'exploration', 'contact', 'intent', 720, 120)


def test_draft_normalization_preserves_unresolved_page_type():
    from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config

    config = {'nodes': [{'id': 'p', 'type': 'page', 'title': 'Serviços', 'path': '/servicos',
                         'stage': 'exploration', 'pageType': 'other',
                         'pageTypeStatus': 'unresolved', 'x': 720, 'y': 120}], 'edges': []}
    normalized, _ = _normalize_flow_config(config, 'example.com')
    assert normalized['nodes'][0]['pageTypeStatus'] == 'unresolved'


def test_typesafe_review_allows_independent_human_choices(monkeypatch):
    from aicentralv2.cadu_connect import reports_flow_suggestions as suggestions

    page = {'id': 'page', 'title': 'Serviços', 'path_prefix': '/servicos'}
    item = {'base_revision': 4, 'evidence_hash': suggestions.evidence_hash(page),
            'result': {'role': 'none', 'page_type': 'service',
                       'question_version': suggestions.FLOW_PAGE_PROMPT_VERSION}}
    statements = []

    def rows(statement, params):
        statements.append((statement, params))
        return [item]

    monkeypatch.setattr(suggestions, '_rows', rows)
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = 'test'
    with app.test_request_context('/'):
        result = suggestions.validate_application('11111111-1111-4111-8111-111111111111',
                                                   'flow', page, {'client_id': 1}, 4,
                                                   'intermediate', 'service')
    assert result['page_type'] == 'service'
    assert any("status='applied'" in statement for statement, _ in statements)
    assert any('"role": "intermediate"' in params[0] and '"page_type": "service"' in params[0]
               for statement, params in statements if 'jsonb_set' in statement)


def test_typesafe_judges_journey_role_and_content_type_independently(monkeypatch):
    from aicentralv2.cadu_connect import reports_typesafe

    def evaluate(state, questions, **_kwargs):
        assert set(questions) == {'page_role', 'page_type'}
        assert state['page']['path'] == '/servicos'
        def choice(options, selected):
            return {'type': 'choice', 'choice': selected, 'confidence': 1,
                    'probabilities': {key: int(key == selected) for key in options}}
        return {'answers': {
            'page_role': choice(reports_typesafe.FLOW_PAGE_ROLES, 'entry'),
            'page_type': choice(reports_typesafe.FLOW_PAGE_TYPES, 'service')},
            'model': 'teste', 'usage': {'input_tokens': 1, 'output_tokens': 1}}

    monkeypatch.setattr(reports_typesafe, 'system_one', evaluate)
    result = reports_typesafe.suggest_flow_page_role({'title': 'Serviços', 'path_prefix': '/servicos'})
    assert result['role'] == 'entry'
    assert result['page_type'] == 'service'
