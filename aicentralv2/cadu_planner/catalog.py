"""Client-safe projections of planning catalogs.

The legacy chat queried wide catalog rows. These projections intentionally expose
only fields that can be explained to a SmartPlanner customer. They are read-only
and do not depend on the selected client's ID because the catalogs are shared.
"""
import json
from urllib.parse import urlparse

from werkzeug.exceptions import BadRequest, NotFound

from ..db import get_db

KINDS = {'canais', 'formatos', 'audiencias', 'interativos'}


def rows(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def _safe_url(value):
    value = str(value or '').strip()
    parsed = urlparse(value)
    return value if parsed.scheme in {'http', 'https'} and parsed.hostname else ''


def _format_detail(record):
    extras = record.pop('extras', None) or {}
    if isinstance(extras, str):
        try:
            extras = json.loads(extras)
        except ValueError:
            extras = {}
    extras = extras if isinstance(extras, dict) else {}
    record['purpose'] = extras.get('objetivo_comercial') or 'Alcance'
    record['creative_category'] = record.get('creative_category') or extras.get('segmento') or record.get('format_type') or 'Formato de mídia'
    record['markets'] = extras.get('mercados_aplicaveis') if isinstance(extras.get('mercados_aplicaveis'), list) else []
    record['segments'] = extras.get('segmentos_aplicaveis') if isinstance(extras.get('segmentos_aplicaveis'), list) else []
    record['image_url'] = _safe_url(extras.get('imagem_referencia'))
    record['creative_url'] = _safe_url(extras.get('creative_url'))
    record['gallery_url'] = _safe_url(extras.get('gallery_url'))
    return record


def query(kind, value='', limit=20, category='', channel=''):
    if kind not in KINDS:
        raise NotFound()
    if not isinstance(value, str):
        raise BadRequest('Busca inválida.')
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise BadRequest('Limite inválido.')
    if not 1 <= limit <= 100:
        raise BadRequest('O limite deve ser de 1 a 30.')
    search = '%' + value.strip()[:100] + '%'
    category = category.strip()[:100] if isinstance(category, str) else ''
    channel = channel.strip()[:100] if isinstance(channel, str) else ''
    if kind == 'audiencias':
        return rows('''SELECT a.id, a.nome AS name, COALESCE(a.descricao_curta, a.descricao) AS description,
                              a.publico_estimado AS audience, a.imagem_url AS image_url,
                              a.perfil_socioeconomico, c.nome AS category, p.nome AS channel
                         FROM cadu_audiencias a
                    LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                    LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                        WHERE a.is_active = TRUE
                          AND (a.nome ILIKE %s OR COALESCE(a.descricao_curta, '') ILIKE %s
                               OR COALESCE(a.descricao, '') ILIKE %s OR COALESCE(c.nome, '') ILIKE %s)
                          AND (%s = '' OR c.nome = %s) AND (%s = '' OR p.nome = %s)
                     ORDER BY a.nome, a.id LIMIT %s''',
                    (search, search, search, search, category, category, channel, channel, limit))
    sql = {'canais': '''SELECT id, nome AS name, descricao AS description, categoria AS category, alcance AS audience FROM cadu_canais WHERE is_active = TRUE AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s OR COALESCE(categoria, '') ILIKE %s) ORDER BY ordem, nome LIMIT %s''',
           'formatos': '''SELECT id, nome AS name, descricao AS description, dimensoes AS dimensions, formatos_arquivo AS files FROM cadu_formatos WHERE is_active = TRUE AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s OR COALESCE(dimensoes, '') ILIKE %s OR COALESCE(formatos_arquivo, '') ILIKE %s) AND is_interativo = FALSE ORDER BY ordem, nome LIMIT %s''',
           'interativos': '''SELECT id, nome AS name, descricao AS description, dimensoes AS dimensions, formatos_arquivo AS files FROM cadu_formatos WHERE is_active = TRUE AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s OR COALESCE(dimensoes, '') ILIKE %s OR COALESCE(formatos_arquivo, '') ILIKE %s) AND is_interativo = TRUE ORDER BY ordem, nome LIMIT %s'''}[kind]
    params = (search, search, search, limit) if kind == 'canais' else (search, search, search, search, limit)
    return rows(sql, params)


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
                                 a.categoria_id AS category_id, a.plataforma_id AS platform_id,
                                 c.nome AS category, s.nome AS subcategory, p.nome AS channel
                            FROM cadu_audiencias a
                       LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                       LEFT JOIN cadu_subcategorias s ON s.id = a.subcategoria_id
                       LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                           WHERE a.id = %s AND a.is_active = TRUE LIMIT 1''',
        'canais': '''SELECT id, nome AS name, descricao AS description, categoria AS category,
                             alcance AS audience
                        FROM cadu_canais WHERE id = %s AND is_active = TRUE LIMIT 1''',
        'formatos': '''SELECT id, nome AS name, descricao AS description,
                              dimensoes AS dimensions, formatos_arquivo AS files,
                              tipo AS format_type, plataforma_slug, categoria_criativa AS creative_category, dados_extras AS extras
                         FROM cadu_formatos WHERE id = %s AND is_active = TRUE LIMIT 1''',
        'interativos': '''SELECT id, nome AS name, descricao AS description,
                                 dimensoes AS dimensions, formatos_arquivo AS files,
                                 tipo AS format_type, plataforma_slug, categoria_criativa AS creative_category, dados_extras AS extras
                            FROM cadu_formatos WHERE id = %s AND is_active = TRUE AND is_interativo = TRUE LIMIT 1''',
    }[kind]
    records = rows(sql, (record_id,))
    if not records:
        raise NotFound('Item de catálogo indisponível.')
    return _format_detail(records[0]) if kind in {'formatos', 'interativos'} else records[0]


def related_audiences(audience, limit=6):
    """Return a compact, explainable comparison set for an audience detail page."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 6
    limit = max(1, min(limit, 8))
    return rows('''SELECT a.id, a.nome AS name, a.publico_estimado AS audience,
                                     COALESCE(p.nome, NULLIF(TRIM(a.fonte), ''), 'Portais') AS channel,
                                     c.nome AS category
                                FROM cadu_audiencias a
                           LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                           LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                               WHERE a.is_active = TRUE AND a.id <> %s
                                 AND (a.categoria_id = %s OR a.plataforma_id = %s)
                            ORDER BY (a.categoria_id = %s) DESC, (a.plataforma_id = %s) DESC, a.nome
                               LIMIT %s''',
                           (audience['id'], audience.get('category_id'), audience.get('platform_id'),
                            audience.get('category_id'), audience.get('platform_id'), limit))


def audience_facets():
    categories = rows('''SELECT DISTINCT c.nome AS value FROM cadu_audiencias a JOIN cadu_categorias c ON c.id = a.categoria_id WHERE a.is_active = TRUE ORDER BY c.nome LIMIT 30''')
    channels = rows('''SELECT DISTINCT p.nome AS value FROM cadu_audiencias a JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id WHERE a.is_active = TRUE ORDER BY p.nome LIMIT 30''')
    return {'categories': [item['value'] for item in categories], 'channels': [item['value'] for item in channels]}
