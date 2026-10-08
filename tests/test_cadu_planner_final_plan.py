import json

import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_planner import final_plan


def plan(**overrides):
    base = {
        'id': 'p1', 'title': 'Lançamento Verão', 'objective': 'awareness', 'revision': 4,
        'advertiser_name': 'Marca X', 'campaign_name': 'Verão',
        'briefing': {'budget': 'R$ 200 mil', 'period': 'jan a mar 2027', 'geography': 'São Paulo',
                     'kpis': 'Alcance; CTR 0,8%', 'notes': 'Lançar a linha de verão para jovens adultos.'},
        'items': [
            {'kind': 'canais', 'resource_id': '10', 'snapshot': {'name': 'YouTube', 'category': 'Vídeo'}},
            {'kind': 'canais', 'resource_id': '11', 'snapshot': {'name': 'Spotify', 'category': 'Áudio'}},
            {'kind': 'audiencias', 'resource_id': 'a1', 'snapshot': {'name': 'Jovens 18-24', 'category': 'Demografia'}},
            {'kind': 'formatos', 'resource_id': 'f1', 'snapshot': {'name': 'Bumper 6s'}},
        ],
        'allocations': [{'resource_id': '10', 'investment': 150000, 'weight': 75, 'flight': 'jan-fev', 'notes': ''},
                        {'resource_id': '11', 'investment': 50000, 'weight': 25, 'flight': '', 'notes': ''}],
        'workbench': {'sections': {'canais': {'value': {'roles': {'10': 'Alcance'}}}}},
    }
    base.update(overrides)
    return base


def raw(**overrides):
    base = {
        'tese': 'Verão é vídeo e som.', 'estrategia': 'YouTube abre, Spotify sustenta.', 'criativo_no_canal': 'Bumper curto.',
        'dado_de_mercado': {'texto': 'O consumo de áudio cresceu.', 'fonte_url': 'https://news.example/a'},
        'defesa': 'Concentra a verba onde o público está.',
        'visao': 'Tornar a linha conhecida em São Paulo.',
        'kpis': [{'kpi': 'CTR', 'meta': '0,8%', 'base': 'briefing'}, {'kpi': 'Alcance', 'meta': '5 milhões de pessoas', 'base': ''}],
        'praca': 'São Paulo.', 'audiencia': 'Jovens 18-24.',
        'mix': [{'canal_id': '10', 'papel': 'x', 'justificativa': 'Escala de vídeo.'},
                {'canal_id': '99', 'papel': 'Busca', 'justificativa': 'Inventado.'}],
        'direcao_criativa': 'Peças curtas. Use também TikTok para viralizar.',
        'fases': [{'fase': 'Lançamento', 'quando': 'janeiro', 'foco': 'alcance'}],
        'premissas': ['CPM de R$ 12 no YouTube.', 'Peças entregues pelo cliente.'],
        'proximos_passos': ['Aprovar o plano.'], 'para_alinharmos': ['Data de lançamento?'],
    }
    base.update(overrides)
    return base


def test_payload_separates_confirmed_from_gaps_and_uses_allocations():
    payload = final_plan.build_payload(plan(briefing={'notes': 'x'}, objective=None), pending=['Qual o prazo?'])
    confirmed = payload['confirmado']
    assert [row['canal'] for row in confirmed['canais']] == ['YouTube', 'Spotify']
    assert confirmed['canais'][0]['percentual'] == 75.0 and confirmed['canais'][0]['papel'] == 'Alcance'
    assert confirmed['verba']['alocada_nos_canais'] == 200000.0
    assert 'sistema_criativo' not in confirmed  # optional and absent: not demanded
    assert any('período' in gap for gap in payload['lacunas'])
    assert payload['pendencias'] == ['Qual o prazo?']


def test_payload_is_bounded_and_includes_creative_system_when_present():
    items = plan()['items'] + [{'kind': 'portais', 'resource_id': str(i), 'snapshot': {'name': 'Portal ' + 'x' * 300 + str(i)}}
                               for i in range(400)]
    wb = {'sections': {'criativos': {'value': {'big_idea': 'Verão sem filtro', 'messages': ['a', 'b']}}}}
    payload = final_plan.build_payload(plan(items=items, workbench=wb))
    assert len(json.dumps(payload, ensure_ascii=False)) <= final_plan.MAX_PAYLOAD_CHARS + 2000
    assert payload['confirmado']['sistema_criativo']['big_idea'] == 'Verão sem filtro'


def test_validate_strips_unsupported_numbers_channels_and_sourceless_market_data():
    payload = final_plan.build_payload(plan())
    document, warnings = final_plan.validate(raw(), payload)
    sections = {s['key']: s for s in document['sections']}
    assert 'TikTok' not in sections['criativo']['body'] and 'Peças curtas.' in sections['criativo']['body']
    assert 'CPM' not in sections['premissas']['body'] and 'Peças entregues' in sections['premissas']['body']
    assert 'Dado de mercado' not in sections['resumo']['body']           # no Radar story → no source
    assert 'CTR** — meta: 0,8%' in sections['kpis']['body']
    assert 'Alcance** — meta a definir' in sections['kpis']['body']
    assert 'Definir a meta de Alcance' in sections['para_alinharmos']['body']
    rows = sections['mix']['rows']
    assert [r['canal'] for r in rows] == ['YouTube', 'Spotify']          # channel 99 dropped
    assert rows[0]['percentual'] == 75.0 and rows[0]['investimento'] == 150000.0 and rows[0]['papel'] == 'Alcance'
    assert {w['reason'] for w in warnings} >= {'canal fora do plano', 'dado de mercado sem fonte do plano'}
    assert document['note'] == final_plan.PRICE_NOTE


def test_market_data_kept_only_with_story_source():
    story = {'angle': 'Calor', 'why_now': 'Onda de calor', 'buzz': [{'title': 'Áudio cresce', 'source': 'Jornal', 'url': 'https://news.example/a'}]}
    document, _ = final_plan.validate(raw(), final_plan.build_payload(plan(), story=story))
    resumo = document['sections'][0]['body']
    assert 'Dado de mercado' in resumo and 'https://news.example/a' in resumo


def test_validate_requires_a_thesis():
    with pytest.raises(BadRequest):
        final_plan.validate(raw(tese=''), final_plan.build_payload(plan()))


def test_stale_when_plan_payload_changes():
    payload = final_plan.build_payload(plan())
    latest = {'version': 1, 'created_at': None, 'origin': 'generated', 'document': {'sections': []},
              'source_hash': final_plan.payload_hash(payload), 'plan_revision': 4}
    share = {'share_enabled': False}
    assert final_plan.describe(plan(), payload, latest, share)['stale'] is False
    changed = final_plan.build_payload(plan(allocations=[]))
    assert final_plan.describe(plan(), changed, latest, share)['stale'] is True


def test_section_edit_and_regeneration_keep_user_sections():
    document, _ = final_plan.validate(raw(), final_plan.build_payload(plan()))
    edited = final_plan.apply_section_edit(document, 'visao', 'Minha visão.')
    assert next(s for s in edited['sections'] if s['key'] == 'visao')['body'] == 'Minha visão.'
    assert next(s for s in document['sections'] if s['key'] == 'visao')['body'] != 'Minha visão.'  # previous untouched
    with pytest.raises(BadRequest):
        final_plan.apply_section_edit(document, 'inexistente', 'x')
    merged, kept = final_plan.merge_edited(document, edited, ['visao'], overwrite=False)
    assert kept == ['visao'] and next(s for s in merged['sections'] if s['key'] == 'visao')['body'] == 'Minha visão.'
    merged, kept = final_plan.merge_edited(document, edited, ['visao'], overwrite=True)
    assert kept == [] and next(s for s in merged['sections'] if s['key'] == 'visao')['body'] != 'Minha visão.'


def test_public_projection_has_no_internal_fields():
    document, _ = final_plan.validate(raw(), final_plan.build_payload(plan()))
    row = {'id': 'secret-id', 'plan_id': 'p1', 'version': 3, 'document': document, 'warnings': [{'x': 1}],
           'charged_tokens': 999, 'created_by': 7, 'source_hash': 'h', 'plan_title': 'Lançamento Verão',
           'advertiser_name': 'Marca X', 'created_at': '2026-10-08'}
    public = final_plan.public_projection(row)
    assert set(public) == {'title', 'advertiser_name', 'version', 'updated_at', 'sections', 'note'}
    text = json.dumps(public, ensure_ascii=False)
    for forbidden in ('secret-id', 'charged_tokens', 'warnings', 'source_hash', 'canal_id', 'created_by', '999'):
        assert forbidden not in text
    assert public['note'] == final_plan.PRICE_NOTE


def test_contacts_are_stripped_and_markdown_has_mix_table():
    document, _ = final_plan.validate(raw(visao='Fale com joao@marca.com sobre a visão.'), final_plan.build_payload(plan()))
    markdown = final_plan.to_markdown(document, 'Lançamento Verão')
    assert 'joao@marca.com' not in markdown
    assert '| YouTube | 75% | R$ 150.000 | Alcance |' in markdown
    assert markdown.rstrip().endswith('_' + final_plan.PRICE_NOTE + '_')


def test_generate_charges_each_response_retries_bad_json_and_keeps_edits(monkeypatch):
    payload = final_plan.build_payload(plan())
    previous_doc, _ = final_plan.validate(raw(), payload)
    previous_doc = final_plan.apply_section_edit(previous_doc, 'visao', 'Minha visão.')
    inserted = {}
    monkeypatch.setattr(final_plan, '_require_available', lambda: None)
    monkeypatch.setattr(final_plan, '_context', lambda *a: (plan(), payload))
    monkeypatch.setattr(final_plan, '_latest', lambda _p: {'document': previous_doc, 'edited_sections': ['visao']})
    monkeypatch.setattr(final_plan, 'estimate', lambda *a: 100)
    monkeypatch.setattr(final_plan, '_insert_version', lambda p, **kw: inserted.update(kw))
    monkeypatch.setattr(final_plan, 'get_state', lambda *a: {'exists': True})

    class Provider:
        calls = 0
        def complete(self, messages, **kwargs):
            Provider.calls += 1
            return {'content': 'não é json' if Provider.calls == 1 else json.dumps(raw()), 'usage': {'total_tokens': 10}}

    class Credits:
        charges = []
        def authorize(self, actor, tokens): self.authorized = tokens
        def charge_provider(self, **kwargs):
            Credits.charges.append(kwargs['idempotency_key'])
            return {'tokens_cobrados': 10}

    state = final_plan.generate(1, 2, 'p1', provider=Provider(), credits=Credits())
    assert Provider.calls == 2 and len(Credits.charges) == 2 and state['charged_tokens'] == 20
    assert inserted['edited'] == ['visao'] and inserted['origin'] == 'generated'
    assert next(s for s in inserted['document']['sections'] if s['key'] == 'visao')['body'] == 'Minha visão.'
