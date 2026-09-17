"""Standalone SmartPlanner audience marketplace; no Family or Workspace runtime dependency."""
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, redirect, render_template, request, session

from ..auth import login_url
from . import catalog

bp = Blueprint('planner_marketplace', __name__)


def _planner_host():
    configured = urlparse(str(current_app.config.get('PLANNER_URL') or '')).hostname
    return (request.host.split(':', 1)[0] or '').lower() == (configured or '').lower()


@bp.before_request
def planner_only():
    if not _planner_host():
        abort(404)


def _url(endpoint, **values):
    from flask import url_for
    return url_for(endpoint, **{key: value for key, value in values.items() if value not in (None, '')})


@bp.get('/audiencias')
def audiences():
    if not session.get('user_id'):
        return redirect(login_url(request.full_path))
    category = request.args.get('category', '')
    channel = request.args.get('channel', '')
    return render_template('cadu_planner/marketplace.html',
                           records=catalog.query('audiencias', request.args.get('q', ''), 100, category, channel),
                           facets=catalog.audience_facets(), category=category, channel=channel,
                           planner_url=_url)


@bp.get('/audiencias/<int:audience_id>')
def audience_detail(audience_id):
    if not session.get('user_id'):
        return redirect(login_url(request.full_path))
    audience = catalog.detail('audiencias', audience_id)
    return render_template('cadu_planner/audience_detail.html', audience=audience,
                           similar_audiences=catalog.related_audiences(audience), planner_url=_url)
