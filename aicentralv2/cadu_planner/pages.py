"""Client-safe planning projections; never import internal planner controllers."""
from ..cadu_family import repository


def load_records(module, user, selected, query='', filters=None):
    filters = filters or {}
    if module in ('inicio', 'planos'):
        from .plans import list_plans
        return list_plans(selected['client_id'], user['id'])
    if module in ('audiencias', 'canais', 'formatos', 'interativos'):
        return repository.catalog(module, query,
                                  category=filters.get('category', ''),
                                  platform=filters.get('platform', ''),
                                  sort=filters.get('sort', 'relevant'),
                                  format_type=filters.get('type', ''),
                                  segment=filters.get('segment', ''))
    if module == 'places':
        from .places import catalog
        return catalog(query)
    if module == 'docs':
        from .docs import list_documents
        return list_documents(selected['client_id'], user['id'])
    return []
