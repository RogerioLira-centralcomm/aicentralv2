"""Shared, reviewable work memory extracted from new project conversations."""
import json
import re
from uuid import uuid4

from ...cadu_family import repository

KINDS = {'decision', 'constraint', 'risk', 'next_step', 'brand_context'}
LABELS = {
    'decis': 'decision', 'restri': 'constraint', 'risco': 'risk',
    'depend': 'risk', 'próxim': 'next_step', 'proxim': 'next_step',
    'marca': 'brand_context', 'posicion': 'brand_context',
}


def available():
    return repository.family_table_available('cadu_working_memories')


def _clean(value, limit=500):
    return ' '.join(str(value or '').replace('*', '').split())[:limit]


def proposals(text):
    """Conservative, local extraction; uncertain prose is deliberately ignored."""
    candidates, seen = [], set()
    active_kind = None
    for raw in str(text or '').splitlines():
        line = _clean(raw)
        heading = line.lstrip('#').strip().lower()
        matched = next((kind for label, kind in LABELS.items() if label in heading), None)
        if matched and raw.lstrip().startswith('#') and len(line) < 120:
            active_kind = matched
            continue
        if not active_kind or len(line) < 18 or not re.match(r'^(?:\-|•|\d+[.)])\s*', line):
            continue
        summary = re.sub(r'^(?:\-|•|\d+[.)])\s*', '', line).strip()
        normalized = summary.lower()
        if normalized not in seen and not re.search(r'\b(talvez|pode ser|acho que)\b', normalized):
            seen.add(normalized); candidates.append({'kind': active_kind, 'summary': summary})
    return candidates[:8]


def capture_turn(*, organization_id, client_id, project_ref, conversation_id, message_id, author_id, answer):
    if not project_ref or not available():
        return []
    items = proposals(answer)
    if not items:
        return []
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            created = []
            for item in items:
                memory_id = str(uuid4())
                cur.execute('''INSERT INTO cadu_working_memories
                    (id, organization_id, client_id, project_ref, scope, kind, summary, confidence, status,
                     source_conversation_id, source_message_id, source_author_id)
                    VALUES (%s,%s,%s,%s,'project',%s,%s,.700,'proposed',%s,%s,%s)''',
                    (memory_id, organization_id, client_id, project_ref, item['kind'], item['summary'],
                     conversation_id, message_id, author_id))
                cur.execute('''INSERT INTO cadu_working_memory_events (memory_id, actor_id, event, detail)
                               VALUES (%s,%s,'proposed',%s::jsonb)''',
                            (memory_id, author_id, json.dumps({'source': 'conversation'})))
                created.append(memory_id)
        conn.commit()
        return created
    except Exception:
        conn.rollback()
        return []


def packet(client_id, project_ref, query, limit=8):
    if not project_ref or not available():
        return ''
    terms = _clean(query, 400)
    records = repository.rows('''SELECT scope, kind, summary FROM cadu_working_memories
        WHERE client_id=%s AND status='confirmed' AND ((scope='project' AND project_ref=%s) OR scope='client')
        ORDER BY CASE WHEN %s <> '' AND to_tsvector('portuguese', summary) @@ plainto_tsquery('portuguese', %s) THEN 1 ELSE 0 END DESC,
                 updated_at DESC LIMIT %s''', (client_id, project_ref, terms, terms, limit))
    return json.dumps({'versao':'1.0','memoria_de_trabalho_confirmada':records}, ensure_ascii=False) if records else ''


def board(user, client_id, project_ref):
    if not project_ref or not available():
        return {'project_ref': project_ref, 'confirmed': [], 'proposals': [], 'weeks': []}
    rows = repository.rows('''SELECT m.*, a.nome_completo AS author_name
        FROM cadu_working_memories m LEFT JOIN tbl_contato_cliente a ON a.id_contato_cliente=m.source_author_id
        WHERE m.organization_id=%s AND m.client_id=%s AND m.project_ref=%s ORDER BY m.updated_at DESC LIMIT 100''',
        (user['organization_id'], client_id, project_ref))
    conversations = repository.rows('''SELECT c.id, c.titulo AS title, c.updated_at, u.nome_completo AS author_name
        FROM cadu_conversations c JOIN cadu_family_conversation_context x ON x.conversation_id=c.id
        LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente=c.id_contato_cliente
        WHERE x.organization_id=%s AND x.client_id=%s AND x.project_ref=%s ORDER BY c.updated_at DESC LIMIT 50''',
        (user['organization_id'], client_id, project_ref))
    weeks = {}
    for row in conversations:
        key = str(row['updated_at'].date().isocalendar()[:2]) if hasattr(row['updated_at'], 'date') else 'recentes'
        weeks.setdefault(key, []).append(row)
    return {'project_ref': project_ref, 'confirmed':[r for r in rows if r['status']=='confirmed'],
            'proposals':[r for r in rows if r['status']=='proposed'],
            'weeks':[{'key': key, 'conversations': value} for key, value in weeks.items()]}


def review(memory_id, user, client_id, project_ref, action, summary=None):
    if action not in {'confirm','dismiss','promote'}:
        raise ValueError('Ação inválida.')
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT * FROM cadu_working_memories WHERE id=%s AND organization_id=%s
                           AND client_id=%s AND project_ref=%s AND scope='project' FOR UPDATE''',
                        (memory_id, user['organization_id'], client_id, project_ref))
            row = cur.fetchone()
            if not row:
                return None
            if action == 'promote' and row['kind'] != 'brand_context':
                raise ValueError('Apenas contexto de marca pode ser promovido para o cliente.')
            status, scope, project_ref = ('dismissed', row['scope'], row['project_ref']) if action == 'dismiss' else ('confirmed', 'client' if action == 'promote' else row['scope'], None if action == 'promote' else row['project_ref'])
            value = _clean(summary, 500) if summary is not None else row['summary']
            if not value:
                raise ValueError('A memória precisa de um resumo.')
            cur.execute('''UPDATE cadu_working_memories SET status=%s, scope=%s, project_ref=%s, summary=%s,
                           reviewed_by=%s, reviewed_at=NOW(), updated_at=NOW() WHERE id=%s RETURNING *''',
                        (status, scope, project_ref, value, user['id'], memory_id))
            result = dict(cur.fetchone())
            event = {'confirm':'confirmed','dismiss':'dismissed','promote':'promoted'}[action]
            if summary is not None: event = 'edited'
            cur.execute('INSERT INTO cadu_working_memory_events (memory_id,actor_id,event) VALUES (%s,%s,%s)', (memory_id,user['id'],event))
        conn.commit(); return result
    except Exception:
        conn.rollback(); raise
