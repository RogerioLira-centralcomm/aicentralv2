"""Private, scoped memory for Cadu conversations.

Memory is not a transcript or a model-training set. Only explicit, useful
statements are captured here; retrieval is always scoped to the signed-in user.
"""
import json
import re
from uuid import uuid4


EXPLICIT_PATTERNS = (
    ('preference', 'response_style', re.compile(r'^(?:eu )?prefiro\s+(.+)', re.I)),
    ('constraint', 'avoid', re.compile(r'^(?:não|nao) use\s+(.+)', re.I)),
    ('role', 'professional_role', re.compile(r'^(?:eu )?(?:trabalho com|atuo com)\s+(.+)', re.I)),
)


def _clean(value, limit):
    return ' '.join(str(value or '').split())[:limit]


def explicit_candidate(message):
    """Return a safe declared preference/role, never an inferred profile."""
    text = _clean(message, 600)
    for kind, key, pattern in EXPLICIT_PATTERNS:
        match = pattern.match(text)
        if match:
            value = _clean(match.group(1).rstrip('.!'), 360)
            if len(value) >= 3:
                return {'kind': kind, 'key': key, 'value': value}
    return None


def capture_explicit(cur, *, user, conversation_id, message_id, text):
    candidate = explicit_candidate(text)
    if not candidate:
        return None
    cur.execute('''SELECT id FROM cadu_user_memories
                    WHERE organization_id=%s AND user_id=%s AND scope='personal'
                      AND kind=%s AND memory_key=%s AND status='active'
                    ORDER BY updated_at DESC LIMIT 1 FOR UPDATE''',
                (user['organization_id'], user['id'], candidate['kind'], candidate['key']))
    current = cur.fetchone()
    if current:
        memory_id = current['id']
        cur.execute('''UPDATE cadu_user_memories SET value=%s, confidence=0.980,
                       source='explicit', source_conversation_id=%s, source_message_id=%s,
                       updated_at=NOW() WHERE id=%s''',
                    (candidate['value'], conversation_id, message_id, memory_id))
        action = 'updated'
    else:
        memory_id = str(uuid4())
        cur.execute('''INSERT INTO cadu_user_memories
                       (id, organization_id, user_id, scope, kind, memory_key, value, confidence,
                        source, source_conversation_id, source_message_id)
                       VALUES (%s,%s,%s,'personal',%s,%s,%s,0.980,'explicit',%s,%s)''',
                    (memory_id, user['organization_id'], user['id'], candidate['kind'], candidate['key'],
                     candidate['value'], conversation_id, message_id))
        action = 'created'
    cur.execute('''INSERT INTO cadu_user_memory_events (memory_id, actor_id, event, detail)
                   VALUES (%s,%s,%s,%s::jsonb)''',
                (memory_id, user['id'], action, json.dumps({'source': 'explicit'})))
    return memory_id


def context_packet(user, selected, project_ref, query, limit=8):
    """Return a compact, relevance-ranked memory envelope for the active user."""
    from ...cadu_family import repository
    terms = _clean(query, 400)
    try:
        if not repository.family_table_available('cadu_user_memories'):
            return ''
        records = repository.rows('''SELECT scope, kind, value, confidence, updated_at,
                    CASE scope WHEN 'project' THEN 30 WHEN 'client' THEN 20 ELSE 10 END
                    + CASE WHEN kind IN ('preference','constraint','role') THEN 5 ELSE 0 END
                    + GREATEST(0, 5 - EXTRACT(EPOCH FROM (NOW() - updated_at)) / 2592000.0) AS scope_score,
                    CASE WHEN %s <> '' AND to_tsvector('portuguese', memory_key || ' ' || value)
                         @@ plainto_tsquery('portuguese', %s) THEN 20 ELSE 0 END AS lexical_score
                  FROM cadu_user_memories
                 WHERE organization_id=%s AND user_id=%s AND status='active'
                   AND (expires_at IS NULL OR expires_at > NOW())
                   AND (scope='personal' OR (scope='client' AND client_id=%s)
                     OR (scope='project' AND client_id=%s AND project_ref=%s))
                 ORDER BY lexical_score DESC, scope_score DESC, confidence DESC, updated_at DESC LIMIT %s''',
                                      (terms, terms, user['organization_id'], user['id'], selected['client_id'],
                                       selected['client_id'], project_ref, limit))
    except Exception:
        return ''
    groups = {'preferencias': [], 'contexto_profissional': [], 'decisoes_e_restricoes': []}
    for row in records:
        value = _clean(row.get('value'), 360)
        if not value:
            continue
        if row['kind'] in ('preference', 'constraint'):
            groups['preferencias'].append(value)
        elif row['kind'] in ('role', 'expertise'):
            groups['contexto_profissional'].append(value)
        else:
            groups['decisoes_e_restricoes'].append(value)
    payload = {key: value for key, value in groups.items() if value}
    return json.dumps({'versao': '1.0', 'memoria_usuario': payload}, ensure_ascii=False,
                      separators=(',', ':'))[:2200] if payload else ''


def list_memories(user, selected):
    from ...cadu_family import repository
    if not repository.family_table_available('cadu_user_memories'):
        return []
    return repository.rows('''SELECT id, scope, kind, memory_key, value, confidence, source, status,
                                      project_ref, expires_at, updated_at, created_at
                               FROM cadu_user_memories
                              WHERE organization_id=%s AND user_id=%s
                                AND (scope='personal' OR client_id=%s)
                              ORDER BY status='active' DESC, updated_at DESC LIMIT 200''',
                           (user['organization_id'], user['id'], selected['client_id']))


def dismiss(memory_id, user, selected):
    from ...cadu_family import repository
    if not repository.family_table_available('cadu_user_memories'):
        return False
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_user_memories SET status='dismissed', updated_at=NOW()
                           WHERE id=%s AND organization_id=%s AND user_id=%s
                             AND (scope='personal' OR client_id=%s) RETURNING id''',
                        (memory_id, user['organization_id'], user['id'], selected['client_id']))
            row = cur.fetchone()
            if row:
                cur.execute('INSERT INTO cadu_user_memory_events (memory_id, actor_id, event) VALUES (%s,%s,%s)',
                            (memory_id, user['id'], 'dismissed'))
        conn.commit()
        return bool(row)
    except Exception:
        conn.rollback()
        raise
