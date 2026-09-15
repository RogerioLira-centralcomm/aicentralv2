"""Connect page data scoped to the authorized advertiser, not the agency."""
from . import repository


def load_records(module, user, selected, query=''):
    if module == 'relatorios':
        return repository.campaigns_for_client(selected['client_id'])
    return []
