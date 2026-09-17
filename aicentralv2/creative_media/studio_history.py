"""Persistência do histórico de direções e itens criativos de um projeto."""
from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json


class StudioCreationHistory:
    def __init__(self, connection):
        self.connection = connection

    def start(self, project_id, client_id, user_id, prompt, context, requested_count):
        run_id = str(uuid4())
        with self.connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cx_studio_creation_runs
                    (id, project_id, client_id, user_id, prompt, context, requested_count)
                SELECT %s, id, client_id, %s, %s, %s, %s
                  FROM cx_studio_projects WHERE id=%s AND client_id=%s
                RETURNING id::text AS id
            ''', (run_id, int(user_id), str(prompt or ''), Json(context or {}), int(requested_count), project_id, int(client_id)))
            row = cursor.fetchone()
        self.connection.commit()
        if not row:
            raise ValueError('Projeto não encontrado nesta marca.')
        return row['id']

    def add_references(self, project_id, client_id, user_id, references):
        references = references if isinstance(references, list) else []
        with self.connection.cursor() as cursor:
            for reference in references[:2]:
                if not isinstance(reference, dict):
                    continue
                asset_url = str(reference.get('url') or '')[:2000]
                if not asset_url:
                    continue
                cursor.execute('''
                    INSERT INTO cx_studio_project_items
                        (id, project_id, client_id, user_id, kind, title, asset_url, source_type, metadata)
                    SELECT %s, id, client_id, %s, 'reference', %s, %s, 'library', %s
                      FROM cx_studio_projects WHERE id=%s AND client_id=%s
                ''', (str(uuid4()), int(user_id), str(reference.get('name') or 'Referência visual')[:160], asset_url,
                      Json({'library_id': str(reference.get('id') or '')[:120]}), project_id, int(client_id)))
        self.connection.commit()

    def complete(self, run_id, project_id, client_id, user_id, result, charged_credits):
        directions = result.get('directions') if isinstance(result, dict) else []
        directions = directions if isinstance(directions, list) else []
        with self.connection.cursor() as cursor:
            cursor.execute('''
                UPDATE cx_studio_creation_runs SET returned_count=%s, model=%s,
                    charged_credits=%s, status='completed', completed_at=NOW()
                WHERE id=%s AND project_id=%s AND client_id=%s
            ''', (len(directions), str(result.get('model') or '')[:180], int(charged_credits or 0), run_id, project_id, int(client_id)))
            for position, direction in enumerate(directions, start=1):
                direction_id = str(uuid4())
                title = str(direction.get('title') or '')[:120]
                summary = str(direction.get('summary') or '')
                prompt = str(direction.get('prompt') or '')
                cursor.execute('''
                    INSERT INTO cx_studio_creation_directions
                        (id, run_id, project_id, position, title, summary, prompt)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (direction_id, run_id, project_id, position, title, summary, prompt))
                cursor.execute('''
                    INSERT INTO cx_studio_project_items
                        (id, project_id, direction_id, client_id, user_id, kind, title, source_type, metadata)
                    VALUES (%s, %s, %s, %s, %s, 'direction', %s, 'studio_create', %s)
                ''', (str(uuid4()), project_id, direction_id, int(client_id), int(user_id), title, Json({
                    'run_id': run_id, 'position': position, 'summary': summary, 'prompt': prompt,
                })))
                direction['id'] = direction_id
        self.connection.commit()

    def select_direction(self, direction_id, project_id, client_id):
        with self.connection.cursor() as cursor:
            cursor.execute('''
                UPDATE cx_studio_creation_directions d SET selected_at=NOW()
                  FROM cx_studio_creation_runs r
                 WHERE d.id=%s AND d.run_id=r.id AND d.project_id=%s AND r.client_id=%s
                RETURNING d.id::text AS id
            ''', (direction_id, project_id, int(client_id)))
            row = cursor.fetchone()
        self.connection.commit()
        if not row:
            raise ValueError('Direção não encontrada neste projeto.')
        return row['id']

    def add_item(self, project_id, client_id, user_id, kind, title, asset_url, metadata=None):
        if kind not in {'image', 'video', 'reference'}:
            raise ValueError('Tipo de item inválido.')
        asset_url = str(asset_url or '').strip()[:2000]
        if not asset_url:
            raise ValueError('Escolha um ativo para vincular ao projeto.')
        with self.connection.cursor() as cursor:
            cursor.execute('''
                SELECT id::text AS id FROM cx_studio_project_items
                 WHERE project_id=%s AND client_id=%s AND kind=%s AND asset_url=%s
                 ORDER BY created_at DESC LIMIT 1
            ''', (project_id, int(client_id), kind, asset_url))
            existing = cursor.fetchone()
            if existing:
                return existing['id']
            cursor.execute('''
                INSERT INTO cx_studio_project_items
                    (id, project_id, client_id, user_id, kind, title, asset_url, source_type, metadata)
                SELECT %s, id, client_id, %s, %s, %s, %s, 'studio_stage', %s
                  FROM cx_studio_projects WHERE id=%s AND client_id=%s
                RETURNING id::text AS id
            ''', (str(uuid4()), int(user_id), kind, str(title or 'Ativo do projeto')[:160], asset_url,
                  Json(metadata if isinstance(metadata, dict) else {}), project_id, int(client_id)))
            row = cursor.fetchone()
        self.connection.commit()
        if not row:
            raise ValueError('Projeto não encontrado nesta marca.')
        return row['id']

    def fail(self, run_id, project_id, client_id, message):
        with self.connection.cursor() as cursor:
            cursor.execute('''
                UPDATE cx_studio_creation_runs SET status='failed', error_message=%s, completed_at=NOW()
                WHERE id=%s AND project_id=%s AND client_id=%s
            ''', (str(message or 'Falha na geração.')[:1200], run_id, project_id, int(client_id)))
        self.connection.commit()

    def history(self, project_id, client_id, limit=30):
        limit = max(1, min(int(limit), 100))
        with self.connection.cursor() as cursor:
            cursor.execute('''
                SELECT r.id::text AS id, r.prompt, r.context, r.requested_count, r.returned_count,
                       r.model, r.charged_credits, r.status, r.error_message,
                       EXTRACT(EPOCH FROM r.created_at) AS created_at,
                       COALESCE(jsonb_agg(jsonb_build_object(
                           'id', d.id::text, 'position', d.position, 'title', d.title,
                           'summary', d.summary, 'prompt', d.prompt,
                           'selected_at', EXTRACT(EPOCH FROM d.selected_at)
                       ) ORDER BY d.position) FILTER (WHERE d.id IS NOT NULL), '[]'::jsonb) AS directions
                FROM cx_studio_creation_runs r
                LEFT JOIN cx_studio_creation_directions d ON d.run_id=r.id
                WHERE r.project_id=%s AND r.client_id=%s
                GROUP BY r.id ORDER BY r.created_at DESC LIMIT %s
            ''', (project_id, int(client_id), limit))
            runs = [dict(row) for row in cursor.fetchall()]
            cursor.execute('''
                SELECT id::text AS id, direction_id::text AS direction_id, kind, title, asset_url,
                       source_type, metadata, EXTRACT(EPOCH FROM created_at) AS created_at
                FROM cx_studio_project_items WHERE project_id=%s AND client_id=%s
                ORDER BY created_at DESC LIMIT %s
            ''', (project_id, int(client_id), limit))
            items = [dict(row) for row in cursor.fetchall()]
        return {'runs': runs, 'items': items}

    def library_sessions(self, client_id, limit=50):
        """Return only the project-to-asset links needed by the library shelf."""
        limit = max(1, min(int(limit), 100))
        with self.connection.cursor() as cursor:
            cursor.execute('''
                SELECT p.id::text AS id, p.name,
                       EXTRACT(EPOCH FROM p.updated_at) AS updated_at,
                       COALESCE(jsonb_agg(i.asset_url ORDER BY i.created_at DESC)
                         FILTER (WHERE i.asset_url IS NOT NULL AND i.asset_url <> ''), '[]'::jsonb) AS assets
                  FROM cx_studio_projects p
             LEFT JOIN cx_studio_project_items i
                    ON i.project_id=p.id AND i.client_id=p.client_id
                 WHERE p.client_id=%s
              GROUP BY p.id, p.name, p.updated_at
              ORDER BY p.updated_at DESC, p.id DESC
                 LIMIT %s
            ''', (int(client_id), limit))
            return [dict(row) for row in cursor.fetchall()]
