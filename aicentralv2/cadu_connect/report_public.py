"""Revocable, read-only public report links. No source images leave Connect."""
import secrets
from datetime import datetime, timedelta, timezone
from flask import abort, redirect, render_template, request, session, url_for
from ..auth import login_required
from ..db import get_db
from .report_sources import authorized_report


def register(bp, rows):
    @bp.post('/relatorios/<int:report_id>/publicar')
    @login_required
    def report_publish(report_id):
        report, selected = authorized_report(rows, report_id, lock=True)
        if selected['role'] == 'viewer' or not secrets.compare_digest(session.get('family_csrf', ''), request.form.get('_csrf', '')):
            abort(403)
        days = request.form.get('expires_days', '30')
        try:
            days = int(days)
            if days not in (7, 30, 90, 0): raise ValueError
        except ValueError:
            abort(400)
        token = secrets.token_urlsafe(32)
        expires = None if days == 0 else datetime.now(timezone.utc) + timedelta(days=days)
        with get_db().cursor() as cur:
            cur.execute('''INSERT INTO cadu_connect_report_public_links (report_id,token,expires_at,created_by,revoked_at)
                VALUES (%s,%s,%s,%s,NULL) ON CONFLICT (report_id) DO UPDATE SET token=EXCLUDED.token,
                expires_at=EXCLUDED.expires_at,revoked_at=NULL,created_by=EXCLUDED.created_by''',
                (report['id'], token, expires, session['user_id']))
        get_db().commit()
        return redirect(url_for('cadu_connect.report_library', report_id=report_id, published=1))

    @bp.post('/relatorios/<int:report_id>/revogar-publicacao')
    @login_required
    def report_unpublish(report_id):
        _, selected = authorized_report(rows, report_id, lock=True)
        if selected['role'] == 'viewer' or not secrets.compare_digest(session.get('family_csrf', ''), request.form.get('_csrf', '')):
            abort(403)
        with get_db().cursor() as cur:
            cur.execute('UPDATE cadu_connect_report_public_links SET revoked_at=NOW() WHERE report_id=%s', (report_id,))
        get_db().commit()
        return redirect(url_for('cadu_connect.report_library', report_id=report_id, revoked=1))

    @bp.get('/r/<token>')
    def public_report(token):
        if not token or len(token) > 96: abort(404)
        found = rows('''SELECT w.campaign_name,w.revision,w.updated_at,w.document,l.expires_at
            FROM cadu_connect_report_public_links l JOIN cadu_connect_report_workspaces w ON w.id=l.report_id
            WHERE l.token=%s AND l.revoked_at IS NULL AND (l.expires_at IS NULL OR l.expires_at > NOW())''', (token,))
        if not found: abort(404)
        return render_template('cadu_connect/public_report.html', report=found[0]), 200, {'Cache-Control': 'private, no-store'}
