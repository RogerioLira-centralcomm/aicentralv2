"""Deterministic page catalog. Evidence and suggestions never imply measured traffic."""
from collections import Counter, defaultdict
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, unquote
import hashlib
import re
from .reports_page_paths import normalize_page_path, translation_key

ROLE_STAGE = {'entry':'entry','institutional':'exploration','offer':'exploration','content':'exploration',
              'intent':'intent','form':'intent','conversion':'conversion','checkout':'intent',
              'legal':'support','error':'support','none':'exploration'}

def canonical_url(url, allowed_host):
    try:
        parsed=urlsplit(url)
        if parsed.scheme not in ("http","https") or parsed.username or parsed.password or parsed.port not in (None,80,443):return None
    except ValueError:return None
    host=(parsed.hostname or '').lower()
    allowed=allowed_host.lower().removeprefix('www.')
    if host.removeprefix('www.')!=allowed and not host.endswith('.'+allowed):
        return None
    path=re.sub(r'/+', '/', unquote(parsed.path).lower())
    path=re.sub(r'/page/\d+/?$', '', path).rstrip('/') or '/'
    path=re.sub(r'/index\.(?:php|html?)$', '', path).rstrip('/') or '/'
    if len(path)>500 or any(part in ('.','..') for part in path.split('/')):return None
    query=[(key,value) for key,value in parse_qsl(parsed.query) if not key.lower().startswith('utm_') and key.lower() not in ('gclid','fbclid','msclkid','page')]
    return urlunsplit(('https',allowed if host.removeprefix('www.')==allowed else host,path,urlencode(sorted(query)),''))

def role_for(page):
    path=page['path_prefix'].casefold()
    if re.search(r'obrigad|agradec|sucesso|confirma|thank|pedido-recebido',path):return 'conversion','Caminho de confirmação'
    if re.search(r'privacidade|termos|cookies|lgpd',path):return 'legal','Página legal'
    if re.search(r'404|/erro(?:/|$)',path):return 'error','Caminho de erro'
    if path=='/':return 'entry','Página inicial'
    if page.get('form_count',0)>0 and any(re.search(r'email|e-mail|telefone|phone|tel',str(field.get('name','')),re.I) for field in page.get('form_fields') or []):return 'form','Formulário com campo de contato'
    if re.search(r'contato|fale-conosco|orcamento|orçamento|agend',path):return 'intent','Caminho de contato'
    if re.search(r'checkout|finalizar|pagamento|carrinho',path):return 'checkout','Caminho de compra'
    if re.search(r'/blog/|/artigos/|/noticias/',path):return 'content','Seção de conteúdo'
    if re.search(r'/produto|/servico|/oferta',path):return 'offer','Seção de ofertas'
    if re.search(r'/sobre|/empresa|/institucional',path):return 'institutional','Seção institucional'
    return 'none','Sem evidência suficiente; escolha o papel'

def build_catalog(pages, host, nodes=()):
    pages=[page for page in pages if page.get('page_status','valida') == 'valida']
    suffixes=Counter(re.split(r'\s+[|–-]\s+',p.get('title') or '')[-1] for p in pages if re.search(r'\s+[|–-]\s+',p.get('title') or ''))
    suffix=next((s for s,n in suffixes.items() if n>=len(pages)*.6),None)
    unique={}
    for page in pages:
        url=canonical_url((page.get('evidence') or {}).get('canonical') or page.get('url') or f"https://{host}{page['path_prefix']}",host)
        if not url:continue
        if url in unique:
            unique[url]['aliases'].append(page.get('url') or url);continue
        parsed=urlsplit(url)
        normalized=normalize_page_path(parsed.path)
        page={**page,'page_host':parsed.hostname,'path_prefix':parsed.path,
              'locale':normalized['locale'],'normalized_path':normalized['path']}
        role,evidence=role_for(page)
        title=page.get('title') or page['path_prefix']
        clean=re.sub(r'\s+[|–-]\s+'+re.escape(suffix)+r'$', '', title) if suffix else title
        matching=next((n['id'] for n in nodes if n.get('type') in ('page','form','conversion','error') and
                       (str(n.get('discoveryPageId'))==str(page.get('id')) or
                        canonical_url(f"https://{n.get('host') or host}{n.get('path') or ''}",host)==url)),None)
        unique[url]={**page,'canonical_url':url,'aliases':[page.get('url') or url],'title_clean':clean,'role':role,'stage':ROLE_STAGE[role],
                     'role_source':'regra','evidence_text':evidence,'template_id':None,'sessions_30d':None,'in_flow_node_id':matching}
    locale_paths=defaultdict(set)
    for page in unique.values():
        locale_paths[(page['page_host'],page['normalized_path'])].add(page['locale'])
    for page in unique.values():
        page['translation_key']=translation_key(page,{page['normalized_path']:locale_paths[(page['page_host'],page['normalized_path'])]})
    templates=defaultdict(list)
    for page in unique.values():
        parts=page['normalized_path'].strip('/').split('/')
        # Do not invent HTML similarity from URL prefixes alone.
        signature=(page.get('evidence') or {}).get('structure_signature')
        if len(parts)>=2 and signature:templates[(page['page_host'],'/'+ '/'.join(parts[:-1])+'/*',signature)].append(page)
    for (page_host,pattern,signature),members in templates.items():
        if len({page['normalized_path'] for page in members})<3:continue
        identifier=hashlib.sha256((page_host+pattern+signature).encode()).hexdigest()[:16]
        for page in members:page['template_id']=identifier;page['template_pattern']=pattern
    return list(unique.values())


def catalog_summary(pages, catalog):
    excluded=Counter(page.get('page_status') for page in pages if page.get('page_status','valida')!='valida')
    excluded['duplicada']=sum(page.get('page_status','valida')=='valida' for page in pages)-len(catalog)
    classified=sum(page['role']!='none' for page in catalog)
    return {'descobertas':len(pages),'validas':len(catalog),'classificadas':classified,
            'sem_tipo':len(catalog)-classified,
            'no_fluxo':len({page['in_flow_node_id'] for page in catalog if page['in_flow_node_id']}),
            'excluidas':dict(excluded)}


def register(bp):
    from flask import abort, jsonify, request
    from ..auth import login_required_api
    from .reports_v1 import _selection, _write_guard, _rows
    from .reports_flow import _flow_row, _host

    def context(host):
        selected=_selection(request.get_json(silent=True) if request.method=='POST' else None)
        flow_id=request.args.get('flow_id') or (request.get_json(silent=True) or {}).get('flow_id')
        if not flow_id:abort(400,description='Informe o fluxo para acessar o catálogo.')
        flow=_flow_row(flow_id,selected)
        if _host(host).removeprefix('www.')!=flow['allowed_host'].removeprefix('www.'):abort(404)
        pages=_rows('''SELECT p.* FROM cadu_reports_flow_discovered_pages p
            WHERE p.client_id=%s AND p.tag_id=%s AND p.run_id=(
              SELECT id FROM cadu_reports_flow_discovery_runs WHERE client_id=%s AND tag_id=%s
              ORDER BY created_at DESC LIMIT 1) ORDER BY p.page_host,p.path_prefix''',
              (selected['client_id'],flow['tag_id'],selected['client_id'],flow['tag_id']))
        return selected,flow,pages

    @bp.get('/api/v2/reports/flow/sites/<host>/catalog')
    @login_required_api
    def catalog(host):
        selected,flow,pages=context(host)
        items=build_catalog(pages,flow['allowed_host'],flow['config'].get('nodes',[]))
        role=request.args.get('role');template=request.args.get('template')
        if role:items=[p for p in items if p['role']==role]
        if template:items=[p for p in items if p['template_id']==template]
        try:offset=max(0,int(request.args.get('offset',0)));limit=max(1,min(100,int(request.args.get('limit',50))))
        except ValueError:abort(400,description='Paginação inválida.')
        return jsonify(items=items[offset:offset+limit],total=len(items),next_offset=offset+limit if offset+limit<len(items) else None)

    @bp.post('/api/v2/reports/flow/sites/<host>/catalog/classify')
    @login_required_api
    def classify(host):
        from .reports_flow_suggestions import suggest
        from ..services.typesafe_service import TypeSafeError
        selected,flow,pages=context(host);_write_guard(selected)
        payload=request.get_json(silent=True) or {};requested=payload.get('page_ids')
        if not isinstance(requested,list) or not 1<=len(requested)<=20:abort(400,description='Selecione de 1 a 20 páginas para análise.')
        by_id={str(p['id']):p for p in pages}
        if any(not isinstance(identifier,str) or identifier not in by_id for identifier in requested):abort(404,description='Página fora do catálogo deste fluxo.')
        results=[]
        for identifier in dict.fromkeys(requested):
            try:results.append(suggest(flow,by_id[identifier],selected))
            except TypeSafeError:
                return jsonify(results=results,message='Análise indisponível. As regras e a edição manual continuam disponíveis.'),503
        return jsonify(results=results)
