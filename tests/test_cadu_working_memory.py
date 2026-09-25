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

    result = working_memory.review('memory-1', {'id': 7, 'organization_id': 12}, 174,
                                   'ci:project-1', 'confirm')

    assert 'project_ref=%s' in statements[0][0]
    assert statements[0][1] == ('memory-1', 12, 174, 'ci:project-1')
    assert result['status'] == 'confirmed'
