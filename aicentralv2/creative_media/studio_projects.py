"""Transactional, immutable project revisions on the studio's shared local storage."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager


class RevisionConflict(ValueError):
    pass


@contextmanager
def connection(root):
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(root / 'projects.sqlite3'), timeout=15)
    db.row_factory = sqlite3.Row
    try:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL,
                updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions (
                project_id TEXT NOT NULL, revision INTEGER NOT NULL,
                document TEXT NOT NULL, created_at REAL NOT NULL,
                PRIMARY KEY (project_id, revision));
        ''')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save(root, document, project_id=None, expected_revision=0):
    if not isinstance(document, dict):
        raise ValueError('Projeto inválido.')
    encoded = json.dumps(document, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > 2_000_000:
        raise ValueError('O projeto excede o tamanho permitido.')
    name = str(document.get('name') or 'Novo projeto').strip()[:120]
    ident = project_id or uuid.uuid4().hex
    now = time.time()
    with connection(root) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT revision FROM projects WHERE id=?', (ident,)).fetchone()
        if project_id and row is None:
            raise ValueError('Projeto não encontrado nesta marca.')
        current = row['revision'] if row else 0
        if isinstance(expected_revision, bool) or expected_revision != current:
            raise RevisionConflict('O projeto foi alterado. Reabra a versão salva antes de continuar; sua edição local foi preservada.')
        revision = current + 1
        db.execute('INSERT INTO revisions VALUES (?,?,?,?)', (ident, revision, encoded, now))
        db.execute('INSERT INTO projects VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, revision=excluded.revision, updated_at=excluded.updated_at', (ident, name, revision, now))
    return {'id': ident, 'name': name, 'revision': revision, 'updated_at': now, 'document': document}


def read(root, ident, revision=None):
    with connection(root) as db:
        row = db.execute('SELECT * FROM projects WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise ValueError('Projeto não encontrado nesta marca.')
        target = row['revision'] if revision is None else revision
        saved = db.execute('SELECT * FROM revisions WHERE project_id=? AND revision=?', (ident, target)).fetchone()
        if saved is None:
            raise ValueError('Revisão não encontrada.')
        return {'id': ident, 'revision': target, 'latest_revision': row['revision'], 'document': json.loads(saved['document']), 'updated_at': saved['created_at']}


def listing(root, offset=0):
    with connection(root) as db:
        return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY updated_at DESC LIMIT 50 OFFSET ?', (max(0, offset),))]
