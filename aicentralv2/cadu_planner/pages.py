"""Client-safe planning projections; never import internal planner controllers."""
from datetime import datetime, timezone

from ..cadu_family import repository


def load_records(module, user, selected, query='', filters=None):
    filters = filters or {}
    if module in ('inicio', 'planos'):
        from .plans import list_plans
        records = list_plans(selected['client_id'], user['id'])
        if module == 'inicio' and records:
            _decorate_home_plan(records[0], selected['client_id'], user['id'])
        return records
    if module in ('audiencias', 'canais', 'formatos', 'interativos'):
        return repository.catalog(module, query,
                                  category=filters.get('category', ''),
                                  platform=filters.get('platform', ''),
                                  sort=filters.get('sort', 'relevant'),
                                  format_type=filters.get('type', ''),
                                  segment=filters.get('segment', ''))
    if module == 'places':
        from .places import catalog
        return catalog(query, category=filters.get('category', ''), city=filters.get('city', ''))
    if module == 'portais':
        from .portals import catalog
        return catalog(query, category=filters.get('category', ''),
                       sort=filters.get('sort', 'featured'))['records']
    if module == 'docs':
        from .docs import list_documents
        return list_documents(selected['client_id'], user['id'])
    return []


def _decorate_home_plan(plan, client_id, actor_id):
    """Add only the decision-support details needed by the signed-in home."""
    from .plans import get_plan

    detailed = get_plan(client_id, actor_id, plan['id'])
    checks = detailed.get('readiness', {}).get('checks', [])
    incomplete = next((item['label'] for item in checks if not item['complete']), None)
    complete = sum(1 for item in checks if item['complete'])
    total = len(checks) or 1
    plan.update(progress_complete=complete, progress_total=total,
                progress_percent=round(complete * 100 / total),
                next_step=incomplete or 'Plano pronto para revisão',
                status_label={'draft': 'Rascunho', 'ready': 'Pronto para revisão'}.get(
                    plan.get('status'), 'Em andamento'),
                updated_label=_relative_updated_at(plan.get('updated_at')))


def _relative_updated_at(value):
    """Keep the home timestamp useful without exposing a raw database value."""
    if not isinstance(value, datetime):
        return 'Atualização indisponível'
    timestamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    elapsed = max(0, int((datetime.now(timezone.utc) - timestamp).total_seconds()))
    if elapsed < 60:
        return 'Atualizado agora'
    if elapsed < 3600:
        return f'Atualizado há {elapsed // 60} min'
    if elapsed < 86400:
        return f'Atualizado há {elapsed // 3600} h'
    if elapsed < 172800:
        return 'Atualizado ontem'
    return f'Atualizado em {timestamp.astimezone().strftime("%d/%m/%Y")}'
