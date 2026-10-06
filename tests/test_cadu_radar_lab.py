from flask import Flask

from aicentralv2.cadu_radar import lab, prompts


def _lab():
    instance = object.__new__(lab.Lab)
    instance.run_id, instance.prompt_label, instance.prompt_set = 'test', '1.0', dict(prompts.V1_0)
    instance.flows = {'F1': {'name': 'a', 'kind': 'web', 'models': {}}, 'F2': {'name': 'b', 'kind': 'web', 'models': {}}}
    return instance


def _three(title):
    return [{'title': f'{title}-{index}'} for index in range(3)]


def _scored(by_flow, values):
    for flow, items in by_flow.items():
        for item, value in zip(items, next(values[flow])):
            item['review'] = {'media': value}


def test_revision_loop_keeps_best_version_and_stops_when_three_are_good():
    instance = _lab()
    # F1: 1 boa → 2 boas → 3 boas (para). F2: 3 boas desde o início, nunca revisa.
    values = {'F1': iter([[4.5, 3.0, 3.0], [4.5, 4.2, 3.0], [4.5, 4.4, 4.3]]),
              'F2': iter([[4.4, 4.3, 4.6]] * 3)}
    revised = []
    instance._judge = lambda flow, ctx, text, packet: _three(flow)
    instance._check = instance.annotate = lambda *args, **kwargs: None
    instance.review = lambda ctx, by_flow, tag: _scored(by_flow, values) or {}

    def revise(flow, ctx, state, items, round_no):
        revised.append((flow, round_no))
        return _three(f'{flow}-r{round_no}')

    instance._revise = revise
    with Flask(__name__).app_context():
        result = instance.evaluate(None, {'F1': {'text': '', 'packet': []}, 'F2': {'text': '', 'packet': []}},
                                   ('F1', 'F2'), revise_rounds=3, target=4.2)
    assert revised == [('F1', 1), ('F1', 2)]
    assert result['by_flow']['F1'][0]['title'] == 'F1-r2-0'
    assert result['score']['F1'] == 13.2
    assert [h['good'] for h in result['history']['F1']] == [1, 2, 3]
    assert not any(h['revised'] for h in result['history']['F2'])


def test_cutting_good_opportunities_does_not_win():
    instance = _lab()
    instance.flows = {'F1': instance.flows['F1']}
    # A revisão sobe a média (4,9) cortando para 1 item, mas perde pontos (4,9 < 8,6): fica a original.
    values = {'F1': iter([[4.3, 4.3, 2.0], [4.9]])}
    instance._judge = lambda *args: _three('original')
    instance._check = instance.annotate = lambda *args, **kwargs: None
    instance._revise = lambda *args: [{'title': 'cortada'}]
    instance.review = lambda ctx, by_flow, tag: _scored(by_flow, values) or {}
    with Flask(__name__).app_context():
        result = instance.evaluate(None, {'F1': {'text': '', 'packet': []}}, ('F1',), revise_rounds=1, target=4.2)
    assert result['by_flow']['F1'][0]['title'] == 'original-0'
    assert result['score']['F1'] == 8.6


def test_low_confidence_never_counts_as_good():
    items = [{'review': {'media': 4.8}, 'confidence': 'baixa'}, {'review': {'media': 4.1}, 'confidence': 'media'}]
    assert lab._points(items) == 4.1


def test_prompt_doctor_changes_must_keep_fields_and_braces():
    verify = prompts.V1_0['verify'][0]
    good = {'prompt': 'verify', 'system': verify.replace('Tente provar', 'Prove')}
    single_braces = {'prompt': 'verify', 'system': 'Responda JSON: {"results": []}'}
    discovery = {'prompt': 'discover_open', 'system': 'x'}
    result, accepted, rejected = prompts.apply_changes(prompts.V1_0, [good, single_braces, discovery])
    assert accepted == [good]
    assert len(rejected) == 2
    assert result['verify'][0].startswith('Você é o verificador. Prove')
    assert prompts.V1_0['verify'][0] == verify  # a versão original não muda


def test_json_mode_only_for_providers_that_accept_it():
    assert lab._json_mode('openai/gpt-5.4-mini') and lab._json_mode('gpt-5-mini')
    assert not lab._json_mode('anthropic/claude-sonnet-5') and not lab._json_mode('perplexity/sonar')


def test_truncated_json_keeps_complete_items():
    cut = '```json\n{"opportunities": [{"title": "a", "x": {"y": 1}}, {"title": "b"}, {"title": "c", "thes'
    assert [item['title'] for item in lab._json(cut)['opportunities']] == ['a', 'b']
    assert lab._json('{"results": [{"index": 0}]}') == {'results': [{'index': 0}]}


def test_doctor_always_edits_the_best_version(monkeypatch):
    instance = _lab()
    seen = []
    loops = iter([{'F1': 4.0}, {'F1': 3.0}, {'F1': 5.0}])  # v1.0, v1.1 perde, v1.2 ganha

    def evaluate(ctx, states, flows, **kwargs):
        return {'label': instance.prompt_label, 'by_flow': {}, 'score': next(loops), 'avg': {}, 'history': {}, 'reviews': []}

    def doctor(ctx, evaluation):
        seen.append((instance.prompt_label, instance.prompt_set['revise'][0][:8]))
        old = instance.prompt_set['revise'][0]
        return [{'prompt': 'revise', 'system': old.replace('Você é', f'V{len(seen)} Você é', 1)}]

    instance.context = lambda: None
    instance.discover = lambda flow, ctx: {'packet': [], 'text': ''}
    instance.evaluate, instance.doctor = evaluate, doctor
    instance.summary = lambda ctx, states, evaluations, best_index, best_set, *rest: (best_index, best_set['revise'][0][:8])
    monkeypatch.setattr(lab, 'prices', lambda: None)
    with Flask(__name__).app_context():
        best_index, best_text = instance.run(('F1',), prompt_loops=2)
    # A volta 2 parte da v1.0 (a v1.1 perdeu), não da v1.1.
    assert seen == [('1.0', 'Você é o'), ('1.0', 'Você é o')]
    assert best_index == 2 and best_text == 'V2 Você '
