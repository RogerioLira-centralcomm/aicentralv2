from unittest.mock import MagicMock

import pytest

from aicentralv2.cadu_skills.repository import charge_project_rag


def test_rag_charge_uses_client_credit_lots_and_records_usage():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {'id': 10, 'tokens_amount': 100, 'tokens_used': 60},
        {'id': 11, 'tokens_amount': 100, 'tokens_used': 0},
    ]
    charged = charge_project_rag(cursor, client_id=42, user_id=7, project_id='project-id',
                                 tokens=70, stage='indexacao', idempotency_key='test-rag-charge')
    assert charged == 70
    sql = '\n'.join(str(call.args[0]) for call in cursor.execute.call_args_list)
    assert 'FOR UPDATE' in sql
    assert 'UPDATE cadu_credits_extras' in sql
    assert 'INSERT INTO cadu_tools_token_usage' in sql


def test_rag_charge_rejects_when_client_has_insufficient_credit():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{'id': 10, 'tokens_amount': 20, 'tokens_used': 10}]
    with pytest.raises(ValueError, match='Saldo Cadu insuficiente'):
        charge_project_rag(cursor, client_id=42, user_id=7, project_id='project-id',
                           tokens=11, stage='indexacao', idempotency_key='test-rag-insufficient')
