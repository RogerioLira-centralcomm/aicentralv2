"""Client-safe projections of planning catalogs.

The legacy chat queried wide catalog rows. These projections intentionally expose
only fields that can be explained to a SmartPlanner customer. They are read-only
and do not depend on the selected client's ID because the catalogs are shared.
"""
from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository

KINDS = {'canais', 'formatos', 'audiencias'}


def query(kind, value='', limit=20):
    if kind not in KINDS:
        raise NotFound()
    if not isinstance(value, str):
        raise BadRequest('Busca inválida.')
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise BadRequest('Limite inválido.')
    if not 1 <= limit <= 30:
        raise BadRequest('O limite deve ser de 1 a 30.')
    # repository.catalog keeps the SQL projection and uses a bounded string.
    return repository.catalog(kind, value.strip()[:100])[:limit]


def detail(kind, value):
    if kind not in KINDS:
        raise NotFound()
    try:
        record_id = int(value)
    except (TypeError, ValueError):
        raise BadRequest('Identificador de catálogo inválido.')
    if record_id < 1:
        raise NotFound()
    sql = {
        'audiencias': '''SELECT id, nome AS name, descricao_curta AS description,
                                 publico_estimado AS audience
                            FROM cadu_audiencias WHERE id = %s AND is_active = TRUE LIMIT 1''',
        'canais': '''SELECT id, nome AS name, descricao AS description, categoria AS category,
                             alcance AS audience
                        FROM cadu_canais WHERE id = %s AND is_active = TRUE LIMIT 1''',
        'formatos': '''SELECT id, nome AS name, descricao AS description,
                              dimensoes AS dimensions, formatos_arquivo AS files
                         FROM cadu_formatos WHERE id = %s AND is_active = TRUE LIMIT 1''',
    }[kind]
    records = repository.rows(sql, (record_id,))
    if not records:
        raise NotFound('Item de catálogo indisponível.')
    return records[0]
