"""Versioned institutional knowledge used by every Cadu solution."""
import re
from pathlib import Path


def clean_rag_content(content):
    """Normalize editorial text before it becomes a global knowledge version.

    This is deliberately deterministic: it does not call an LLM, create
    embeddings or rewrite factual content. Headings, lists, tables, glossary
    rows and FAQ answers remain intact so the same text can be audited later.
    """
    value = str(content or '').replace('\ufeff', '').replace('\u200b', '')
    value = value.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not value:
        return ''

    lines = []
    blank = False
    for raw_line in value.split('\n'):
        line = re.sub(r'[ \t]+$', '', raw_line).strip() if raw_line.strip() else ''
        if not line:
            if not blank:
                lines.append('')
            blank = True
            continue
        lines.append(line)
        blank = False

    value = '\n'.join(lines).strip()
    # Keep Markdown readable for both lexical search and future chunking.
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value


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
    kind = str(data.get('kind') or 'markdown')
    content = clean_rag_content(data.get('content')) if kind == 'markdown' else str(data.get('content') or '').replace('\r\n', '\n').strip()
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
    """Create editable draft templates once; examples are never published.

    The global media package is intentionally installed as drafts in the same
    institutional knowledge base. It is not project knowledge and it is never
    published by this helper.
    """
    seed_dir = Path(__file__).with_name('knowledge_seed')
    definitions = (
        ('Centralcomm — identidade e posicionamento', 'markdown', '01-centralcomm-identidade.md'),
        ('Centralcomm — serviços e soluções', 'markdown', '02-servicos-e-solucoes.md'),
        ('Canais, formatos e places', 'csv', '03-canais-formatos-places.csv'),
        ('Audiências e programática', 'csv', '04-audiencias-e-programatica.csv'),
        ('Cases e evidências aprovadas', 'csv', '05-cases-e-evidencias.csv'),
    )
    global_rag_dir = Path(__file__).resolve().parents[2] / 'docs' / 'rag'
    definitions += (
        ('RAG Global — Glossário de marketing e mídia', 'markdown', global_rag_dir / '01-glossario-marketing-midia.md'),
        ('RAG Global — Tipos de mídia e linguagem técnica', 'markdown', global_rag_dir / '02-tipos-de-midia-e-linguagem-tecnica.md'),
        ('RAG Global — Métodos de investimento em mídia', 'markdown', global_rag_dir / '03-metodos-de-investimento-em-midia.md'),
        ('RAG Global — Balanceamento multicanal e estratégia', 'markdown', global_rag_dir / '04-balanceamento-multicanal-e-estrategia.md'),
    )
    existing = {str(row.get('title') or '').strip() for row in documents()}
    created = []
    for title, kind, filename in definitions:
        if title in existing:
            continue
        source = Path(filename)
        if not source.is_file():
            continue
        result = save({'title': title, 'kind': kind,
                       'content': (source if source.is_absolute() else seed_dir / source).read_text(encoding='utf-8'),
                       'source_note': ('RAG Global do Cadu — pacote editorial v1; rascunho para revisão, '
                                       'validação de fontes e publicação manual.' if source.is_absolute() else
                                       'Modelo inicial CentralX — complete, valide e publique.')}, actor_id)
        created.append(result['id'])
    return created
