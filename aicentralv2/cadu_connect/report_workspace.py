"""Manual report workspace. AI ingestion and public publication are separate stages."""
import json
import re
import secrets
from datetime import date
from flask import abort, redirect, render_template, request, session, url_for
from ..auth import login_required
from ..cadu_family import context
from ..db import get_db
from .report_rules import planned_phase


def rows(sql, args=()):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return [dict(row) for row in cur.fetchall()]


def available():
    result = rows("SELECT to_regclass('public.cadu_connect_report_workspaces') IS NOT NULL AND to_regclass('public.cadu_connect_report_workspace_versions') IS NOT NULL AS ready")
    return result[0]['ready']


def validate_document(form, entities):
    project = next((e for e in entities if e['ref'] == form.get('project_ref') and e['kind'] == 'project'), None)
    if not project:
        raise ValueError('Selecione um projeto autorizado.')
    name = (form.get('campaign_name') or '').strip()
    if not name or len(name) > 200:
        raise ValueError('Informe o nome da campanha com até 200 caracteres.')
    brand_ref = form.get('brand_ref') or ''
    brand = next((e for e in entities if e['ref'] == brand_ref and e['kind'] == 'brand'), None)
    if brand_ref and (not brand or brand_ref not in project.get('related_refs', [])):
        raise ValueError('A marca precisa estar vinculada ao projeto no Workspace.')
    dates = {}
    for field in ('start_date', 'end_date'):
        raw = form.get(field) or ''
        try:
            dates[field] = date.fromisoformat(raw) if raw else None
        except ValueError:
            raise ValueError('Informe datas válidas.')
    planned_phase(dates['start_date'], dates['end_date'], today=date.today())
    accent = form.get('accent') or '#1363c5'
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        raise ValueError('Cor inválida.')
    mode = form.get('brand_mode', 'cobrand')
    if mode not in ('cobrand', 'project'):
        raise ValueError('Identidade inválida.')
    document = dict(project_ref=project['ref'], project_name=project['name'],
                    campaign_name=name, brand_ref=brand_ref,
                    brand_name=brand['name'] if brand else '', accent=accent, brand_mode=mode)
    for field, limit in (('objective', 2000), ('goals', 4000), ('management_notes', 8000),
                         ('platform', 100), ('external_account_id', 200), ('external_campaign_id', 200)):
        value = (form.get(field) or '').strip()
        if len(value) > limit:
            raise ValueError('O campo excede o limite permitido.')
        document[field] = value
    document.update({key: value.isoformat() if value else '' for key, value in dates.items()})
    return document


def register(bp):
    from .report_sources import register as register_sources, source_storage_ready
    register_sources(bp, rows)
    from .report_review import register as register_reviews
    register_reviews(bp, rows)
    from .report_public import register as register_public
    register_public(bp, rows)
    @bp.route('/relatorios', methods=['GET', 'POST'])
    @login_required
    def report_library():
        selected = context.resolve()
        entities = context.inventory(selected['client_id'])
        session.setdefault('family_csrf', secrets.token_urlsafe(32))
        ready = available()
        error = None
        if request.method == 'POST':
            if selected['role'] == 'viewer':
                abort(403)
            if not secrets.compare_digest(session['family_csrf'], request.form.get('_csrf', '')):
                abort(403)
            if not ready:
                abort(503, description='O armazenamento de relatórios ainda não foi instalado.')
            try:
                document = validate_document(request.form, entities)
                document['client_name'] = selected['client_name']
                org, client = selected['organization_id'], selected['client_id']
                user = session['user_id']
                report_id = request.form.get('report_id')
                conn = get_db()
                if report_id:
                    revision = int(request.form.get('revision', '0'))
                    current = rows('''SELECT * FROM cadu_connect_report_workspaces
                        WHERE id=%s AND organization_id=%s AND client_id=%s FOR UPDATE''', (int(report_id), org, client))
                    if not current:
                        abort(404)
                    current = current[0]
                    if current['project_ref'] != document['project_ref']:
                        raise ValueError('O projeto de um relatório existente não pode ser trocado aqui.')
                    if current['campaign_name'] != document['campaign_name']:
                        raise ValueError('Preserve a campanha existente ao atualizar este relatório.')
                    if current['revision'] != revision:
                        raise ValueError('Este relatório mudou. Reabra a versão mais recente antes de salvar.')
                    if current['document'] == document:
                        conn.rollback()
                        return redirect(url_for('cadu_connect.report_library', report_id=report_id))
                    note = (request.form.get('update_note') or '').strip()
                    if not note or len(note) > 2000:
                        raise ValueError('Descreva o que mudou, com até 2000 caracteres.')
                    revision += 1
                    with conn.cursor() as cur:
                        cur.execute('''UPDATE cadu_connect_report_workspaces SET document=%s::jsonb,
                            revision=%s, updated_by=%s, updated_at=NOW() WHERE id=%s''',
                                    (json.dumps(document), revision, user, int(report_id)))
                else:
                    # Same name is a candidate, never an automatic merge.
                    key = ' '.join(document['campaign_name'].casefold().split())
                    created = rows('''INSERT INTO cadu_connect_report_workspaces
                        (organization_id,client_id,project_ref,campaign_name,campaign_key,document,created_by,updated_by)
                        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                        ON CONFLICT (organization_id,client_id,project_ref,campaign_key) DO NOTHING RETURNING id''',
                        (org, client, document['project_ref'], document['campaign_name'], key, json.dumps(document), user, user))
                    if not created:
                        raise ValueError('Já existe uma campanha com esse nome neste projeto. Abra o relatório na biblioteca para atualizar; se forem campanhas distintas, diferencie os nomes.')
                    report_id, revision, note = created[0]['id'], 1, 'Campanha e identidade cadastradas.'
                with conn.cursor() as cur:
                    cur.execute('''INSERT INTO cadu_connect_report_workspace_versions
                        (report_id,revision,document,note,created_by) VALUES (%s,%s,%s::jsonb,%s,%s)''',
                        (int(report_id), revision, json.dumps(document), note, user))
                conn.commit()
                return redirect(url_for('cadu_connect.report_library', report_id=report_id, saved=1))
            except ValueError as exc:
                get_db().rollback()
                error = str(exc)
            except Exception:
                get_db().rollback()
                raise
        reports = rows('''SELECT id,campaign_name,project_ref,revision,updated_at,document
            FROM cadu_connect_report_workspaces WHERE organization_id=%s AND client_id=%s
            ORDER BY updated_at DESC''', (selected['organization_id'], selected['client_id'])) if ready else []
        project_refs = {e['ref'] for e in entities if e['kind'] == 'project'}
        reports = [r for r in reports if r['project_ref'] in project_refs]
        report_id = request.args.get('report_id', type=int)
        report = next((r for r in reports if r['id'] == report_id), None)
        if report_id and not report:
            abort(404)
        history = rows('''SELECT revision,note,created_at FROM cadu_connect_report_workspace_versions
            WHERE report_id=%s ORDER BY revision DESC''', (report_id,)) if report else []
        document = report['document'] if report else {}
        sources_ready = source_storage_ready(rows) if report else False
        sources = rows('''SELECT id,original_name,supplier,period_start,period_end,status,
            width,height,created_at FROM cadu_connect_report_sources
            WHERE report_id=%s ORDER BY created_at DESC,id DESC''', (report_id,)) if sources_ready else []
        public_link = None
        if report and rows("SELECT to_regclass('public.cadu_connect_report_public_links') IS NOT NULL AS ready")[0]['ready']:
            found_link = rows('''SELECT token,expires_at FROM cadu_connect_report_public_links
                WHERE report_id=%s AND revoked_at IS NULL''', (report_id,))
            public_link = found_link[0] if found_link else None
        if error:
            document = {**document, **{k: request.form.get(k, '') for k in (
                'campaign_name','project_ref','brand_ref','brand_mode','accent','start_date','end_date',
                'objective','goals','management_notes','platform','external_account_id','external_campaign_id')}}
        return render_template('cadu_connect/reports.html', selected=selected, entities=entities,
            reports=reports, report=report, document=document, history=history, ready=ready, error=error,
            sources=sources, sources_ready=sources_ready, public_link=public_link)
