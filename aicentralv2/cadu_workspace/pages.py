"""Workspace page data, after the family boundary authorizes the context."""
from ..cadu_family import repository


def load_records(module, user, selected, query=''):
    organization_id = user['organization_id']
    loaders = {'equipe': repository.team, 'planos': repository.plan,
               'consumo': repository.consumption, 'faturamento': repository.invoices,
               'integracoes': repository.integrations}
    if module not in loaders:
        return []
    result = loaders[module](organization_id)
    return [result] if module == 'planos' else result
