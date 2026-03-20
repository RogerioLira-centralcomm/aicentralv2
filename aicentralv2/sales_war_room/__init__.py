from flask import Blueprint

bp = Blueprint('sales_war_room', __name__, url_prefix='/sales-war-room')

from . import routes, ia_routes
