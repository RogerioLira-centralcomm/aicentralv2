"""Manual report workspace. AI ingestion and public publication are separate stages."""
import json
import re
import secrets
import uuid
from datetime import date
from flask import abort, flash, redirect, render_template, request, session, url_for
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
    project_ref = form.get('project_ref') or None
    project = next((e for e in entities if e['ref'] == project_ref and e['kind'] == 'project'), None)
    if project_ref and not project:
        raise ValueError('Selecione um projeto autorizado.')
    name = (form.get('campaign_name') or '').strip()
    if not name or len(name) > 200:
        raise ValueError('Informe o nome da campanha com até 200 caracteres.')
    brand_ref = form.get('brand_ref') or ''
    brand = next((e for e in entities if e['ref'] == brand_ref and e['kind'] == 'brand'), None)
    if brand_ref and (not brand or (project and brand_ref not in project.get('related_refs', []))):
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
    document = dict(project_ref=project['ref'] if project else None, project_name=project['name'] if project else '',
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
    @bp.get('/importacoes')
    @login_required
    def report_imports():
        from .reports_access import resolve as resolve_reports
        selected = resolve_reports()
        if not available() or not source_storage_ready(rows):
            return render_template('cadu_connect/imports.html', selected=selected, imports=[], ready=False)
        imports = rows('''SELECT s.id,s.original_name,s.supplier,s.period_start,s.period_end,s.status,s.created_at,
            w.id AS report_id,w.campaign_name,w.document FROM cadu_connect_report_sources s
            JOIN cadu_connect_report_workspaces w ON w.id=s.report_id
            WHERE w.organization_id=%s AND w.client_id=%s ORDER BY s.created_at DESC''',
            (selected['organization_id'], selected['client_id']))
        inbox = rows('''SELECT id,original_name,supplier,period_start,period_end,status,created_at,report_id,
            NULL::text AS campaign_name,NULL::jsonb AS document FROM cadu_connect_report_imports
            WHERE organization_id=%s AND client_id=%s ORDER BY created_at DESC''',
            (selected['organization_id'], selected['client_id']))
        imports.extend(inbox)
        imports.sort(key=lambda item: item['created_at'], reverse=True)
        from .import_recognition import recognize_platform
        for item in imports:
            item.update(recognize_platform(item.get('supplier'), item.get('original_name')))
        return render_template('cadu_connect/imports.html', selected=selected, imports=imports, ready=True)
    @bp.post('/importacoes')
    @login_required
    def receive_import():
        from .reports_access import resolve as resolve_reports
        selected = resolve_reports()
        if selected['role'] == 'viewer' or not secrets.compare_digest(session.get('family_csrf', ''), request.form.get('_csrf', '')):
            abort(403)
        if not rows("SELECT to_regclass('public.cadu_connect_report_imports') IS NOT NULL AS ready")[0]['ready']:
            abort(503)
        try:
            from .import_inbox import validate_inbox_upload
            item = validate_inbox_upload(request.files.get('print'), request.form) if request.files.get('print') else None
            if not item: raise ValueError('Escolha um print PNG, JPEG ou WebP.')
            inserted = rows('''INSERT INTO cadu_connect_report_imports
                (organization_id,client_id,original_name,sha256,image_bytes,mime_type,supplier,period_start,period_end,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,client_id,sha256) DO NOTHING RETURNING id''',
                (selected['organization_id'],selected['client_id'],item['original_name'],item['sha256'],item['image_bytes'],item['mime_type'],item['supplier'],item['period_start'],item['period_end'],session['user_id']))
            get_db().commit()
            flash('Importação recebida. Associe a campanha antes de revisar os dados.' if inserted else 'Este arquivo já está na caixa de entrada.', 'report_import')
        except ValueError as exc:
            get_db().rollback(); flash(str(exc), 'report_import_error')
        return redirect(url_for('cadu_connect.report_imports'))
    @bp.route('/importacoes/<int:import_id>/resolver', methods=['GET', 'POST'])
    @login_required
    def resolve_import(import_id):
        from .reports_access import resolve as resolve_reports
        selected = resolve_reports()
        found = rows('''SELECT * FROM cadu_connect_report_imports WHERE id=%s AND organization_id=%s AND client_id=%s''',
                     (import_id, selected['organization_id'], selected['client_id']))
        if not found: abort(404)
        item = found[0]
        reports = rows('''SELECT id,campaign_name,document,revision FROM cadu_connect_report_workspaces
            WHERE organization_id=%s AND client_id=%s ORDER BY updated_at DESC''', (selected['organization_id'], selected['client_id']))
        if request.method == 'POST':
            if selected['role'] == 'viewer' or not secrets.compare_digest(session.get('family_csrf', ''), request.form.get('_csrf', '')): abort(403)
            report_id = request.form.get('report_id', type=int)
            report = next((row for row in reports if row['id'] == report_id), None)
            if not report: abort(400, description='Selecione uma campanha disponível.')
            inserted = rows('''INSERT INTO cadu_connect_report_sources
                (report_id,batch_id,original_name,sha256,image_bytes,mime_type,supplier,period_start,period_end,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (report_id,sha256) DO NOTHING RETURNING id''',
                (report_id,str(uuid.uuid4()),item['original_name'],item['sha256'],item['image_bytes'],item['mime_type'],item['supplier'],item['period_start'],item['period_end'],session['user_id']))
            if inserted:
                revision = report['revision'] + 1
                with get_db().cursor() as cur:
                    cur.execute("UPDATE cadu_connect_report_imports SET status='matched',report_id=%s WHERE id=%s",(report_id,import_id))
                    cur.execute('''UPDATE cadu_connect_report_workspaces SET revision=%s,updated_by=%s,updated_at=NOW() WHERE id=%s''',
                                (revision,session['user_id'],report_id))
                    cur.execute('''INSERT INTO cadu_connect_report_workspace_versions
                        (report_id,revision,document,note,created_by) VALUES (%s,%s,%s::jsonb,%s,%s)''',
                                (report_id,revision,json.dumps(report['document']),f'Importação #{import_id} associada. Aguardando revisão dos dados.',session['user_id']))
                get_db().commit()
                return redirect(url_for('cadu_connect.report_review_source',report_id=report_id,source_id=inserted[0]['id']))
            get_db().rollback(); flash('Esta fonte já existe na campanha escolhida.', 'report_import_error')
        return render_template('cadu_connect/resolve_import.html', selected=selected, item=item, reports=reports)
    @bp.route('/relatorios', methods=['GET', 'POST'])
    @login_required
    def report_library():
        from .reports_access import inventory as reports_inventory, reports_only, resolve as resolve_reports
        selected = resolve_reports()
        entities = reports_inventory(selected['client_id'])
        if reports_only():
            existing_id = (request.form.get('report_id') if request.method == 'POST'
                           else request.args.get('report_id'))
            if existing_id:
                try:
                    existing_id = int(existing_id)
                except (TypeError, ValueError):
                    abort(400, description='Relatório inválido.')
                existing = rows('''SELECT document FROM cadu_connect_report_workspaces
                    WHERE id=%s AND organization_id=%s AND client_id=%s''',
                    (existing_id, selected['organization_id'], selected['client_id']))
                if not existing:
                    abort(404)
                stored = existing[0]['document'] or {}
                project_ref, brand_ref = stored.get('project_ref'), stored.get('brand_ref')
                if project_ref:
                    entities.append({'kind': 'project', 'ref': project_ref,
                                     'name': stored.get('project_name') or 'Projeto do relatório',
                                     'related_refs': [brand_ref] if brand_ref else []})
                if brand_ref:
                    entities.append({'kind': 'brand', 'ref': brand_ref,
                                     'name': stored.get('brand_name') or 'Marca do relatório'})
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
        if not reports_only():
            reports = [r for r in reports if not r['project_ref'] or r['project_ref'] in project_refs]
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
