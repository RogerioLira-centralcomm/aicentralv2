"""Completar o perfil da marca: a proposta nunca grava, e o salvamento soma ao que já existe."""
import json

import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_radar import brand_profile as bp

PROFILE = {'competitors': ['Enel'], 'positioning': '', 'target_audience': 'Famílias de Minas', 'differentiators': ['rede própria']}


def test_gaps_list_only_what_the_radar_uses_and_the_profile_lacks():
    assert [item['key'] for item in bp.gaps({'competitors': [], 'positioning': '  ', 'target_audience': 'x'})] == ['competitors', 'positioning']
    assert bp.gaps({'competitors': ['A'], 'positioning': 'p', 'target_audience': 't'}) == []


def test_competitors_are_read_whatever_shape_is_stored():
    assert [item['name'] for item in bp.competitor_items('A, B\nC')] == ['A', 'B', 'C']
    assert bp.competitor_items([{'nome': 'Enel', 'descricao': 'x'}, 'Light', {'name': ''}, None]) == [
        {'name': 'Enel', 'description': 'x'}, {'name': 'Light', 'description': ''}]


def test_competitors_are_added_without_repeating_or_touching_the_existing_ones():
    merged = bp.merge_competitors([{'name': 'Enel', 'description': 'minha nota'}],
                                  [{'name': 'ENEL', 'description': 'nova'}, {'name': 'Light', 'description': 'RJ'}, {'name': 'Équatorial'}, {'name': 'equatorial'}])
    assert [item['name'] for item in merged] == ['Enel', 'Light', 'Équatorial']
    assert merged[0]['description'] == 'minha nota'  # o que já existia não é reescrito


def test_competitor_list_is_capped():
    many = [{'name': f'Marca {index}'} for index in range(40)]
    assert len(bp.merge_competitors([], many)) == bp.MAX_COMPETITORS


def test_text_fills_only_when_empty_unless_the_user_asks_to_replace():
    changes, changed = bp.build_update(PROFILE, positioning='Energia confiável', target_audience='Outro público')
    assert changed == ['positioning'] and changes['positioning'] == 'Energia confiável'
    assert 'target_audience' not in changes  # já estava preenchido
    changes, changed = bp.build_update(PROFILE, target_audience='Outro público', replace={'target_audience': True})
    assert changed == ['target_audience'] and changes['target_audience'] == 'Outro público'
    changes, changed = bp.build_update(PROFILE, target_audience='Outro público', replace={'target_audience': 'sim'})  # só True de verdade vale
    assert changes == {} and changed == []


def test_nothing_new_means_no_write_at_all():
    assert bp.build_update(PROFILE, competitors=[{'name': 'enel'}]) == ({}, [])
    assert bp.build_update(PROFILE) == ({}, [])


def test_each_update_is_recorded_in_radar_enrichment_and_never_touches_field_provenance():
    profile = {'field_provenance': {'name': {'confidence': 0.9}}}
    changes, _ = bp.build_update(profile, competitors=[{'name': 'Light'}], sources=['https://x.com', 'lixo'], actor_id=2)
    assert 'field_provenance' not in changes  # outros fluxos escrevem lá, com estados de evidência fechados
    record = changes['radar_enrichment']
    assert record['sources']['competitors']['urls'] == ['https://x.com']
    assert record['history'][-1]['fields'] == ['competitors'] and record['history'][-1]['by'] == 2
    older = {'radar_enrichment': {'history': [{'at': str(index)} for index in range(30)], 'sources': {'positioning': {'urls': ['u']}}}}
    changes, _ = bp.build_update(older, competitors=[{'name': 'Nova'}])
    assert len(changes['radar_enrichment']['history']) == bp.HISTORY_LIMIT  # o histórico não cresce sem limite
    assert 'positioning' in changes['radar_enrichment']['sources']  # a proveniência dos outros campos é mantida


def test_save_sends_only_changed_keys_to_the_official_writer(monkeypatch):
    from aicentralv2 import creative_modeling_repository as repo
    sent = []
    monkeypatch.setattr(bp, 'load_brand', lambda client_id, ref: {'id': 31, 'name': 'Cemig', 'brand_profile': dict(PROFILE)})
    monkeypatch.setattr(repo.CreativeModelingRepository, 'update_client_brand_profile', lambda self, brand_id, changes: sent.append((brand_id, changes)))
    result = bp.save(174, 2, 'studio:31', competitors=[{'name': 'Light'}], positioning='Energia confiável')
    (brand_id, changes), = sent
    assert brand_id == 31 and sorted(changes) == ['competitors', 'positioning', 'radar_enrichment']
    assert 'differentiators' not in changes and 'target_audience' not in changes  # o resto do perfil nem é enviado
    assert result['changed'] == ['competitors', 'positioning'] and result['gaps'] == []
    sent.clear()
    assert bp.save(174, 2, 'studio:31', competitors=[{'name': 'Enel'}])['changed'] == [] and sent == []  # nada novo: nenhuma gravação


def test_brand_ref_must_be_a_studio_brand():
    with pytest.raises(BadRequest):
        bp.load_brand(1, 'ci:abc')
    with pytest.raises(BadRequest):
        bp.load_brand(1, 'studio:x')


def test_propose_researches_with_todays_date_and_never_writes(monkeypatch):
    from aicentralv2.cadu_planner import context as plan_context
    from aicentralv2.cadu_radar import pipeline
    from aicentralv2.services import cadu_ai_connector
    seen = {}
    answer = {'concorrentes': [{'nome': 'Enel', 'motivo': 'distribuidora'}, {'nome': 'Light', 'motivo': 'RJ'}], 'posicionamento': 'Energia confiável.[2] Com inovação.[1][3]',
              'publico': 'Famílias', 'fontes': ['https://g1.globo.com/x', 'não é url']}

    class FakeAI:
        def complete(self, messages, **kwargs):
            seen.update(messages=messages, kwargs=kwargs)
            return {'message': {'content': json.dumps(answer)}, 'cadu_charge': {'tokens_cobrados': 40}}

    monkeypatch.setattr(cadu_ai_connector, 'CaduAIConnector', FakeAI)
    monkeypatch.setattr(bp, 'load_brand', lambda client_id, ref: {'id': 31, 'name': 'Cemig', 'sector': 'Energia', 'website_url': 'https://cemig.com.br',
                                                                  'brand_profile': dict(PROFILE)})
    monkeypatch.setattr(plan_context, 'load_plan_context', lambda *args: {'brand': {'fields': [{'label': 'Público-alvo'}]}})
    monkeypatch.setattr(pipeline, 'usd_to_tokens', lambda client, usd: 250)
    proposal = bp.propose(174, 2, 'studio:31')
    assert [(item['name'], item['is_new']) for item in proposal['competitors']] == [('Enel', False), ('Light', True)]  # Enel já estava
    assert proposal['positioning'] == 'Energia confiável. Com inovação.'  # sem as marcas de nota de rodapé da busca
    assert proposal['sources'] == ['https://g1.globo.com/x'] and proposal['cost_tokens'] == 40
    assert [item['key'] for item in proposal['gaps']] == ['positioning']
    assert 'Hoje é 20' in seen['messages'][0]['content'] and 'concorrentes: Enel' in seen['messages'][1]['content']
    assert seen['kwargs']['provider'] == 'openrouter' and seen['kwargs']['app'] == 'Cadu Radar'
