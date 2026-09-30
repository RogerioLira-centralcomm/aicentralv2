"""Stable page identity for the Reports site inventory."""
import re
from urllib.parse import unquote, urlsplit


def normalize_page_path(url_or_path, locales=('en', 'es'), default='pt'):
    value = str(url_or_path)
    path = value.split('?', 1)[0].split('#', 1)[0] if value.startswith('//') and '.' not in value[2:].split('/', 1)[0] else urlsplit(value).path or '/'
    path = re.sub(r'/+', '/', unquote(path).lower())
    path = re.sub(r'/index\.(?:php|html?)$', '', path).rstrip('/') or '/'
    locale = default
    parts = path.split('/')
    if len(parts) > 1 and parts[1] in locales:
        locale = parts[1]
        path = '/' + '/'.join(parts[2:])
        path = path.rstrip('/') or '/'
    return {'locale': locale, 'path': path}


def translation_key(page, locale_paths):
    """Use explicit evidence before paths; never infer translated slugs by title."""
    if page.get('translation_key'):
        return page['translation_key']
    alternates = (page.get('evidence') or {}).get('hreflang') or {}
    if isinstance(alternates, dict):
        for language in ('x-default', 'pt', 'pt-BR'):
            if alternates.get(language):
                return normalize_page_path(alternates[language])['path']
    normalized = normalize_page_path(page.get('path_prefix') or page.get('url') or '/')
    if len(locale_paths.get(normalized['path'], ())) > 1:
        return normalized['path']
    return f"{normalized['path']}:{normalized['locale']}"
