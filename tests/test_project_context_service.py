from aicentralv2.cadu_workspace import project_context_service as service


def _row(revision=3, custom=None):
    return {
        "id": "project-1", "nome": "Projeto", "descricao": "Direção",
        "instrucoes": "", "tom_de_voz": "", "publico": "", "posicionamento": "",
        "cor": "#176b5e", "campos_personalizados": custom or {},
        "context_revision": revision, "updated_at": "2026-09-23T18:00:00Z",
    }


def test_custom_fields_normalize_lists_and_preserve_type():
    assert service._custom_fields({
        "Orçamento mensal": {"label": "Orçamento mensal", "value": " R$ 2.000 ", "type": "currency"},
        "canais": {"label": "Canais", "value": [" Google Ads ", "", "Instagram Ads"], "type": "list"},
    }) == {
        "orcamento_mensal": {"label": "Orçamento mensal", "value": "R$ 2.000", "type": "currency"},
        "canais": {"label": "Canais", "value": ["Google Ads", "Instagram Ads"], "type": "list"},
    }


def test_context_items_are_stable_searchable_payloads():
    snapshot = service._snapshot(_row(custom={
        "orcamento_mensal": {"label": "Orçamento mensal", "value": "R$ 2.000", "type": "currency"},
        "canais": {"label": "Canais", "value": ["Google Ads", "Instagram Ads"], "type": "list"},
    }))
    items = service.context_items(snapshot)
    budget = next(item for item in items if item["key"] == "orcamento_mensal")
    assert budget["id"] == "context:custom:orcamento_mensal"
    assert budget["field_kind"] == "custom"
    assert budget["revision"] == 3
    assert service.search_context(snapshot, "instagram canais")[0]["key"] == "canais"
    assert service.search_context(snapshot, "orçamento 2000")[0]["key"] == "orcamento_mensal"


def test_update_context_rejects_archived_project(monkeypatch):
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass
        def fetchone(self): return {**_row(), "status": "arquivado"}
    class Connection:
        def cursor(self): return Cursor()
        def commit(self): raise AssertionError("não deve confirmar")
        def rollback(self): pass
    monkeypatch.setattr(service, "get_db", lambda: Connection())
    try:
        service.update_context(client_id=12, actor_id=7, project_ref="ci:project-1",
                               standard_fields={"description": "Nova"})
    except service.ProjectContextError as exc:
        assert "Reative" in str(exc)
    else:
        raise AssertionError("deveria bloquear projeto arquivado")


def test_update_context_uses_revision_and_records_history(monkeypatch):
    calls = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, sql, params=()): calls.append((sql, params))
        def fetchone(self):
            if len(calls) == 1:
                return _row(custom={"prazo": {"label": "Prazo", "value": "Outubro"}})
            return _row(4, {"canais": {"label": "Canais", "value": ["Google Ads"], "type": "list"}})

    class Connection:
        committed = False
        rolled_back = False
        def cursor(self): return Cursor()
        def commit(self): self.committed = True
        def rollback(self): self.rolled_back = True

    connection = Connection()
    monkeypatch.setattr(service, "get_db", lambda: connection)
    result = service.update_context(
        client_id=12, actor_id=7, project_ref="ci:project-1", expected_revision=3,
        standard_fields={"description": "Nova direção"},
        custom_fields={"canais": {"label": "Canais", "value": ["Google Ads"], "type": "list"}},
        remove_custom_fields=["prazo"], source="test",
    )
    assert result["revision"] == 4
    assert result["updated_fields"] == ["-prazo", "canais", "description"]
    assert connection.committed is True
    assert "context_revision=context_revision+1" in calls[1][0]
    assert "INSERT INTO cadu_project_context_revisions" in calls[2][0]


def test_update_context_rejects_stale_revision(monkeypatch):
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass
        def fetchone(self): return _row(revision=5)
    class Connection:
        def cursor(self): return Cursor()
        def commit(self): raise AssertionError("não deve confirmar")
        def rollback(self): pass
    monkeypatch.setattr(service, "get_db", lambda: Connection())
    try:
        service.update_context(client_id=12, actor_id=7, project_ref="ci:project-1",
                               expected_revision=4, standard_fields={"description": "Nova"})
    except service.ProjectContextConflict as exc:
        assert "outra pessoa" in str(exc)
    else:
        raise AssertionError("deveria bloquear uma revisão antiga")
