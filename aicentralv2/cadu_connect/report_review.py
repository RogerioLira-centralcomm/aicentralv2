"""Human-reviewed, source-bound metrics with immutable revision history."""
import json
import re
import secrets

from flask import abort, jsonify, redirect, render_template, request, session, url_for
from ..auth import login_required
from ..db import get_db
from .report_rules import decimal_value, metric_change
from .report_sources import authorized_report

UNITS = ('count', 'BRL', 'USD', 'percent', 'seconds')


def parse_metrics(form):
    names = form.getlist('metric_name')
    fields = ('metric_value', 'metric_unit', 'metric_definition', 'metric_scope', 'metric_evidence')
    values = {field: form.getlist(field) for field in fields}
    if not 1 <= len(names) <= 60 or any(len(column) != len(names) for column in values.values()):
        raise ValueError('Informe de 1 a 60 indicadores, com todos os campos de cada linha.')
    metrics, keys = [], set()
    for i, name in enumerate(names):
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError('Cada indicador precisa de um nome de até 120 caracteres.')
        unit = values['metric_unit'][i]
        if unit not in UNITS:
            raise ValueError('Unidade inválida.')
        raw = values['metric_value'][i].strip()
        # Explicit pt-BR input convention; no guessing thousands or decimal units.
        if raw and not re.fullmatch(r'-?\d{1,15}(,\d{1,6})?', raw):
            raise ValueError('Use números sem separador de milhar, com vírgula decimal: 12450,80. Deixe vazio quando desconhecido.')
        number = decimal_value(raw.replace(',', '.')) if raw else None
        details = {}
        for field in ('metric_definition', 'metric_scope', 'metric_evidence'):
            value = values[field][i].strip()
            if not value or len(value) > 1000:
                raise ValueError('Preencha definição, escopo e evidência de cada indicador (até 1000 caracteres).')
            details[field.removeprefix('metric_')] = value
        key = (name.casefold(), unit, details['definition'].casefold(), details['scope'].casefold())
        if key in keys:
            raise ValueError('Há indicadores repetidos com a mesma definição, unidade e escopo.')
        keys.add(key)
        metrics.append(dict(name=name, value=str(number) if number is not None else None,
                            raw=raw, unit=unit, **details))
    return metrics


def compare_metrics(before, after):
    """Only compares revisions of the SAME source; no cross-period inference."""
    def key(row):
        return tuple(row[k].casefold() for k in ('name', 'unit', 'definition', 'scope'))
    previous = {key(row): row for row in before}
    current = {key(row): row for row in after}
    result = []
    for identity, row in current.items():
        old = previous.get(identity)
        change = metric_change(old['value'], row['value'], comparable=True,
                               percentage_points=row['unit'] == 'percent') if old else {'status': 'added', 'difference': None, 'relative_percent': None}
        result.append(dict(name=row['name'], before=old['value'] if old else None,
                           after=row['value'], unit=row['unit'], **change))
    for identity, row in previous.items():
        if identity not in current:
            result.append(dict(name=row['name'], before=row['value'], after=None, unit=row['unit'],
                               status='removed', difference=None, relative_percent=None))
    return result


def register(bp, rows):
    @bp.post('/relatorios/<int:report_id>/fontes/<int:source_id>/sugerir')
    @login_required
    def report_suggest_metrics(report_id, source_id):
        report, selected = authorized_report(rows, report_id)
        if selected['role'] == 'viewer' or not secrets.compare_digest(session.get('family_csrf', ''), request.form.get('_csrf', '')):
            abort(403)
        source = rows('''SELECT id,image_bytes FROM cadu_connect_report_sources
            WHERE id=%s AND report_id=%s''', (source_id, report_id))
        if not source:
            abort(404)
        try:
            from .report_analysis import extract_suggestion
            from ..services.openrouter_service import chat_completion
            suggestion = extract_suggestion(source[0], report['document'], complete=chat_completion)
        except (ValueError, json.JSONDecodeError) as exc:
            return jsonify(error=str(exc)), 422
        except Exception:
            return jsonify(error='Não foi possível gerar a sugestão agora. Revise manualmente ou tente novamente.'), 502
        usage, model = suggestion.pop('_usage', {}), suggestion.pop('_model', 'gpt-5-nano')
        try:
            if rows("SELECT to_regclass('public.cadu_connect_report_ai_runs') IS NOT NULL AS ready")[0]['ready']:
                with get_db().cursor() as cur:
                    cur.execute('''INSERT INTO cadu_connect_report_ai_runs
                        (report_id,source_id,created_by,operation,model,usage,status) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)''',
                        (report_id,source_id,session['user_id'],'extract_suggestion',model,json.dumps(usage),'succeeded'))
                get_db().commit()
        except Exception:
            get_db().rollback()
        return jsonify(suggestion=suggestion, model=model, usage=usage, review_required=True)

    @bp.route('/relatorios/<int:report_id>/fontes/<int:source_id>/revisar', methods=['GET', 'POST'])
    @login_required
    def report_review_source(report_id, source_id):
        report, selected = authorized_report(rows, report_id, lock=request.method == 'POST')
        source = rows('''SELECT id,original_name,supplier,period_start,period_end
            FROM cadu_connect_report_sources WHERE id=%s AND report_id=%s''', (source_id, report_id))
        if not source:
            abort(404)
        source = source[0]
        ready = rows("SELECT to_regclass('public.cadu_connect_report_source_reviews') IS NOT NULL AS ready")[0]['ready']
        if not ready:
            abort(503, description='A revisão dos dados ainda não foi instalada.')
        session.setdefault('family_csrf', secrets.token_urlsafe(32))
        history = rows('''SELECT metrics,note,report_revision,created_at FROM cadu_connect_report_source_reviews
            WHERE source_id=%s ORDER BY report_revision DESC''', (source_id,))
        metrics = history[0]['metrics'] if history else []
        error = None
        if request.method == 'POST':
            if selected['role'] == 'viewer' or not secrets.compare_digest(session['family_csrf'], request.form.get('_csrf', '')):
                abort(403)
            try:
                if int(request.form.get('revision', '0')) != report['revision']:
                    raise ValueError('O relatório mudou. Reabra a revisão antes de confirmar os dados.')
                candidate = parse_metrics(request.form)
                note = request.form.get('note', '').strip()
                if not note or len(note) > 2000:
                    raise ValueError('Registre uma nota da revisão com até 2000 caracteres.')
                if history and candidate == metrics:
                    get_db().rollback()
                    return redirect(url_for('cadu_connect.report_review_source', report_id=report_id, source_id=source_id))
                revision = report['revision'] + 1
                with get_db().cursor() as cur:
                    cur.execute('''INSERT INTO cadu_connect_report_source_reviews
                        (source_id,report_revision,metrics,note,created_by) VALUES (%s,%s,%s::jsonb,%s,%s)''',
                        (source_id,revision,json.dumps(candidate),note,session['user_id']))
                    cur.execute("UPDATE cadu_connect_report_sources SET status='reviewed' WHERE id=%s", (source_id,))
                    cur.execute('''UPDATE cadu_connect_report_workspaces SET revision=%s,updated_by=%s,
                        updated_at=NOW() WHERE id=%s''', (revision,session['user_id'],report_id))
                    cur.execute('''INSERT INTO cadu_connect_report_workspace_versions
                        (report_id,revision,document,note,created_by) VALUES (%s,%s,%s::jsonb,%s,%s)''',
                        (report_id,revision,json.dumps(report['document']),f'Print #{source_id} revisado: {note}',session['user_id']))
                get_db().commit()
                return redirect(url_for('cadu_connect.report_review_source', report_id=report_id, source_id=source_id, saved=1))
            except ValueError as exc:
                get_db().rollback()
                error = str(exc)
                # Preserve submitted values even when parsing fails.
                metrics = [dict(name=name, raw=request.form.getlist('metric_value')[i] if i < len(request.form.getlist('metric_value')) else '',
                    **{field: (request.form.getlist('metric_'+field)[i] if i < len(request.form.getlist('metric_'+field)) else '')
                       for field in ('unit','definition','scope','evidence')}) for i,name in enumerate(request.form.getlist('metric_name')[:60])]
            except Exception:
                get_db().rollback()
                raise
        changes = compare_metrics(history[1]['metrics'] if len(history) > 1 else [], history[0]['metrics']) if history else []
        response = render_template('cadu_connect/report_review.html', report=report, source=source,
            selected=selected, metrics=metrics, history=history, changes=changes, error=error, units=UNITS)
        return response, 200, {'Cache-Control': 'private, no-store'}
