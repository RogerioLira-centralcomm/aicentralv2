import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'deploy.sh').read_text()
ORDER = (ROOT / 'migrations' / 'ORDER.txt').read_text()


def position(marker):
    assert SCRIPT.count(marker) >= 1, marker
    return SCRIPT.index(marker)


def test_deploy_script_is_valid_bash():
    assert subprocess.run(['bash', '-n', str(ROOT / 'deploy.sh')], capture_output=True).returncode == 0


def test_service_stays_up_until_code_schema_and_build_are_ready():
    pull = position('git pull origin main')
    deps = position('# 2. Atualizar dependencias')
    migrations = position('# 3. Atualizar schema e dados idempotentes')
    build = position('# 4. Build frontend')
    stop = position('\nstop_service_for_deploy\n')
    workers = position('# Workers: instaladores')
    start = position('sudo systemctl start "$APP_SERVICE"\nsleep 3')
    assert pull < deps < migrations < build < stop < workers < start


def test_every_flow_table_migration_the_code_needs_is_registered():
    for migration in ('add_reports_flow_private_tags_v1.sql', 'add_reports_flow_ownership_v1.sql', 'add_reports_flow_plan_versions_v1.sql',
                      'add_reports_flow_plan_only_v1.sql', 'add_reports_flow_templates_v1.sql', 'add_reports_flow_probe_runs_v1.sql',
                      'add_reports_site_pages_v1.sql'):
        assert (ROOT / 'migrations' / migration).is_file(), migration
        assert f'run_sql_migration.py {migration}' in ORDER, migration
    order = [ORDER.index(name) for name in ('add_reports_flow_private_tags_v1.sql', 'add_reports_flow_ownership_v1.sql', 'add_reports_flow_plan_versions_v1.sql')]
    assert order == sorted(order)


def test_the_flow_reset_never_runs_in_the_deploy():
    assert 'run_reset_reports_flows_v3' not in SCRIPT + ORDER
    assert 'reset_reports_client_scope_v2' not in SCRIPT + ORDER


def test_migration_order_file_points_only_to_existing_files():
    result = subprocess.run([sys.executable, str(ROOT / 'migrations' / 'run_deploy_migrations.py'), '--check'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_deploy_runs_migrations_only_through_the_order_file():
    assert 'migrations/run_deploy_migrations.py' in SCRIPT
    assert 'run_sql_migration.py' not in SCRIPT


def test_every_sql_migration_is_in_the_order_file_or_called_by_a_runner():
    """Um .sql novo em migrations/ precisa entrar no ORDER.txt ou ser chamado por um run_*.py."""
    runners = ''.join(path.read_text() for path in (ROOT / 'migrations').glob('run_*.py'))
    legacy = set((ROOT / 'tests' / 'fixtures' / 'migrations_sem_deploy.txt').read_text().split())
    forgotten = sorted(
        path.name for path in (ROOT / 'migrations').glob('*.sql')
        if path.name not in ORDER and path.name not in runners and path.name not in legacy
    )
    assert not forgotten, f'Fora do deploy: {forgotten}. Inclua em migrations/ORDER.txt.'


def test_link_tester_migrations_can_rerun_after_the_table_became_a_view():
    """move_link_tester_to_reports_v1 troca a tabela por uma view; os SQLs anteriores precisam ignorar a reexecução."""
    for name in ('add_cadu_planner_link_test_runs.sql', 'add_reports_link_associations_v1.sql'):
        sql = (ROOT / 'migrations' / name).read_text()
        assert "relkind FROM pg_class WHERE oid = to_regclass('cadu_planner_link_test_runs')) = 'v'" in sql, name


def _runner():
    import importlib.util
    spec = importlib.util.spec_from_file_location('run_deploy_migrations', ROOT / 'migrations' / 'run_deploy_migrations.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_with_order(tmp_path, monkeypatch, *, v2_installed):
    runner = _runner()
    order = tmp_path / 'ORDER.txt'
    order.write_text('migrations/a.py\n~migrations/legacy.py\n?~migrations/legacy_optional.py\nmigrations/b.py\n')
    monkeypatch.setattr(runner, 'ORDER_FILE', order)
    monkeypatch.setattr(runner, 'missing_files', lambda steps, root=None: [])
    monkeypatch.setattr(runner, 'reports_v2_installed', lambda: v2_installed)
    ran = []
    monkeypatch.setattr(runner.subprocess, 'run', lambda cmd, cwd=None: ran.append(cmd[1]) or type('R', (), {'returncode': 0})())
    assert runner.main([]) == 0
    return ran


def test_legacy_reports_steps_are_skipped_once_reports_v2_is_installed(tmp_path, monkeypatch):
    assert _run_with_order(tmp_path, monkeypatch, v2_installed=True) == ['migrations/a.py', 'migrations/b.py']


def test_legacy_reports_steps_run_when_reports_v2_is_not_installed(tmp_path, monkeypatch):
    ran = _run_with_order(tmp_path, monkeypatch, v2_installed=False)
    assert ran == ['migrations/a.py', 'migrations/legacy.py', 'migrations/legacy_optional.py', 'migrations/b.py']


def test_every_legacy_step_exists_and_none_comes_after_the_post_v2_ones():
    runner = _runner()
    steps = runner.read_steps()
    legacy = [step for step in steps if step['legacy']]
    assert legacy and not runner.missing_files(legacy)
