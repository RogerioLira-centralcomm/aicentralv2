from aicentralv2.cadu_workspace.conversations import conversation_memory


def messages(count=40):
    return [
        {'id': f'id-{index}', 'position': index, 'role': 'user' if index % 2 else 'assistant',
         'content': ('Minha primeira pergunta sobre reggae' if index == 1 else f'Mensagem número {index}')}
        for index in range(1, count + 1)
    ]


def test_positional_retrieval_keeps_the_first_user_question_after_long_chat():
    found = conversation_memory._positional_messages(messages(120), 'Qual foi a minha primeira pergunta?')
    assert [item['position'] for item in found] == [1]
    assert found[0]['content'] == 'Minha primeira pergunta sobre reggae'


def test_positional_retrieval_supports_second_and_third_user_turns():
    data = messages(80)
    assert conversation_memory._positional_messages(data, 'Qual foi minha segunda pergunta?')[0]['position'] == 3
    assert conversation_memory._positional_messages(data, 'E a terceira?')[0]['position'] == 5


def test_structured_state_preserves_corrections_and_decisions_with_sources():
    data = messages(10)
    data[4]['content'] = 'Na verdade, agora são R$ 70 mil.'
    data[8]['content'] = 'Ficou definido que vamos usar a opção B.'
    state = conversation_memory._structured_state(data)
    assert state['goal'] == 'Minha primeira pergunta sobre reggae'
    assert state['corrections'][0]['message_id'] == 'id-5'
    assert state['decisions'][0]['message_id'] == 'id-9'


def test_structured_state_preserves_recent_urls_with_message_provenance():
    data = messages(8)
    data[2]['content'] = 'Use https://example.com/proposta como referência.'
    state = conversation_memory._structured_state(data)
    assert state['entities']['urls'] == [{
        'message_id': 'id-3',
        'url': 'https://example.com/proposta',
        'text': 'Use https://example.com/proposta como referência.',
    }]


def test_structured_state_preserves_files_and_artifacts_with_provenance():
    data = messages(4)
    data[0]['files'] = [{'id': 'file-1', 'name': 'briefing.pdf'}, {'id': 'file-2', 'name': 'dados.xlsx'}]
    data[1]['metadata'] = {'artifact_id': 'artifact-9', 'artifact_title': 'Plano de mídia'}
    state = conversation_memory._structured_state(data)
    assert [item['name'] for item in state['entities']['files']] == ['briefing.pdf', 'dados.xlsx']
    assert state['entities']['artifacts'][0] == {
        'message_id': 'id-2', 'id': 'artifact-9', 'title': 'Plano de mídia',
    }


def test_assistant_proposal_never_becomes_a_confirmed_conversation_decision():
    data = messages(6)
    data[1]['content'] = 'Vamos usar a opção que eu recomendei.'
    assert conversation_memory._structured_state(data)['decisions'] == []


def test_segment_summary_is_bounded_and_keeps_roles_and_positions():
    summary = conversation_memory._segment_summary(messages(200))
    assert len(summary) <= conversation_memory.MAX_STATE_CHARS
    assert '#1 Usuário:' in summary


def test_long_checkpoint_is_split_without_losing_message_coverage():
    data = messages(40)
    for item in data:
        item['content'] = 'x' * 700
    chunks = conversation_memory._segment_chunks(data)
    assert len(chunks) > 1
    assert [item['position'] for chunk in chunks for item in chunk] == list(range(1, 41))
    assert all(len(conversation_memory._segment_summary(chunk)) <= conversation_memory.MAX_STATE_CHARS
               for chunk in chunks)


def test_prompt_payload_keeps_long_memory_separate_from_recent_history():
    import json
    from aicentralv2.cadu_workspace.agent_v2.contracts import IntentRoute, RequestContext
    from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import build_payload
    request = RequestContext(organization_id=1, client_id=2, user_id=3,
                             conversation_id='conversation', surface='conversations')
    payload = build_payload(
        message='Qual foi a primeira pergunta?', request=request,
        route=IntentRoute(domain='general', action='answer', complexity='low', response_mode='direct'),
        resolved={}, policy={'mode': 'direct'}, user_label='user-3',
        history='Usuário: mensagem recente',
        conversation_state={'primeira_mensagem_usuario': 'Pergunta antiga',
                            'regra': 'O transcript original prevalece.'},
    )
    evidence = json.loads(payload['inputs']['evidence'])
    assert evidence['conversation_state']['primeira_mensagem_usuario'] == 'Pergunta antiga'
    assert evidence['conversation_history'] == 'Usuário: mensagem recente'


def test_prompt_budget_preserves_structured_memory_before_large_tool_evidence():
    import json
    from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import _bounded_json
    evidence = json.loads(_bounded_json({
        'large_tool': {'content': 'x' * 20000},
        'conversation_state': {
            'primeira_mensagem_usuario': 'Pergunta que não pode desaparecer',
            'mensagens_originais_recuperadas': [
                {'message_id': '1', 'content': 'Trecho original importante'}
            ],
        },
        'conversation_history': 'histórico ' * 2000,
    }, 6000))
    assert evidence['conversation_state']['primeira_mensagem_usuario'] == 'Pergunta que não pode desaparecer'
    assert evidence['conversation_state']['mensagens_originais_recuperadas'][0]['content'] == 'Trecho original importante'
    assert 'large_tool' not in evidence


def test_prompt_budget_reserves_recent_history_before_tool_evidence():
    import json
    from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import _bounded_json
    history = 'Usuário: use o arquivo enviado\nAssistente: vou preservar esse contexto'
    evidence = json.loads(_bounded_json({
        'current_context': {'project_ref': 'ci:7'},
        'conversation_history': history,
        'large_tool': {'content': 'x' * 20000},
    }, 1800))
    assert evidence['conversation_history'] == history
    assert 'large_tool' not in evidence


def test_repository_allows_the_conversation_memory_schema_probe(monkeypatch):
    from flask import Flask
    from aicentralv2.cadu_family import repository
    monkeypatch.setattr(repository, 'rows', lambda *_: [{'available': True}])
    with Flask(__name__).test_request_context('/'):
        assert repository.family_table_available('cadu_conversation_memory_state') is True
