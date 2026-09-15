"""Client-safe planning projections; never import internal planner controllers."""
from ..cadu_family import repository


def load_records(module, user, selected, query=''):
    if module == 'cotacoes':
        return repository.quotes(selected['client_id'])
    if module in ('audiencias', 'canais', 'formatos', 'interativos'):
        return repository.catalog(module, query)
    return []
