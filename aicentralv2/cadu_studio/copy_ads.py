"""Copy Ads format contract ported from PHP api/copy-ads/formatos.php.

Legacy recommendations are compatibility rules, not claims about today's
platform policies. No database writes or provider calls are performed here.
"""
import json
import re

from werkzeug.exceptions import BadRequest

from ..cadu_family import repository


def field(name, label, limit, recommended=None):
    return dict(name=name, label=label, limit=limit, recommended=recommended or limit)


def aspect_ratio(dimensions):
    match = re.match(r'\s*(\d+)\s*[x×]\s*(\d+)', str(dimensions or ''), re.I)
    return int(match[1]) / int(match[2]) if match and int(match[2]) else 0


def fields_for(row):
    extra = row.get('dados_extras') or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except ValueError:
            extra = {}
    custom = extra.get('campos_copy') if isinstance(extra, dict) else None
    if isinstance(custom, list) and custom:
        result = []
        for item in custom[:30]:
            if not isinstance(item, dict):
                raise ValueError('Invalid legacy copy field')
            name, label = item.get('nome'), item.get('label')
            limit = item.get('limite')
            recommended = item.get('recomendado') or limit
            if (not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,63}', name)
                    or not isinstance(label, str) or not isinstance(limit, int)
                    or not isinstance(recommended, int) or not 1 <= recommended <= limit <= 20000):
                raise ValueError('Invalid legacy copy field')
            result.append(field(name, label[:150], limit, recommended))
        if len({item['name'] for item in result}) != len(result):
            raise ValueError('Duplicate legacy copy field')
        return result
    platform = str(row.get('plataforma_slug') or '').lower()
    kind = str(row.get('tipo') or '').lower()
    name = str(row.get('nome') or '').lower()
    ratio = aspect_ratio(row.get('dimensoes'))
    carousel = 'carrossel' in name or 'carousel' in name
    descriptions = lambda n, limit: [field('descricao_' + str(i), 'Descrição ' + str(i), limit) for i in range(1, n + 1)]
    if 'google' in platform:
        if kind == 'search' or 'pmax' in name or 'performance max' in name:
            result = [field('headline_' + str(i), 'Headline ' + str(i), 30) for i in range(1, 4)]
            if kind != 'search':
                result.append(field('headline_longo', 'Headline Longo', 90))
            return result + descriptions(2, 90)
        rec = (18, 60, 50) if ratio > 2.5 else (20, 70, 60) if ratio < 0.5 else (25, 80, 70)
        return [field('headline_curto', 'Headline Curto', 30, rec[0]), field('headline_longo', 'Headline Longo', 90, rec[1]), field('descricao', 'Descrição', 90, rec[2])]
    if any(part in platform for part in ('meta', 'facebook', 'instagram')):
        if 'stories' in name or 'reels' in name or 0 < ratio < 0.7:
            return [field('texto_principal', 'Texto Principal', 500, 72), field('headline', 'Headline', 40, 20)]
        rec = (100, 25, 20) if carousel else (90, 25, 25) if ratio > 1.4 else (125, 27, 27)
        return [field('texto_principal', 'Texto Principal (acima)' if carousel else 'Texto Principal', 500, rec[0]), field('headline', 'Headline do Card' if carousel else 'Headline', 40, rec[1]), field('descricao', 'Descrição do Link', 30, rec[2])]
    if 'linkedin' in platform:
        if 'message' in name or 'inmail' in name:
            return [field('assunto', 'Assunto', 60, 40), field('corpo_mensagem', 'Corpo da Mensagem', 1500, 500), field('cta', 'CTA', 20, 15)]
        if carousel:
            return [field('texto_intro', 'Texto Introdutório', 600, 120), field('headline', 'Headline do Card', 200, 45), field('cta', 'CTA Final', 20, 15)]
        result = [field('texto_intro', 'Texto Introdutório', 600, 100 if kind == 'video' else 150), field('headline', 'Headline', 200, 50 if kind == 'video' else 70)]
        return result if kind == 'video' else result + [field('descricao', 'Descrição', 300, 100)]
    if 'tiktok' in platform:
        spark = 'spark' in name
        return [field('texto_ad', 'Texto do Anúncio', 150 if spark else 100, 100 if spark else 80), field('cta', 'CTA', 20, 12 if spark else 15)]
    if 'youtube' in platform:
        if 'bumper' in name:
            return [field('headline', 'Headline', 40, 25), field('cta', 'CTA', 10)]
        if 'discovery' in name or 'in-feed' in name:
            return [field('headline', 'Headline', 100, 60)] + descriptions(2, 35)
        return [field('headline', 'Headline', 40)] + descriptions(2, 35) + [field('cta', 'CTA', 10)]
    if 'twitter' in platform or 'x_ads' in platform:
        result = [field('tweet', 'Tweet', 280, 200 if kind == 'video' else 250), field('headline_card', 'Headline Card', 70, 50)]
        return result + [field('cta', 'CTA', 20, 15)] if kind == 'video' else result
    if kind == 'native':
        return [field('headline', 'Headline', 90, 50), field('descricao', 'Descrição', 300, 150), field('marca', 'Nome da Marca', 25)]
    rec = (30, 90, 15)
    if ratio > 2.5: rec = (18, 50, 12)
    elif ratio > 1.5: rec = (22, 60, 12)
    elif 0 < ratio < 0.4: rec = (20, 60, 12)
    elif 0 < ratio < 0.7: rec = (22, 70, 15)
    return [field('headline', 'Headline', 40, rec[0]), field('descricao', 'Descrição', 150, rec[1]), field('cta', 'CTA', 20, rec[2])]


def formats():
    rows = repository.rows('''SELECT f.id, f.nome, f.plataforma_slug, f.tipo, f.descricao,
                                    f.dimensoes, f.specs_texto, f.dados_extras, p.nome AS plataforma_nome
                               FROM cadu_formatos f
                               JOIN cadu_plataformas_formatos p ON p.slug = f.plataforma_slug
                              WHERE f.is_active = TRUE AND p.is_active = TRUE
                           ORDER BY p.ordem, f.ordem, f.id''')
    return [{'id': row['id'], 'name': row['nome'], 'platform': row['plataforma_nome'],
             'dimensions': row['dimensoes'], 'description': row['descricao'],
             'fields': fields_for(row), 'specs': [part.strip() for part in (row['specs_texto'] or '').split('|') if part.strip()]}
            for row in rows]


def validate_copy(spec, values):
    if not isinstance(values, dict) or set(values) - {item['name'] for item in spec['fields']}:
        raise BadRequest('Campos de texto inválidos para este formato.')
    result = []
    for item in spec['fields']:
        text = values.get(item['name'], '')
        if not isinstance(text, str) or len(text) > 20000:
            raise BadRequest('Texto inválido ou muito longo.')
        result.append({**item, 'text': text, 'count': len(text),
                       'valid': bool(text.strip()) and len(text) <= item['limit'],
                       'above_recommended': len(text) > item['recommended']})
    return {'valid': all(item['valid'] for item in result), 'fields': result}
