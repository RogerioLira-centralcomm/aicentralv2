import importlib.util
from datetime import datetime, timezone
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('apply_snapshot', Path(__file__).resolve().parents[1] / 'scripts' / 'apply_planner_catalog_snapshot.py')
apply_snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apply_snapshot)


def test_newer_only_overwrites_older_or_missing_data():
    old = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert apply_snapshot.newer('2026-10-08T12:00:00+00:00', old)
    assert apply_snapshot.newer('2026-10-08T12:00:00+00:00', None)
    assert not apply_snapshot.newer('2026-08-01T00:00:00+00:00', old)
    assert not apply_snapshot.newer(None, old)


def test_json_columns_are_wrapped_and_plain_ones_are_not():
    assert apply_snapshot.value_for('produtos', ['a']).__class__.__name__ == 'Json'
    assert apply_snapshot.value_for('descricao', 'texto') == 'texto'
    assert apply_snapshot.value_for('ad_formats', None) is None
