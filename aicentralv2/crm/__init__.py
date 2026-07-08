from flask import Blueprint

bp = Blueprint('crm', __name__, url_prefix='/crm')

from . import routes, ia_routes
