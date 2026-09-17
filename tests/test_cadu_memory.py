from unittest import mock

from aicentralv2.cadu_workspace.conversations import memory


def test_captures_only_explicit_safe_statements():
    assert memory.explicit_candidate('prefiro respostas em texto corrido.') == {
        'kind': 'preference', 'key': 'response_style', 'value': 'respostas em texto corrido'
    }
    assert memory.explicit_candidate('faça uma análise sobre a campanha') is None


def test_explicit_capture_creates_auditable_personal_memory():
    cursor = mock.MagicMock()
    cursor.fetchone.return_value = None
    memory_id = memory.capture_explicit(cursor, user={'id': 7, 'organization_id': 9},
                                        conversation_id='conversation', message_id='00000000-0000-0000-0000-000000000001',
                                        text='Eu prefiro entregas concisas.')
    assert memory_id
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert any('INSERT INTO cadu_user_memories' in statement for statement in statements)
    assert any('INSERT INTO cadu_user_memory_events' in statement for statement in statements)


def test_memory_packet_orders_project_client_and_personal_context(monkeypatch):
    from aicentralv2.cadu_family import repository
    monkeypatch.setattr(repository, 'family_table_available', lambda name: True)
    monkeypatch.setattr(repository, 'rows', lambda *args: [
        {'kind': 'preference', 'value': 'texto corrido'},
        {'kind': 'role', 'value': 'mídia e estratégia'},
        {'kind': 'decision', 'value': 'priorizar lançamento'},
    ])
    packet = memory.context_packet({'id': 7, 'organization_id': 9}, {'client_id': 12}, 'ci:42', 'lancamento')
    assert 'texto corrido' in packet
    assert 'mídia e estratégia' in packet
