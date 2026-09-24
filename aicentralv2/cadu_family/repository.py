"""Narrow projections of existing data. Query errors must never grant access."""
import json
from uuid import uuid4
from urllib.parse import urlparse

from ..db import get_db
from flask import g, current_app
from psycopg.types.json import Json
from ..product_domains import product_url
from ..smart_planner.logos import public_logo


def family_table_available(name):
    """Inspect schema without creating it; do not swallow connectivity errors."""
    if name not in {'cadu_family_client_access', 'cadu_family_entity_links', 'cadu_family_conversation_context',
                    'cadu_family_chat_uploads', 'cadu_family_project_brands', 'cadu_family_project_visibility',
                    'cadu_family_project_access', 'cadu_user_memories',
                    'cadu_working_memories', 'cadu_conversation_memory_state',
                    'cadu_visual_identity_versions',
                    'cadu_conversation_organization', 'cadu_conversation_sections',
                    'cadu_conversation_shares'}:
        raise ValueError('Unsupported family table')
    cache = g.setdefault('family_schema', {})
    if name not in cache:
        result = rows('SELECT to_regclass(%s) IS NOT NULL AS available', ('public.' + name,))
        cache[name] = bool(result and result[0]['available'])
    return cache[name]


def rows(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def actor(user_id):
    result = rows('''SELECT u.id_contato_cliente AS id, u.pk_id_tbl_cliente AS organization_id,
                            u.nome_completo AS name, u.email, u.telefone AS phone,
                            cargo.descricao AS role_name,
                            u.pk_id_tbl_cargo AS role_id, u.user_type, u.is_finance_admin
                       FROM tbl_contato_cliente u
                  LEFT JOIN tbl_cargo_contato cargo ON cargo.id_cargo_contato = u.pk_id_tbl_cargo
                      WHERE u.id_contato_cliente = %s AND u.status = TRUE
                        AND EXISTS (SELECT 1 FROM tbl_cliente c
                                     WHERE c.id_cliente = u.pk_id_tbl_cliente AND c.status = TRUE)''', (user_id,))
    return result[0] if result else None


def clients(user):
    if not family_table_available('cadu_family_client_access'):
        # Absence of migration never implies agency access to other clients.
        return rows('''SELECT id_cliente AS id, nome_fantasia AS name, %s AS role
                         FROM tbl_cliente WHERE id_cliente = %s AND status = TRUE''',
                    (account_role(user), user['organization_id']))
    return rows('''SELECT c.id_cliente AS id, c.nome_fantasia AS name,
                         CASE WHEN c.id_cliente = %s THEN %s ELSE a.role END AS role
                    FROM tbl_cliente c
               LEFT JOIN cadu_family_client_access a
                      ON a.client_id = c.id_cliente AND a.organization_id = %s
                     AND a.user_id = %s AND a.revoked_at IS NULL
                   WHERE c.status = TRUE AND (c.id_cliente = %s OR a.client_id IS NOT NULL)
                ORDER BY c.nome_fantasia, c.id_cliente''',
                (user['organization_id'], account_role(user),
                 user['organization_id'], user['id'], user['organization_id']))


def account_role(user):
    # Cargo is a professional title (e.g. media analyst), never an authorization role.
    role = user.get('user_type')
    if role in ('admin', 'superadmin'):
        return 'admin'
    return 'viewer' if role == 'viewer' else 'member'


def entities(client_id):
    # Qualified references retain legacy IDs and avoid collisions between tables.
    items = rows('''SELECT 'ci:' || id::text AS ref, nome AS name,
                         CASE WHEN tipo = 'marca' THEN 'brand' ELSE 'project' END AS kind,
                         'ci' AS source, NULL::text AS logo_url
                    FROM cadu_ci_projetos WHERE id_cliente = %s AND status <> 'deletado'
                  UNION ALL
                  SELECT 'projects:' || id::text, nome, 'project', 'projects', NULL::text
                    FROM cadu_projetos WHERE id_cliente = %s AND deleted_at IS NULL
                  UNION ALL
                  SELECT 'studio:' || id::text, name, 'brand', 'studio',
                         COALESCE(logo_upload_path, logo_url)
                    FROM cx_clients WHERE crm_client_id = %s
                  ORDER BY 2''', (client_id, client_id, client_id))
    for item in items:
        item['logo_url'] = public_logo(item.get('logo_url') or '')
    return items


def entity_links(client_id):
    if not family_table_available('cadu_family_entity_links'):
        return []
    return rows('''SELECT source || ':' || source_id AS ref,
                         canonical_source || ':' || canonical_id AS canonical_ref
                    FROM cadu_family_entity_links WHERE client_id = %s''', (client_id,))


def project_brand_links(client_id):
    """Return explicit business relationships; aliases stay in entity_links."""
    if not family_table_available('cadu_family_project_brands'):
        return []
    return rows('''SELECT project_ref, brand_ref
                    FROM cadu_family_project_brands
                   WHERE client_id = %s
                ORDER BY project_ref, brand_ref''', (client_id,))


def set_project_brand_link(client_id, user_id, project_ref, brand_ref, linked):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if linked:
                cur.execute('''INSERT INTO cadu_family_project_brands
                               (client_id, project_ref, brand_ref, created_by)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (client_id, project_ref, brand_ref) DO NOTHING''',
                            (client_id, project_ref, brand_ref, user_id))
            else:
                cur.execute('''DELETE FROM cadu_family_project_brands
                                WHERE client_id = %s AND project_ref = %s AND brand_ref = %s''',
                            (client_id, project_ref, brand_ref))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def project_access(client_id, project_ref):
    if not family_table_available('cadu_family_project_access'):
        return []
    return rows('''SELECT a.user_id, a.role, a.source, a.granted_by, a.created_at,
                          u.nome_completo AS name, u.email, u.status
                     FROM cadu_family_project_access a
                LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = a.user_id
                    WHERE a.client_id = %s AND a.project_ref = %s AND a.revoked_at IS NULL
                 ORDER BY CASE a.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,
                          LOWER(COALESCE(u.nome_completo, '')), a.user_id''', (client_id, project_ref))


def project_visibility(client_id, project_ref):
    if not family_table_available('cadu_family_project_visibility'):
        return {'visibility': 'private'}
    result = rows('''SELECT visibility, updated_by, updated_at
                       FROM cadu_family_project_visibility
                      WHERE client_id = %s AND project_ref = %s''', (client_id, project_ref))
    return result[0] if result else {'visibility': 'private'}


def project_user_can_view(client_id, project_ref, user_id):
    """Project-level authorization; absence of a row never grants access."""
    actor_row = actor(user_id)
    if actor_row and actor_row.get('organization_id') == client_id and account_role(actor_row) == 'admin':
        return True
    visibility = project_visibility(client_id, project_ref).get('visibility', 'private')
    if visibility == 'team':
        return bool(actor_row and actor_row.get('organization_id') == client_id)
    if not family_table_available('cadu_family_project_access'):
        return False
    return bool(rows('''SELECT 1 FROM cadu_family_project_access
                         WHERE client_id = %s AND project_ref = %s AND user_id = %s
                           AND revoked_at IS NULL LIMIT 1''', (client_id, project_ref, user_id)))


def seed_project_owner(client_id, project_ref, user_id):
    if not family_table_available('cadu_family_project_access'):
        return
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_family_project_access
                              (client_id, project_ref, user_id, role, source, granted_by)
                           VALUES (%s, %s, %s, 'owner', 'owner', %s)
                           ON CONFLICT (client_id, project_ref, user_id) DO NOTHING''',
                        (client_id, project_ref, user_id, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def set_project_visibility(client_id, user_id, project_ref, visibility):
    if visibility not in {'private', 'team', 'restricted'}:
        raise ValueError('Visibilidade inválida.')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_family_project_visibility
                              (client_id, project_ref, visibility, updated_by)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (client_id, project_ref) DO UPDATE SET
                              visibility = EXCLUDED.visibility, updated_by = EXCLUDED.updated_by,
                              updated_at = NOW()''', (client_id, project_ref, visibility, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def grant_project_access(client_id, project_ref, user_id, role, granted_by):
    if role not in {'admin', 'editor', 'member', 'viewer'}:
        raise ValueError('Papel de projeto inválido.')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_family_project_access
                              (client_id, project_ref, user_id, role, source, granted_by)
                           VALUES (%s, %s, %s, %s, 'direct', %s)
                           ON CONFLICT (client_id, project_ref, user_id) DO UPDATE SET
                              role = EXCLUDED.role, source = 'direct', granted_by = EXCLUDED.granted_by,
                              revoked_at = NULL, updated_at = NOW()''',
                        (client_id, project_ref, user_id, role, granted_by))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def revoke_project_access(client_id, project_ref, user_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_family_project_access SET revoked_at = NOW(), updated_at = NOW()
                           WHERE client_id = %s AND project_ref = %s AND user_id = %s''',
                        (client_id, project_ref, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def visual_identity_versions(client_id, owner_type, owner_ref, visual_type=None):
    if not family_table_available('cadu_visual_identity_versions'):
        return []
    params = [client_id, owner_type, owner_ref]
    visual_filter = ''
    if visual_type:
        visual_filter = ' AND visual_type = %s'
        params.append(visual_type)
    return rows(f'''SELECT id, owner_type, owner_ref, source_brand_ref, visual_type, version,
                           status, image_url, vector_url, prompt, model, token_usage,
                           contrast_metadata, created_by, approved_by, created_at, approved_at
                      FROM cadu_visual_identity_versions
                     WHERE client_id = %s AND owner_type = %s AND owner_ref = %s{visual_filter}
                  ORDER BY visual_type, version DESC, id DESC''', tuple(params))


def create_visual_identity_version(client_id, owner_type, owner_ref, visual_type, user_id,
                                   *, source_brand_ref=None, prompt='', model='', token_usage=0):
    if owner_type not in {'brand', 'project'} or visual_type not in {'icon', 'avatar', 'background', 'hero'}:
        raise ValueError('Identidade visual inválida.')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                        (f'{client_id}:{owner_type}:{owner_ref}:{visual_type}',))
            cur.execute('''SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                             FROM cadu_visual_identity_versions
                            WHERE client_id = %s AND owner_type = %s AND owner_ref = %s AND visual_type = %s''',
                        (client_id, owner_type, owner_ref, visual_type))
            version = int((cur.fetchone() or {}).get('next_version') or 1)
            cur.execute('''INSERT INTO cadu_visual_identity_versions
                              (client_id, owner_type, owner_ref, source_brand_ref, visual_type, version,
                               status, prompt, model, token_usage, created_by)
                           VALUES (%s,%s,%s,%s,%s,%s,'processing',%s,%s,%s,%s)
                        RETURNING id, version, status''',
                        (client_id, owner_type, owner_ref, source_brand_ref, visual_type, version,
                         prompt, model, int(token_usage or 0), user_id))
            result = dict(cur.fetchone())
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def update_visual_identity_version(client_id, version_id, *, status=None, image_url=None,
                                   vector_url=None, contrast_metadata=None, token_usage=None,
                                   approved_by=None):
    changes, params = [], []
    if status is not None:
        if status not in {'draft', 'processing', 'ready', 'approved', 'archived', 'failed'}:
            raise ValueError('Status visual inválido.')
        changes.append('status = %s'); params.append(status)
    for column, value in (('image_url', image_url), ('vector_url', vector_url),
                          ('contrast_metadata', contrast_metadata), ('token_usage', token_usage)):
        if value is not None:
            changes.append(f'{column} = %s'); params.append(Json(value) if column == 'contrast_metadata' else value)
    if approved_by is not None:
        changes.extend(['approved_by = %s', 'approved_at = NOW()']); params.append(approved_by)
    if not changes:
        return None
    changes.append('updated_at = NOW()')
    params.extend([client_id, version_id])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''UPDATE cadu_visual_identity_versions SET {', '.join(changes)}
                             WHERE client_id = %s AND id = %s
                         RETURNING id, owner_type, owner_ref, visual_type, version, status,
                                   image_url, vector_url, contrast_metadata, approved_by, approved_at''', tuple(params))
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        raise


def profile_update(user_id, name, phone):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE tbl_contato_cliente SET nome_completo = %s, telefone = %s
                           WHERE id_contato_cliente = %s AND status = TRUE''', (name, phone, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def team(organization_id):
    return rows('''SELECT id_contato_cliente AS id, nome_completo AS name, email, status
                    FROM tbl_contato_cliente WHERE pk_id_tbl_cliente = %s
                ORDER BY nome_completo''', (organization_id,))


def plan(organization_id):
    result = rows('''SELECT plan_type, plan_status, tokens_monthly_limit
                      FROM cadu_client_plans WHERE id_cliente = %s AND plan_status = 'active'
                      LIMIT 1''', (organization_id,))
    return result[0] if result else {'plan_type': 'free', 'plan_status': 'active', 'tokens_monthly_limit': 0}


def consumption(organization_id):
    return rows('''SELECT DATE_TRUNC('month', created_at) AS month, SUM(quantidade) AS tokens
                    FROM cadu_token_usage WHERE id_cliente = %s
                GROUP BY 1 ORDER BY 1 DESC LIMIT 12''', (organization_id,))


def conversations(user_id):
    return rows('''SELECT id, titulo AS title, updated_at, total_mensagens AS message_count
                    FROM cadu_conversations WHERE id_contato_cliente = %s
                ORDER BY updated_at DESC LIMIT 100''', (user_id,))


def conversation_history(user, client_id, limit=20, offset=0, query='', archived=False):
    statuses = ['arquivada', 'archived'] if archived else ['ativa', 'active']
    if not family_table_available('cadu_family_conversation_context'):
        return rows('''SELECT id, titulo AS title, updated_at, NULL AS profile,
                              CASE WHEN projeto_id IS NOT NULL THEN 'ci:' || projeto_id::text END AS project_ref,
                              NULL AS brand_ref
                         FROM cadu_conversations
                        WHERE id_contato_cliente = %s AND id_cliente = %s AND titulo ILIKE %s AND status = ANY(%s)
                     ORDER BY updated_at DESC, id DESC LIMIT %s OFFSET %s''',
                    (user['id'], client_id, '%' + query + '%', statuses, limit, offset))
    return rows('''SELECT c.id, c.titulo AS title, c.updated_at, x.profile,
                         COALESCE(x.project_ref, CASE WHEN c.projeto_id IS NOT NULL
                                  THEN 'ci:' || c.projeto_id::text END) AS project_ref,
                         x.brand_ref
                    FROM cadu_conversations c
               LEFT JOIN cadu_family_conversation_context x ON x.conversation_id = c.id
                   WHERE c.id_contato_cliente = %s AND c.id_cliente = %s AND c.titulo ILIKE %s AND c.status = ANY(%s)
                     AND (x.conversation_id IS NULL OR
                          (x.user_id = %s AND x.organization_id = %s AND x.client_id = %s))
                ORDER BY c.updated_at DESC, c.id DESC LIMIT %s OFFSET %s''',
                (user['id'], client_id, '%' + query + '%', statuses, user['id'], user['organization_id'], client_id, limit, offset))


def conversation_history_all(user, client_id, query='', limit=500):
    statuses = ['ativa', 'active', 'arquivada', 'archived']
    active_statuses = ['ativa', 'active']
    if not family_table_available('cadu_family_conversation_context'):
        return rows('''SELECT id, titulo AS title, updated_at, status, NULL AS profile,
                              CASE WHEN projeto_id IS NOT NULL THEN 'ci:' || projeto_id::text END AS project_ref,
                              NULL AS brand_ref
                         FROM cadu_conversations
                        WHERE id_contato_cliente = %s AND id_cliente = %s AND titulo ILIKE %s AND status = ANY(%s)
                     ORDER BY CASE WHEN status = ANY(%s) THEN 0 ELSE 1 END, updated_at DESC, id DESC LIMIT %s''',
                    (user['id'], client_id, '%' + query + '%', statuses, active_statuses, limit))
    organization_join = family_table_available('cadu_conversation_organization')
    if not organization_join:
        return rows('''SELECT c.id, c.titulo AS title, c.updated_at, c.status, x.profile,
                         COALESCE(x.project_ref, CASE WHEN c.projeto_id IS NOT NULL
                                  THEN 'ci:' || c.projeto_id::text END) AS project_ref,
                         x.brand_ref,
                         EXISTS (SELECT 1 FROM cadu_family_chat_runs r WHERE r.conversation_id=c.id AND r.status='running') AS running,
                         'recent'::text AS section, FALSE AS automation_enabled, NULL::text AS schedule_label,
                         COALESCE(last_message.role = 'assistant' AND (
                             COALESCE(last_message.metadata->'response'->'blocks', '[]'::jsonb) @> '[{"type":"questions"}]'::jsonb
                             OR COALESCE(last_message.metadata->'response'->'blocks', '[]'::jsonb) @> '[{"type":"question"}]'::jsonb
                             OR COALESCE(last_message.metadata->'response'->'blocks', '[]'::jsonb) @> '[{"type":"decision"}]'::jsonb
                             OR jsonb_array_length(CASE WHEN jsonb_typeof(last_message.metadata->'response'->'questions')='array'
                                                        THEN last_message.metadata->'response'->'questions' ELSE '[]'::jsonb END) > 0
                         ), FALSE) AS awaiting_response
                    FROM cadu_conversations c
               LEFT JOIN cadu_family_conversation_context x ON x.conversation_id = c.id
               LEFT JOIN LATERAL (SELECT role, metadata FROM cadu_conversation_messages
                                   WHERE conversation_id = c.id AND role IN ('user', 'assistant')
                                   ORDER BY conversation_sequence DESC NULLS LAST, created_at DESC, id DESC LIMIT 1) last_message ON TRUE
                   WHERE c.id_contato_cliente = %s AND c.id_cliente = %s AND c.titulo ILIKE %s AND c.status = ANY(%s)
                     AND (x.conversation_id IS NULL OR
                          (x.user_id = %s AND x.organization_id = %s AND x.client_id = %s))
                ORDER BY CASE WHEN c.status = ANY(%s) THEN 0 ELSE 1 END, c.updated_at DESC, c.id DESC LIMIT %s''',
                (user['id'], client_id, '%' + query + '%', statuses, user['id'], user['organization_id'], client_id,
                 active_statuses, limit))
    return rows('''SELECT c.id, c.titulo AS title, c.updated_at, c.status, x.profile,
                         COALESCE(x.project_ref, CASE WHEN c.projeto_id IS NOT NULL
                                  THEN 'ci:' || c.projeto_id::text END) AS project_ref,
                         x.brand_ref,
                         EXISTS (SELECT 1 FROM cadu_family_chat_runs r WHERE r.conversation_id=c.id AND r.status='running') AS running,
                         COALESCE(o.section, 'recent') AS section,
                         o.custom_section_id::text AS custom_section_id,
                         s.name AS custom_section_name,
                         COALESCE(o.is_unread, FALSE) AS is_unread,
                         COALESCE(o.automation_enabled, FALSE) AS automation_enabled,
                         o.schedule_label,
                         COALESCE(last_message.role = 'assistant' AND (
                             COALESCE(last_message.metadata->'response'->'blocks', '[]'::jsonb) @> '[{"type":"questions"}]'::jsonb
                             OR COALESCE(last_message.metadata->'response'->'blocks', '[]'::jsonb) @> '[{"type":"question"}]'::jsonb
                             OR COALESCE(last_message.metadata->'response'->'blocks', '[]'::jsonb) @> '[{"type":"decision"}]'::jsonb
                             OR jsonb_array_length(CASE WHEN jsonb_typeof(last_message.metadata->'response'->'questions')='array'
                                                        THEN last_message.metadata->'response'->'questions' ELSE '[]'::jsonb END) > 0
                         ), FALSE) AS awaiting_response
                    FROM cadu_conversations c
               LEFT JOIN cadu_family_conversation_context x ON x.conversation_id = c.id
               LEFT JOIN cadu_conversation_organization o ON o.conversation_id = c.id
               LEFT JOIN cadu_conversation_sections s ON s.id = o.custom_section_id
               LEFT JOIN LATERAL (SELECT role, metadata FROM cadu_conversation_messages
                                   WHERE conversation_id = c.id AND role IN ('user', 'assistant')
                                   ORDER BY conversation_sequence DESC NULLS LAST, created_at DESC, id DESC LIMIT 1) last_message ON TRUE
                   WHERE c.id_contato_cliente = %s AND c.id_cliente = %s AND c.titulo ILIKE %s AND c.status = ANY(%s)
                     AND (x.conversation_id IS NULL OR
                          (x.user_id = %s AND x.organization_id = %s AND x.client_id = %s))
                ORDER BY CASE WHEN c.status = ANY(%s) THEN 0 ELSE 1 END,
                         CASE WHEN COALESCE(o.section, 'recent') = 'pinned' THEN 0 ELSE 1 END,
                         c.updated_at DESC, c.id DESC LIMIT %s''',
                (user['id'], client_id, '%' + query + '%', statuses, user['id'], user['organization_id'], client_id,
                 active_statuses, limit))


def organize_conversation(user_id, client_id, conversation_id, section, automation_enabled=None,
                          custom_section_id=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_conversation_organization
                (conversation_id, user_id, client_id, section, automation_enabled, custom_section_id)
                SELECT id, %s, %s, %s, %s, %s FROM cadu_conversations
                 WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s
                ON CONFLICT (conversation_id) DO UPDATE SET
                    section=EXCLUDED.section,
                    custom_section_id=EXCLUDED.custom_section_id,
                    automation_enabled=CASE WHEN EXCLUDED.section='automation'
                        THEN COALESCE(%s, cadu_conversation_organization.automation_enabled)
                        ELSE FALSE END,
                    updated_at=NOW()
                RETURNING conversation_id, section, custom_section_id, automation_enabled, schedule_label''',
                (user_id, client_id, section, bool(automation_enabled) if automation_enabled is not None else False,
                 custom_section_id, conversation_id, user_id, client_id, automation_enabled))
            result = cur.fetchone()
        conn.commit()
        return dict(result) if result else None
    except Exception:
        conn.rollback()
        raise


def conversation_sections(user_id, organization_id, client_id):
    return rows('''SELECT id::text AS id, name, sort_order
                     FROM cadu_conversation_sections
                    WHERE user_id=%s AND organization_id=%s AND client_id=%s
                 ORDER BY sort_order, lower(name), id''', (user_id, organization_id, client_id))


def create_conversation_section(user_id, organization_id, client_id, name):
    section_id = str(uuid4())
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_conversation_sections
                               (id, organization_id, client_id, user_id, name)
                           VALUES (%s,%s,%s,%s,%s)
                           RETURNING id::text AS id, name, sort_order''',
                        (section_id, organization_id, client_id, user_id, name))
            result = dict(cur.fetchone())
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def rename_conversation_section(user_id, organization_id, client_id, section_id, name):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_conversation_sections SET name=%s, updated_at=NOW()
                            WHERE id=%s AND user_id=%s AND organization_id=%s AND client_id=%s
                        RETURNING id::text AS id, name, sort_order''',
                        (name, section_id, user_id, organization_id, client_id))
            result = cur.fetchone()
        conn.commit()
        return dict(result) if result else None
    except Exception:
        conn.rollback()
        raise


def delete_conversation_section(user_id, organization_id, client_id, section_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_conversation_organization o
                              SET section='recent', custom_section_id=NULL, updated_at=NOW()
                             FROM cadu_conversations c
                            WHERE o.conversation_id=c.id AND o.custom_section_id=%s
                              AND o.user_id=%s AND o.client_id=%s
                              AND c.id_contato_cliente=%s AND c.id_cliente=%s''',
                        (section_id, user_id, client_id, user_id, client_id))
            cur.execute('''DELETE FROM cadu_conversation_sections
                            WHERE id=%s AND user_id=%s AND organization_id=%s AND client_id=%s
                        RETURNING id''', (section_id, user_id, organization_id, client_id))
            result = cur.fetchone()
        conn.commit()
        return bool(result)
    except Exception:
        conn.rollback()
        raise


def set_conversation_unread(user_id, client_id, conversation_id, unread):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_conversation_organization
                               (conversation_id, user_id, client_id, section, is_unread)
                           SELECT id, %s, %s, 'recent', %s FROM cadu_conversations
                            WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s
                           ON CONFLICT (conversation_id) DO UPDATE SET
                               is_unread=EXCLUDED.is_unread, updated_at=NOW()
                           RETURNING conversation_id, is_unread''',
                        (user_id, client_id, unread, conversation_id, user_id, client_id))
            result = cur.fetchone()
        conn.commit()
        return dict(result) if result else None
    except Exception:
        conn.rollback()
        raise


def move_conversation_project(user, client_id, conversation_id, project_ref):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT id FROM cadu_conversations
                            WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s FOR UPDATE''',
                        (conversation_id, user['id'], client_id))
            if not cur.fetchone():
                conn.rollback()
                return None
            cur.execute('''INSERT INTO cadu_family_conversation_context
                              (conversation_id,user_id,organization_id,client_id,profile,project_ref,brand_ref)
                           VALUES (%s,%s,%s,%s,'workspace',%s,NULL)
                           ON CONFLICT (conversation_id) DO UPDATE SET project_ref=EXCLUDED.project_ref,
                               updated_at=NOW()
                           WHERE cadu_family_conversation_context.user_id=%s
                             AND cadu_family_conversation_context.organization_id=%s
                             AND cadu_family_conversation_context.client_id=%s
                       RETURNING profile, project_ref, brand_ref''',
                        (conversation_id, user['id'], user['organization_id'], client_id, project_ref,
                         user['id'], user['organization_id'], client_id))
            result = cur.fetchone()
            if not result:
                conn.rollback()
                return None
            legacy_project_id = project_ref[3:] if project_ref and project_ref.startswith('ci:') else None
            cur.execute('''UPDATE cadu_conversations SET projeto_id=%s, updated_at=NOW()
                            WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s''',
                        (legacy_project_id, conversation_id, user['id'], client_id))
        conn.commit()
        return dict(result)
    except Exception:
        conn.rollback()
        raise


def fork_conversation(user, client_id, conversation_id):
    conn = get_db()
    fork_id = str(uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT id, titulo, projeto_id FROM cadu_conversations
                            WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s
                              AND status IN ('ativa','active') FOR UPDATE''',
                        (conversation_id, user['id'], client_id))
            source = cur.fetchone()
            if not source:
                conn.rollback()
                return None
            cur.execute('''SELECT 1 FROM cadu_family_chat_runs
                            WHERE conversation_id=%s AND status='running' LIMIT 1''', (conversation_id,))
            if cur.fetchone():
                conn.rollback()
                raise ValueError('running')
            cur.execute('''SELECT profile, project_ref, brand_ref FROM cadu_family_conversation_context
                            WHERE conversation_id=%s AND user_id=%s AND organization_id=%s AND client_id=%s''',
                        (conversation_id, user['id'], user['organization_id'], client_id))
            saved_context = cur.fetchone() or {'profile': 'workspace', 'project_ref': None, 'brand_ref': None}
            title = (str(source['titulo'] or 'Conversa')[:132] + ' — ramificação')[:150]
            cur.execute('''SELECT conversation_sequence FROM cadu_conversation_messages
                            WHERE conversation_id=%s AND role IN ('user','assistant')
                         ORDER BY conversation_sequence DESC NULLS LAST, created_at DESC, id DESC LIMIT 1''',
                        (conversation_id,))
            fork_sequence = (cur.fetchone() or {}).get('conversation_sequence')
            cur.execute('''INSERT INTO cadu_conversations
                              (id,id_cliente,id_contato_cliente,titulo,status,total_mensagens,projeto_id,
                               parent_conversation_id,forked_from_sequence,created_at,updated_at)
                           VALUES (%s,%s,%s,%s,'ativa',0,%s,%s,%s,NOW(),NOW())''',
                        (fork_id, client_id, user['id'], title, source['projeto_id'], conversation_id, fork_sequence))
            cur.execute('''INSERT INTO cadu_family_conversation_context
                              (conversation_id,user_id,organization_id,client_id,profile,project_ref,brand_ref)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                        (fork_id, user['id'], user['organization_id'], client_id, saved_context['profile'],
                         saved_context['project_ref'], saved_context['brand_ref']))
            cur.execute('''INSERT INTO cadu_conversation_organization
                              (conversation_id,user_id,client_id,section)
                           VALUES (%s,%s,%s,'recent')''', (fork_id, user['id'], client_id))
            cur.execute('''SELECT role,content,created_at
                            FROM cadu_conversation_messages
                           WHERE conversation_id=%s AND role IN ('user','assistant')
                           ORDER BY conversation_sequence ASC NULLS FIRST,created_at ASC,id ASC''',
                        (conversation_id,))
            messages = cur.fetchall()
            for message in messages:
                cur.execute('''INSERT INTO cadu_conversation_messages
                                  (id,conversation_id,role,content,files,metadata,created_at)
                               VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                            (str(uuid4()), fork_id, message['role'], message['content'],
                             Json([]), Json({}), message['created_at']))
            cur.execute('''UPDATE cadu_conversations SET total_mensagens=%s,updated_at=NOW()
                            WHERE id=%s''', (len(messages), fork_id))
        conn.commit()
        return {'id': fork_id, 'title': title, 'parent_conversation_id': conversation_id,
                'forked_from_sequence': fork_sequence, 'message_count': len(messages)}
    except Exception:
        conn.rollback()
        raise


def create_conversation_share(user, selected, conversation_id, token_hash):
    share_id = str(uuid4())
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT id FROM cadu_conversations
                            WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s
                              AND status IN ('ativa','active') FOR UPDATE''',
                        (conversation_id, user['id'], selected['client_id']))
            if not cur.fetchone():
                conn.rollback()
                return []
            cur.execute('''UPDATE cadu_conversation_shares SET revoked_at=NOW()
                            WHERE conversation_id=%s AND user_id=%s AND client_id=%s
                              AND revoked_at IS NULL''',
                        (conversation_id, user['id'], selected['client_id']))
            cur.execute('''INSERT INTO cadu_conversation_shares
                               (id,conversation_id,organization_id,client_id,user_id,token_hash)
                           SELECT %s,c.id,%s,%s,%s,%s FROM cadu_conversations c
                            WHERE c.id=%s AND c.id_contato_cliente=%s AND c.id_cliente=%s
                              AND c.status IN ('ativa','active')
                           RETURNING id::text AS id,expires_at''',
                        (share_id, user['organization_id'], selected['client_id'], user['id'], token_hash,
                         conversation_id, user['id'], selected['client_id']))
            result = cur.fetchone()
        conn.commit()
        return [dict(result)] if result else []
    except Exception:
        conn.rollback()
        raise


def revoke_conversation_share(user_id, client_id, conversation_id, share_id=None):
    params = [conversation_id, user_id, client_id]
    share_filter = ''
    if share_id:
        share_filter = ' AND id=%s'
        params.append(share_id)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''UPDATE cadu_conversation_shares SET revoked_at=NOW()
                             WHERE conversation_id=%s AND user_id=%s AND client_id=%s
                               AND revoked_at IS NULL{share_filter}
                         RETURNING id::text AS id''', tuple(params))
            result = [dict(row) for row in cur.fetchall()]
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def public_conversation_share(token_hash):
    share = rows('''SELECT s.id::text AS share_id,c.titulo AS title,c.id AS conversation_id
                      FROM cadu_conversation_shares s
                      JOIN cadu_conversations c ON c.id=s.conversation_id
                     WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>NOW()
                       AND c.status IN ('ativa','active')''', (token_hash,))
    if not share:
        return None
    result = share[0]
    result['messages'] = rows('''SELECT role,content,created_at
                                  FROM cadu_conversation_messages
                                 WHERE conversation_id=%s AND role IN ('user','assistant')
                              ORDER BY conversation_sequence ASC NULLS FIRST,created_at ASC,id ASC''',
                             (result['conversation_id'],))
    return result


def set_conversation_automation(user_id, client_id, conversation_id, enabled):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_conversation_organization o
                              SET automation_enabled=%s, updated_at=NOW()
                             FROM cadu_conversations c
                            WHERE o.conversation_id=c.id AND o.conversation_id=%s
                              AND o.section='automation' AND o.user_id=%s AND o.client_id=%s
                              AND c.id_contato_cliente=%s AND c.id_cliente=%s
                        RETURNING o.conversation_id, o.section, o.automation_enabled, o.schedule_label''',
                        (enabled, conversation_id, user_id, client_id, user_id, client_id))
            result = cur.fetchone()
        conn.commit()
        return dict(result) if result else None
    except Exception:
        conn.rollback()
        raise


def update_conversation(user_id, client_id, conversation_id, title=None, archived=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_conversations
                             SET titulo = COALESCE(%s, titulo),
                                 status = CASE WHEN %s::boolean IS NULL THEN status
                                               WHEN %s THEN 'arquivada' ELSE 'ativa' END,
                                 updated_at = NOW()
                           WHERE id = %s AND id_contato_cliente = %s AND id_cliente = %s
                             AND status IN ('ativa', 'active', 'arquivada', 'archived')
                       RETURNING id, titulo AS title, status''',
                        (title, archived, archived, conversation_id, user_id, client_id))
            result = cur.fetchone()
            if result and archived is True and family_table_available('cadu_conversation_organization'):
                cur.execute('''UPDATE cadu_conversation_organization
                                  SET automation_enabled=FALSE, updated_at=NOW()
                                WHERE conversation_id=%s AND user_id=%s AND client_id=%s''',
                            (conversation_id, user_id, client_id))
            if result and archived is True and family_table_available('cadu_conversation_shares'):
                cur.execute('''UPDATE cadu_conversation_shares SET revoked_at=NOW()
                                WHERE conversation_id=%s AND user_id=%s AND client_id=%s
                                  AND revoked_at IS NULL''', (conversation_id, user_id, client_id))
        conn.commit()
        return dict(result) if result else None
    except Exception:
        conn.rollback()
        raise


def conversation_context(user, client_id, conversation_id):
    if not family_table_available('cadu_family_conversation_context'):
        return None
    records = rows('''SELECT profile, project_ref, brand_ref
                       FROM cadu_family_conversation_context
                      WHERE conversation_id = %s AND user_id = %s
                        AND organization_id = %s AND client_id = %s''',
                   (conversation_id, user['id'], user['organization_id'], client_id))
    return records[0] if records else None


def invoices(organization_id):
    return rows('''SELECT invoice_number AS number, total, status, due_date, paid_at
                    FROM cadu_invoices WHERE id_cliente = %s
                ORDER BY created_at DESC LIMIT 100''', (organization_id,))


def integrations(organization_id):
    return rows('''SELECT platform AS platform, platform_account_name AS account, status, last_sync_at
                    FROM cadu_integrations WHERE client_id = %s
                ORDER BY platform, platform_account_name''', (organization_id,))


def catalog(module, query='', category='', platform='', sort='relevant', format_type='', segment=''):
    search = '%' + query[:100] + '%'
    if module == 'audiencias':
        category = category.strip()[:100] if isinstance(category, str) else ''
        platform = platform.strip()[:100] if isinstance(platform, str) else ''
        sort = sort if sort in {'relevant', 'name'} else 'relevant'
        ordering = 'a.nome, a.id' if sort == 'name' else 'COALESCE(a.relevancia_score, 0) DESC, a.nome, a.id'
        return rows('''SELECT a.id, a.nome AS name, COALESCE(a.descricao_curta, a.descricao) AS description,
                             a.publico_estimado AS audience, a.imagem_url AS image_url,
                             a.perfil_socioeconomico, a.propensao_compra, a.tamanho,
                             a.id_audiencia_plataforma AS platform_audience_id,
                             c.nome AS category, s.nome AS subcategory, p.nome AS platform
                        FROM cadu_audiencias a
                   LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
                   LEFT JOIN cadu_subcategorias s ON s.id = a.subcategoria_id
                   LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                       WHERE a.is_active = TRUE
                         AND (a.nome ILIKE %s OR COALESCE(a.descricao_curta, '') ILIKE %s
                              OR COALESCE(a.descricao, '') ILIKE %s OR COALESCE(c.nome, '') ILIKE %s)
                         AND (%s = '' OR c.nome = %s)
                         AND (%s = '' OR p.nome = %s)
                    ORDER BY ''' + ordering + ''' LIMIT 100''',
                    (search, search, search, search, category, category, platform, platform))
    if module == 'canais':
        category = category.strip()[:100] if isinstance(category, str) else ''
        return rows('''SELECT id, slug, nome AS name, descricao AS description, categoria AS category,
                             alcance AS audience, logo_path, cor
                        FROM cadu_canais
                       WHERE is_active = TRUE AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s
                             OR COALESCE(categoria, '') ILIKE %s)
                         AND (%s = '' OR categoria = %s)
                    ORDER BY ordem, nome LIMIT 100''',
                    (search, search, search, category, category))
    if module in ('formatos', 'interativos'):
        platform = platform.strip()[:80] if isinstance(platform, str) else ''
        format_type = format_type.strip()[:80] if isinstance(format_type, str) else ''
        segment = segment.strip()[:100] if isinstance(segment, str) else ''
        records = rows('''SELECT f.id, f.nome AS name, f.descricao AS description,
                             f.dimensoes AS dimensions, f.formatos_arquivo AS files,
                             f.tipo AS format_type, f.plataforma_slug AS platform_slug,
                             p.nome AS platform, p.logo_path AS platform_logo, f.dados_extras AS extras,
                             f.categoria_criativa AS creative_category,
                             f.dados_extras ->> 'objetivo_comercial' AS purpose
                        FROM cadu_formatos f
                   LEFT JOIN cadu_plataformas_formatos p ON p.slug = f.plataforma_slug
                       WHERE f.is_active = TRUE
                         AND (f.nome ILIKE %s OR COALESCE(f.descricao, '') ILIKE %s
                              OR COALESCE(f.dimensoes, '') ILIKE %s OR COALESCE(f.formatos_arquivo, '') ILIKE %s)
                         AND f.is_interativo = %s
                         AND (%s = '' OR f.plataforma_slug = %s)
                         AND (%s = '' OR f.tipo = %s)
                         AND (%s = '' OR LOWER(COALESCE(NULLIF(TRIM(f.categoria_criativa), ''), NULLIF(TRIM(f.dados_extras ->> 'segmento'), ''), NULLIF(f.tipo, ''), 'Geral')) = LOWER(%s))
                    ORDER BY p.ordem NULLS LAST, f.ordem, f.nome LIMIT 100''',
                    (search, search, search, search, module == 'interativos',
                     platform, platform, format_type, format_type, segment, segment))
        return [_decorate_format(record) for record in records]
    raise ValueError('Catálogo inválido.')


def audience_catalog_facets():
    """Small, stable filter lists for the customer-facing audience marketplace."""
    categories = rows('''SELECT DISTINCT c.nome AS value FROM cadu_audiencias a
                           JOIN cadu_categorias c ON c.id = a.categoria_id
                          WHERE a.is_active = TRUE AND c.nome IS NOT NULL
                          ORDER BY c.nome LIMIT 30''')
    platforms = rows('''SELECT DISTINCT p.nome AS value FROM cadu_audiencias a
                          JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
                         WHERE a.is_active = TRUE AND p.nome IS NOT NULL
                         ORDER BY p.nome LIMIT 30''')
    return {'categories': [row['value'] for row in categories],
            'platforms': [row['value'] for row in platforms]}


def format_catalog_facets(interactive=False):
    """Platforms and format types exposed by the shared creative catalog."""
    platforms = rows('''SELECT DISTINCT f.plataforma_slug AS slug, p.nome AS name
                          FROM cadu_formatos f
                     LEFT JOIN cadu_plataformas_formatos p ON p.slug = f.plataforma_slug
                         WHERE f.is_active = TRUE AND f.is_interativo = %s
                           AND f.plataforma_slug IS NOT NULL AND f.plataforma_slug <> ''
                      ORDER BY name NULLS LAST, slug LIMIT 40''', (interactive,))
    types = rows('''SELECT DISTINCT tipo AS value FROM cadu_formatos
                      WHERE is_active = TRUE AND is_interativo = %s
                        AND tipo IS NOT NULL AND tipo <> '' ORDER BY tipo LIMIT 20''', (interactive,))
    segments = rows('''SELECT DISTINCT COALESCE(NULLIF(TRIM(categoria_criativa), ''), NULLIF(TRIM(dados_extras ->> 'segmento'), ''),
                                                   NULLIF(tipo, ''), 'Geral') AS value
                         FROM cadu_formatos
                        WHERE is_active = TRUE AND is_interativo = %s
                        ORDER BY value LIMIT 30''', (interactive,)) if interactive else []
    return {'platforms': platforms, 'types': [row['value'] for row in types],
            'segments': [row['value'] for row in segments]}


def channel_catalog_facets():
    categories = rows('''SELECT DISTINCT categoria AS value FROM cadu_canais
                          WHERE is_active = TRUE AND categoria IS NOT NULL AND categoria <> ''
                          ORDER BY categoria LIMIT 20''')
    return {'categories': [row['value'] for row in categories], 'platforms': [], 'types': [], 'segments': []}


def _decorate_format(record):
    """Expose one safe creative link and its editorial segment when present."""
    extras = record.pop('extras', None) or {}
    if isinstance(extras, str):
        try:
            extras = json.loads(extras)
        except ValueError:
            extras = {}
    extras = extras if isinstance(extras, dict) else {}
    segment = record.get('creative_category') or extras.get('segmento') or record.get('format_type') or 'Geral'
    if isinstance(segment, list):
        segment = segment[0] if segment else 'Geral'
    record['segment'] = str(segment).strip()[:100] or 'Geral'
    record['purpose'] = str(record.get('purpose') or extras.get('objetivo_comercial') or '').strip()[:40]
    record['image_url'] = _current_creative_url(extras.get('imagem_referencia', ''))
    raw_url = next((extras.get(key) for key in ('creative_url', 'preview_url', 'link', 'url') if extras.get(key)), '')
    record['creative_url'] = _current_creative_url(raw_url)
    return record


def _current_creative_url(raw_url):
    """Keep stored creative references usable after the Cadu host migration."""
    value = str(raw_url or '').strip()
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        return ''
    if parsed.hostname.lower() != 'cadu.centralcomm.media':
        return value
    path = parsed.path or '/'
    if not (path.startswith('/parametros/modelagem-criativos') or path.startswith('/criativos/')):
        return value
    target = product_url('studio', path)
    return target + (('?' + parsed.query) if parsed.query else '')


def conversation_messages(user_id, client_id, conversation_id, limit=500):
    owned = rows('''SELECT id FROM cadu_conversations
                    WHERE id = %s AND id_contato_cliente = %s AND id_cliente = %s''',
                 (conversation_id, user_id, client_id))
    if not owned:
        return None
    limit = min(500, max(1, int(limit or 100)))
    messages = rows('''SELECT * FROM (SELECT id, role, content, files, metadata, created_at,
                             to_jsonb(m)->'tool_calls' AS tool_calls, conversation_sequence
                    FROM cadu_conversation_messages m WHERE conversation_id = %s
                     AND role IN ('user', 'assistant')
                    ORDER BY conversation_sequence DESC NULLS LAST, created_at DESC, id DESC LIMIT %s) recent
                    ORDER BY conversation_sequence NULLS LAST, created_at, id''', (conversation_id, limit))
    from ..cadu_workspace.conversations.legacy_results import project_message
    base = current_app.config.get('CADU_LEGACY_ASSET_BASE_URL')
    return [project_message(message, base) for message in messages]


def count_distinct_entities(active_refs, links):
    """Count explicit ID equivalence groups, never infer identity from names."""
    parent = {}

    def root(ref):
        parent.setdefault(ref, ref)
        while parent[ref] != ref:
            parent[ref] = parent[parent[ref]]
            ref = parent[ref]
        return ref

    for link in links:
        source, target = root(link['ref']), root(link['canonical_ref'])
        parent[source] = target
    return len({root(ref) for ref in active_refs})


def active_entity_count(client_id):
    active = rows('''SELECT 'ci:' || id::text AS ref FROM cadu_ci_projetos
                     WHERE id_cliente = %s AND status = 'ativo'
                     UNION ALL
                    SELECT 'projects:' || id::text FROM cadu_projetos
                     WHERE id_cliente = %s AND deleted_at IS NULL
                     UNION ALL
                    SELECT 'studio:' || id::text FROM cx_clients WHERE crm_client_id = %s''',
                  (client_id, client_id, client_id))
    return count_distinct_entities([row['ref'] for row in active], entity_links(client_id))


def create_entity(client_id, user_id, payload, *, return_created=False):
    """Write to the PHP source of truth and serialize the plan limit per client."""
    from uuid import NAMESPACE_URL, uuid4, uuid5
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id_cliente FROM tbl_cliente WHERE id_cliente = %s FOR UPDATE', (client_id,))
            idempotency_key = str(payload.get('idempotency_key') or '').strip()
            entity_id = str(uuid5(NAMESPACE_URL, f'cadu-project:{client_id}:{idempotency_key}')) if idempotency_key else str(uuid4())
            if idempotency_key:
                cur.execute('''SELECT id,status FROM cadu_ci_projetos
                                WHERE id = %s AND id_cliente = %s LIMIT 1''',
                            (entity_id, client_id))
                existing = cur.fetchone()
                if existing:
                    if existing.get('status') == 'deletado':
                        cur.execute('''UPDATE cadu_ci_projetos
                                         SET nome=%s, descricao=%s, tipo=%s, instrucoes=%s,
                                             tom_de_voz=%s, publico=%s, posicionamento=%s, cor=%s,
                                             campos_personalizados=%s, status='ativo', updated_at=NOW()
                                       WHERE id=%s AND id_cliente=%s''',
                                    (payload['name'], payload.get('description', ''),
                                     'marca' if payload['kind'] == 'brand' else 'projeto',
                                     payload.get('instructions', ''), payload.get('tone_of_voice', ''),
                                     payload.get('audience', ''), payload.get('positioning', ''),
                                     payload.get('color'), Json(payload.get('custom_fields') or {}),
                                     entity_id, client_id))
                        conn.commit()
                        ref = 'ci:' + str(existing['id'])
                        return (ref, True) if return_created else ref
                    conn.commit()
                    ref = 'ci:' + str(existing['id'])
                    return (ref, False) if return_created else ref
            cur.execute('''SELECT plan_type FROM cadu_client_plans
                           WHERE id_cliente = %s AND plan_status = 'active' LIMIT 1''', (client_id,))
            current = cur.fetchone()
            limit = 10 if current and current['plan_type'] in ('pro', 'enterprise') else 1
            if active_entity_count(client_id) >= limit:
                raise ValueError(f'O plano permite {limit} projeto(s)/marca(s) ativos.')
            cur.execute('''INSERT INTO cadu_ci_projetos
                (id, id_cliente, criado_por, nome, descricao, tipo, instrucoes,
                 tom_de_voz, publico, posicionamento, cor, campos_personalizados,
                 dify_dataset_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, 'ativo', NOW(), NOW())''',
                (entity_id, client_id, user_id, payload['name'], payload.get('description', ''),
                 'marca' if payload['kind'] == 'brand' else 'projeto', payload.get('instructions', ''),
                 payload.get('tone_of_voice', ''), payload.get('audience', ''),
                 payload.get('positioning', ''), payload.get('color'), Json(payload.get('custom_fields') or {}),
                 entity_id))
        conn.commit()
        ref = 'ci:' + entity_id
        return (ref, True) if return_created else ref
    except Exception:
        conn.rollback()
        raise


def discard_created_entity(client_id, project_ref):
    """Compensate a failed post-create setup without touching replayed projects."""
    source, source_id = str(project_ref or '').split(':', 1)
    if source != 'ci':
        raise ValueError('Somente projetos nativos podem ser descartados.')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_ci_projetos
                              SET status = 'deletado', updated_at = NOW()
                            WHERE id = %s AND id_cliente = %s AND status = 'ativo' ''',
                        (source_id, client_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def update_entity(client_id, ref, payload):
    source, source_id = ref.split(':', 1)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if source == 'ci':
                cur.execute('''UPDATE cadu_ci_projetos SET nome = %s, descricao = COALESCE(%s, descricao),
                               instrucoes = COALESCE(%s, instrucoes), updated_at = NOW()
                               WHERE id = %s AND id_cliente = %s AND status <> 'deletado' RETURNING id''',
                            (payload['name'], payload.get('description'), payload.get('instructions'), source_id, client_id))
            elif source == 'studio':
                cur.execute('''UPDATE cx_clients SET name = %s
                               WHERE id = %s AND crm_client_id = %s RETURNING id''',
                            (payload['name'], source_id, client_id))
            elif source == 'projects':
                cur.execute('''UPDATE cadu_projetos SET nome = %s, descricao = COALESCE(%s, descricao), updated_at = NOW()
                               WHERE id = %s AND id_cliente = %s AND deleted_at IS NULL RETURNING id''',
                            (payload['name'], payload.get('description'), source_id, client_id))
            else:
                raise ValueError('Origem inválida.')
            if not cur.fetchone():
                raise ValueError('Registro não encontrado.')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
