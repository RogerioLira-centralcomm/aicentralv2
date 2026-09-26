"""Authenticated legacy URL redirects into the React Reports workspace."""
from flask import abort, redirect, request, url_for
from ..auth import login_required


def register(bp):
    from .report_sources import register as register_sources
    def rows(sql, args=()):
        from ..db import get_db
        with get_db().cursor() as cur:
            cur.execute(sql, args)
            return [dict(row) for row in cur.fetchall()]
    register_sources(bp, rows)
    from .report_review import register as register_reviews
    register_reviews(bp, rows)
    from .report_public import register as register_public
    register_public(bp, rows)
    @bp.route('/importacoes', methods=['GET', 'POST'])
    @login_required
    def report_imports():
        if request.method == 'POST':
            abort(410, description='As importações agora são feitas no Reports.')
        return redirect(url_for('cadu_connect.reports_v1_app') + '#imports', code=302)
    @bp.route('/importacoes/<int:import_id>/resolver', methods=['GET', 'POST'])
    @login_required
    def resolve_import(import_id):
        if request.method == 'POST':
            abort(410, description='A associação de importações agora é feita no Reports.')
        return redirect(url_for('cadu_connect.reports_v1_app') + '#imports', code=302)
    @bp.route('/relatorios', methods=['GET', 'POST'])
    @login_required
    def report_library():
        if request.method == 'POST':
            abort(410, description='A edição de relatórios agora acontece no Reports.')
        return redirect(url_for('cadu_connect.reports_v1_app') + '#reports', code=302)
