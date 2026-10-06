from unittest import mock

from aicentralv2.cadu_skills import repository


def _position(lots, plan):
    cursor = mock.MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [lots, plan]
    connection = mock.MagicMock()
    connection.cursor.return_value = cursor
    with mock.patch.object(repository, '_db', return_value=connection):
        return repository.credit_position(12), cursor


def test_credit_position_uses_two_queries_and_reads_configured_from_the_plan_row():
    result, cursor = _position({'granted': 0, 'used': 0, 'available': 0},
                               {'monthly_limit': 1000, 'monthly_used': 250})
    assert cursor.execute.call_count == 2
    assert result['configured'] is True
    assert result['monthly_limit'] == 1000


def test_credit_position_is_configured_by_granted_lots_without_a_plan():
    result, _cursor = _position({'granted': 500, 'used': 100, 'available': 400}, None)
    assert result['configured'] is True
    assert result['available'] == 400


def test_credit_position_is_unconfigured_without_plan_or_lots():
    result, _cursor = _position({'granted': 0, 'used': 0, 'available': 0}, None)
    assert result['configured'] is False
