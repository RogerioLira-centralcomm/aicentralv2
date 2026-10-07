from aicentralv2.cadu_connect import reports_overview


def test_site_sql_narrows_to_customer_only_when_given():
    assert 's.customer_id=%(customer)s' not in reports_overview._site_sql({'period': 1})
    assert 's.customer_id=%(customer)s' in reports_overview._site_sql({'period': 1}, 7)


def test_site_daily_sql_has_customer_slot():
    sql = reports_overview._SITE_DAILY_SQL.format(customer_filter=' AND s.customer_id=%(customer)s')
    assert 's.customer_id=%(customer)s' in sql
    assert '{' not in reports_overview._SITE_DAILY_SQL.format(customer_filter='')
