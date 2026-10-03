import unittest

from flask import Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config


def node(**extra):
    return {'id': 'n1', 'type': 'page', 'title': 'Home', 'path': '/', 'x': 80, 'y': 80, **extra}


class FlowContractTests(unittest.TestCase):
    def setUp(self):
        self.context = Flask(__name__).test_request_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()

    def test_kind_survives_v1_normalization(self):
        source = {'id': 's1', 'type': 'source', 'title': 'Meta', 'kind': 'traffic.meta', 'source': 'meta', 'x': 0, 'y': 0}
        config, _ = _normalize_flow_config({'nodes': [source, node()], 'edges': []}, 'exemplo.com.br')
        self.assertEqual(config['nodes'][0]['kind'], 'traffic.meta')
        self.assertEqual(config['nodes'][0]['source'], 'meta')

    def test_invalid_kind_falls_back_to_the_default_kind_of_its_type(self):
        config, _ = _normalize_flow_config({'nodes': [node(kind='<script>')], 'edges': []}, 'exemplo.com.br')
        self.assertEqual(config['nodes'][0]['kind'], 'page.generic')
        self.assertEqual(config['schema_version'], 3)

    def test_site_kind(self):
        config, _ = _normalize_flow_config({'nodes': [node()], 'edges': [], 'site_kind': 'landing'}, 'exemplo.com.br')
        self.assertEqual(config['site_kind'], 'landing')
        with self.assertRaises(BadRequest):
            _normalize_flow_config({'nodes': [node()], 'edges': [], 'site_kind': 'blog'}, 'exemplo.com.br')


if __name__ == '__main__':
    unittest.main()


def test_flow_list_carries_what_each_tag_received(monkeypatch):
    from aicentralv2.cadu_connect import reports_flow

    seen = {}

    def fake_rows(sql, params=()):
        seen["params"] = params
        return [{"tag_id": "t-1", "events": 12, "sessions": 5, "entry_sessions": 4, "converted_sessions": 1,
                 "conversions": 2, "last_event_at": "2026-10-03T10:00:00"}]

    monkeypatch.setattr(reports_flow, "_rows", fake_rows)
    flows = reports_flow._with_flow_stats([{"tag_id": "t-1"}, {"tag_id": "t-2"}, {"tag_id": None}], (7,))
    assert flows[0]["stats"]["events"] == 12 and flows[0]["stats"]["days"] == 30
    assert flows[1]["stats"]["events"] == 0 and flows[1]["stats"]["last_event_at"] is None
    assert flows[2]["stats"]["conversions"] == 0
    assert seen["params"] == (7, ["t-1", "t-2"], 30)


def test_both_flow_list_queries_carry_stats_and_monitor_fields():
    # The list screen loads view=create, a different query from the monitor view; both must feed the same columns.
    import inspect
    from aicentralv2.cadu_connect import reports_flow

    source = inspect.getsource(reports_flow)
    assert source.count("_with_flow_stats(") >= 3          # definition + create/edit branch + main branch
    assert source.count("f.monitor_enabled,f.monitor_interval_minutes,f.monitor_status,f.monitor_checked_at") >= 2
