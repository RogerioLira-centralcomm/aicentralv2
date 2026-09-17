"""Read-only channel detail projections owned by SmartPlanner."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from werkzeug.exceptions import NotFound

from ..db import get_db


_LOGOS = {
    'prime-video': 'prime-video.svg', 'globoplay': 'globoplay.png',
    'g1-globo': 'g1-globo.svg', 'sbt': 'sbt.png', 'uol': 'uol.png',
    'r7': 'r7.png', 'spotify': 'spotify.svg', 'deezer': 'deezer.png',
    'tiktok': 'tiktok.png', 'twitch': 'twitch.svg', 'waze': 'waze.png',
    'ifood': 'ifood.svg', 'eletromidia': 'eletromidia.svg',
}

_CHANNEL_CONCEPTS = {
    'prime-video': [{
        'image_url': '/static/images/channel-creatives/loreal-prime-video-revitalift-concept.png',
        'title': 'L’Oréal Paris Revitalift',
        'description': 'Conceito de pre-roll CTV 16:9 para demonstrar o formato no Prime Video.',
        'format': 'Pre-roll CTV · 16:9',
    }],
}


def _rows(sql, params=()):
    with get_db().cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall() or []


def _safe_media_url(value):
    """Accept only public HTTP(S) URLs or a local static path that exists."""
    raw = str(value or '').strip()
    parsed = urlparse(raw)
    if parsed.scheme in {'http', 'https'} and parsed.hostname:
        return raw
    if not raw.startswith('/static/'):
        return ''
    relative = raw.removeprefix('/static/')
    static_root = Path(__file__).resolve().parents[1] / 'static'
    return raw if (static_root / relative).is_file() else ''


def detail(channel_id):
    records = _rows('''SELECT id, slug, nome AS name, categoria, tipo, cor, logo_path,
                              imagem_path, og_image_path, imagens, descricao, alcance,
                              usuarios_unicos, tempo_medio, viewability, completion_rate,
                              taxa_engajamento, demografia, segmentacao, formatos_resumo,
                              especificacoes, investimento_minimo, modelo_compra,
                              prazo_entrega, integracao, brand_safety, medicao,
                              diferenciais, produtos, lp_data, segmentacoes, formatos
                         FROM cadu_canais
                        WHERE id = %s AND is_active IS TRUE
                        LIMIT 1''', (channel_id,))
    if not records:
        raise NotFound('Canal indisponível.')
    channel = records[0]
    slug = str(channel.get('slug') or '').lower()
    logo = _LOGOS.get(slug)
    channel['logo_url'] = f'/static/images/canais/{logo}' if logo else _safe_media_url(channel.get('logo_path'))
    channel['hero_image_url'] = _safe_media_url(channel.get('imagem_path')) or _safe_media_url(channel.get('og_image_path'))
    channel['gallery'] = [url for url in (channel.get('imagens') or []) if _safe_media_url(url)]
    channel['demografia'] = channel.get('demografia') or {}
    channel['segmentacao'] = channel.get('segmentacao') or {}
    channel['segmentacoes'] = channel.get('segmentacoes') or []
    return channel


def related_media(channel):
    """Only return media explicitly attached to the channel or an approved ad example."""
    channel_id, slug = channel['id'], str(channel.get('slug') or '')
    gallery = [{'url': url, 'label': 'Imagem do canal'} for url in channel.get('gallery') or []]
    gallery.extend(
        {'url': item['image_url'], 'label': item['titulo']}
        for item in _rows('''SELECT titulo, imagem_url FROM cadu_canais_noticias
                               WHERE canal_id = %s AND is_active IS TRUE
                                 AND imagem_url IS NOT NULL AND imagem_url <> ''
                               ORDER BY data_publicacao DESC NULLS LAST, id DESC LIMIT 8''', (channel_id,))
        if _safe_media_url(item.get('image_url'))
    )
    platform_slugs = tuple({slug, slug.replace('-', '_')})
    examples = _rows('''SELECT image_url, title, source_url, source_domain, formato_slug
                           FROM cadu_formato_exemplos
                          WHERE plataforma_slug = ANY(%s) AND status = 'approved'
                            AND image_url IS NOT NULL AND image_url <> ''
                          ORDER BY score DESC NULLS LAST, id DESC LIMIT 8''', (list(platform_slugs),))
    ads = [
        {**item, 'image_url': _safe_media_url(item.get('image_url'))}
        for item in examples if _safe_media_url(item.get('image_url'))
    ]
    return gallery, ads


def activation_concepts(channel):
    """Curated concepts are clearly separate from client-approved ad examples."""
    return _CHANNEL_CONCEPTS.get(str(channel.get('slug') or '').lower(), [])


def formats(channel):
    slug = str(channel.get('slug') or '')
    return _rows('''SELECT id, nome AS name, descricao, dimensoes, formatos_arquivo,
                           tipo, dados_extras
                      FROM cadu_formatos
                     WHERE is_active IS TRUE
                       AND plataforma_slug = ANY(%s)
                     ORDER BY ordem NULLS LAST, nome''', ([slug, slug.replace('-', '_')],))


def news(channel_id):
    return _rows('''SELECT titulo, resumo, fonte, fonte_url, categoria, data_publicacao
                      FROM cadu_canais_noticias
                     WHERE canal_id = %s AND is_active IS TRUE
                     ORDER BY data_publicacao DESC NULLS LAST, id DESC LIMIT 6''', (channel_id,))
