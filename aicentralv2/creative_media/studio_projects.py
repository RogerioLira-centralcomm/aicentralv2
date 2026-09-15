"""Transactional, immutable project revisions on the studio's shared local storage."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from psycopg.types.json import Json


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


class PostgresProjectRepository:
    """Canonical studio projects store. Kept separate from the local SQLite fallback.

    SQLite remains useful in isolated tests and for reading legacy projects during rollout,
    but production projects must survive worker and web-node changes.
    """

    def __init__(self, conn):
        self.conn = conn

    def listing(self, client_id, offset=0):
        with self.conn.cursor() as cursor:
            cursor.execute('''
                SELECT id::text AS id, name, revision,
                       EXTRACT(EPOCH FROM updated_at) AS updated_at
                  FROM cx_studio_projects
                 WHERE client_id=%s
                 ORDER BY updated_at DESC, id DESC
                 LIMIT 50 OFFSET %s
            ''', (int(client_id), max(0, int(offset))))
            return [dict(row) for row in cursor.fetchall()]

    def import_legacy(self, root, client_id):
        """One-time, per-brand import of the former local SQLite projects."""
        if self.listing(client_id):
            return
        for item in listing(root):
            try:
                document = read(root, item['id'])['document']
                self.save(client_id, document)
            except (ValueError, sqlite3.Error):
                # A corrupt legacy entry must not prevent opening the Studio.
                continue

    def read(self, client_id, ident, revision=None):
        with self.conn.cursor() as cursor:
            cursor.execute('SELECT revision FROM cx_studio_projects WHERE id=%s AND client_id=%s', (ident, int(client_id)))
            project = cursor.fetchone()
            if not project:
                raise ValueError('Projeto não encontrado nesta marca.')
            target = project['revision'] if revision is None else int(revision)
            cursor.execute('''
                SELECT document, EXTRACT(EPOCH FROM created_at) AS updated_at
                  FROM cx_studio_project_revisions
                 WHERE project_id=%s AND revision=%s
            ''', (ident, target))
            saved = cursor.fetchone()
            if not saved:
                raise ValueError('Revisão não encontrada.')
            return {'id': str(ident), 'revision': target, 'latest_revision': project['revision'],
                    'document': saved['document'], 'updated_at': saved['updated_at']}

    def save(self, client_id, document, project_id=None, expected_revision=0):
        if not isinstance(document, dict):
            raise ValueError('Projeto inválido.')
        encoded = json.dumps(document, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 2_000_000:
            raise ValueError('O projeto excede o tamanho permitido.')
        name = str(document.get('name') or 'Novo projeto').strip()[:120]
        ident = project_id or str(uuid.uuid4())
        with self.conn.cursor() as cursor:
            if project_id:
                cursor.execute('''
                    UPDATE cx_studio_projects
                       SET name=%s, revision=revision+1, document=%s, updated_at=NOW()
                     WHERE id=%s AND client_id=%s AND revision=%s
                 RETURNING revision, EXTRACT(EPOCH FROM updated_at) AS updated_at
                ''', (name, Json(document), ident, int(client_id), expected_revision))
                row = cursor.fetchone()
                if not row:
                    cursor.execute('SELECT 1 FROM cx_studio_projects WHERE id=%s AND client_id=%s', (ident, int(client_id)))
                    if cursor.fetchone():
                        raise RevisionConflict('O projeto foi alterado. Reabra a versão salva antes de continuar; sua edição local foi preservada.')
                    raise ValueError('Projeto não encontrado nesta marca.')
            else:
                if expected_revision not in (0, None):
                    raise RevisionConflict('O projeto foi alterado. Reabra a versão salva antes de continuar; sua edição local foi preservada.')
                cursor.execute('''
                    INSERT INTO cx_studio_projects (id, client_id, name, revision, document)
                    VALUES (%s, %s, %s, 1, %s)
                    RETURNING revision, EXTRACT(EPOCH FROM updated_at) AS updated_at
                ''', (ident, int(client_id), name, Json(document)))
                row = cursor.fetchone()
            cursor.execute('''
                INSERT INTO cx_studio_project_revisions (project_id, revision, document)
                VALUES (%s, %s, %s)
            ''', (ident, row['revision'], Json(document)))
        self.conn.commit()
        return {'id': str(ident), 'name': name, 'revision': row['revision'], 'updated_at': row['updated_at'], 'document': document}
