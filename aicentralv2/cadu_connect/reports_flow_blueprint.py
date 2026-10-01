"""Bounded, tenant-scoped blueprint jobs; never modify a draft in the worker."""
import json
import os
import time
import uuid
from .reports_flow_validation import MAX_FLOW_PAGES
from pathlib import Path
from flask import abort, current_app, jsonify, request, session
from ..db import get_db
from ..auth import login_required_api
from .reports_v1 import _selection, _write_guard, _rows
from .reports_flow import _flow_row, _discover_site
from .reports_flow_catalog import build_catalog, ROLE_STAGE
from .reports_flow_previews import _pool, _slots

STEPS=['Descobrindo páginas','Agrupando modelos','Classificando papéis','Detectando objetivos','Lendo caminhos observados','Montando proposta']

def _root(client):
    path=Path(current_app.instance_path)/'reports-blueprints'/str(client)
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path

def _write(path,state):
    temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,default=str));os.replace(temporary,path)

def _read(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):abort(404,description='Montagem não encontrada nesta conta.')

def observations(flow, client_id):
    """Only aggregate consented site data. Never return visitor identities."""
    if not flow.get('site_id'):return {'pages':[], 'transitions':[], 'sources':[]}
    _rows("SELECT set_config('statement_timeout','8000',true)")
    scope=(client_id,flow['site_id'])
    base="FROM cadu_reports_supertag_events WHERE client_id=%s AND site_id=%s AND occurred_at>NOW()-INTERVAL '90 days' AND expires_at>NOW()"
    pages=_rows("SELECT page_path,COUNT(DISTINCT session_id)::int AS sessions "+base+" AND event_kind='page_view' GROUP BY page_path ORDER BY sessions DESC LIMIT 500",scope)
    transitions=_rows("""WITH ordered AS (
      SELECT page_path,event_kind,session_id,
        LEAD(page_path) OVER w AS next_path,LEAD(event_kind) OVER w AS next_kind
      """+base+""" AND event_kind IN ('page_view','form_submit','conversion')
      WINDOW w AS (PARTITION BY session_id ORDER BY occurred_at,id))
      SELECT page_path AS source,next_path AS target,event_kind,
        COUNT(DISTINCT session_id)::int AS sessions FROM ordered
      WHERE next_kind='page_view' AND next_path<>page_path
      GROUP BY page_path,next_path,event_kind ORDER BY sessions DESC LIMIT 500""",scope)
    sources=_rows("SELECT COALESCE(NULLIF(attribution->>'utm_source',''),NULLIF(referrer_host,''),'direct') AS source,COUNT(DISTINCT session_id)::int AS sessions "+base+" AND event_kind='page_view' GROUP BY 1 ORDER BY sessions DESC LIMIT 12",scope)
    return {'pages':pages,'transitions':transitions,'sources':sources}

def enrich_catalog(catalog, observed):
    counts={p['page_path']:p['sessions'] for p in observed.get('pages',[])}
    after={}
    for passage in observed.get('transitions',[]):
        if passage['event_kind']=='form_submit':after[passage['target']]=max(after.get(passage['target'],0),passage['sessions'])
    for page in catalog:
        path=page['path_prefix'];page['sessions_90d']=counts.get(path,0)
        # A repeated immediate post-submit destination is a candidate, not proof of revenue.
        if page['role']=='none' and after.get(path,0)>=3 and counts.get(path,0) and after[path]/counts[path]>=.8:
            page.update(role='conversion',stage='conversion',role_source='observado',evidence_text=f"Ao menos {after[path]} sessões chegaram após envio de formulário; confirme o objetivo")
    return catalog

def propose(catalog,goal,observed=None,media=None):
    observed=observed or {};media=media or []
    priority={'entry':0,'conversion':1,'intent':2,'form':3,'offer':4,'institutional':5,'content':6,'checkout':2,'none':7}
    pages=sorted((p for p in catalog if p['role'] not in ('legal','error')),key=lambda p:(priority.get(p['role'],9),-p.get('sessions_90d',0),p['canonical_url']))
    if goal=='sale':pages.sort(key=lambda p:(p['role'] not in ('entry','checkout','conversion','offer'),priority.get(p['role'],9)))
    elif goal=='appointment':pages.sort(key=lambda p:(not any(w in p['path_prefix'] for w in ('agend','calendar','booking')) and p['role']!='entry',priority.get(p['role'],9)))
    nodes=[];groups=[];templates={};visible=0;columns={};warnings=[]
    source_limit=min(3,len(observed.get('sources',[]))+len(media))
    page_limit=MAX_FLOW_PAGES
    for page in pages:
        template=page.get('template_id')
        if visible>=page_limit and template not in templates:continue
        if len(nodes)>=195:break
        stage=page['stage'];index=columns.get(stage,0)
        if not template or template not in templates:columns[stage]=index+1
        node_type=page['role'] if page['role'] in ('form','conversion') else 'page'
        node={'id':str(uuid.uuid4()),'type':node_type,'title':page['title_clean'][:120],
            'path':page['path_prefix'],'host':page['page_host'],'stage':stage,'role':page['role'],
            'role_source':page.get('role_source','regra'),'origin':'blueprint','evidence':page['evidence_text'],
            'isEntry':page['role']=='entry','x':80+['source','entry','exploration','intent','conversion','support'].index(stage)*320,
            'y':100+index*240}
        if template:
            if template not in templates:
                group={'id':str(uuid.uuid4()),'name':page['template_pattern'],'memberIds':[],'bounds':{'x':node['x']-32,'y':node['y']-48,'width':240,'height':280}}
                templates[template]=group;groups.append(group);visible+=1
            group=templates[template];node['groupId']=group['id'];group['memberIds'].append(node['id'])
            member_index=len(group['memberIds'])-1
            node['x']=group['bounds']['x']+32+(member_index%8)*220
            node['y']=group['bounds']['y']+48+(member_index//8)*240
            group['bounds']['height']=(member_index//8+1)*240+80
            group['bounds']['width']=min(8,len(group['memberIds']))*220+64
        else:visible+=1
        nodes.append(node)
    # Sources are explicitly linked to measured site evidence or a connected media account.
    source_rows=observed.get('sources',[]) if observed else []
    source_rows=[*source_rows,*[{'source':p,'sessions':None} for p in media]]
    known=set()
    for row in source_rows:
        source=str(row['source'])[:80]
        if len(known)>=source_limit:break
        if source in known:continue
        known.add(source);visible+=1
        nodes.append({'id':str(uuid.uuid4()),'type':'source','source':source,'title':source,'stage':'source','origin':'blueprint','role_source':'observado','evidence':f"{row['sessions']} sessões no site" if row['sessions'] is not None else 'Conta de mídia conectada; tráfego não atribuído','x':80,'y':100+len(known)*200})
    edges=[];by_path={n.get('path'):n for n in nodes if n.get('path')};pairs=set()
    def connect(source,target,observed_count=None):
        if len(edges)>=20 or source['id']==target['id'] or (source['id'],target['id']) in pairs:return
        pairs.add((source['id'],target['id']))
        edges.append({'id':str(uuid.uuid4()),'from':source['id'],'to':target['id'],'variant':'direct' if observed_count is not None else 'planned','origin':'blueprint','label':f'{observed_count} sessões observadas' if observed_count is not None else 'Proposta lógica','evidence':f'{observed_count} sessões com passagem direta (90 dias)' if observed_count is not None else 'Sequência de etapas; requer revisão'})
    for passage in observed.get('transitions',[]):
        if passage['event_kind']=='page_view' and passage['source'] in by_path and passage['target'] in by_path:
            connect(by_path[passage['source']],by_path[passage['target']],passage['sessions'])
    stages=[stage for stage in ['source','entry','exploration','intent','conversion'] if any(n['stage']==stage for n in nodes)]
    for left,right in zip(stages,stages[1:]):
        sources=[n for n in nodes if n['stage']==left];targets=[n for n in nodes if n['stage']==right]
        for source in sources:
            if any(e['from']==source['id'] for e in edges):continue
            for target in targets[:2]:connect(source,target)
    if goal=='whatsapp':warnings.append('Confirme um evento whatsapp_click do site como objetivo; clique não equivale a venda.')
    if not any(n['type']=='conversion' for n in nodes):warnings.append('Nenhuma página de confirmação encontrada. Escolha um evento ou página de conversão antes de publicar.')
    return {'nodes':nodes,'edges':edges,'groups':groups,'catalog':catalog,'goal':goal,'requires_confirmation':True,
            'warnings':warnings,'omitted_pages':max(0,len(catalog)-sum(n['type']!='source' for n in nodes))}

def stored_catalog(flow, client_id, observed):
    rows=_rows("""SELECT p.* FROM cadu_reports_flow_discovered_pages p
      WHERE p.client_id=%s AND p.tag_id=%s AND p.run_id=(SELECT id FROM cadu_reports_flow_discovery_runs
      WHERE client_id=%s AND tag_id=%s AND created_at>NOW()-INTERVAL '24 hours'
      AND status='completed' ORDER BY created_at DESC LIMIT 1)""",(client_id,flow['tag_id'],client_id,flow['tag_id']))
    known={p['path_prefix'] for p in rows}
    if any(p['page_path'] not in known for p in observed.get('pages',[])):return []
    return rows

def store_discovery(flow,client_id,actor_id,pages,pending,truncated):
    run_id=str(uuid.uuid4())
    _rows("""INSERT INTO cadu_reports_flow_discovery_runs
      (id,client_id,tag_id,root_url,status,page_count,created_by,pending_urls,pending_truncated)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id""",
      (run_id,client_id,flow['tag_id'],'https://'+flow['allowed_host'],'partial' if pending or truncated else 'completed',len(pages),actor_id,json.dumps(pending),bool(truncated)))
    stored=[]
    for page in pages:
        evidence={'structure_signature':page.get('structure_signature'),'canonical':page.get('canonical'),'h1':page.get('h1'),'signals':page.get('evidence',[])}
        row=_rows("""INSERT INTO cadu_reports_flow_discovered_pages
          (id,run_id,client_id,tag_id,url,page_host,path_prefix,title,suggested_role,confidence,evidence,form_count,form_fields)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb) RETURNING *""",
          (str(uuid.uuid4()),run_id,client_id,flow['tag_id'],page['url'],page['host'],page['path'],page['title'],page['role'],page['confidence'],json.dumps(evidence),page['forms'],json.dumps(page['form_fields'])))[0]
        stored.append(row)
    get_db().commit()
    return stored

def _run(app,path,host,goal,flow,client_id,use_observed,include_media,actor_id,use_ai):
    state={"status":"failed"}
    try:
        with app.app_context():
            state=_read(path)
            def progress(step):
                if path.with_suffix('.cancel').exists():raise InterruptedError()
                state.update(status='running',step=step,updated_at=time.time());_write(path,state)
            progress(0)
            deadline=time.monotonic()+50
            def checkpoint():
                if path.with_suffix('.cancel').exists():raise InterruptedError()
                return time.monotonic()<deadline
            available_observations=observations(flow,client_id)
            observed=available_observations if use_observed else {}
            adapted=stored_catalog(flow,client_id,available_observations);get_db().commit()
            pending=[];truncated=False
            if not adapted:
                pages,pending,truncated=_discover_site('https://'+host,host,max_pages=500,checkpoint=checkpoint,extra_urls=['https://'+host+p['page_path'] for p in available_observations.get('pages',[])])
                checkpoint()
                adapted=store_discovery(flow,client_id,actor_id,pages,pending,truncated)
            progress(1)
            catalog=build_catalog(adapted,host)
            progress(2)
            analyzed=0;ai_warning=None
            if use_ai:
                from .reports_flow_suggestions import suggest
                from ..services.typesafe_service import TypeSafeError
                from werkzeug.exceptions import HTTPException
                selected={'client_id':client_id}
                representatives=set()
                by_id={str(p['id']):p for p in adapted}
                for page in catalog:
                    key=page.get('template_id') or page['canonical_url']
                    if page['role']!='none' or key in representatives:continue
                    if analyzed>=20 or time.monotonic()>deadline:
                        ai_warning='Páginas restantes mantidas sem papel; limite de tempo ou 20 análises atingido.';break
                    representatives.add(key);progress(2)
                    try:
                        result=suggest(flow,by_id[str(page['id'])],selected,actor_id=actor_id);analyzed+=1
                    except (TypeSafeError,HTTPException):
                        get_db().rollback();ai_warning='Classificação de IA indisponível ou cota atingida. A proposta usa as evidências restantes.';break
                    role={'intermediate':'institutional'}.get(result['suggestion']['role'],result['suggestion']['role'])
                    if role in ROLE_STAGE and role!='none':
                        for member in catalog:
                            if member['canonical_url']==page['canonical_url'] or (page.get('template_id') and member.get('template_id')==page['template_id']):
                                member.update(role=role,stage=ROLE_STAGE[role],role_source='ia',evidence_text='Papel sugerido por IA a partir do título, caminho e formulário; requer confirmação')
            progress(3)
            progress(4)
            catalog=enrich_catalog(catalog,observed)
            media=[r['platform'] for r in _rows('SELECT DISTINCT platform FROM cadu_reports_accounts WHERE client_id=%s',(client_id,))] if include_media else []
            result=propose(catalog,goal,observed,media)
            result['ai_analyses']=analyzed
            if ai_warning:result['warnings'].append(ai_warning)
            if pending or truncated:result['warnings'].append('Descoberta parcial; existem páginas adicionais para analisar.')
            progress(5)
            state.update(status='ready',result=result,updated_at=time.time());_write(path,state)
    except InterruptedError:
        state.update(status='cancelled',updated_at=time.time());_write(path,state)
    except Exception:
        app.logger.exception('Reports blueprint failed')
        state.update(status='failed',message='Não foi possível montar a proposta. Tente novamente.',updated_at=time.time());_write(path,state)
    finally:_slots.release()

def register(bp):
    @bp.post('/api/v2/reports/flow/flows/<flow_id>/blueprint')
    @login_required_api
    def create_blueprint(flow_id):
        payload=request.get_json(silent=True)
        if not isinstance(payload,dict):abort(400)
        selected=_selection(payload);_write_guard(selected);flow=_flow_row(flow_id,selected)
        domain=payload.get('domain') or flow['allowed_host']
        if domain!=flow['allowed_host']:abort(400,description='Use o domínio autorizado deste fluxo.')
        goal=payload.get('goal','auto')
        if goal not in ('auto','leads','sale','appointment','whatsapp'):abort(400)
        if not _slots.acquire(blocking=False):abort(429,description='Há outras capturas ou montagens em andamento. Tente novamente.')
        job_id=str(uuid.uuid4());path=_root(selected['client_id'])/(job_id+'.json')
        state={'job_id':job_id,'flow_id':str(flow['id']),'status':'queued','step':0,'steps':STEPS,'updated_at':time.time()}
        try:
            _write(path,state);_pool.submit(_run,current_app._get_current_object(),path,domain,goal,flow,selected['client_id'],payload.get('use_observed') is True,payload.get('include_media') is True,session['user_id'],payload.get('use_ai') is True)
        except Exception:_slots.release();raise
        return jsonify(state),202

    @bp.route('/api/v2/reports/flow/blueprint-jobs/<uuid:job_id>',methods=['GET','DELETE'])
    @login_required_api
    def blueprint_status(job_id):
        selected=_selection();path=_root(selected['client_id'])/(str(job_id)+'.json');state=_read(path)
        _flow_row(state['flow_id'],selected)
        if request.method=='DELETE':
            _write_guard(selected);path.with_suffix('.cancel').touch();state['status']='cancelled';_write(path,state)
        elif path.with_suffix('.cancel').exists():state['status']='cancelled'
        elif state['status'] in ('queued','running') and time.time()-state['updated_at']>300:
            state.update(status='failed',message='A montagem foi interrompida. Inicie novamente.')
        return jsonify(state)
