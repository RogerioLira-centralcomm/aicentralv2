"""Client-safe projections of planning catalogs.

The legacy chat queried wide catalog rows. These projections intentionally expose
only fields that can be explained to a SmartPlanner customer. They are read-only
and do not depend on the selected client's ID because the catalogs are shared.
"""
from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository

KINDS = {'canais', 'formatos', 'audiencias', 'interativos'}


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
        'audiencias': '''SELECT a.id, a.nome AS name, COALESCE(a.descricao, a.descricao_curta) AS description,
                                 a.descricao_curta, a.descricao_comercial, a.caso_uso_principal,
                                 a.insights_planejamento, a.diferenciais_competitivos, a.tags, a.imagem_url AS image_url,
                                 a.publico_estimado AS audience, a.tamanho, a.fonte,
                                 a.perfil_socioeconomico, a.propensao_compra, a.sazonalidade,
                                 a.demografia_homens, a.demografia_mulheres, a.idade_18_24,
                                 a.idade_25_34, a.idade_35_44, a.idade_45_mais,
                                 a.dispositivo_mobile, a.dispositivo_desktop, a.dispositivo_tablet,
                                 c.nome AS category, s.nome AS subcategory, p.nome AS platform
                            FROM cadu_audiencias a
                       LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                       LEFT JOIN cadu_subcategorias s ON s.id = a.subcategoria_id
                       LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                           WHERE a.id = %s AND a.is_active = TRUE LIMIT 1''',
        'canais': '''SELECT id, nome AS name, descricao AS description, categoria AS category,
                             alcance AS audience
                        FROM cadu_canais WHERE id = %s AND is_active = TRUE LIMIT 1''',
        'formatos': '''SELECT id, nome AS name, descricao AS description,
                              dimensoes AS dimensions, formatos_arquivo AS files
                         FROM cadu_formatos WHERE id = %s AND is_active = TRUE LIMIT 1''',
        'interativos': '''SELECT id, nome AS name, descricao AS description,
                                 dimensoes AS dimensions, formatos_arquivo AS files
                            FROM cadu_formatos WHERE id = %s AND is_active = TRUE AND is_interativo = TRUE LIMIT 1''',
    }[kind]
    records = repository.rows(sql, (record_id,))
    if not records:
        raise NotFound('Item de catálogo indisponível.')
    return records[0]
