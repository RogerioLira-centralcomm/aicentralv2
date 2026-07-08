from flask import Blueprint

bp = Blueprint('crm_comercial', __name__, url_prefix='/crm-comercial')

from . import routes, ia_routes
