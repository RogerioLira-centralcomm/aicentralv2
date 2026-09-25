from aicentralv2.cadu_workspace.conversations import working_memory

proposals = working_memory.proposals


def test_extracts_only_actionable_project_sections_as_proposals():
    result = proposals('''## Riscos
- Aprovação do key visual ainda depende da direção.
## Próximos passos
1. Validar o pacote de formatos com criação.
## Texto livre
Talvez seja melhor fazer algo depois.''')
    assert result == [
        {'kind': 'risk', 'summary': 'Aprovação do key visual ainda depende da direção.'},
        {'kind': 'next_step', 'summary': 'Validar o pacote de formatos com criação.'},
    ]


def test_ignores_unstructured_or_uncertain_prose():
    assert proposals('''Acho que talvez seja bom fazer uma revisão.\n\nSem lista estruturada.''') == []


def test_assistant_memory_proposal_keeps_assistant_source(monkeypatch):
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, sql, params): statements.append((sql, params))
    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): pass
    monkeypatch.setattr(working_memory, 'available', lambda: True)
    monkeypatch.setattr(working_memory.repository, 'get_db', lambda: Connection())

    created = working_memory.capture_turn(
        client_id=174, project_ref='ci:project-1', conversation_id='conversation-1',
        message_id='assistant-message-1', author_id=7,
        answer='## Decisões\n- Vamos priorizar a campanha de lançamento no próximo mês.',
    )

    assert len(created) == 1
    assert 'source_author_id' in statements[0][0]
    assert 'NULL)' in statements[0][0]
    assert statements[0][1][-1] == 'assistant-message-1'
    assert 'assistant_answer' in statements[1][1][-1]


def test_review_restricts_memory_to_the_selected_project(monkeypatch):
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, sql, params): statements.append((sql, params))
        def fetchone(self):
            if len(statements) == 1:
                return {'id': 'memory-1', 'kind': 'decision', 'scope': 'project',
                        'project_ref': 'ci:project-1', 'summary': 'Foco em mídia'}
            return {'id': 'memory-1', 'kind': 'decision', 'status': 'confirmed', 'summary': 'Foco em mídia'}
    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): pass
    monkeypatch.setattr(working_memory.repository, 'get_db', lambda: Connection())

    result = working_memory.review('memory-1', {'id': 7}, 174,
                                   'ci:project-1', 'confirm')

    assert 'project_ref=%s' in statements[0][0]
    assert statements[0][1] == ('memory-1', 174, 'ci:project-1')
    assert result['status'] == 'confirmed'


def test_dify_memory_packet_requires_client_and_confirmed_status(monkeypatch):
    captured = {}
    monkeypatch.setattr(working_memory, 'available', lambda: True)
    def rows(sql, params):
        captured['sql'], captured['params'] = sql, params
        return [{'scope': 'project', 'kind': 'decision', 'summary': 'Foco em B2B'}]
    monkeypatch.setattr(working_memory.repository, 'rows', rows)

    packet = working_memory.packet(174, 'ci:project-1', 'B2B')

    assert "client_id=%s AND status='confirmed'" in captured['sql']
    assert "organization_id" not in captured['sql']
    assert captured['params'][:2] == (174, 'ci:project-1')
    assert 'Foco em B2B' in packet


def test_work_memory_board_lists_only_the_requesting_users_conversations(monkeypatch):
    queries = []
    monkeypatch.setattr(working_memory, 'available', lambda: True)
    def rows(sql, params):
        queries.append((sql, params))
        return []
    monkeypatch.setattr(working_memory.repository, 'rows', rows)

    board = working_memory.board({'id': 7}, 174, 'ci:project-1')

    assert board['weeks'] == []
    assert 'x.user_id=%s' in queries[1][0]
    assert 'c.id_contato_cliente=%s' in queries[1][0]
    assert queries[1][1] == (174, 'ci:project-1', 7, 174, 7)


def test_legacy_memory_review_requires_project_editor(monkeypatch):
    from aicentralv2.cadu_family import routes
    monkeypatch.setattr(routes.repository, 'account_role', lambda _: 'member')
    monkeypatch.setattr(routes.repository, 'project_access', lambda *_: [
        {'user_id': 7, 'role': 'viewer'}, {'user_id': 8, 'role': 'editor'},
    ])

    assert not routes._can_review_work_memory(174, 'ci:project-1', {'id': 7})
    assert routes._can_review_work_memory(174, 'ci:project-1', {'id': 8})


def test_legacy_memory_board_requires_project_view(monkeypatch):
    from flask import Flask
    from werkzeug.exceptions import Forbidden
    from aicentralv2.cadu_family import routes
    monkeypatch.setattr(routes.context, 'inventory', lambda _: [
        {'ref': 'ci:project-1', 'kind': 'project'},
    ])
    monkeypatch.setattr(routes.context, 'identity', lambda: {'id': 7})
    monkeypatch.setattr(routes.repository, 'project_user_can_view', lambda *_: False)

    with Flask(__name__).app_context():
        import pytest
        with pytest.raises(Forbidden):
            routes._work_memory_project({'client_id': 174}, 'ci:project-1')
