import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_notification_schema_projects_long_jobs_into_user_inbox():
    sql = (ROOT / 'migrations' / 'add_cadu_workspace_notifications.sql').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS cadu_workspace_notifications' in sql
    assert 'trg_cadu_notify_long_job_change' in sql
    assert "NEW.status NOT IN ('waiting','completed','failed','budget_exhausted')" in sql
    assert 'ON CONFLICT (long_job_id) DO UPDATE' in sql
    assert "WHEN NEW.status IN ('queued','running') THEN 'processing'" in sql
    assert "WHEN NEW.status = 'cancelled' THEN 'archived'" in sql
    assert 'status IS DISTINCT FROM EXCLUDED.status' in sql


def test_notification_service_is_scoped_and_supports_lifecycle_actions():
    service = (ROOT / 'aicentralv2' / 'cadu_workspace' / 'notification_service.py').read_text(encoding='utf-8')
    assert 'client_id = %s AND user_id = %s' in service
    assert "'read':" in service
    assert "'resolve':" in service
    assert "'archive':" in service
    assert 'cadu_workspace_brand_audit_runs' in service
    assert 'estimated_hours_saved' in service
    assert 'cost_brl' in service
    assert 'cadu_workspace_ingestion_sessions' in service
    assert 'processed_count' in service


def test_project_react_surface_consumes_durable_notifications():
    component = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceProject.jsx').read_text(encoding='utf-8')
    template = (ROOT / 'aicentralv2' / 'templates' / 'cadu_workspace' / 'project_detail_react.html').read_text(encoding='utf-8')
    assert 'remoteNotifications' in component
    assert 'projectLinks.notifications' in component
    assert "workspace_notifications_api" in template


def test_notification_center_is_shared_by_desktop_and_mobile_workspace_shells():
    provider = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceNotifications.jsx').read_text(encoding='utf-8')
    dock = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'CaduDock.jsx').read_text(encoding='utf-8')
    mobile = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceMobileChrome.jsx').read_text(encoding='utf-8')
    entry = (ROOT / 'frontend' / 'conversations-v2' / 'main.jsx').read_text(encoding='utf-8')
    assert 'WorkspaceNotificationsProvider' in entry
    assert "window.setInterval(refresh, 60000)" in provider
    assert 'useWorkspaceNotifications' in dock
    assert 'useWorkspaceNotifications' in mobile
    assert 'cadu-ds-mobile-chrome__notifications' in mobile
    center = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceNotificationCenter.jsx').read_text(encoding='utf-8')
    center_css = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceNotificationCenter.css').read_text(encoding='utf-8')
    assert 'estimated_hours_saved' in center
    assert 'cost_brl' in center
    assert 'processed_count' in center
    # Gaveta ancorada à direita (com margem no desktop, tela cheia no celular).
    assert re.search(r'inset:\s*16px 16px 16px auto', center_css)


def test_notification_migration_validates_every_trigger_column():
    runner = (ROOT / 'migrations' / 'run_add_cadu_workspace_notifications.py').read_text(encoding='utf-8')
    for column in ('organization_id', 'brand_ref', 'conversation_id', 'run_id', 'long_job_id', 'detail', 'created_at', 'updated_at'):
        assert repr(column) in runner


def test_brand_audit_notifications_project_only_the_fields_they_read():
    from unittest import mock
    from aicentralv2.cadu_workspace import notification_service

    executed = []
    cursor = mock.MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.execute.side_effect = lambda sql, params=None: executed.append(sql)
    answers = iter([
        {'available': True},   # inbox table exists
        {'available': True},   # audit table exists
        {'available': False},  # ingestion table
    ])
    cursor.fetchone.side_effect = lambda: next(answers, {'available': False})
    audit = {'job_id': 'j1', 'brand_id': 5, 'analysis_mode': 'full', 'status': 'approved', 'sources': [{}, {}],
             'collected_data': {'pages_analyzed': 7, 'assets_found': 3, 'fields_count': 12},
             'costs': {'actual_cost_brl': 2.5}, 'human_effort': {'estimated_person_hours': 4},
             'created_at': None, 'updated_at': None, 'completed_at': None, 'brand_name': 'Acme'}
    cursor.fetchall.side_effect = [[], [audit], []]
    connection = mock.MagicMock()
    connection.cursor.return_value = cursor

    with mock.patch.object(notification_service, 'get_db', return_value=connection):
        result = notification_service.list_notifications(12, 7)

    audit_sql = next(sql for sql in executed if 'cadu_workspace_brand_audit_runs r' in sql)
    assert 'r.collected_data,' not in audit_sql
    assert "jsonb_array_length(r.collected_data->'fields')" in audit_sql
    [item] = [entry for entry in result['items'] if str(entry['id']).startswith('brand-audit:')]
    assert item['action_payload']['pages_analyzed'] == 7
    assert item['action_payload']['fields_generated'] == 12
    assert item['action_payload']['sources_count'] == 2
