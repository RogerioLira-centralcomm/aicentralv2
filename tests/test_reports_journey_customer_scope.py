from aicentralv2.cadu_connect import reports_journey as journey


def test_narrowing_adds_only_what_was_asked():
    assert journey._narrowing(None, None) == ''
    assert journey._narrowing('site-1', None) == 'AND e.site_id=%(site)s::uuid'
    assert journey._narrowing(None, 7) == 'AND s.customer_id=%(customer)s'
    both = journey._narrowing('site-1', 7)
    assert 'e.site_id=%(site)s::uuid' in both and 's.customer_id=%(customer)s' in both


def test_one_site_scopes_the_shared_where_clause_to_the_advertiser():
    sql = f'SELECT 1 {journey._SCOPE} GROUP BY 1'
    assert journey._one_site(sql, None, None) == sql
    narrowed = journey._one_site(sql, None, 7)
    assert 's.customer_id=%(customer)s' in narrowed and narrowed.endswith('GROUP BY 1')
    assert narrowed.count('s.customer_id') == 1


def test_every_site_template_reads_the_sites_table_as_s():
    """The advertiser term uses the alias ``s``: each query that takes a {site} slot must join the sites table under it."""
    templates = [value for name, value in vars(journey).items() if name.startswith('_') and name.endswith('_SQL') and isinstance(value, str) and ('{site}' in value or '@SCOPE@' in value or journey._SCOPE in value)]
    assert templates
    for sql in templates:
        assert 'cadu_reports_supertag_sites s' in sql.replace('@SCOPE@', journey._SCOPE), sql[:80]
