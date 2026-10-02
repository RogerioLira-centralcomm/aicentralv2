"""Mídia → Criativos: briefings built from campaign data and handed to the Studio with brand and project.

Reports never generates images nor spends credits here. It writes a prompt from what the campaign already shows
(objective, landing page, converting search terms, performance), resolves the Workspace project and the Studio brand
of the campaign, and opens a resumable Studio session through the same function the Workspace agent uses. Direction
approval, generation and billing stay in the Studio.
"""
import json
import uuid
from datetime import date, timedelta
from urllib.parse import urlencode

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_management import workspace_items
from .reports_v1 import _column_exists, _rows, _selection, _write_guard

FORMATS = {
    'feed': ('Feed 4:5', '4:5', 'Peça vertical para feed (1080×1350).'),
    'stories': ('Stories e Reels 9:16', '9:16', 'Peça vertical de tela cheia (1080×1920), com área segura para texto.'),
    'square': ('Quadrado 1:1', '1:1', 'Peça quadrada (1080×1080).'),
    'display': ('Display 16:9', '16:9', 'Peça horizontal para display e YouTube (1920×1080).'),
}
ANGLES = {
    'benefit': ('Benefício direto', 'Mostre o principal benefício de forma concreta e imediata, com a oferta legível em poucos segundos.'),
    'trust': ('Prova e confiança', 'Transmita credibilidade: pessoas reais, selo, resultado ou garantia, sem exagero.'),
    'urgency': ('Oferta e urgência', 'Destaque a oferta e um motivo para agir agora, com CTA forte e contraste alto.'),
}
PLATFORMS = {'google_ads': 'Google Ads', 'meta_ads': 'Meta Ads', 'microsoft_ads': 'Microsoft Ads'}
WINDOW_DAYS = 30


def _exists(table):
    return bool(_rows('SELECT to_regclass(%s) IS NOT NULL AS ready', (f'public.{table}',))[0]['ready'])


def _campaign(selected, campaign_id):
    try:
        campaign_id = int(campaign_id)
    except (TypeError, ValueError):
        abort(400, description='Campanha inválida.')
    rows = _rows('''SELECT c.id,c.customer_id,c.name,c.status,c.objective,c.external_id,c.account_id,
            a.platform,a.name AS account_name
        FROM cadu_reports_campaigns c LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
        WHERE c.id=%s AND c.client_id=%s''', (campaign_id, selected['client_id']))
    if not rows:
        abort(404, description='Campanha não encontrada.')
    campaign = rows[0]
    project = None
    if _column_exists('cadu_reports_campaigns', 'workspace_project_id'):
        found = _rows('SELECT workspace_project_id::text AS id FROM cadu_reports_campaigns WHERE id=%s', (campaign_id,))
        project = f"ci:{found[0]['id']}" if found and found[0]['id'] else None
    if not project and _exists('cadu_reports_workspace_links'):
        linked = _rows('''SELECT project_ref FROM cadu_reports_workspace_links
            WHERE client_id=%s AND campaign_id=%s ORDER BY project_ref LIMIT 1''', (selected['client_id'], campaign_id))
        project = linked[0]['project_ref'] if linked else None
    campaign['project_ref'] = project
    return campaign


def _signals(selected, campaign):
    """What the data says about the campaign: landing page, converting terms and headline metrics."""
    end = date.today()
    scope = {'client': selected['client_id'], 'account': campaign['account_id'], 'campaign': str(campaign['external_id'] or ''),
             'start': end - timedelta(days=WINDOW_DAYS - 1), 'end': end}
    out = {'landing_page': None, 'terms': [], 'keywords': [], 'metrics': None}
    if not campaign['account_id'] or campaign['platform'] != 'google_ads':
        return out
    where = 'x.client_id=%(client)s AND x.account_id=%(account)s AND x.campaign_external_id=%(campaign)s AND x.metric_date BETWEEN %(start)s AND %(end)s'
    if _exists('cadu_reports_gads_landing_page_daily'):
        page = _rows(f'''SELECT x.page_host,x.page_path,SUM(x.clicks)::bigint AS clicks FROM cadu_reports_gads_landing_page_daily x
            WHERE {where} GROUP BY x.page_host,x.page_path ORDER BY clicks DESC LIMIT 1''', scope)
        out['landing_page'] = f"{page[0]['page_host']}{page[0]['page_path']}" if page else None
    if _exists('cadu_reports_gads_search_term_daily'):
        out['terms'] = [row['search_term'] for row in _rows(f'''SELECT x.search_term FROM cadu_reports_gads_search_term_daily x
            WHERE {where} GROUP BY x.term_hash,x.search_term HAVING SUM(x.conversions)>0
            ORDER BY SUM(x.conversions) DESC,SUM(x.clicks) DESC LIMIT 5''', scope)]
    if _exists('cadu_reports_gads_keyword_daily'):
        out['keywords'] = [row['keyword_text'] for row in _rows(f'''SELECT x.keyword_text FROM cadu_reports_gads_keyword_daily x
            WHERE {where} GROUP BY x.criterion_external_id,x.keyword_text ORDER BY SUM(x.clicks) DESC LIMIT 5''', scope)]
    metrics = _rows('''SELECT SUM(m.impressions)::bigint AS impressions,SUM(m.clicks)::bigint AS clicks,
            SUM(m.conversions)::numeric AS conversions FROM cadu_reports_campaign_daily_metrics m
        WHERE m.client_id=%(client)s AND m.campaign_id=%(id)s AND m.metric_date BETWEEN %(start)s AND %(end)s''',
                    {**scope, 'id': campaign['id']})
    if metrics and metrics[0]['impressions']:
        out['metrics'] = {key: float(value or 0) for key, value in metrics[0].items()}
    return out


def _context(selected, campaign):
    """Brand and project for the brief: the campaign's project, its Studio brand, else the customer's brand."""
    items = workspace_items(selected)
    brands = [{'ref': i['ref'], 'name': i['name'], 'logo_url': i.get('logo_url'), 'studio': str(i['ref']).startswith('studio:')}
              for i in items if i['kind'] == 'brand']
    projects = [{'ref': i['ref'], 'name': i['name'], 'brand_refs': i.get('related_refs') or []} for i in items if i['kind'] == 'project']
    project = campaign['project_ref'] if any(p['ref'] == campaign['project_ref'] for p in projects) else None
    studio_brands = {b['ref'] for b in brands if b['studio']}
    brand = None
    if project:
        linked = [ref for ref in next(p for p in projects if p['ref'] == project)['brand_refs'] if ref in studio_brands]
        brand = linked[0] if len(linked) == 1 else None
    if not brand and campaign.get('customer_id') and _exists('cadu_reports_customer_workspace_brand_links'):
        linked = [row['brand_ref'] for row in _rows('''SELECT brand_ref FROM cadu_reports_customer_workspace_brand_links
            WHERE client_id=%s AND customer_id=%s''', (selected['client_id'], campaign['customer_id'])) if row['brand_ref'] in studio_brands]
        brand = linked[0] if len(linked) == 1 else None
    if not brand and len(studio_brands) == 1:
        brand = next(iter(studio_brands))
    return {'brands': [b for b in brands if b['studio']], 'projects': projects, 'brand_ref': brand, 'project_ref': project}


def build_prompt(campaign, signals, format_key='feed', angle='benefit', notes=''):
    """Portuguese creative brief the Studio's creative director turns into a direction."""
    fmt, angle_text = FORMATS.get(format_key, FORMATS['feed']), ANGLES.get(angle, ANGLES['benefit'])
    platform = PLATFORMS.get(campaign.get('platform'), 'mídia paga')
    lines = [f'Criativo de anúncio para a campanha "{campaign["name"]}" ({platform}).']
    if campaign.get('objective'):
        lines.append(f'Objetivo da campanha: {campaign["objective"]}.')
    if signals.get('terms'):
        lines.append('As pessoas que converteram buscaram: ' + ', '.join(f'"{term}"' for term in signals['terms'][:4]) + '. Use essa intenção como mensagem principal.')
    elif signals.get('keywords'):
        lines.append('Temas com mais cliques: ' + ', '.join(signals['keywords'][:4]) + '.')
    if signals.get('landing_page'):
        lines.append(f'O clique leva para {signals["landing_page"]}; a peça deve prometer o que essa página entrega.')
    metrics = signals.get('metrics')
    if metrics and metrics.get('impressions'):
        ctr = metrics['clicks'] * 100 / metrics['impressions']
        lines.append(f'Desempenho nos últimos {WINDOW_DAYS} dias: CTR de {ctr:.1f}%'.replace('.', ',') +
                     (f' e {int(metrics["conversions"])} conversões.' if metrics.get('conversions') else '.'))
    lines.append(f'Ângulo: {angle_text[0]}. {angle_text[1]}')
    lines.append(f'Formato: {fmt[0]}. {fmt[2]}')
    lines.append('Use a identidade da marca (logo, cores e tom de voz), um título curto, no máximo uma linha de apoio e um CTA claro.')
    if notes:
        lines.append(f'Observações: {notes.strip()}')
    return '\n'.join(lines)[:3900]


def register(bp):
    @bp.get('/api/v2/reports/creatives/campaigns/<campaign_id>')
    @login_required_api
    def reports_creative_context(campaign_id):
        """Suggested brief, signals and the brand/project the Studio session will carry."""
        selected = _selection()
        campaign = _campaign(selected, campaign_id)
        signals = _signals(selected, campaign)
        context = _context(selected, campaign)
        return jsonify(campaign={key: campaign[key] for key in ('id', 'name', 'platform', 'objective', 'status', 'account_name')},
                       signals=signals, prompt=build_prompt(campaign, signals, request.args.get('format', 'feed'), request.args.get('angle', 'benefit')), **context,
                       formats=[{'key': key, 'label': value[0], 'ratio': value[1]} for key, value in FORMATS.items()],
                       angles=[{'key': key, 'label': value[0]} for key, value in ANGLES.items()])

    @bp.post('/api/v2/reports/creatives/studio')
    @login_required_api
    def reports_creative_studio():
        """Open a Studio session with the brief, the brand and the project. No generation, no credits."""
        from ..cadu_workspace.agent_v2.contracts import RequestContext
        from ..cadu_workspace.mcp.tools.media import start_studio_session
        from ..db import get_db
        payload = request.get_json(silent=True)
        selected = _selection(payload)
        _write_guard(selected)
        campaign = _campaign(selected, payload.get('campaign_id'))
        context = _context(selected, campaign)
        prompt = str(payload.get('prompt') or '').strip()
        if not 3 <= len(prompt) <= 4000:
            abort(400, description='Escreva o briefing do criativo (até 4.000 caracteres).')
        brand_ref = payload.get('brand_ref') or None
        project_ref = payload.get('project_ref') or None
        if brand_ref and brand_ref not in {b['ref'] for b in context['brands']}:
            abort(403, description='Marca indisponível para este cliente.')
        if project_ref and project_ref not in {p['ref'] for p in context['projects']}:
            abort(403, description='Projeto indisponível para você.')
        format_key = payload.get('format') if payload.get('format') in FORMATS else 'feed'
        request_id = str(payload.get('request_id') or uuid.uuid4())[:120]
        ctx = RequestContext(client_id=int(selected['client_id']), user_id=int(selected['user_id']), conversation_id=None,
                             surface='reports', request_id=request_id, project_ref=project_ref, brand_ref=brand_ref)
        session = start_studio_session(ctx, {
            'kind': 'ad' if brand_ref else 'image', 'prompt': prompt, 'request_id': f'reports:{request_id}',
            'title': f'Criativo · {campaign["name"]}'[:160],
            **({'brand_id': int(brand_ref[7:])} if brand_ref else {}),
        })
        # Tag the session so Reports can list what was created from each campaign, and keep the format chosen here.
        with get_db().cursor() as cursor:
            cursor.execute('''UPDATE cx_studio_sessions SET metadata=metadata||%s::jsonb WHERE id=%s''', (
                json.dumps({'origin': 'cadu_reports', 'reports_client_id': int(selected['client_id']),
                                          'reports_campaign_id': int(campaign['id']), 'reports_campaign_name': campaign['name'],
                                          'aspect_ratio': FORMATS[format_key][1], 'format_key': format_key}),
                session['session_id']))
        get_db().commit()
        # The Studio project picker reads project_id (Workspace project UUID) so brand references are not lost.
        url = session['studio_url']
        if project_ref and project_ref.startswith('ci:'):
            url += ('&' if '?' in url else '?') + urlencode({'project_id': project_ref[3:]})
        return jsonify(session_id=session['session_id'], studio_url=url, brand_ref=brand_ref, project_ref=project_ref,
                       creative_client_id=session['creative_client_id'])

    @bp.get('/api/v2/reports/creatives/sessions')
    @login_required_api
    def reports_creative_sessions():
        """Studio sessions opened from Reports for this client, newest first, with the latest image when there is one."""
        selected = _selection()
        if not _exists('cx_studio_sessions'):
            return jsonify(sessions=[])
        rows = _rows('''SELECT s.id::text AS id,s.client_id AS creative_client_id,s.title,s.status,s.created_at,s.updated_at,
                s.metadata->>'reports_campaign_id' AS campaign_id,s.metadata->>'reports_campaign_name' AS campaign_name,
                s.metadata->>'workspace_project_ref' AS project_ref,s.metadata->>'format_key' AS format_key,
                (SELECT a.asset_url FROM cx_studio_assets a WHERE a.id=s.active_asset_id AND a.deleted_at IS NULL) AS image_url
            FROM cx_studio_sessions s
            WHERE s.metadata->>'origin'='cadu_reports' AND s.metadata->>'reports_client_id'=%s
            ORDER BY s.created_at DESC LIMIT 60''', (str(selected['client_id']),))
        from ..product_domains import product_url
        for row in rows:
            query = {'studio_session_id': row['id'], 'creative_client_id': row['creative_client_id']}
            if (row['project_ref'] or '').startswith('ci:'):
                query['project_id'] = row['project_ref'][3:]
            row['studio_url'] = product_url('studio', f'/criar?{urlencode(query)}')
        return jsonify(sessions=rows)
