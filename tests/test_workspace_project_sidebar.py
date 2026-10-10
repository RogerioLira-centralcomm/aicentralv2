from aicentralv2.cadu_workspace import routes


def test_projects_show_in_sidebar_until_someone_turns_it_off():
    assert routes._shows_in_sidebar({'id': 1}) is True              # column not migrated yet
    assert routes._shows_in_sidebar({'mostrar_na_sidebar': True}) is True
    assert routes._shows_in_sidebar({'mostrar_na_sidebar': None}) is True
    assert routes._shows_in_sidebar({'mostrar_na_sidebar': False}) is False


def test_sidebar_migration_is_additive_and_repeatable():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1] / 'migrations' / 'add_cadu_project_sidebar_visibility.sql').read_text()
    assert 'ADD COLUMN IF NOT EXISTS mostrar_na_sidebar BOOLEAN NOT NULL DEFAULT TRUE' in sql
    assert 'DROP' not in sql.upper()
