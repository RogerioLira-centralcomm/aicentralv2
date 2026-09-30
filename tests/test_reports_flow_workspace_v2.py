from datetime import datetime, timedelta, timezone
from unittest import TestCase
from flask import Flask
from werkzeug.exceptions import BadRequest
from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config
from aicentralv2.cadu_connect.reports_flow_live import build_live_snapshot

class WorkspaceContractTests(TestCase):
    def setUp(self):
        self.ctx=Flask(__name__).app_context();self.ctx.push();self.addCleanup(self.ctx.pop)
    def test_group_roundtrip_and_invalid_reference(self):
        config={'schema_version':2,'nodes':[{'id':'a','type':'page','title':'A','path':'/','x':40,'y':60,'groupId':'g'}], 'edges':[],
                'groups':[{'id':'g','name':'Grupo','bounds':{'x':0,'y':0,'width':300,'height':300},'memberIds':['a']}]}
        normalized,_=_normalize_flow_config(config,'example.com')
        self.assertEqual(normalized['nodes'][0]['groupId'],'g')
        self.assertEqual(normalized['groups'],config['groups'])
        config['groups'][0]['memberIds']=['foreign']
        with self.assertRaises(BadRequest):_normalize_flow_config(config,'example.com')
    def test_draft_can_have_unconfigured_event(self):
        config={'nodes':[{'id':'e','type':'event','path':'/configurar-e','event_name':''}],'edges':[]}
        normalized,_=_normalize_flow_config(config,'example.com')
        self.assertFalse(normalized['nodes'][0].get('event_name'))
    def test_presence_does_not_imply_event_happening(self):
        now=datetime.now(timezone.utc)
        nodes=[{'id':'p','type':'page','path':'/'},{'id':'e','type':'event','path':'/','event_name':'lead'}]
        events=[{'id':1,'session_id':'s','page_host':'example.com','page_path':'/','event_kind':'page_view','occurred_at':now-timedelta(seconds=1)}]
        result=build_live_snapshot(events,nodes,[],now)
        self.assertEqual(result['node_presence'],{'p':1})
    def test_repeated_visits_collapse_and_unmapped_stops_path(self):
        now=datetime.now(timezone.utc)
        nodes=[{'id':x,'type':'page','path':'/'+x} for x in ('a','b')]
        edges=[{'id':'ab','from':'a','to':'b'}]
        def events(paths):return [{'id':i+1,'session_id':'s','page_host':'example.com','page_path':'/'+p,'event_kind':'page_view','occurred_at':now-timedelta(seconds=20-i)} for i,p in enumerate(paths)]
        self.assertEqual(build_live_snapshot(events(['a','a','b']),nodes,edges,now)['transitions'],{'ab':'3'})
        self.assertEqual(build_live_snapshot(events(['a','x','b']),nodes,edges,now)['transitions'],{})
