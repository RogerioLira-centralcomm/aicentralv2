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


def test_assistant_proposal_never_becomes_a_confirmed_conversation_decision():
    data = messages(6)
    data[1]['content'] = 'Vamos usar a opção que eu recomendei.'
    assert conversation_memory._structured_state(data)['decisions'] == []


def test_segment_summary_is_bounded_and_keeps_roles_and_positions():
    summary = conversation_memory._segment_summary(messages(200))
    assert len(summary) <= conversation_memory.MAX_STATE_CHARS
    assert '#1 Usuário:' in summary


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
