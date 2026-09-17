"""Authentication boundary owned by the Studio product."""
from functools import wraps
from urllib.parse import urlparse

from flask import current_app, request

from ..auth import admin_required_api, login_required_api


def studio_or_admin_required_api(view):
    """Use Studio login on its host and the staff guard only on legacy mounts."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        studio_host = urlparse(str(current_app.config.get("STUDIO_URL") or "")).hostname
        current_host = (request.host.split(":", 1)[0] or "").lower()
        guard = login_required_api if studio_host and current_host == studio_host.lower() else admin_required_api
        return guard(view)(*args, **kwargs)
    return wrapped
