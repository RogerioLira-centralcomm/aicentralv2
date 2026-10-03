"""Who sees the Creative Lab: only the organizations listed in CREATIVE_LAB_CLIENT_IDS (default 174).

Everyone else gets a 404 — the Lab does not exist for them, not even as a forbidden page.
"""

from __future__ import annotations

import os
from functools import wraps

from flask import abort, jsonify, request, session


def lab_client_ids() -> frozenset[int]:
    raw = os.getenv("CREATIVE_LAB_CLIENT_IDS", "174")
    return frozenset(int(item) for item in raw.replace(" ", "").split(",") if item.isdigit())


def current_client_id() -> int:
    try:
        return int(session.get("cliente_id") or 0)
    except (TypeError, ValueError):
        return 0


def lab_enabled() -> bool:
    """True for a logged-in user of an allowed organization (used by the navbar link too)."""
    return bool(session.get("user_id")) and current_client_id() in lab_client_ids()


def lab_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not lab_enabled():
            if request.path.startswith("/lab/api/"):
                return jsonify({"error": "not_found"}), 404
            abort(404)
        return view(*args, **kwargs)
    return wrapped
