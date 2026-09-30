from datetime import datetime, timedelta, timezone
from unittest import TestCase
from aicentralv2.cadu_connect.reports_flow_live import build_live_snapshot

class LiveContractTests(TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.nodes = [dict(id=p, type='page', path='/'+p) for p in ('a','b','c')]
        self.edges = [dict(id='ab', **{'from':'a','to':'b'}), dict(id='ac', **{'from':'a','to':'c'})]

    def event(self, id, path, age, kind='page_view', session='s', name=''):
        return dict(id=id, page_path='/'+path, page_host='example.com', session_id=session,
                    event_kind=kind, event_name=name, occurred_at=self.now-timedelta(seconds=age))

    def build(self, events):
        return build_live_snapshot(events,self.nodes,self.edges,self.now)

    def test_one_current_page_per_session(self):
        result=self.build([self.event(1,'a',50),self.event(2,'b',20)])
        self.assertEqual(result['active_sessions'],1)
        self.assertEqual(result['node_presence'],{'a':0,'b':1,'c':0})
        self.assertEqual(result['transitions'],{'ab':'2'})

    def test_no_invented_direct_transition_through_intermediate(self):
        result=self.build([self.event(1,'a',80),self.event(2,'b',50),self.event(3,'c',20)])
        self.assertNotIn('ac',result['transitions'])

    def test_unmapped_page_breaks_direct_path(self):
        self.assertNotIn('ac',self.build([self.event(1,'a',80),self.event(2,'unmapped',50),self.event(3,'c',20)])['transitions'])

    def test_exit_and_expiry_remove_presence(self):
        result=self.build([self.event(1,'a',95),self.event(2,'b',20,session='second'),self.event(3,'b',10,'page_leave','second')])
        self.assertEqual(result['active_sessions'],0)

    def test_named_conversions_do_not_match_other_event(self):
        self.nodes += [dict(id='sale',type='conversion',path='/b',event_name='sale')]
        self.edges += [dict(id='as',**{'from':'a','to':'sale'})]
        self.assertNotIn('as',self.build([self.event(1,'a',50),self.event(2,'b',20,'conversion',name='lead')])['transitions'])

    def test_heartbeat_refreshes_presence_without_transition(self):
        result=self.build([self.event(1,'a',100),self.event(2,'a',5,'heartbeat')])
        self.assertEqual(result['active_sessions'],1)
        self.assertEqual(result['transitions'],{})

    def test_out_of_order_input_is_sorted(self):
        result=self.build([self.event(2,'b',10),self.event(1,'a',50)])
        self.assertEqual(result['transitions'],{'ab':'2'})

    def test_page_visit_to_conversion_emits_transition(self):
        self.nodes.append(dict(id='sale',type='conversion',path='/thanks'))
        self.edges.append(dict(id='as',**{'from':'a','to':'sale'}))
        result=self.build([self.event(1,'a',50),self.event(2,'thanks',20)])
        self.assertEqual(result['transitions'],{'as':'2'})
        self.assertEqual(set(result['edge_activity']),{'as'})

    def test_page_visit_to_error_emits_transition(self):
        self.nodes.append(dict(id='error',type='error',path='/error'))
        self.edges.append(dict(id='ae',**{'from':'a','to':'error'}))
        self.assertEqual(self.build([self.event(1,'a',50),self.event(2,'error',20)])['transitions'],{'ae':'2'})

    def test_heartbeat_does_not_mark_unobserved_edges(self):
        self.assertEqual(self.build([self.event(1,'a',10,'heartbeat')])['edge_activity'],{})
