from flask import Flask
from aicentralv2.cadu_connect.reports_flow_catalog import canonical_url, build_catalog
from aicentralv2.cadu_connect.reports_flow_blueprint import propose
from aicentralv2.cadu_connect.reports_flow import _SitePageParser, _normalize_flow_config


def page(path, signature='main|h1|section|h2'):
    return {'id':path,'url':'https://www.example.com'+path,'page_host':'example.com','path_prefix':path,'title':path+' - Example','form_count':0,'evidence':{'structure_signature':signature}}


def test_normalization_and_scope():
    assert canonical_url('http://www.example.com/blog/page/2/?utm_source=x#g','example.com')=='https://example.com/blog'
    assert canonical_url('https://evil.example/blog','example.com') is None


def test_templates_require_three_and_structure():
    assert all(p['template_id'] is None for p in build_catalog([page('/blog/a'),page('/blog/b')],'example.com'))
    assert all(p['template_id'] is None for p in build_catalog([page('/blog/a'),page('/blog/b'),page('/blog/c','main|form')],'example.com'))
    catalog=build_catalog([page('/blog/a'),page('/blog/b'),page('/blog/c')],'example.com')
    assert len({p['template_id'] for p in catalog})==1 and catalog[0]['template_id']


def test_conversion_and_blueprint_roundtrip():
    catalog=build_catalog([page('/'),page('/servicos'),page('/contato'),page('/obrigado')],'example.com')
    assert catalog[-1]['role']=='conversion'
    result=propose(catalog,'leads')
    with Flask(__name__).app_context():
        normalized,_=_normalize_flow_config({'nodes':result['nodes'],'edges':result['edges']},'example.com')
    assert all(n['origin']=='blueprint' for n in normalized['nodes'])
    assert len(normalized['edges'])<=20


def test_structure_extraction():
    parser=_SitePageParser();parser.feed('<main><h1>Title</h1><section><h2>Offer</h2></section></main>')
    assert parser.structure==['main','h1','section','h2']


def test_grouped_blueprint_keeps_limits_and_valid_coordinates():
    pages=[page('/'),page('/contato'),page('/obrigado')]+[page('/blog/'+str(i)) for i in range(60)]
    result=propose(build_catalog(pages,'example.com'),'leads')
    grouped={i for group in result['groups'] for i in group['memberIds']}
    assert len(result['nodes'])-len(grouped)+len(result['groups'])<=15
    assert len(result['edges'])<=20
    with Flask(__name__).app_context():
        normalized,_=_normalize_flow_config({'schema_version':2,'nodes':result['nodes'],'edges':result['edges'],'groups':result['groups']},'example.com')
    assert len(normalized['groups'])==1


def test_post_form_destination_needs_repeated_observed_evidence():
    from aicentralv2.cadu_connect.reports_flow_blueprint import enrich_catalog
    catalog=build_catalog([page('/done-xyz')],'example.com')
    observed={'pages':[{'page_path':'/done-xyz','sessions':10}],'transitions':[{'event_kind':'form_submit','target':'/done-xyz','sessions':9}]}
    result=enrich_catalog(catalog,observed)
    assert result[0]['role']=='conversion' and result[0]['role_source']=='observado'


def test_publication_requires_goal_confirmation_and_intent_path():
    from aicentralv2.cadu_connect.reports_flow_validation import validate_flow_config
    issues=validate_flow_config({'nodes':[{'id':'f','type':'form','path':'/contact','origin':'blueprint'},{'id':'c','type':'conversion','path':'/done'}],'edges':[]})
    assert {'intent_without_goal','unconfirmed_goal'} <= {i['code'] for i in issues}


def test_blueprint_jobs_are_scoped_and_cancel_is_authoritative(tmp_path, monkeypatch):
    from flask import Blueprint, request
    from types import SimpleNamespace
    from aicentralv2.cadu_connect import reports_flow_blueprint as jobs
    app=Flask(__name__,instance_path=str(tmp_path));app.secret_key='test-only'
    bp=Blueprint('studio_test',__name__);jobs.register(bp);app.register_blueprint(bp)
    monkeypatch.setattr(jobs,'_selection',lambda *args:{'client_id':int(request.args.get('client_id','1'))})
    monkeypatch.setattr(jobs,'_write_guard',lambda selected:None)
    monkeypatch.setattr(jobs,'_flow_row',lambda identifier,selected:{'id':identifier,'allowed_host':'example.com'})
    monkeypatch.setattr(jobs,'_slots',SimpleNamespace(acquire=lambda **kw:True,release=lambda:None))
    monkeypatch.setattr(jobs,'_pool',SimpleNamespace(submit=lambda *args:None))
    client=app.test_client()
    with client.session_transaction() as session:session['user_id']=1
    response=client.post('/api/v2/reports/flow/flows/test/blueprint',json={'domain':'example.com'})
    assert response.status_code==202
    job_id=response.json['job_id'];url=f'/api/v2/reports/flow/blueprint-jobs/{job_id}'
    assert client.get(url+'?client_id=2').status_code==404
    assert client.delete(url).json['status']=='cancelled'
    with app.app_context():
        path=jobs._root(1)/(job_id+'.json');state=jobs._read(path);state['status']='ready';jobs._write(path,state)
    assert client.get(url).json['status']=='cancelled'
    assert client.post('/api/v2/reports/flow/flows/test/blueprint',json={'domain':'other.test'}).status_code==400


def test_blueprint_limits_unique_sources_with_few_pages():
    catalog=build_catalog([page('/')],'example.com')
    observed={'sources':[{'source':f'source-{i}', 'sessions':10} for i in range(12)]}
    result=propose(catalog,'auto',observed,['meta','google'])
    assert len([n for n in result['nodes'] if n['type']=='source']) == 3
    observed['sources']=[{'source':'same','sessions':10}]*4
    result=propose(catalog,'auto',observed,['same','google'])
    assert len([n for n in result['nodes'] if n['type']=='source']) == 2
