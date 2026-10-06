"""Client-safe projections of planning catalogs.

The legacy chat queried wide catalog rows. These projections intentionally expose
only fields that can be explained to a SmartPlanner customer. They are read-only
and do not depend on the selected client's ID because the catalogs are shared.
"""
import json
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlparse

from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from .channels import _channel_logo

KINDS = {'canais', 'formatos', 'audiencias', 'interativos'}


# Every field below corresponds to a column from cadu_audiencias (plus the
# resolved names from the category and platform joins). Keeping this map here
# makes the detail page auditable: it never presents a value without exposing
# the variable from which it came.
AUDIENCE_DATA_GROUPS = (
    ('Identificação e origem', (
        ('id', 'Identificador interno'), ('id_audiencia_plataforma', 'Identificador na plataforma'),
        ('nome', 'Nome cadastrado'), ('slug', 'Slug'), ('titulo_chamativo', 'Título de apresentação'),
        ('fonte', 'Fonte declarada'), ('plataforma_id', 'ID da plataforma'), ('channel', 'Nome da plataforma'),
        ('categoria_id', 'ID da categoria'), ('category', 'Categoria'), ('subcategoria_id', 'ID da subcategoria'),
        ('subcategory', 'Subcategoria'), ('imagem_url', 'Imagem principal'),
    )),
    ('Narrativa e aplicação', (
        ('descricao', 'Descrição'), ('descricao_curta', 'Descrição curta'),
        ('descricao_comercial', 'Descrição comercial'), ('descricao_ia', 'Descrição gerada por IA'),
        ('storytelling', 'Storytelling'), ('caso_uso_principal', 'Caso de uso principal'),
        ('insights_planejamento', 'Insights de planejamento'), ('insights_planejamento_cards', 'Cards de insight'),
        ('diferenciais_competitivos', 'Diferenciais competitivos'), ('tags', 'Tags'),
    )),
    ('Público, perfil e comportamento', (
        ('publico_estimado', 'Público estimado'), ('publico_numero', 'Público em número'),
        ('tamanho', 'Classificação de tamanho'), ('perfil_socioeconomico', 'Perfil socioeconômico'),
        ('grau_instrucao', 'Grau de instrução'), ('estado_civil_predominante', 'Estado civil predominante'),
        ('perfil_consumo', 'Perfil de consumo'), ('momentos_chave', 'Momentos-chave'),
        ('interesses_correlatos', 'Interesses correlatos'), ('categorias_alto_desempenho', 'Categorias de alto desempenho'),
        ('propensao_compra', 'Propensão de compra'), ('sazonalidade', 'Sazonalidade'),
    )),
    ('Demografia e dispositivos', (
        ('demografia_homens', 'Homens', 'percentage'), ('demografia_mulheres', 'Mulheres', 'percentage'),
        ('idade_18_24', 'Faixa 18–24', 'percentage'), ('idade_25_34', 'Faixa 25–34', 'percentage'),
        ('idade_35_44', 'Faixa 35–44', 'percentage'), ('idade_45_mais', 'Faixa 45+', 'percentage'),
        ('dispositivo_mobile', 'Mobile', 'percentage'), ('dispositivo_desktop', 'Desktop', 'percentage'),
        ('dispositivo_tablet', 'Tablet', 'percentage'),
    )),
    ('Métricas e precificação', (
        ('cpm_custo', 'CPM de custo', 'currency'), ('cpm_venda', 'CPM de venda', 'currency'),
        ('cpm_minimo', 'CPM mínimo', 'currency'), ('cpm_maximo', 'CPM máximo', 'currency'),
        ('ctr_medio_estimado', 'CTR médio estimado', 'percentage'),
        ('taxa_conversao_estimada', 'Taxa de conversão estimada', 'percentage'),
        ('cpa_estimado_min', 'CPA estimado mínimo', 'currency'), ('cpa_estimado_max', 'CPA estimado máximo', 'currency'),
        ('tamanho_mercado_brl', 'Tamanho de mercado (BRL)', 'currency'), ('ticket_medio_estimado', 'Ticket médio estimado', 'currency'),
        ('relevancia_score', 'Score de relevância'), ('overlap_facebook', 'Sobreposição Facebook', 'percentage'),
        ('overlap_google', 'Sobreposição Google', 'percentage'), ('alcance_incremental', 'Alcance incremental'),
    )),
    ('Disponibilidade, qualidade e rastreabilidade', (
        ('is_premium', 'É premium', 'boolean'), ('is_active', 'Está ativa', 'boolean'),
        ('requer_cotacao', 'Requer cotação', 'boolean'), ('mensagem_cotacao', 'Mensagem de cotação'),
        ('views_count', 'Visualizações'), ('added_to_cart_count', 'Adições ao plano'), ('quoted_count', 'Cotações'),
        ('confiabilidade_score', 'Score de confiabilidade'), ('dados_validos', 'Dados válidos', 'boolean'),
        ('campos_estimados_total', 'Campos estimados'), ('campos_com_dados_reais', 'Campos com dados reais'),
        ('versao_pipeline', 'Versão do pipeline'), ('validacao_final', 'Validação final'),
        ('metadados_geracao', 'Metadados de geração'), ('pipeline_tracking', 'Rastreamento do pipeline'),
        ('data_processamento', 'Processado em', 'datetime'), ('created_at', 'Criado em', 'datetime'),
        ('updated_at', 'Atualizado em', 'datetime'),
    )),
    ('Classificação editorial vinculada', (
        ('taxonomy', 'Registro completo de cadu_audience_taxonomy'),
    )),
)


def rows(sql, params=()):
    """Use the shared, read-only catalog gateway for every projection."""
    return repository.rows(sql, params)


def _safe_url(value):
    value = str(value or '').strip()
    parsed = urlparse(value)
    return value if parsed.scheme in {'http', 'https'} and parsed.hostname else ''


def _format_audience_value(value, kind=''):
    if value is None or value == '' or value == [] or value == {}:
        return 'Não informado.'
    if kind == 'boolean':
        return 'Sim' if value else 'Não'
    if kind == 'percentage':
        return f'{value}%'
    if kind == 'currency':
        try:
            return f"R$ {float(value):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except (TypeError, ValueError):
            return str(value)
    if kind == 'datetime' and isinstance(value, (date, datetime)):
        return value.strftime('%d/%m/%Y %H:%M')
    if isinstance(value, (list, tuple)):
        return ', '.join(map(str, value))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _audience_data_groups(record):
    groups = []
    for title, fields in AUDIENCE_DATA_GROUPS:
        entries = []
        for field in fields:
            variable, label, *format_kind = field
            raw_value = record.get(variable)
            entries.append({
                'variable': variable,
                'label': label,
                'value': _format_audience_value(raw_value, format_kind[0] if format_kind else ''),
                'is_empty': raw_value is None or raw_value == '' or raw_value == [] or raw_value == {},
                'is_structured': isinstance(raw_value, dict),
            })
        groups.append({'title': title, 'fields': entries})
    return groups


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
    if not 1 <= limit <= 30:
        raise BadRequest('O limite deve ser de 1 a 30.')
    # Keep the API and the Planner pages on one audited projection.  The
    # repository caps source records; the API's smaller limit is then applied
    # after validation, without duplicating database SQL here.
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
        'audiencias': '''SELECT a.*, a.nome AS name, COALESCE(a.descricao, a.descricao_curta) AS description,
                                 a.publico_estimado AS audience, a.imagem_url AS image_url,
                                 a.plataforma_id AS platform_id,
                                 c.nome AS category, s.nome AS subcategory, p.nome AS channel,
                                 to_jsonb(t) AS taxonomy
                            FROM cadu_audiencias a
                       LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                       LEFT JOIN cadu_subcategorias s ON s.id = a.subcategoria_id
                       LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                       LEFT JOIN cadu_audience_taxonomy t ON t.audience_id = a.id
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
    if kind in {'formatos', 'interativos'}:
        return _format_detail(records[0])
    if kind == 'audiencias':
        records[0]['data_groups'] = _audience_data_groups(records[0])
    return records[0]


# What a customer may see of an audience: its public description, people and
# estimated indicators. Costs, sale prices, internal ids and pipeline tracking
# stay with the internal tools that call ``detail`` directly.
CLIENT_AUDIENCE_KEYS = ('id', 'name', 'description', 'audience', 'image_url', 'category', 'subcategory', 'channel')
CLIENT_AUDIENCE_GROUPS = {
    'Narrativa e aplicação': None,
    'Público, perfil e comportamento': None,
    'Demografia e dispositivos': None,
    'Métricas e precificação': ('Indicadores estimados', {
        'ctr_medio_estimado', 'taxa_conversao_estimada', 'cpa_estimado_min', 'cpa_estimado_max',
        'tamanho_mercado_brl', 'alcance_incremental'}),
}


def client_projection(kind, record):
    """Reduce a catalog record to the fields a Planner customer may see."""
    if kind != 'audiencias' or not isinstance(record, dict):
        return record
    projected = {key: record.get(key) for key in CLIENT_AUDIENCE_KEYS if record.get(key) not in (None, '')}
    groups = []
    for group in record.get('data_groups') or _audience_data_groups(record):
        rule = CLIENT_AUDIENCE_GROUPS.get(group.get('title'), False)
        if rule is False:
            continue
        title, allowed = rule if rule else (group['title'], None)
        fields = [field for field in group.get('fields') or []
                  if (allowed is None or field.get('variable') in allowed)
                  and not field.get('is_empty') and not field.get('is_structured')]
        if fields:
            groups.append({'title': title, 'fields': fields})
    projected['data_groups'] = groups
    return projected


def client_detail(kind, value):
    return client_projection(kind, detail(kind, value))


def related_audiences(audience, limit=6):
    """Return a compact, explainable comparison set for an audience detail page."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 6
    limit = max(1, min(limit, 8))
    return repository.decorate_audiences(rows('''SELECT a.id, a.nome AS name, a.publico_estimado AS audience,
                                     COALESCE(p.nome, NULLIF(TRIM(a.fonte), ''), 'Portais') AS channel,
                                     COALESCE(p.nome, NULLIF(TRIM(a.fonte), ''), 'Portais') AS platform,
                                     c.nome AS category
                                FROM cadu_audiencias a
                           LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                           LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                               WHERE a.is_active = TRUE AND a.id <> %s
                                 AND (a.categoria_id = %s OR a.plataforma_id = %s)
                            ORDER BY (a.categoria_id = %s) DESC, (a.plataforma_id = %s) DESC, a.nome
                               LIMIT %s''',
                           (audience['id'], audience.get('category_id'), audience.get('platform_id'),
                            audience.get('category_id'), audience.get('platform_id'), limit)))


def audience_facets():
    categories = rows('''SELECT DISTINCT c.nome AS value FROM cadu_audiencias a JOIN cadu_categorias c ON c.id = a.categoria_id WHERE a.is_active = TRUE ORDER BY c.nome LIMIT 30''')
    channels = rows('''SELECT DISTINCT p.nome AS value FROM cadu_audiencias a JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id WHERE a.is_active = TRUE ORDER BY p.nome LIMIT 30''')
    return {'categories': [item['value'] for item in categories], 'channels': [item['value'] for item in channels]}


# Papel típico de um canal num plano, inferido da categoria/tipo cadastrados.
# É um ponto de partida explicável; o Cadu ajusta o papel por plano.
CHANNEL_ROLES = (
    (('search', 'busca', 'google ads'), 'Capturar demanda', 'Aparece quando a pessoa já procura pelo assunto.'),
    (('video', 'vídeo', 'youtube', 'ctv', 'tv', 'svod', 'avod'), 'Construir alcance',
     'Explica a ideia em vídeo e gera cobertura.'),
    (('social', 'rede', 'meta', 'instagram', 'facebook', 'tiktok'), 'Frequência e variações',
     'Distribui variações criativas com segmentação fina.'),
    (('audio', 'áudio', 'música', 'musica', 'podcast', 'spotify', 'deezer'), 'Frequência em contexto',
     'Acompanha a rotina com mensagens em áudio.'),
    (('dooh', 'ooh', 'exterior', 'mobiliário', 'mobiliario'), 'Presença local',
     'Marca presença física na praça prioritária.'),
    (('portal', 'programática', 'programatica', 'notícia', 'noticia', 'display'), 'Contexto e expansão',
     'Leva a mensagem para conteúdos relacionados ao tema.'),
    (('retail', 'marketplace', 'delivery', 'ecommerce', 'e-commerce', 'ifood', 'amazon'), 'Perto da compra',
     'Fala com quem está decidindo o que comprar.'),
)

# Campos do canal que um cliente do Planner pode ver. Investimento mínimo e
# dados de landing page ficam com o time comercial.
CLIENT_CHANNEL_KEYS = (
    'id', 'slug', 'name', 'categoria', 'tipo', 'cor', 'logo_url', 'hero_image_url', 'descricao', 'alcance',
    'usuarios_unicos', 'tempo_medio', 'viewability', 'completion_rate', 'taxa_engajamento', 'demografia',
    'segmentacao', 'segmentacoes', 'formatos_resumo', 'especificacoes', 'modelo_compra', 'brand_safety',
    'medicao', 'diferenciais', 'produtos',
)


def channel_roles(channel):
    import re
    haystack = ' '.join(str(channel.get(key) or '') for key in ('categoria', 'category', 'tipo', 'slug', 'name')).lower()
    words = set(re.findall(r'[\w-]+', haystack))
    # Palavras inteiras: "tv" não pode casar com "streaming" nem "spotify".
    return [{'role': role, 'description': description}
            for keywords, role, description in CHANNEL_ROLES
            if any((word in words) if ' ' not in word else (word in haystack) for word in keywords)][:3]


def channel_audiences(channel, limit=8):
    """Audiences bought on this channel's platform (matched by platform name), biggest first."""
    name = str(channel.get('name') or '').strip()
    if not name:
        return []
    return repository.decorate_audiences(rows('''SELECT a.id, a.nome AS name, a.publico_estimado AS audience,
                                     p.nome AS channel, p.nome AS platform, c.nome AS category,
                                     a.imagem_url AS image_url
                                FROM cadu_audiencias a
                                JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                           LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                               WHERE a.is_active = TRUE AND LOWER(p.nome) = LOWER(%s)
                            ORDER BY a.publico_numero DESC NULLS LAST, a.nome
                               LIMIT %s''', (name, limit)))


def channel_profile(channel_id):
    """Ficha completa do canal para o cliente: dados, formatos, exemplos e notícias."""
    from . import channels
    try:
        record_id = int(channel_id)
    except (TypeError, ValueError):
        raise BadRequest('Identificador de canal inválido.')
    channel = channels.detail(record_id)
    gallery, ads = channels.related_media(channel)
    profile = {key: channel.get(key) for key in CLIENT_CHANNEL_KEYS if channel.get(key) not in (None, '', [], {})}
    profile.update(
        description=channel.get('descricao'), category=channel.get('categoria'), audience=channel.get('alcance'),
        roles=channel_roles(channel), gallery=gallery, ad_examples=ads,
        concepts=channels.activation_concepts(channel),
        formats=[{'id': row['id'], 'name': row['name'], 'description': row.get('descricao'),
                  'dimensions': row.get('dimensoes'), 'format_type': row.get('tipo')}
                 for row in channels.formats(channel)],
        news=channels.news(record_id),
        audiences=channel_audiences(channel),
    )
    return profile


def format_profile(kind, value):
    """Formato ou interativo com os canais onde ele pode rodar."""
    record = detail(kind, value)
    slug = str(record.get('plataforma_slug') or '')
    record['channels'] = rows('''SELECT id, slug, nome AS name, categoria AS category, logo_path
                                   FROM cadu_canais
                                  WHERE is_active = TRUE AND slug = ANY(%s)
                               ORDER BY ordem NULLS LAST, nome LIMIT 12''',
                              (list({slug, slug.replace('_', '-'), *repository.FORMAT_PLATFORM_CHANNELS.get(slug, [])}),)) if slug else []
    for channel in record['channels']:
        channel['logo_path'] = _channel_logo(channel.get('slug'), channel.get('logo_path'))
    record['platform_logo'] = repository.platform_logo_by_slug(slug, '')
    return record


def audience_profile(value):
    """Audiência projetada para o cliente, com audiências parecidas para comparar."""
    record = detail('audiencias', value)
    related = related_audiences({'id': record['id'], 'category_id': record.get('categoria_id'),
                                 'platform_id': record.get('plataforma_id')})
    projected = client_projection('audiencias', record)
    projected['related'] = related
    projected['platform_logo'] = repository.platform_logo_by_name(record.get('channel'))
    return projected
