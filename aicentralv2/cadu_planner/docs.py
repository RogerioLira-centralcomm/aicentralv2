"""Smart Docs compatibility service backed by the legacy Cadu tables.

The module intentionally uses the existing PHP schema. It does not copy
documents: ownership is always constrained by client and actor on every write.
"""
from __future__ import annotations

import re
import secrets
from html import escape
from io import BytesIO

from psycopg.types.json import Json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from ..cadu_family import repository
from ..db import get_db

MAX_HTML = 500_000
_DANGEROUS = re.compile(r"<(?:script|style|iframe|object|embed)[^>]*>.*?</(?:script|style|iframe|object|embed)>", re.I | re.S)
_EVENTS = re.compile(r"\s+on[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_JS_URL = re.compile(r"\s(?:href|src)\s*=\s*(?:\"\s*javascript:[^\"]*\"|'\s*javascript:[^']*'|javascript:[^\s>]+)", re.I)
_TAGS = re.compile(r"<[^>]+>")


def markdown_to_safe_html(value):
    """Small safe Markdown projection for plans created from a chat response.

    The chat renderer accepts a deliberately bounded Markdown dialect.  Keep
    the stored SmartDoc equally predictable and escape every model-provided
    character before adding the few allowed tags.
    """
    lines = str(value or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    output, items, ordered = [], [], None

    def inline(text):
        text = escape(text, quote=False)
        text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)
        text = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong>\1</strong>', text)
        return re.sub(r'\*([^*\n]+)\*', r'<em>\1</em>', text)

    def flush_items():
        nonlocal items, ordered
        if items:
            tag = 'ol' if ordered else 'ul'
            output.append('<%s>%s</%s>' % (tag, ''.join('<li>%s</li>' % inline(item) for item in items), tag))
        items, ordered = [], None

    for raw in lines:
        text = raw.strip()
        marker = re.match(r'^(?:([-*+])|(\d+)\.)\s+(.+)$', text)
        if marker:
            is_ordered = bool(marker.group(2))
            if items and ordered != is_ordered:
                flush_items()
            ordered = is_ordered
            items.append(marker.group(3))
            continue
        flush_items()
        if not text:
            continue
        heading = re.match(r'^#{1,6}\s+(.+)$', text)
        if heading:
            output.append('<h2>%s</h2>' % inline(heading.group(1)))
        elif text.startswith('>'):
            output.append('<blockquote>%s</blockquote>' % inline(text[1:].lstrip()))
        else:
            output.append('<p>%s</p>' % inline(text))
    flush_items()
    return ''.join(output) or '<p></p>'


def _available(name):
    row = repository.rows("SELECT to_regclass(%s) IS NOT NULL AS available", ("public." + name,))
    return bool(row and row[0]["available"])


def sanitize_html(value):
    html = str(value or "")[:MAX_HTML]
    html = _DANGEROUS.sub("", html)
    html = _EVENTS.sub("", html)
    return _JS_URL.sub("", html)


def _doc_where(client_id, actor_id, doc_id=None):
    sql = "id_cliente = %s AND (id_contato_cliente = %s OR share_enabled = TRUE)"
    params = [client_id, actor_id]
    if doc_id is not None:
        sql += " AND id = %s"
        params.append(doc_id)
    return sql, params


def list_documents(client_id, actor_id):
    if not _available("cadu_artifacts"):
        return []
    where, params = _doc_where(client_id, actor_id)
    return repository.rows(f'''SELECT id, titulo AS title, tipo AS type, status, template_id,
                                       branding_id, share_enabled, share_token, created_at, updated_at,
                                       id_contato_cliente = %s AS is_owner
                                  FROM cadu_artifacts WHERE {where}
                                 ORDER BY updated_at DESC LIMIT 100''', [actor_id, *params])


def templates(client_id):
    if not _available("cadu_docs_templates"):
        return []
    return repository.rows('''SELECT id, slug, nome AS name, descricao AS description, categoria AS category,
                                     icone AS icon, cor_tema AS color, conteudo_html_padrao AS html
                                FROM cadu_docs_templates
                               WHERE ativo = TRUE AND (is_system = TRUE OR id_cliente = %s OR id_cliente IS NULL)
                               ORDER BY is_system DESC, ordem, id''', (client_id,))


def get_document(client_id, actor_id, doc_id):
    where, params = _doc_where(client_id, actor_id, int(doc_id))
    records = repository.rows(f'''SELECT id, titulo AS title, tipo AS type, status, conteudo_html AS html,
                                          template_id, branding_id, share_enabled, share_token, export_config,
                                          allow_download, created_at, updated_at, id_contato_cliente = %s AS is_owner
                                     FROM cadu_artifacts WHERE {where} LIMIT 1''', [actor_id, *params])
    if not records:
        raise NotFound("Documento indisponível.")
    document = records[0]
    try:
        from .revisions import history
        document['review_history'] = history(client_id, actor_id, document_id=int(doc_id))
    except Exception:
        document['review_history'] = []
    return document


def document_preview(client_id, actor_id, doc_id):
    """Return a plain-text review projection; never ship stored HTML to the UI."""
    document = get_document(client_id, actor_id, doc_id)
    text = _TAGS.sub(" ", sanitize_html(document.get("html") or ""))
    text = re.sub(r"\s+", " ", text).replace("&nbsp;", " ").strip()
    return {key: document.get(key) for key in ('id', 'title', 'type', 'status', 'updated_at', 'is_owner')}, text[:20000]


def create_document(client_id, actor_id, data):
    title = str(data.get("title") or "Novo documento").strip()[:255]
    kind = str(data.get("type") or "documento").strip()[:40]
    template_id = data.get("template_id") or None
    base = ""
    if template_id:
        available = {item["id"]: item for item in templates(client_id)}
        try:
            template_id = int(template_id)
        except (TypeError, ValueError):
            raise BadRequest("Template inválido.")
        if template_id not in available:
            raise NotFound("Template indisponível.")
        base = available[template_id].get("html") or ""
    html = sanitize_html(data.get("html", base))
    project_id = data.get('project_id') or None
    if project_id:
        project = repository.rows('''SELECT id FROM cadu_ci_projetos
                                      WHERE id = %s AND id_cliente = %s AND status <> 'arquivado' LIMIT 1''',
                                  (str(project_id), client_id))
        if not project:
            raise NotFound('Projeto indisponível para receber este documento.')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_artifacts
                (id_cliente, id_contato_cliente, projeto_id, titulo, tipo, status, conteudo_html, template_id, share_enabled)
                VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s, FALSE) RETURNING id''',
                (client_id, actor_id, project_id, title, kind, html, template_id))
            doc_id = cur.fetchone()["id"]
        conn.commit()
        return get_document(client_id, actor_id, doc_id)
    except Exception:
        conn.rollback()
        raise


def save_document(client_id, actor_id, doc_id, data, *, expected_updated_at=None):
    current = get_document(client_id, actor_id, doc_id)
    if not current["is_owner"]:
        raise BadRequest("Somente o autor pode editar este documento.")
    allowed_status = {"draft", "published", "archived"}
    status = str(data.get("status", current["status"]))
    if status not in allowed_status:
        raise BadRequest("Status inválido.")
    title = str(data.get("title", current["title"]) or "").strip()[:255]
    if not title:
        raise BadRequest("Informe o título.")
    html = sanitize_html(data.get("html", current.get("html") or ""))
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_artifacts SET titulo = %s, status = %s, conteudo_html = %s,
                           updated_at = NOW() WHERE id = %s AND id_cliente = %s AND id_contato_cliente = %s
                             AND (%s IS NULL OR updated_at IS NOT DISTINCT FROM %s) RETURNING id''',
                        (title, status, html, doc_id, client_id, actor_id, expected_updated_at, expected_updated_at))
            if not cur.fetchone():
                raise Conflict('O documento foi alterado enquanto a revisão estava em andamento. Atualize e tente novamente.')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_document(client_id, actor_id, doc_id)


def duplicate_document(client_id, actor_id, doc_id):
    source = get_document(client_id, actor_id, doc_id)
    return create_document(client_id, actor_id, {"title": "Cópia de " + source["title"], "type": source["type"],
                                                   "template_id": source.get("template_id"), "html": source.get("html")})


def share_document(client_id, actor_id, doc_id, enabled):
    current = get_document(client_id, actor_id, doc_id)
    if not current["is_owner"]:
        raise BadRequest("Somente o autor pode compartilhar este documento.")
    token = current.get("share_token") or secrets.token_urlsafe(24)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cadu_artifacts SET share_enabled=%s, share_token=%s, updated_at=NOW() WHERE id=%s AND id_cliente=%s AND id_contato_cliente=%s",
                        (bool(enabled), token, doc_id, client_id, actor_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_document(client_id, actor_id, doc_id)


def public_document(token):
    records = repository.rows('''SELECT id, titulo AS title, tipo AS type, status, conteudo_html AS html,
                                        updated_at FROM cadu_artifacts
                                  WHERE share_token = %s AND share_enabled = TRUE AND status = 'published' LIMIT 1''', (token,))
    if not records:
        raise NotFound("Documento não publicado.")
    document = records[0]
    document["html"] = sanitize_html(document.get("html"))
    return document


def export_pdf(document):
    text = _TAGS.sub(" ", document.get("html") or "").replace("&nbsp;", " ")
    stream = BytesIO()
    report = SimpleDocTemplate(stream, pagesize=A4)
    style = getSampleStyleSheet()["BodyText"]
    report.build([Paragraph(escape(document.get("title") or "Documento"), getSampleStyleSheet()["Title"]),
                  Paragraph(escape(text[:100000]), style)])
    return stream.getvalue()
