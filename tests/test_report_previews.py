from datetime import date

from aicentralv2.cadu_connect import report_previews

TODAY = date(2026, 10, 7)


def fake_rows(daily, covers=None, platforms=None, report_covers=None):
    def rows(sql, params=()):
        if 'to_regclass' in sql:
            return [{'ready': True}]
        if 'FROM cadu_reports_campaigns c' in sql:
            return [{'id': key, 'platform': value} for key, value in (platforms or {}).items()]
        if 'cx_studio_sessions' in sql:
            return ([{'report_id': str(key), 'campaign_id': None, 'url': value} for key, value in (report_covers or {}).items()]
                    + [{'report_id': None, 'campaign_id': str(key), 'url': value} for key, value in (covers or {}).items()])
        if 'cadu_reports_campaign_daily_metrics' in sql:
            return [{'campaign_id': campaign, 'metric_date': day, 'clicks': clicks, 'conversions': conversions}
                    for (campaign, day), (clicks, conversions) in daily.items()]
        raise AssertionError(sql)
    return rows


def test_report_without_campaign_has_an_empty_preview(monkeypatch):
    monkeypatch.setattr(report_previews, '_rows', fake_rows({}))
    out = report_previews.build_previews(7, [{'id': 1, 'media_campaign_id': None, 'flow_campaigns': None}], TODAY)
    assert out == [{'id': 1, 'platforms': [], 'cover_url': None, 'metric': None, 'total': None, 'previous': None, 'series': []}]


def test_campaign_report_gets_platform_cover_and_conversions_series_over_its_period(monkeypatch):
    daily = {(100, date(2026, 9, 29)): (40, 2), (100, date(2026, 9, 30)): (60, 3), (100, date(2026, 9, 27)): (10, 1)}
    monkeypatch.setattr(report_previews, '_rows', fake_rows(daily, covers={100: 'https://cdn/x.png'}, platforms={100: 'google_ads'}))
    row = {'id': 1, 'media_campaign_id': 100, 'flow_campaigns': None, 'start_date': '2026-09-29', 'end_date': '2026-09-30'}
    preview = report_previews.build_previews(7, [row], TODAY)[0]
    assert preview['platforms'] == ['google_ads']
    assert preview['cover_url'] == 'https://cdn/x.png'
    assert preview['metric'] == 'conversions'
    assert preview['series'] == [{'date': '2026-09-29', 'value': 2.0}, {'date': '2026-09-30', 'value': 3.0}]
    assert (preview['total'], preview['previous']) == (5.0, 1.0)


def test_flow_report_sums_its_campaigns_and_falls_back_to_clicks(monkeypatch):
    daily = {(100, date(2026, 10, 6)): (5, 0), (101, date(2026, 10, 6)): (7, 0)}
    monkeypatch.setattr(report_previews, '_rows', fake_rows(daily, platforms={100: 'google_ads', 101: 'meta_ads'}))
    row = {'id': 2, 'media_campaign_id': None, 'flow_campaigns': [{'id': 100}, {'id': '101'}], 'start_date': None, 'end_date': None}
    preview = report_previews.build_previews(7, [row], TODAY)[0]
    assert preview['platforms'] == ['google_ads', 'meta_ads']
    assert preview['metric'] == 'clicks'
    assert len(preview['series']) == 30, 'sem período, os últimos 30 dias até ontem'
    assert preview['series'][-1] == {'date': '2026-10-06', 'value': 12}


def test_long_period_keeps_only_the_last_days_and_no_data_means_no_series(monkeypatch):
    monkeypatch.setattr(report_previews, '_rows', fake_rows({}, platforms={100: 'google_ads'}))
    row = {'id': 3, 'media_campaign_id': 100, 'flow_campaigns': None, 'start_date': '2026-01-01', 'end_date': '2026-12-31'}
    preview = report_previews.build_previews(7, [row], TODAY)[0]
    assert preview['platforms'] == ['google_ads'] and preview['series'] == [] and preview['metric'] is None
    start, end, _, _ = report_previews._window(row, TODAY)
    assert (start, end) == (date(2026, 9, 8), TODAY)


def test_cover_made_for_the_report_wins_over_the_campaign_creative(monkeypatch):
    monkeypatch.setattr(report_previews, '_rows', fake_rows({}, covers={100: 'https://cdn/campaign.png'}, platforms={100: 'google_ads'},
                                                            report_covers={1: 'https://cdn/report.png'}))
    rows = [{'id': 1, 'media_campaign_id': 100, 'flow_campaigns': None}, {'id': 2, 'media_campaign_id': 100, 'flow_campaigns': None},
            {'id': 3, 'media_campaign_id': None, 'flow_campaigns': None}]
    covers = {item['id']: item['cover_url'] for item in report_previews.build_previews(7, rows, TODAY)}
    assert covers == {1: 'https://cdn/report.png', 2: 'https://cdn/campaign.png', 3: None}
