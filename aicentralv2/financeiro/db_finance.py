"""Acesso a dados do módulo de reembolsos (finance_*)."""
from decimal import Decimal
from ..db import get_db


def _serialize_row(row):
    if not row:
        return None
    out = dict(row)
    for k, v in list(out.items()):
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif hasattr(v, 'isoformat') and not isinstance(v, str):
            try:
                out[k] = v.isoformat()
            except Exception:
                out[k] = str(v)
        elif v is not None and type(v).__name__ == 'UUID':
            out[k] = str(v)
    return out


def list_categories(active_only=True):
    conn = get_db()
    with conn.cursor() as cur:
        if active_only:
            cur.execute(
                'SELECT id, slug, label, active FROM finance_expense_categories '
                'WHERE active = TRUE ORDER BY label'
            )
        else:
            cur.execute(
                'SELECT id, slug, label, active FROM finance_expense_categories ORDER BY label'
            )
        return [_serialize_row(r) for r in cur.fetchall()]


def create_expense(user_id, data):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO finance_expenses (
                user_id, status, category_id, association_type, association_label,
                client_id, merchant_name, expense_date, currency, total_amount, notes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING *
        ''', (
            user_id,
            data.get('status') or 'draft',
            data.get('category_id') or None,
            data.get('association_type') or None,
            (data.get('association_label') or '').strip() or None,
            data.get('client_id') or None,
            (data.get('merchant_name') or '').strip() or None,
            data.get('expense_date') or None,
            data.get('currency') or 'BRL',
            data.get('total_amount'),
            (data.get('notes') or '').strip() or None,
        ))
        row = cur.fetchone()
    conn.commit()
    return _serialize_row(row)


def get_expense(expense_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT e.*,
                   cat.slug AS category_slug,
                   cat.label AS category_label,
                   cli.nome_fantasia AS client_name
            FROM finance_expenses e
            LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
            LEFT JOIN tbl_cliente cli ON cli.id_cliente = e.client_id
            WHERE e.id = %s
        ''', (expense_id,))
        return _serialize_row(cur.fetchone())


def list_expenses_for_user(user_id, filtros=None):
    filtros = filtros or {}
    conn = get_db()
    clauses = ['e.user_id = %s']
    params = [user_id]

    if filtros.get('status'):
        clauses.append('e.status = %s')
        params.append(filtros['status'])
    if filtros.get('association_type'):
        clauses.append('e.association_type = %s')
        params.append(filtros['association_type'])
    if filtros.get('date_from'):
        clauses.append('e.expense_date >= %s')
        params.append(filtros['date_from'])
    if filtros.get('date_to'):
        clauses.append('e.expense_date <= %s')
        params.append(filtros['date_to'])

    where = ' AND '.join(clauses)
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT e.*,
                   cat.slug AS category_slug,
                   cat.label AS category_label
            FROM finance_expenses e
            LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
            WHERE {where}
            ORDER BY e.created_at DESC
            LIMIT 200
        ''', params)
        return [_serialize_row(r) for r in cur.fetchall()]


EDITABLE_STATUSES = ('draft', 'rejected', 'extracted', 'extraction_failed')
# Só é possível excluir enquanto a despesa está em um status editável.
# Após "submitted" (enviado), aprovado ou fechado, exclusão é bloqueada.
DELETABLE_STATUSES = EDITABLE_STATUSES
DELETABLE_BEFORE = ('approved', 'closed')  # mantido por compatibilidade


def get_category_id_by_slug(slug):
    if not slug:
        return None
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT id FROM finance_expense_categories WHERE slug = %s',
            (slug,),
        )
        row = cur.fetchone()
    if not row:
        return None
    row = _serialize_row(row)
    return row.get('id')


def update_expense(expense_id, data):
    from psycopg.types.json import Json
    conn = get_db()
    fields = []
    params = []
    mapping = {
        'category_id': 'category_id',
        'association_type': 'association_type',
        'association_label': 'association_label',
        'client_id': 'client_id',
        'merchant_name': 'merchant_name',
        'expense_date': 'expense_date',
        'currency': 'currency',
        'total_amount': 'total_amount',
        'notes': 'notes',
        'status': 'status',
        'rejection_reason': 'rejection_reason',
        'ai_confidence': 'ai_confidence',
        'needs_review': 'needs_review',
        'ai_raw_response': 'ai_raw_response',
    }
    for key, col in mapping.items():
        if key in data:
            fields.append(f'{col} = %s')
            val = data[key]
            if key in ('association_label', 'merchant_name', 'notes') and isinstance(val, str):
                val = val.strip() or None
            if key in ('category_id', 'client_id') and val == '':
                val = None
            if key == 'ai_raw_response' and val is not None:
                val = Json(val)
            params.append(val)

    if not fields:
        return get_expense(expense_id)

    fields.append('updated_at = now()')
    params.append(expense_id)
    with conn.cursor() as cur:
        cur.execute(
            f'UPDATE finance_expenses SET {", ".join(fields)} WHERE id = %s RETURNING *',
            params,
        )
        row = cur.fetchone()
    conn.commit()
    return _serialize_row(row)


def delete_expense(expense_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('DELETE FROM finance_expenses WHERE id = %s RETURNING id', (expense_id,))
        row = cur.fetchone()
    conn.commit()
    return bool(row)


def replace_expense_items(expense_id, items):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('DELETE FROM finance_expense_items WHERE expense_id = %s', (expense_id,))
        for i, item in enumerate(items or []):
            desc = (item.get('description') or '').strip()
            if not desc:
                continue
            cur.execute('''
                INSERT INTO finance_expense_items
                    (expense_id, description, quantity, unit_amount, amount, position)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                expense_id,
                desc,
                item.get('quantity') if item.get('quantity') is not None else 1,
                item.get('unit_amount'),
                item.get('amount') or 0,
                i,
            ))
    conn.commit()


def list_expense_items(expense_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT * FROM finance_expense_items
            WHERE expense_id = %s
            ORDER BY position
        ''', (expense_id,))
        return [_serialize_row(r) for r in cur.fetchall()]


def add_receipt_file(expense_id, meta):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO finance_receipt_files
                (expense_id, storage_key, file_name, mime_type, file_size)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        ''', (
            expense_id,
            meta['storage_key'],
            meta['file_name'],
            meta['mime_type'],
            meta['file_size'],
        ))
        row = cur.fetchone()
    conn.commit()
    return _serialize_row(row)


def list_receipts(expense_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT * FROM finance_receipt_files
            WHERE expense_id = %s
            ORDER BY uploaded_at
        ''', (expense_id,))
        return [_serialize_row(r) for r in cur.fetchall()]


def get_receipt(receipt_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT r.*, e.user_id AS expense_user_id
            FROM finance_receipt_files r
            JOIN finance_expenses e ON e.id = r.expense_id
            WHERE r.id = %s
        ''', (receipt_id,))
        return _serialize_row(cur.fetchone())


def summary_for_user(user_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT status,
                   COUNT(*) AS qtd,
                   COALESCE(SUM(total_amount), 0) AS total
            FROM finance_expenses
            WHERE user_id = %s
            GROUP BY status
        ''', (user_id,))
        by_status = {_serialize_row(r)['status']: _serialize_row(r) for r in cur.fetchall()}
    return {
        'by_status': by_status,
        'draft_total': (by_status.get('draft') or {}).get('total') or 0,
        'submitted_total': (by_status.get('submitted') or {}).get('total') or 0,
        'approved_total': (by_status.get('approved') or {}).get('total') or 0,
        'rejected_total': (by_status.get('rejected') or {}).get('total') or 0,
    }


def search_clients(q, limit=30):
    conn = get_db()
    term = f"%{(q or '').strip()}%"
    with conn.cursor() as cur:
        if (q or '').strip():
            cur.execute('''
                SELECT id_cliente, nome_fantasia, razao_social
                FROM tbl_cliente
                WHERE status IS DISTINCT FROM FALSE
                  AND (
                    nome_fantasia ILIKE %s OR razao_social ILIKE %s
                  )
                ORDER BY nome_fantasia
                LIMIT %s
            ''', (term, term, limit))
        else:
            cur.execute('''
                SELECT id_cliente, nome_fantasia, razao_social
                FROM tbl_cliente
                WHERE status IS DISTINCT FROM FALSE
                ORDER BY nome_fantasia
                LIMIT %s
            ''', (limit,))
        return [_serialize_row(r) for r in cur.fetchall()]


def _admin_filter_clauses(filtros):
    filtros = filtros or {}
    clauses = []
    params = []
    if filtros.get('status'):
        clauses.append('e.status = %s')
        params.append(filtros['status'])
    if filtros.get('user_id'):
        clauses.append('e.user_id = %s')
        params.append(filtros['user_id'])
    if filtros.get('category_id'):
        clauses.append('e.category_id = %s')
        params.append(filtros['category_id'])
    if filtros.get('date_from'):
        clauses.append('e.expense_date >= %s')
        params.append(filtros['date_from'])
    if filtros.get('date_to'):
        clauses.append('e.expense_date <= %s')
        params.append(filtros['date_to'])
    return clauses, params


def list_all_expenses(filtros=None):
    """Admin: lista todos os reembolsos com usuário e categoria."""
    conn = get_db()
    clauses, params = _admin_filter_clauses(filtros)
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT e.*,
                   cat.slug  AS category_slug,
                   cat.label AS category_label,
                   u.nome_completo AS user_name,
                   u.email         AS user_email
            FROM finance_expenses e
            LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
            LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = e.user_id
            {where}
            ORDER BY e.expense_date DESC NULLS LAST, e.created_at DESC
            LIMIT 500
        ''', params)
        return [_serialize_row(r) for r in cur.fetchall()]


def admin_summary(filtros=None):
    """Admin: totais por status (respeitando filtros de usuário/categoria/período)."""
    conn = get_db()
    clauses, params = _admin_filter_clauses(dict((filtros or {}), **{'status': None}))
    # remover eventual filtro de status para o resumo por status
    clauses = [c for c in clauses if not c.startswith('e.status')]
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT e.status,
                   COUNT(*) AS qtd,
                   COALESCE(SUM(e.total_amount), 0) AS total
            FROM finance_expenses e
            {where}
            GROUP BY e.status
        ''', params)
        by_status = {}
        for r in cur.fetchall():
            row = _serialize_row(r)
            by_status[row['status']] = row
    return {
        'by_status': by_status,
        'submitted_total': (by_status.get('submitted') or {}).get('total') or 0,
        'submitted_qtd': (by_status.get('submitted') or {}).get('qtd') or 0,
        'approved_total': (by_status.get('approved') or {}).get('total') or 0,
        'approved_qtd': (by_status.get('approved') or {}).get('qtd') or 0,
        'draft_total': (by_status.get('draft') or {}).get('total') or 0,
        'draft_qtd': (by_status.get('draft') or {}).get('qtd') or 0,
        'rejected_total': (by_status.get('rejected') or {}).get('total') or 0,
        'rejected_qtd': (by_status.get('rejected') or {}).get('qtd') or 0,
    }


def list_expense_users():
    """Usuários que possuem despesas (para filtro admin)."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT DISTINCT u.id_contato_cliente AS id, u.nome_completo AS nome, u.email
            FROM finance_expenses e
            JOIN tbl_contato_cliente u ON u.id_contato_cliente = e.user_id
            ORDER BY u.nome_completo
        ''')
        return [_serialize_row(r) for r in cur.fetchall()]


def write_audit(user_id, entity_type, entity_id, action, payload=None):
    from psycopg.types.json import Json
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO finance_audit_log (user_id, entity_type, entity_id, action, payload)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, entity_type, str(entity_id), action, Json(payload) if payload is not None else None))
    conn.commit()
