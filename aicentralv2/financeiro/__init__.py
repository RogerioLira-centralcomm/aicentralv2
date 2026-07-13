from flask import Blueprint

bp = Blueprint('financeiro', __name__, url_prefix='/financeiro')

from . import routes  # noqa: E402, F401
