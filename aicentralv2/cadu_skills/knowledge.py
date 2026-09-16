"""Versioned institutional knowledge used by every Cadu solution."""
import re
from pathlib import Path


def _db():
    from ..db import get_db
    return get_db()


def documents():
    try:
        with _db().cursor() as cur:
            cur.execute('''SELECT d.*, COALESCE(v.content, '') AS content, v.source_note, v.model, v.created_at AS version_created_at
                             FROM cadu_knowledge_documents d
                        LEFT JOIN LATERAL (SELECT * FROM cadu_knowledge_document_versions
                                           WHERE document_id = d.id ORDER BY version DESC LIMIT 1) v ON TRUE
                            ORDER BY d.updated_at DESC, d.id DESC''')
            return [dict(row) for row in cur.fetchall()]
    except Exception:
        return []


def save(data, actor_id):
    title = str(data.get('title') or '').strip()[:180]
    content = str(data.get('content') or '').replace('\r\n', '\n').strip()
    kind = str(data.get('kind') or 'markdown')
    source_note = str(data.get('source_note') or '').strip()[:500]
    if not title or len(content) < 20 or kind not in ('markdown', 'csv'):
        raise ValueError('Informe título, formato e ao menos 20 caracteres de conteúdo.')
    raw_id = data.get('id')
    document_id = int(raw_id) if raw_id else None
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:110] or 'base-cadu'
    conn = _db()
    try:
        with conn.cursor() as cur:
            if document_id:
                cur.execute('SELECT id, slug FROM cadu_knowledge_documents WHERE id = %s FOR UPDATE', (document_id,))
                document = cur.fetchone()
                if not document:
                    raise ValueError('Documento não encontrado.')
                cur.execute('SELECT COALESCE(MAX(version), 0) + 1 AS version FROM cadu_knowledge_document_versions WHERE document_id = %s', (document_id,))
                version = cur.fetchone()['version']
                cur.execute('UPDATE cadu_knowledge_documents SET title=%s, kind=%s, updated_by=%s, updated_at=NOW() WHERE id=%s',
                            (title, kind, actor_id, document_id))
            else:
                cur.execute('INSERT INTO cadu_knowledge_documents (slug, title, kind, created_by, updated_by) VALUES (%s,%s,%s,%s,%s) RETURNING id',
                            (slug, title, kind, actor_id, actor_id))
                document_id = cur.fetchone()['id']; version = 1
            cur.execute('''INSERT INTO cadu_knowledge_document_versions (document_id, version, content, source_note, created_by)
                           VALUES (%s,%s,%s,%s,%s)''', (document_id, version, content, source_note, actor_id))
        conn.commit()
        return {'id': document_id, 'version': version}
    except Exception:
        conn.rollback(); raise


def publish(document_id, actor_id):
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COALESCE(MAX(version), 0) AS version FROM cadu_knowledge_document_versions WHERE document_id=%s', (document_id,))
            version = cur.fetchone()['version']
            if not version:
                raise ValueError('Salve uma versão antes de publicar.')
            cur.execute('''UPDATE cadu_knowledge_documents SET status='published', published_version=%s,
                           updated_by=%s, updated_at=NOW() WHERE id=%s RETURNING id''', (version, actor_id, document_id))
            if not cur.fetchone(): raise ValueError('Documento não encontrado.')
        conn.commit(); return version
    except Exception:
        conn.rollback(); raise


def context(query, limit=3):
    """Small, attributable published-only packet for the Cadu chat."""
    terms = ' '.join(str(query or '').split())[:400]
    if not terms:
        return []
    try:
        with _db().cursor() as cur:
            cur.execute('''SELECT d.title, d.kind, LEFT(v.content, 2200) AS content
                             FROM cadu_knowledge_documents d
                             JOIN cadu_knowledge_document_versions v ON v.document_id=d.id AND v.version=d.published_version
                            WHERE d.status='published'
                              AND to_tsvector('portuguese', v.content) @@ plainto_tsquery('portuguese', %s)
                            ORDER BY d.updated_at DESC LIMIT %s''', (terms, limit))
            return [{'fonte': row['title'], 'tipo': row['kind'], 'trecho': row['content']} for row in cur.fetchall()]
    except Exception:
        return []


def install_seed(actor_id):
    """Create editable draft templates once; examples are never published."""
    seed_dir = Path(__file__).with_name('knowledge_seed')
    definitions = (
        ('Centralcomm — identidade e posicionamento', 'markdown', '01-centralcomm-identidade.md'),
        ('Centralcomm — serviços e soluções', 'markdown', '02-servicos-e-solucoes.md'),
        ('Canais, formatos e places', 'csv', '03-canais-formatos-places.csv'),
        ('Audiências e programática', 'csv', '04-audiencias-e-programatica.csv'),
        ('Cases e evidências aprovadas', 'csv', '05-cases-e-evidencias.csv'),
    )
    existing = {str(row.get('title') or '').strip() for row in documents()}
    created = []
    for title, kind, filename in definitions:
        if title in existing:
            continue
        result = save({'title': title, 'kind': kind,
                       'content': (seed_dir / filename).read_text(encoding='utf-8'),
                       'source_note': 'Modelo inicial CentralX — complete, valide e publique.'}, actor_id)
        created.append(result['id'])
    return created
