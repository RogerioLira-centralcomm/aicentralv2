"""Read-only projection of saved attachments. Never relocate or fetch assets."""
import json
from urllib.parse import urljoin, urlsplit


def safe_url(value, legacy_base=None):
    if not isinstance(value, str) or not value or len(value) > 8192:
        return None
    if any(ord(char) < 33 for char in value) or '\\' in value:
        return None
    try:
        parsed = urlsplit(value)
        if not parsed.scheme:
            # A relative legacy path must never resolve against the new app.
            if not legacy_base or value.startswith('//') or not safe_url(legacy_base):
                return None
            return safe_url(urljoin(legacy_base, value))
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            return None
        parsed.port  # Reject malformed ports too.
        return value  # Keep signed URLs, query strings and original hosts intact.
    except ValueError:
        return None


def project_files(value, legacy_base=None):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:100]:
        if isinstance(item, str):
            item = {'name': item}
        if not isinstance(item, dict):
            continue
        name = item.get('name') or item.get('filename') or 'Arquivo'
        if not isinstance(name, str):
            name = 'Arquivo'
        url = next((link for key in ('url', 'file_url', 'remote_url', 'download_url')
                    if (link := safe_url(item.get(key), legacy_base))), None)
        result.append({'name': name[:250], 'url': url})
    return result
