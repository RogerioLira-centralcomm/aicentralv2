from pathlib import Path

from aicentralv2.config import Config
from aicentralv2.cadu_family.catalog import PROFILES


ROOT = Path(__file__).resolve().parents[1]


def test_mutating_cadu_features_are_closed_by_default():
    assert Config.CADU_FAMILY_WRITES_ENABLED is False
    assert Config.CADU_FAMILY_CHAT_ENABLED is False
    assert Config.CADU_CHAT_WORKER_ENABLED is False


def test_schema_accepts_every_shared_conversation_profile():
    sql = (ROOT / 'migrations' / 'add_cadu_family.sql').read_text(encoding='utf-8')
    compatibility = (ROOT / 'migrations' / 'add_cadu_family_skills_profile.sql').read_text(encoding='utf-8')
    for profile in PROFILES:
        assert f"'{profile}'" in sql
        assert f"'{profile}'" in compatibility


def test_chat_runtime_runner_applies_dependencies_in_order():
    source = (ROOT / 'migrations' / 'run_add_cadu_chat_runtime.py').read_text(encoding='utf-8')
    positions = [source.index(name) for name in (
        'add_cadu_family.sql',
        'add_cadu_chat_request_hash.sql',
        'add_cadu_chat_jobs.sql',
        'add_cadu_family_skills_profile.sql',
    )]
    assert positions == sorted(positions)


def test_token_ledger_runner_is_independent_from_flask_request_context():
    source = (ROOT / 'migrations' / 'run_add_cadu_tool_token_ledger.py').read_text(encoding='utf-8')
    assert 'psycopg.connect' in source
    assert 'get_db' not in source
    assert 'DB_HOST' in source and 'DB_NAME' in source and 'DB_USER' in source
