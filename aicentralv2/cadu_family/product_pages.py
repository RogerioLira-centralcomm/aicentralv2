"""Explicit registry: request values can never select arbitrary Python/templates."""
from importlib import import_module

PRODUCT_PACKAGES = {
    'workspace': 'cadu_workspace',
    'planner': 'cadu_planner',
    'studio': 'cadu_studio',
    'connect': 'cadu_connect',
}


def page_template(product):
    if product == 'planner':
        return 'cadu_planner/react.html'
    return f'{PRODUCT_PACKAGES[product]}/family/page.html'


def load_records(product, module, user, selected, query='', filters=None):
    package = PRODUCT_PACKAGES[product]
    pages = import_module(f'aicentralv2.{package}.pages')
    if product == 'planner':
        return pages.load_records(module, user, selected, query, filters)
    return pages.load_records(module, user, selected, query)
