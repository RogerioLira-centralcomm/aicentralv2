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


def test_sidebar_flag_works_inside_a_get_request():
    # _request_memo keys its cache on the call arguments; a dict argument is unhashable, so the helper must not be memoized.
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/app', method='GET'):
        assert routes._shows_in_sidebar({'id': 1, 'mostrar_na_sidebar': False}) is False
        assert routes._shows_in_sidebar({'id': 1}) is True


def test_workspace_projects_keeps_its_request_memo():
    assert getattr(routes._workspace_projects, '__wrapped__', None) is not None
    assert getattr(routes._shows_in_sidebar, '__wrapped__', None) is None
