"""Reports V1 media inventory and Link Tester API, scoped to one authorized client."""
import json
import re
import secrets
import uuid
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlparse
from flask import abort, jsonify, render_template, request, session

from ..auth import login_required, login_required_api
from ..cadu_family import context
from ..db import get_db


def _rows(sql, params=()):
    with get_db().cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def _ready():
    return bool(_rows("SELECT to_regclass('public.cadu_reports_accounts') IS NOT NULL "
                      "AND to_regclass('public.cadu_reports_campaigns') IS NOT NULL AS ready")[0]['ready'])


def _selection(payload=None):
    supplied = (payload or {}).get('client_id') if payload is not None else request.args.get('client_id')
    return context.resolve(supplied)


def _write_guard(selected):
    if selected['role'] == 'viewer':
        abort(403)
    token = request.headers.get('X-CSRF-Token', '')
    if not token or not secrets.compare_digest(session.get('family_csrf', ''), token):
        abort(403, description='Token de sessão inválido.')


def _required_text(payload, field, limit):
    value = payload.get(field)
    if not isinstance(value, str):
        abort(400, description=f'Informe {field}.')
    value = ' '.join(value.strip().split())
    if not value or len(value) > limit:
        abort(400, description=f'{field} deve ter entre 1 e {limit} caracteres.')
    return value


def register(bp):
    @bp.get('/app')
    @login_required
    def reports_v1_app():
        selected = context.resolve(request.args.get('client_id'))
        if request.args.get('client_id'):
            session['cliente_id'] = selected['client_id']
        return render_template('cadu_connect/app_v1.html')

    @bp.get('/api/v1/reports/bootstrap')
    @login_required_api
    def reports_v1_bootstrap():
        selected = _selection()
        session.setdefault('family_csrf', secrets.token_urlsafe(32))
        clients = [{'id': int(item['id']), 'name': item['name']} for item in context.authorized_clients()]
        if not _ready():
            return jsonify(ready=False, client=selected, csrf=session['family_csrf'],
                           clients=clients, accounts=[], campaigns=[], reports=[], link_tests=[])
        params = (selected['organization_id'], selected['client_id'])
        accounts = _rows('''SELECT id,platform,external_id,name,parent_account_id,account_kind,
                currency,time_zone,status,updated_at FROM cadu_reports_accounts
                WHERE organization_id=%s AND client_id=%s ORDER BY platform,account_kind DESC,name''', params)
        campaigns = _rows('''SELECT c.id,c.account_id,c.external_id,c.name,c.status,c.objective,
                a.name AS account_name,a.platform FROM cadu_reports_campaigns c
                JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE c.organization_id=%s AND c.client_id=%s ORDER BY a.name,c.name''', params)
        reports = _rows('''SELECT id,campaign_name,project_ref,account_id,media_campaign_id,
                revision,updated_at FROM cadu_connect_report_workspaces
                WHERE organization_id=%s AND client_id=%s ORDER BY updated_at DESC LIMIT 60''', params)
        link_tests = _rows('''SELECT id,mode,final_url,score,status_label,created_at
                FROM cadu_planner_link_test_runs WHERE client_id=%s
                ORDER BY created_at DESC LIMIT 20''', (selected['client_id'],))
        return jsonify(ready=True, client=selected, clients=clients, csrf=session['family_csrf'],
                       accounts=accounts, campaigns=campaigns, reports=reports, link_tests=link_tests)

    @bp.post('/api/v1/reports/accounts')
    @login_required_api
    def reports_v1_create_account():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _ready():
            abort(503, description='Instale a migração de Reports V1.')
        platform = _required_text(payload, 'platform', 32).lower()
        if not re.fullmatch(r'[a-z][a-z0-9_]*', platform):
            abort(400, description='Plataforma inválida.')
        external_id = _required_text(payload, 'external_id', 160)
        name = _required_text(payload, 'name', 240)
        kind = payload.get('account_kind', 'advertiser')
        if kind not in ('manager', 'advertiser'):
            abort(400, description='Tipo de conta inválido.')
        parent_id = payload.get('parent_account_id') or None
        if parent_id is not None:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                abort(400, description='Conta gerente inválida.')
            parent = _rows('''SELECT id FROM cadu_reports_accounts WHERE id=%s
                    AND organization_id=%s AND client_id=%s AND platform=%s AND account_kind='manager' ''',
                    (parent_id, selected['organization_id'], selected['client_id'], platform))
            if not parent:
                abort(400, description='A conta gerente precisa pertencer ao mesmo cliente e plataforma.')
        created = _rows('''INSERT INTO cadu_reports_accounts
                (organization_id,client_id,platform,external_id,name,parent_account_id,account_kind)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (organization_id,client_id,platform,external_id)
                DO UPDATE SET name=EXCLUDED.name,updated_at=NOW()
                RETURNING id,platform,external_id,name,parent_account_id,account_kind,status''',
                (selected['organization_id'], selected['client_id'], platform, external_id, name, parent_id, kind))
        get_db().commit()
        return jsonify(account=created[0]), 201

    @bp.post('/api/v1/reports/campaigns')
    @login_required_api
    def reports_v1_create_campaign():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _ready():
            abort(503)
        try:
            account_id = int(payload.get('account_id'))
        except (TypeError, ValueError):
            abort(400, description='Selecione uma conta.')
        account = _rows('''SELECT id FROM cadu_reports_accounts WHERE id=%s
                AND organization_id=%s AND client_id=%s AND account_kind='advertiser' ''',
                (account_id, selected['organization_id'], selected['client_id']))
        if not account:
            abort(404, description='Conta de mídia não encontrada neste cliente.')
        external_id = _required_text(payload, 'external_id', 160)
        name = _required_text(payload, 'name', 240)
        created = _rows('''INSERT INTO cadu_reports_campaigns
                (organization_id,client_id,account_id,external_id,name)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (account_id,external_id)
                DO UPDATE SET name=EXCLUDED.name,updated_at=NOW()
                RETURNING id,account_id,external_id,name,status''',
                (selected['organization_id'], selected['client_id'], account_id, external_id, name))
        get_db().commit()
        return jsonify(campaign=created[0]), 201

    @bp.post('/api/v1/reports/workspaces')
    @login_required_api
    def reports_v1_create_workspace():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _ready():
            abort(503)
        name = _required_text(payload, 'campaign_name', 200)
        campaign_id = payload.get('media_campaign_id') or None
        account_id = None
        platform = ''
        external_account_id = ''
        external_campaign_id = ''
        if campaign_id is not None:
            try:
                campaign_id = int(campaign_id)
            except (TypeError, ValueError):
                abort(400, description='Campanha inválida.')
            matched = _rows('''SELECT c.id,c.account_id,c.external_id,a.external_id AS account_external_id,
                    a.platform FROM cadu_reports_campaigns c JOIN cadu_reports_accounts a ON a.id=c.account_id
                    WHERE c.id=%s AND c.organization_id=%s AND c.client_id=%s''',
                    (campaign_id, selected['organization_id'], selected['client_id']))
            if not matched:
                abort(404, description='Campanha não encontrada neste cliente.')
            row = matched[0]
            account_id, platform = row['account_id'], row['platform']
            external_account_id, external_campaign_id = row['account_external_id'], row['external_id']
        document = {
            'project_ref': None, 'project_name': '', 'campaign_name': name,
            'client_name': selected['client_name'], 'brand_ref': '', 'brand_name': '',
            'brand_mode': 'cobrand', 'accent': '#1767c5', 'platform': platform,
            'external_account_id': external_account_id,
            'external_campaign_id': external_campaign_id,
        }
        campaign_key = f"media:{campaign_id}" if campaign_id else f"standalone:{uuid.uuid4()}"
        created = _rows('''INSERT INTO cadu_connect_report_workspaces
                (organization_id,client_id,project_ref,campaign_name,campaign_key,document,
                 account_id,media_campaign_id,created_by,updated_by)
                VALUES (%s,%s,NULL,%s,%s,%s::jsonb,%s,%s,%s,%s) RETURNING id,revision''',
                (selected['organization_id'], selected['client_id'], name, campaign_key,
                 json.dumps(document), account_id, campaign_id, session['user_id'], session['user_id']))
        report = created[0]
        _rows('''INSERT INTO cadu_connect_report_workspace_versions
                (report_id,revision,document,note,created_by)
                VALUES (%s,%s,%s::jsonb,%s,%s) RETURNING report_id''',
                (report['id'], report['revision'], json.dumps(document),
                 'Espaço independente criado no Reports.', session['user_id']))
        get_db().commit()
        return jsonify(report=report), 201

    @bp.post('/api/v1/reports/link-tests')
    @login_required_api
    def reports_v1_test_link():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        from ..cadu_planner import link_tester
        result = link_tester.test({'url': payload.get('url'), 'mode': payload.get('mode')},
                                  selected['client_id'], session['user_id'])
        return jsonify(result=result)

    @bp.get('/api/v1/reports/ai/status')
    @login_required_api
    def reports_v1_ai_status():
        from ..services.integration_credentials import resolve_typesafe_api_key
        return jsonify(provider='typesafe', configured=bool(resolve_typesafe_api_key()))

    @bp.post('/api/v1/reports/link-tests/<run_id>/suggest-campaign')
    @login_required_api
    def reports_v1_suggest_link_campaign(run_id):
        """Suggest a campaign for a tested URL; a person confirms any association."""
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _ready():
            abort(503)
        run = _rows('''SELECT final_url,result FROM cadu_planner_link_test_runs
                WHERE id::text=%s AND client_id=%s''', (run_id, selected['client_id']))
        if not run:
            abort(404)
        parsed = urlparse(run[0]['final_url'])
        query = parse_qs(parsed.query)
        campaign_hints = {key: values[0][:160] for key, values in query.items()
                          if key.lower() in {'utm_campaign', 'utm_id', 'campaign_id'}
                          and values and '@' not in values[0]}
        hint_values = [str(value).strip().casefold() for value in campaign_hints.values() if str(value).strip()]
        for hint in hint_values:
            exact = _rows('''SELECT c.id,c.name,c.external_id,a.name AS account_name,a.platform
                FROM cadu_reports_campaigns c JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE c.organization_id=%s AND c.client_id=%s AND lower(c.external_id)=%s LIMIT 2''',
                (selected['organization_id'], selected['client_id'], hint))
            if len(exact) == 1:
                return jsonify(suggestion=exact[0], confidence=1,
                               probabilities={str(exact[0]['id']): 1},
                               model='exact_id', requires_confirmation=True, page_role=None)
        campaigns = _rows('''SELECT c.id,c.name,c.external_id,a.name AS account_name,a.platform
                FROM cadu_reports_campaigns c JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE c.organization_id=%s AND c.client_id=%s ORDER BY c.name LIMIT 500''',
                (selected['organization_id'], selected['client_id']))
        if not campaigns:
            return jsonify(suggestion=None, reason='Nenhuma campanha disponível para comparação.')
        if hint_values:
            campaigns.sort(key=lambda row: max(
                SequenceMatcher(None, hint, row['name'].casefold()).ratio()
                for hint in hint_values), reverse=True)
        campaigns = campaigns[:25]
        evidence = run[0]['result'].get('evidence', {}) if isinstance(run[0]['result'], dict) else {}
        state = {
            'destination': {'host': parsed.hostname, 'path': parsed.path[:300],
                            'campaign_hints': campaign_hints, 'title': str(evidence.get('title') or '')[:180],
                            'description': str(evidence.get('description') or '')[:300]},
            'campaigns': [{'id': row['id'], 'name': row['name'], 'external_id': row['external_id'],
                           'account_name': row['account_name'], 'platform': row['platform']} for row in campaigns],
        }
        criteria = {'none': 'Nenhuma campanha da lista tem ligação clara com o destino.'}
        criteria.update({str(row['id']): f"{row['platform']} · {row['account_name']} · {row['name']} · ID {row['external_id']}"
                         for row in campaigns})
        from ..services.typesafe_service import TypeSafeError, system_one
        try:
            evaluation = system_one(state, {'campaign': {
                'type': 'choice',
                'instructions': 'Qual campanha listada é mais provavelmente a origem do destino? Use apenas sinais presentes em destination e campaigns. Escolha none quando não houver evidência suficiente.',
                'criteria': criteria,
            }, 'page_role': {
                'type': 'choice',
                'instructions': 'Qual é o papel mais provável da página de destino no funil? Considere somente o host, caminho, título e descrição disponíveis; use unknown quando os sinais forem insuficientes.',
                'criteria': {
                    'landing': 'Página de entrada de campanha que apresenta uma oferta ou proposta.',
                    'form': 'Página cujo objetivo aparente é iniciar ou preencher um formulário.',
                    'thank_you': 'Página exibida após o envio ou compra, confirmando uma ação concluída.',
                    'content': 'Conteúdo informativo ou institucional sem etapa de conversão clara.',
                    'unknown': 'Não há sinais suficientes para classificar a função da página.'
                },
            }})
            answer = evaluation['answers'].get('campaign')
            role_answer = evaluation['answers'].get('page_role')
            if not isinstance(answer, dict) or answer.get('type') != 'choice' or \
                    answer.get('choice') not in criteria or not isinstance(answer.get('probabilities'), dict):
                raise TypeSafeError('A resposta TypeSafe de campanha veio incompleta.')
            if not isinstance(role_answer, dict) or role_answer.get('type') != 'choice' or \
                    role_answer.get('choice') not in {'landing', 'form', 'thank_you', 'content', 'unknown'}:
                raise TypeSafeError('A resposta TypeSafe da página veio incompleta.')
        except TypeSafeError as exc:
            return jsonify(suggestion=None, error=str(exc)), 503
        choice = str(answer.get('choice') or 'none')
        candidate = next((row for row in campaigns if str(row['id']) == choice), None)
        return jsonify(suggestion=candidate, confidence=answer.get('confidence'),
                       probabilities=answer.get('probabilities'), page_role=role_answer.get('choice'),
                       page_role_confidence=role_answer.get('confidence'),
                       model=evaluation.get('model'), requires_confirmation=True)
