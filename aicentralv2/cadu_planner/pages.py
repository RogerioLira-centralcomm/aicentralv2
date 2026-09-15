"""Client-safe planning projections; never import internal planner controllers."""
from ..cadu_family import repository


def load_records(module, user, selected, query=''):
    if module == 'cotacoes':
        return repository.quotes(selected['client_id'])
    if module in ('audiencias', 'canais', 'formatos', 'interativos'):
        return repository.catalog(module, query)
    if module == 'places':
        from .places import catalog
        return catalog(query)
    if module == 'docs':
        from .docs import list_documents
        return list_documents(selected['client_id'], user['id'])
    return []
