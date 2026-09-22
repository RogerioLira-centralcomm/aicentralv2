from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_notification_schema_projects_long_jobs_into_user_inbox():
    sql = (ROOT / 'migrations' / 'add_cadu_workspace_notifications.sql').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS cadu_workspace_notifications' in sql
    assert 'trg_cadu_notify_long_job_change' in sql
    assert "NEW.status NOT IN ('waiting','completed','failed','budget_exhausted')" in sql
    assert 'ON CONFLICT (long_job_id) DO UPDATE' in sql


def test_notification_service_is_scoped_and_supports_lifecycle_actions():
    service = (ROOT / 'aicentralv2' / 'cadu_workspace' / 'notification_service.py').read_text(encoding='utf-8')
    assert 'client_id = %s AND user_id = %s' in service
    assert "'read':" in service
    assert "'resolve':" in service
    assert "'archive':" in service


def test_project_react_surface_consumes_durable_notifications():
    component = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceProject.jsx').read_text(encoding='utf-8')
    template = (ROOT / 'aicentralv2' / 'templates' / 'cadu_workspace' / 'project_detail_react.html').read_text(encoding='utf-8')
    assert 'remoteNotifications' in component
    assert 'projectLinks.notifications' in component
    assert "workspace_notifications_api" in template
