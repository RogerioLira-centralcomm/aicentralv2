"""Narrow projections of existing data. Query errors must never grant access."""
from ..db import get_db
from flask import g, current_app


def family_table_available(name):
    """Inspect schema without creating it; do not swallow connectivity errors."""
    if name not in {'cadu_family_client_access', 'cadu_family_entity_links', 'cadu_family_conversation_context',
                    'cadu_family_chat_uploads', 'cadu_family_project_brands'}:
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
    result = rows('''SELECT id_contato_cliente AS id, pk_id_tbl_cliente AS organization_id,
                            nome_completo AS name, email, telefone AS phone,
                            pk_id_tbl_cargo AS role_id, user_type, is_finance_admin
                       FROM tbl_contato_cliente u
                      WHERE id_contato_cliente = %s AND status = TRUE
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
    return rows('''SELECT 'ci:' || id::text AS ref, nome AS name,
                         CASE WHEN tipo = 'marca' THEN 'brand' ELSE 'project' END AS kind,
                         'ci' AS source
                    FROM cadu_ci_projetos WHERE id_cliente = %s AND status <> 'deletado'
                  UNION ALL
                  SELECT 'projects:' || id::text, nome, 'project', 'projects'
                    FROM cadu_projetos WHERE id_cliente = %s AND deleted_at IS NULL
                  UNION ALL
                  SELECT 'studio:' || id::text, name, 'brand', 'studio'
                    FROM cx_clients WHERE crm_client_id = %s
                  ORDER BY name''', (client_id, client_id, client_id))


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
                              NULL AS project_ref, NULL AS brand_ref
                         FROM cadu_conversations
                        WHERE id_contato_cliente = %s AND id_cliente = %s AND titulo ILIKE %s AND status = ANY(%s)
                     ORDER BY updated_at DESC, id DESC LIMIT %s OFFSET %s''',
                    (user['id'], client_id, '%' + query + '%', statuses, limit, offset))
    return rows('''SELECT c.id, c.titulo AS title, c.updated_at, x.profile,
                         x.project_ref, x.brand_ref
                    FROM cadu_conversations c
               LEFT JOIN cadu_family_conversation_context x ON x.conversation_id = c.id
                   WHERE c.id_contato_cliente = %s AND c.id_cliente = %s AND c.titulo ILIKE %s AND c.status = ANY(%s)
                     AND (x.conversation_id IS NULL OR
                          (x.user_id = %s AND x.organization_id = %s AND x.client_id = %s))
                ORDER BY c.updated_at DESC, c.id DESC LIMIT %s OFFSET %s''',
                (user['id'], client_id, '%' + query + '%', statuses, user['id'], user['organization_id'], client_id, limit, offset))


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


def catalog(module, query=''):
    search = '%' + query[:100] + '%'
    if module == 'audiencias':
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
                    ORDER BY a.nome, a.id LIMIT 100''', (search, search, search, search))
    if module == 'canais':
        return rows('''SELECT id, nome AS name, descricao AS description, categoria AS category,
                             alcance AS audience FROM cadu_canais
                       WHERE is_active = TRUE AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s
                             OR COALESCE(categoria, '') ILIKE %s) ORDER BY ordem, nome LIMIT 100''',
                    (search, search, search))
    if module in ('formatos', 'interativos'):
        return rows('''SELECT id, nome AS name, descricao AS description,
                             dimensoes AS dimensions, formatos_arquivo AS files
                        FROM cadu_formatos WHERE is_active = TRUE
                         AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s
                              OR COALESCE(dimensoes, '') ILIKE %s OR COALESCE(formatos_arquivo, '') ILIKE %s)
                         AND (%s = FALSE OR is_interativo = TRUE)
                    ORDER BY ordem, nome LIMIT 100''', (search, search, search, search, module == 'interativos'))
    raise ValueError('Catálogo inválido.')


def conversation_messages(user_id, client_id, conversation_id):
    owned = rows('''SELECT id FROM cadu_conversations
                    WHERE id = %s AND id_contato_cliente = %s AND id_cliente = %s''',
                 (conversation_id, user_id, client_id))
    if not owned:
        return None
    messages = rows('''SELECT id, role, content, files, metadata, created_at,
                             to_jsonb(m)->'tool_calls' AS tool_calls
                    FROM cadu_conversation_messages m WHERE conversation_id = %s
                     AND role IN ('user', 'assistant') ORDER BY created_at, id LIMIT 500''', (conversation_id,))
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


def create_entity(client_id, user_id, payload):
    """Write to the PHP source of truth and serialize the plan limit per client."""
    from uuid import uuid4
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id_cliente FROM tbl_cliente WHERE id_cliente = %s FOR UPDATE', (client_id,))
            cur.execute('''SELECT plan_type FROM cadu_client_plans
                           WHERE id_cliente = %s AND plan_status = 'active' LIMIT 1''', (client_id,))
            current = cur.fetchone()
            limit = 10 if current and current['plan_type'] in ('pro', 'enterprise') else 1
            if active_entity_count(client_id) >= limit:
                raise ValueError(f'O plano permite {limit} projeto(s)/marca(s) ativos.')
            entity_id = str(uuid4())
            cur.execute('''INSERT INTO cadu_ci_projetos
                (id, id_cliente, criado_por, nome, descricao, tipo, instrucoes,
                 dify_dataset_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ativo', NOW(), NOW())''',
                (entity_id, client_id, user_id, payload['name'], payload.get('description', ''),
                 'marca' if payload['kind'] == 'brand' else 'projeto', payload.get('instructions', ''), entity_id))
        conn.commit()
        return 'ci:' + entity_id
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
