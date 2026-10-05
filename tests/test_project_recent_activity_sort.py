from datetime import datetime, timezone

from aicentralv2.cadu_workspace.routes import _project_recent_activity


def test_activity_sorts_mixed_naive_and_aware_timestamps():
    project = {
        "nome": "Projeto", "updated_at": datetime(2026, 10, 5, 12, 0),
        "conversations": [{"titulo": "Conversa", "updated_at": datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc)}],
        "links": [{"titulo": "Link", "url": "https://a.test", "created_at": datetime(2026, 10, 4, 9, 0)},
                  {"titulo": "Outro", "url": "https://b.test", "created_at": datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)}],
    }
    result = _project_recent_activity(project)
    assert result[0]["title"] == "Conversa atualizada"
