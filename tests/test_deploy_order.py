import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'deploy.sh').read_text()


def position(marker):
    assert SCRIPT.count(marker) >= 1, marker
    return SCRIPT.index(marker)


def test_deploy_script_is_valid_bash():
    assert subprocess.run(['bash', '-n', str(ROOT / 'deploy.sh')], capture_output=True).returncode == 0


def test_service_stays_up_until_code_schema_and_build_are_ready():
    pull = position('git pull origin main')
    deps = position('# 3. Atualizar dependencias')
    migrations = position('# 8. Atualizar schema e dados idempotentes')
    build = position('# 2b. Build frontend')
    stop = position('\nstop_service_for_deploy\n')
    workers = position('# Workers: instaladores')
    start = position('sudo systemctl start "$APP_SERVICE"\nsleep 3')
    assert pull < deps < migrations < build < stop < workers < start


def test_every_flow_table_migration_the_code_needs_is_registered():
    for migration in ('add_reports_flow_private_tags_v1.sql', 'add_reports_flow_ownership_v1.sql', 'add_reports_flow_plan_versions_v1.sql',
                      'add_reports_flow_plan_only_v1.sql', 'add_reports_flow_templates_v1.sql', 'add_reports_flow_probe_runs_v1.sql',
                      'add_reports_site_pages_v1.sql'):
        assert (ROOT / 'migrations' / migration).is_file(), migration
        assert f'run_sql_migration.py {migration}' in SCRIPT, migration
    order = [SCRIPT.index(name) for name in ('add_reports_flow_private_tags_v1.sql', 'add_reports_flow_ownership_v1.sql', 'add_reports_flow_plan_versions_v1.sql')]
    assert order == sorted(order)


def test_the_flow_reset_never_runs_in_the_deploy():
    assert 'run_reset_reports_flows_v3' not in SCRIPT
    assert 'reset_reports_client_scope_v2' not in SCRIPT
