"""Standalone SmartPlanner audience marketplace; no Family or Workspace runtime dependency."""
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, redirect, request, session

from ..auth import login_url

bp = Blueprint('planner_marketplace', __name__)


def _planner_host():
    configured = urlparse(str(current_app.config.get('PLANNER_URL') or '')).hostname
    return (request.host.split(':', 1)[0] or '').lower() == (configured or '').lower()


@bp.before_request
def planner_only():
    if not _planner_host():
        abort(404)


@bp.get('/audiencias')
def audiences():
    """Keep the public Planner URL while using its canonical app shell."""
    if not session.get('user_id'):
        return redirect(login_url(request.full_path))
    return current_app.view_functions['cadu_family.page']('planner', 'audiencias')


@bp.get('/audiencias/<int:audience_id>')
def audience_detail(audience_id):
    """Keep legacy deep links on the same full Planner experience."""
    return current_app.view_functions['cadu_family.planner_audience_detail'](audience_id)
