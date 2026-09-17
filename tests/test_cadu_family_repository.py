from unittest.mock import patch

from aicentralv2.cadu_family import repository


def test_entities_orders_union_by_output_position_for_postgres():
    with patch('aicentralv2.cadu_family.repository.rows', return_value=[]) as rows:
        repository.entities(42)

    query = rows.call_args.args[0]
    assert 'ORDER BY 2' in query
    assert 'ORDER BY name' not in query
