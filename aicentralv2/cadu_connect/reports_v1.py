"""Reports V1 media inventory and Link Tester API, scoped to one authorized client."""
import json
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlparse
from flask import abort, jsonify, render_template, request, session

from ..auth import login_required, login_required_api
from ..db import get_db
from . import reports_access
from .report_rules import planned_phase


def _rows(sql, params=()):
    with get_db().cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def _ready():
    return bool(_rows("SELECT to_regclass('public.cadu_reports_accounts') IS NOT NULL "
                      "AND to_regclass('public.cadu_reports_campaigns') IS NOT NULL AS ready")[0]['ready'])


def _selection(payload=None):
    supplied = (payload or {}).get('client_id') if payload is not None else request.args.get('client_id')
    return reports_access.resolve(supplied)


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


def _optional_positive_id(value, field):
    if value in (None, ''):
        return None
    if isinstance(value, bool) or isinstance(value, (list, dict, float)):
        abort(400, description=f'{field} inválido.')
    try:
        number = int(value)
    except (TypeError, ValueError):
        abort(400, description=f'{field} inválido.')
    if number < 1:
        abort(400, description=f'{field} inválido.')
    return number


def register(bp):
    @bp.get('/app')
    @login_required
    def reports_v1_app():
        selected = reports_access.resolve(request.args.get('client_id'))
        if request.args.get('client_id'):
            session['cliente_id'] = selected['client_id']
        return render_template('cadu_connect/app_v1.html')

    @bp.get('/api/v1/reports/bootstrap')
    @login_required_api
    def reports_v1_bootstrap():
        selected = _selection()
        session.setdefault('family_csrf', secrets.token_urlsafe(32))
        clients = [{'id': int(item['id']), 'name': item['name']} for item in reports_access.authorized_clients()]
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
        link_tests = _rows('''SELECT r.id,r.mode,r.original_url,r.final_url,r.score,r.status_label,
                r.created_at,r.account_id,r.media_campaign_id,r.report_workspace_id,
                r.association_updated_at,c.name AS campaign_name,w.campaign_name AS report_name
                FROM cadu_planner_link_test_runs r
                LEFT JOIN cadu_reports_campaigns c ON c.id=r.media_campaign_id
                    AND c.organization_id=%s AND c.client_id=%s
                LEFT JOIN cadu_connect_report_workspaces w ON w.id=r.report_workspace_id
                    AND w.organization_id=%s AND w.client_id=%s
                WHERE r.client_id=%s ORDER BY r.created_at DESC LIMIT 20''',
                (*params, *params, selected['client_id']))
        return jsonify(ready=True, client=selected, clients=clients, csrf=session['family_csrf'],
                       can_manage_access=selected['role'] == 'admin' and
                           session.get('user_type') in ('admin', 'superadmin') and not reports_access.reports_only(),
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

    @bp.get('/api/v1/reports/workspaces/<int:report_id>')
    @login_required_api
    def reports_v1_workspace_detail(report_id):
        selected = _selection()
        params = (report_id, selected['organization_id'], selected['client_id'])
        found = _rows('''SELECT id,campaign_name,project_ref,account_id,media_campaign_id,
            document,revision,created_at,updated_at FROM cadu_connect_report_workspaces
            WHERE id=%s AND organization_id=%s AND client_id=%s''', params)
        if not found:
            abort(404)
        versions = _rows('''SELECT revision,note,created_by,created_at
            FROM cadu_connect_report_workspace_versions WHERE report_id=%s
            ORDER BY revision DESC LIMIT 30''', (report_id,))
        sources = _rows('''SELECT id,original_name,supplier,period_start,period_end,status,created_at
            FROM cadu_connect_report_sources WHERE report_id=%s
            ORDER BY created_at DESC LIMIT 100''', (report_id,))
        published = _rows('''SELECT token,expires_at,created_at
            FROM cadu_connect_report_public_links
            WHERE report_id=%s AND revoked_at IS NULL
                AND (expires_at IS NULL OR expires_at > NOW())''', (report_id,))
        return jsonify(report=found[0], versions=versions, sources=sources,
                       public_link=published[0] if published else None)

    @bp.post('/api/v1/reports/workspaces/<int:report_id>/document')
    @login_required_api
    def reports_v1_update_workspace_document(report_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get('document'), dict):
            abort(400, description='Envie os campos do relatório.')
        selected = _selection(payload)
        _write_guard(selected)
        revision = _optional_positive_id(payload.get('revision'), 'Versão')
        if revision is None:
            abort(400, description='Informe a versão atual.')
        note = _required_text(payload, 'update_note', 2000)
        found = _rows('''SELECT id,document,revision FROM cadu_connect_report_workspaces
            WHERE id=%s AND organization_id=%s AND client_id=%s FOR UPDATE''',
            (report_id, selected['organization_id'], selected['client_id']))
        if not found:
            abort(404)
        current = found[0]
        if current['revision'] != revision:
            abort(409, description='Este relatório mudou. Reabra a versão mais recente.')
        changes = payload['document']
        allowed = {'objective': 2000, 'goals': 4000, 'management_notes': 8000,
                   'start_date': 10, 'end_date': 10, 'accent': 7}
        if not changes or set(changes) - set(allowed):
            abort(400, description='Envie apenas os campos editáveis do contexto.')
        document = dict(current['document'] or {})
        for field, value in changes.items():
            if not isinstance(value, str) or len(value) > allowed[field]:
                abort(400, description=f'{field} inválido.')
            document[field] = value.strip()
        if 'accent' in changes and not re.fullmatch(r'#[0-9a-fA-F]{6}', document['accent']):
            abort(400, description='Cor inválida.')
        dates = {}
        for field in ('start_date', 'end_date'):
            try:
                dates[field] = date.fromisoformat(document.get(field) or '') if document.get(field) else None
            except ValueError:
                abort(400, description='Informe datas válidas.')
        try:
            planned_phase(dates['start_date'], dates['end_date'], today=date.today())
        except ValueError as exc:
            abort(400, description=str(exc))
        if document == current['document']:
            get_db().rollback()
            return jsonify(unchanged=True, revision=revision)
        next_revision = revision + 1
        _rows('''UPDATE cadu_connect_report_workspaces SET document=%s::jsonb,
            revision=%s,updated_by=%s,updated_at=NOW() WHERE id=%s RETURNING id''',
            (json.dumps(document), next_revision, session['user_id'], report_id))
        _rows('''INSERT INTO cadu_connect_report_workspace_versions
            (report_id,revision,document,note,created_by)
            VALUES (%s,%s,%s::jsonb,%s,%s) RETURNING report_id''',
            (report_id, next_revision, json.dumps(document), note, session['user_id']))
        get_db().commit()
        return jsonify(unchanged=False, revision=next_revision)

    @bp.post('/api/v1/reports/workspaces/<int:report_id>/publish')
    @login_required_api
    def reports_v1_publish_workspace(report_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        try:
            days = int(payload.get('expires_days', 30))
        except (TypeError, ValueError):
            abort(400, description='Prazo inválido.')
        if days not in (0, 7, 30, 90):
            abort(400, description='Prazo inválido.')
        if not _rows('''SELECT id FROM cadu_connect_report_workspaces
            WHERE id=%s AND organization_id=%s AND client_id=%s''',
            (report_id, selected['organization_id'], selected['client_id'])):
            abort(404)
        token = secrets.token_urlsafe(32)
        expires = None if days == 0 else datetime.now(timezone.utc) + timedelta(days=days)
        _rows('''INSERT INTO cadu_connect_report_public_links
            (report_id,token,expires_at,created_by,revoked_at)
            VALUES (%s,%s,%s,%s,NULL)
            ON CONFLICT (report_id) DO UPDATE SET token=EXCLUDED.token,
                expires_at=EXCLUDED.expires_at,created_by=EXCLUDED.created_by,revoked_at=NULL
            RETURNING report_id''', (report_id, token, expires, session['user_id']))
        get_db().commit()
        return jsonify(public_url=f'/connect/r/{token}', expires_at=expires)

    @bp.post('/api/v1/reports/workspaces/<int:report_id>/unpublish')
    @login_required_api
    def reports_v1_unpublish_workspace(report_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _rows('''SELECT id FROM cadu_connect_report_workspaces
            WHERE id=%s AND organization_id=%s AND client_id=%s''',
            (report_id, selected['organization_id'], selected['client_id'])):
            abort(404)
        _rows('''UPDATE cadu_connect_report_public_links SET revoked_at=NOW()
            WHERE report_id=%s AND revoked_at IS NULL RETURNING id''', (report_id,))
        get_db().commit()
        return jsonify(revoked=True)

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
        run = _rows('''SELECT original_url,final_url,result FROM cadu_planner_link_test_runs
                WHERE id::text=%s AND client_id=%s''', (run_id, selected['client_id']))
        if not run:
            abort(404)
        parsed = urlparse(run[0]['final_url'])
        original = urlparse(run[0]['original_url'])
        campaign_hints = {}
        for source, url in (('original', original), ('final', parsed)):
            query = parse_qs(url.query)
            campaign_hints[source] = {key.lower(): values[0][:160] for key, values in query.items()
                                      if key.lower() in {'utm_campaign', 'utm_id', 'campaign_id'}
                                      and values and '@' not in values[0]}
        id_hints = list(dict.fromkeys(str(source_hints[key]).strip().casefold()
                        for source_hints in campaign_hints.values() for key in ('utm_id', 'campaign_id')
                        if source_hints.get(key) and str(source_hints[key]).strip()))
        name_hints = list(dict.fromkeys(str(source_hints['utm_campaign']).strip().casefold()
                          for source_hints in campaign_hints.values()
                          if source_hints.get('utm_campaign') and str(source_hints['utm_campaign']).strip()))
        hint_values = list(dict.fromkeys(id_hints + name_hints))
        for hint in id_hints:
            exact = _rows('''SELECT c.id,c.name,c.external_id,a.name AS account_name,a.platform
                FROM cadu_reports_campaigns c JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE c.organization_id=%s AND c.client_id=%s AND lower(c.external_id)=%s LIMIT 2''',
                (selected['organization_id'], selected['client_id'], hint))
            if len(exact) == 1:
                return jsonify(suggestion=exact[0], confidence=1,
                               probabilities={str(exact[0]['id']): 1},
                               model='exact_id', requires_confirmation=True, page_role=None)
        for hint in name_hints:
            exact = _rows('''SELECT c.id,c.name,c.external_id,a.name AS account_name,a.platform
                FROM cadu_reports_campaigns c JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE c.organization_id=%s AND c.client_id=%s AND lower(c.name)=%s LIMIT 2''',
                (selected['organization_id'], selected['client_id'], hint))
            if len(exact) == 1:
                return jsonify(suggestion=exact[0], confidence=1,
                               probabilities={str(exact[0]['id']): 1},
                               model='exact_name', requires_confirmation=True, page_role=None)
        compact_hints = list(dict.fromkeys(re.sub(r'[^a-z0-9]', '', hint) for hint in hint_values))
        compact_hints = [hint for hint in compact_hints if len(hint) >= 4]
        campaigns = []
        if compact_hints:
            campaigns = _rows('''SELECT c.id,c.name,c.external_id,a.name AS account_name,a.platform
                FROM cadu_reports_campaigns c JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE c.organization_id=%s AND c.client_id=%s
                  AND regexp_replace(lower(c.name),'[^a-z0-9]','','g') LIKE ANY(%s)
                ORDER BY c.name,c.id LIMIT 26''',
                (selected['organization_id'], selected['client_id'],
                 ['%' + hint + '%' for hint in compact_hints]))
        too_many = len(campaigns) > 25
        if too_many:
            campaigns = []
        elif campaigns:
            campaigns.sort(key=lambda row: max(
                SequenceMatcher(None, hint, row['name'].casefold()).ratio()
                for hint in hint_values), reverse=True)
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
        questions = {'page_role': {
            'type': 'choice',
            'instructions': 'Qual é o papel mais provável da página de destino no funil? Considere somente o host, caminho, título e descrição disponíveis; use unknown quando os sinais forem insuficientes.',
            'criteria': {
                'landing': 'Página de entrada de campanha que apresenta uma oferta ou proposta.',
                'form': 'Página cujo objetivo aparente é iniciar ou preencher um formulário.',
                'thank_you': 'Página exibida após o envio ou compra, confirmando uma ação concluída.',
                'content': 'Conteúdo informativo ou institucional sem etapa de conversão clara.',
                'unknown': 'Não há sinais suficientes para classificar a função da página.'
            },
        }}
        if campaigns:
            questions['campaign'] = {
                'type': 'choice',
                'instructions': 'Qual campanha listada é mais provavelmente a origem do destino? Use apenas sinais presentes em destination e campaigns. Escolha none quando não houver evidência suficiente.',
                'criteria': criteria,
            }
        from ..services.typesafe_service import TypeSafeError, system_one
        try:
            evaluation = system_one(state, questions)
            answer = evaluation['answers'].get('campaign')
            role_answer = evaluation['answers'].get('page_role')
            if campaigns and (not isinstance(answer, dict) or answer.get('type') != 'choice' or
                              answer.get('choice') not in criteria or not isinstance(answer.get('probabilities'), dict)):
                raise TypeSafeError('A resposta TypeSafe de campanha veio incompleta.')
            if not isinstance(role_answer, dict) or role_answer.get('type') != 'choice' or \
                    role_answer.get('choice') not in {'landing', 'form', 'thank_you', 'content', 'unknown'}:
                raise TypeSafeError('A resposta TypeSafe da página veio incompleta.')
        except TypeSafeError as exc:
            return jsonify(suggestion=None, error=str(exc)), 503
        choice = str(answer.get('choice') or 'none') if campaigns else 'none'
        candidate = next((row for row in campaigns if str(row['id']) == choice), None)
        reason = ('Há muitas campanhas compatíveis; refine o UTM para sugerir uma campanha.' if too_many
                  else 'Sem uma campanha identificável no link.' if not campaigns else None)
        return jsonify(suggestion=candidate, reason=reason,
                       confidence=answer.get('confidence') if campaigns else None,
                       probabilities=answer.get('probabilities') if campaigns else {}, page_role=role_answer.get('choice'),
                       page_role_confidence=role_answer.get('confidence'),
                       model=evaluation.get('model'), requires_confirmation=True)

    @bp.post('/api/v1/reports/link-tests/<run_id>/association')
    @login_required_api
    def reports_v1_associate_link(run_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, description='Envie uma decisão de associação.')
        selected = _selection(payload)
        _write_guard(selected)
        if not _ready():
            abort(503)
        if 'campaign_id' not in payload:
            abort(400, description='Escolha uma campanha ou limpe a associação explicitamente.')
        try:
            run_uuid = str(uuid.UUID(run_id))
        except ValueError:
            abort(400, description='Teste de link inválido.')
        campaign_id = _optional_positive_id(payload.get('campaign_id'), 'Campanha')
        report_id = _optional_positive_id(payload.get('report_id'), 'Relatório')
        if not campaign_id and report_id:
            abort(400, description='Escolha uma campanha antes de associar um relatório.')
        params = (selected['organization_id'], selected['client_id'])
        run = _rows('''SELECT id,account_id,media_campaign_id,report_workspace_id
            FROM cadu_planner_link_test_runs WHERE id=%s AND client_id=%s FOR UPDATE''',
            (run_uuid, selected['client_id']))
        if not run:
            abort(404)
        account_id = None
        if campaign_id:
            campaign = _rows('''SELECT id,account_id FROM cadu_reports_campaigns
                WHERE id=%s AND organization_id=%s AND client_id=%s''', (campaign_id, *params))
            if not campaign:
                abort(404, description='Campanha fora deste cliente.')
            account_id = campaign[0]['account_id']
        if report_id:
            report = _rows('''SELECT id,account_id,media_campaign_id
                FROM cadu_connect_report_workspaces
                WHERE id=%s AND organization_id=%s AND client_id=%s''', (report_id, *params))
            if not report:
                abort(404, description='Relatório fora deste cliente.')
            if (report[0]['account_id'] and report[0]['account_id'] != account_id) or \
                    (report[0]['media_campaign_id'] and report[0]['media_campaign_id'] != campaign_id):
                abort(400, description='O relatório está vinculado a outra conta ou campanha.')
        previous = run[0]
        if (previous['account_id'], previous['media_campaign_id'], previous['report_workspace_id']) == \
                (account_id, campaign_id, report_id):
            get_db().rollback()
            return jsonify(unchanged=True, account_id=account_id,
                           campaign_id=campaign_id, report_id=report_id)
        _rows('''UPDATE cadu_planner_link_test_runs
            SET account_id=%s,media_campaign_id=%s,report_workspace_id=%s,
                association_updated_at=NOW() WHERE id=%s RETURNING id''',
            (account_id, campaign_id, report_id, run_uuid))
        _rows('''INSERT INTO cadu_reports_link_association_history
            (run_id,organization_id,client_id,previous_account_id,previous_campaign_id,
             previous_report_id,account_id,campaign_id,report_id,action,decided_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (run_uuid, *params, previous['account_id'], previous['media_campaign_id'],
             previous['report_workspace_id'], account_id, campaign_id, report_id,
             'associate' if campaign_id else 'clear', session['user_id']))
        get_db().commit()
        return jsonify(unchanged=False, account_id=account_id,
                       campaign_id=campaign_id, report_id=report_id)

    @bp.get('/api/v1/reports/link-tests/<run_id>/association-history')
    @login_required_api
    def reports_v1_link_association_history(run_id):
        selected = _selection()
        try:
            run_uuid = str(uuid.UUID(run_id))
        except ValueError:
            abort(400, description='Teste de link inválido.')
        if not _rows('SELECT id FROM cadu_planner_link_test_runs WHERE id=%s AND client_id=%s',
                     (run_uuid, selected['client_id'])):
            abort(404)
        history = _rows('''SELECT action,previous_campaign_id,previous_report_id,campaign_id,
            report_id,decided_by,decided_at FROM cadu_reports_link_association_history
            WHERE run_id=%s AND organization_id=%s AND client_id=%s
            ORDER BY decided_at DESC,id DESC LIMIT 50''',
            (run_uuid, selected['organization_id'], selected['client_id']))
        return jsonify(history=history)
