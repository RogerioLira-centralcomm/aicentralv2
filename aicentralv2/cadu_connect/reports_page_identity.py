"""One canonical identity for a web page across Super Tag, flows and Google Ads.

A page is ``(host, path)`` after the normalization the flow monitor applies when it matches events: ``www.`` is
dropped, the host is lower-cased, and the path is lower-cased with no trailing slash. Query strings and fragments never
take part in identity (campaign UTMs must not split one page into many).

The rule is kept here on purpose instead of importing it from the flow matcher, so ingestion and the page view do not
depend on the flow module; tests/test_reports_pages.py pins both to the same behavior.
"""
from urllib.parse import urlsplit


def normalize_path(path):
    return (str(path or '/').rstrip('/') or '/').lower()


def normalize_host(host):
    host = str(host or '').lower()
    return host[4:] if host.startswith('www.') else host

# Same rule as normalize_path, for SQL over a stored page_path column.
SQL_NORMALIZED_PATH = "COALESCE(NULLIF(LOWER(RTRIM({column},'/')),''),'/')"


def canonical_page(host, path):
    return normalize_host(host), normalize_path(path)


def split_url(url):
    """(host, path) for an http(s) URL, or None when it is not a web page address."""
    parts = urlsplit(str(url or '').strip())
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return None
    return canonical_page(parts.hostname, parts.path or '/')


def sql_normalized_path(column='page_path'):
    return SQL_NORMALIZED_PATH.format(column=column)
