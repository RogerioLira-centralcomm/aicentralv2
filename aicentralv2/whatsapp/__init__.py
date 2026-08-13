from flask import Blueprint

bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')

from . import routes  # noqa: E402, F401
