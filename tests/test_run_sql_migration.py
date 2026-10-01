import hashlib
from unittest.mock import MagicMock, patch

import pytest

from migrations import run_sql_migration


@pytest.fixture
def migration(tmp_path, monkeypatch):
    (tmp_path / "add_thing.sql").write_text("SELECT 1;", encoding="utf-8")
    monkeypatch.setattr(run_sql_migration, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.delenv("FORCE_SQL_MIGRATIONS", raising=False)
    return "add_thing.sql", hashlib.sha256(b"SELECT 1;").hexdigest()


def _run(recorded_sha):
    cursor = MagicMock()
    cursor.fetchone.return_value = (recorded_sha,) if recorded_sha else None
    connection = MagicMock()
    connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
    with patch.object(run_sql_migration.psycopg, "connect", return_value=connection):
        run_sql_migration.main("add_thing.sql")
    return [call.args[0] for call in cursor.execute.call_args_list]


def test_applies_a_new_migration_and_records_its_hash(migration):
    statements = _run(None)

    assert "SELECT 1;" in statements
    assert any("INSERT INTO deploy_sql_migrations" in statement for statement in statements)


def test_skips_a_migration_already_applied_with_the_same_content(migration):
    statements = _run(migration[1])

    assert "SELECT 1;" not in statements


def test_reapplies_a_migration_whose_content_changed(migration):
    assert "SELECT 1;" in _run("stale-hash")


def test_force_flag_reapplies_an_applied_migration(migration, monkeypatch):
    monkeypatch.setenv("FORCE_SQL_MIGRATIONS", "1")

    assert "SELECT 1;" in _run(migration[1])
