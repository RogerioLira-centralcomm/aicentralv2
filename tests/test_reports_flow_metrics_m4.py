from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


path = Path(__file__).resolve().parents[1] / 'aicentralv2/cadu_connect/reports_flow_metrics.py'
spec = spec_from_file_location('reports_flow_metrics', path)
module = module_from_spec(spec)
spec.loader.exec_module(module)


def test_no_data_differs_from_zero_observed():
    edge = {'from': 'a', 'to': 'b'}
    assert module.edge_observation(edge, {'a', 'b'}, {}, {}, False)['status'] == 'no_data'
    observed = module.edge_observation(edge, {'a', 'b'}, {'a': {'sessions': 10}}, {}, True)
    assert observed == {'status': 'measured', 'sessions': 0, 'rate': 0.0, 'denominator': 10}


def test_rate_uses_source_sessions_and_unmeasured_edge_is_null():
    edge = {'from': 'a', 'to': 'b'}
    observed = module.edge_observation(edge, {'a', 'b'}, {'a': {'sessions': 25}}, {('a', 'b'): 5}, True)
    assert (observed['sessions'], observed['rate'], observed['denominator']) == (5, 20.0, 25)
    assert module.edge_observation(edge, {'b'}, {}, {}, True)['sessions'] is None


class OriginLandingTests(__import__('unittest').TestCase):
    def test_landings_flag_origins_the_flow_does_not_draw(self):
        from aicentralv2.cadu_connect.reports_flow_metrics import origin_landings
        config={'nodes':[{'id':'s','type':'source','kind':'traffic.direct','source':'direct'}]}
        bounds=[{'first_node':'p','last_node':'p','origin':None,'sessions':2},
                {'first_node':'p','last_node':'q','origin':'ref:partner.example','sessions':3},
                {'first_node':None,'last_node':None,'origin':'ref:ignored.example','sessions':9}]
        rows=origin_landings(bounds,config)
        self.assertEqual([(r['platform'],r['node_id'],r['sessions'],r['drawn']) for r in rows],
                         [('referral','p',3,False),('direct','p',2,True)])
