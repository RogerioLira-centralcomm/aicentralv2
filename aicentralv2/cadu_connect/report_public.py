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

    @bp.route('/r/<token>', methods=['GET', 'POST'])
    def public_report(token):
        """Main link shows the latest published version; ?v=N shows an older published one. Optional password."""
        if not token or len(token) > 96: abort(404)
        frozen = bool(rows("""SELECT 1 FROM information_schema.columns WHERE table_schema='public'
            AND table_name='cadu_connect_report_workspaces' AND column_name='published_revision'"""))
        found = rows(f'''SELECT w.id,w.campaign_name,w.revision,w.updated_at,w.document,l.expires_at
                {',w.published_revision,l.password_hash,l.locked_until > NOW() AS locked' if frozen else ''}
            FROM cadu_connect_report_public_links l JOIN cadu_connect_report_workspaces w ON w.id=l.report_id
            WHERE l.token=%s AND l.revoked_at IS NULL AND (l.expires_at IS NULL OR l.expires_at > NOW())''', (token,))
        if not found: abort(404)
        report = dict(found[0])
        headers = {'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex'}
        if frozen and report.get('password_hash'):
            from werkzeug.security import check_password_hash
            granted = session.setdefault('report_links', [])
            if token not in granted:
                error = ''
                if request.method == 'POST' and report.get('locked'):
                    error = 'Muitas tentativas. Tente de novo em 15 minutos.'
                elif request.method == 'POST':
                    if check_password_hash(report['password_hash'], request.form.get('password', '')):
                        rows('UPDATE cadu_connect_report_public_links SET failed_attempts=0,locked_until=NULL WHERE token=%s RETURNING id', (token,))
                        get_db().commit()
                        session['report_links'] = [*granted[-19:], token]
                        return redirect(request.full_path.rstrip('?'))
                    # Five wrong passwords lock the link for 15 minutes, for everyone (the counter lives on the link).
                    rows('''UPDATE cadu_connect_report_public_links SET
                            failed_attempts=CASE WHEN failed_attempts >= 4 THEN 0 ELSE failed_attempts + 1 END,
                            locked_until=CASE WHEN failed_attempts >= 4 THEN NOW() + INTERVAL '15 minutes' ELSE locked_until END
                        WHERE token=%s RETURNING id''', (token,))
                    get_db().commit()
                    error = 'Senha incorreta.'
                status = 429 if report.get('locked') and request.method == 'POST' else 401 if error else 200
                return render_template('cadu_connect/public_report_password.html', title=report['campaign_name'], error=error), status, headers
        snapshot, versions = None, []
        if frozen and report.get('published_revision'):
            versions = [row['revision'] for row in rows('''SELECT revision FROM cadu_connect_report_workspace_versions
                WHERE report_id=%s AND published_at IS NOT NULL ORDER BY revision DESC LIMIT 30''', (report['id'],))]
            wanted = request.args.get('v', type=int) or report['published_revision']
            if wanted not in versions: abort(404)
            version = rows('''SELECT revision,snapshot,published_at FROM cadu_connect_report_workspace_versions
                WHERE report_id=%s AND revision=%s''', (report['id'], wanted))[0]
            snapshot = version['snapshot'] or {}
            report.update(document=snapshot.get('document') or report['document'], revision=version['revision'],
                          updated_at=version['published_at'])
        from .report_blocks import blocks_of
        return render_template('cadu_connect/public_report.html', report=report, snapshot=snapshot, versions=versions,
                               blocks=[block for block in blocks_of(report['document']) if not block.get('hidden')],
                               latest=report.get('published_revision'), token=token), 200, headers
