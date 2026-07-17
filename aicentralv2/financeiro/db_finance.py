"""Acesso a dados do módulo de reembolsos (finance_*)."""
from datetime import date
from decimal import Decimal
from ..db import get_db

MONTH_NAMES_PT = (
    '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
)


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


def _summary_description(reference_month, seq_in_month):
    month_name = MONTH_NAMES_PT[reference_month.month]
    return f'{month_name}_{seq_in_month:02d}'


def get_summary(summary_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('SELECT * FROM finance_summary WHERE id = %s', (summary_id,))
        return _serialize_row(cur.fetchone())


def get_open_summary(user_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT * FROM finance_summary
            WHERE user_id = %s AND status = 'open'
            LIMIT 1
        ''', (user_id,))
        return _serialize_row(cur.fetchone())


def resolve_open_summary(user_id):
    """Retorna summary aberto existente ou cria novo com nome_mes_ind."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT * FROM finance_summary
            WHERE user_id = %s AND status = 'open'
            LIMIT 1
            FOR UPDATE
        ''', (user_id,))
        row = cur.fetchone()
        if row:
            conn.commit()
            return _serialize_row(row)

        today = date.today()
        ref_month = date(today.year, today.month, 1)
        cur.execute('''
            SELECT COUNT(*) AS cnt FROM finance_summary
            WHERE user_id = %s AND reference_month = %s AND status = 'paid'
        ''', (user_id, ref_month))
        count_row = cur.fetchone()
        seq = (count_row['cnt'] if count_row else 0) + 1
        description = _summary_description(ref_month, seq)

        cur.execute('''
            INSERT INTO finance_summary (
                user_id, description, reference_month, seq_in_month, status
            ) VALUES (%s, %s, %s, %s, 'open')
            RETURNING *
        ''', (user_id, description, ref_month, seq))
        created = cur.fetchone()
    conn.commit()
    return _serialize_row(created)


def recalc_summary_totals(summary_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            UPDATE finance_summary SET
                total_payable = (
                    SELECT COALESCE(SUM(total_amount), 0) FROM finance_expenses
                    WHERE summary_id = %s AND status = 'approved'
                ),
                total_rejected = (
                    SELECT COALESCE(SUM(total_amount), 0) FROM finance_expenses
                    WHERE summary_id = %s AND status = 'rejected'
                ),
                updated_at = now()
            WHERE id = %s
            RETURNING *
        ''', (summary_id, summary_id, summary_id))
        row = cur.fetchone()
    conn.commit()
    return _serialize_row(row)


def find_duplicate_expense(user_id, expense_date, total_amount, merchant_name, exclude_id=None):
    if not expense_date or total_amount is None or not (merchant_name or '').strip():
        return None
    conn = get_db()
    clauses = [
        'user_id = %s',
        'expense_date = %s',
        'total_amount = %s',
        "LOWER(TRIM(merchant_name)) = LOWER(TRIM(%s))",
    ]
    params = [user_id, expense_date, total_amount, merchant_name]
    if exclude_id:
        clauses.append('id != %s')
        params.append(exclude_id)
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT id, merchant_name, expense_date, total_amount
            FROM finance_expenses
            WHERE {' AND '.join(clauses)}
            LIMIT 1
        ''', params)
        return _serialize_row(cur.fetchone())


FINAL_EXPENSE_STATUSES = ('approved', 'rejected')


def count_unresolved_expenses_in_summary(summary_id):
    """Reembolsos do lote que ainda não foram aprovados nem rejeitados pelo admin."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT COUNT(*) AS cnt FROM finance_expenses
            WHERE summary_id = %s AND status NOT IN ('approved', 'rejected')
        ''', (summary_id,))
        row = cur.fetchone()
    return row['cnt'] if row else 0


def count_submitted_in_summary(summary_id):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT COUNT(*) AS cnt FROM finance_expenses
            WHERE summary_id = %s AND status = 'submitted'
        ''', (summary_id,))
        row = cur.fetchone()
    return row['cnt'] if row else 0


def mark_summary_paid(summary_id, payment_date, admin_id):
    summary = get_summary(summary_id)
    if not summary:
        return None, 'Reembolso não encontrado'
    if summary['status'] != 'open':
        return None, 'Este reembolso já foi concluído'
    if not payment_date:
        return None, 'Informe a data de pagamento'
    pending = count_unresolved_expenses_in_summary(summary_id)
    if pending > 0:
        plural = 'reembolso' if pending == 1 else 'reembolsos'
        verbo = 'ainda não foi aprovado nem rejeitado' if pending == 1 else 'ainda não foram aprovados nem rejeitados'
        return None, (
            f'Não é possível marcar como pago: {pending} {plural} {verbo}. '
            f'Use Aprovar ou Reprovar em cada item do lote antes de concluir.'
        )

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            UPDATE finance_summary SET
                status = 'paid',
                payment_date = %s,
                paid_at = now(),
                paid_by = %s,
                updated_at = now()
            WHERE id = %s AND status = 'open'
            RETURNING *
        ''', (payment_date, admin_id, summary_id))
        row = cur.fetchone()
    conn.commit()
    if not row:
        return None, 'Não foi possível concluir o reembolso'
    return _serialize_row(row), None


def list_summaries_for_user(user_id, filtros=None):
    filtros = filtros or {}
    conn = get_db()
    clauses = ['s.user_id = %s']
    params = [user_id]
    if filtros.get('status'):
        clauses.append('s.status = %s')
        params.append(filtros['status'])
    where = ' AND '.join(clauses)
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT s.*,
                   (SELECT COUNT(*) FROM finance_expenses e WHERE e.summary_id = s.id) AS expense_count,
                   (SELECT COALESCE(SUM(total_amount), 0) FROM finance_expenses e
                    WHERE e.summary_id = s.id AND e.status = 'submitted') AS total_submitted,
                   (SELECT COALESCE(SUM(total_amount), 0) FROM finance_expenses e
                    WHERE e.summary_id = s.id AND e.status IN ('draft', 'extracted', 'extraction_failed', 'rejected')) AS total_draft
            FROM finance_summary s
            WHERE {where}
            ORDER BY s.created_at DESC
            LIMIT 100
        ''', params)
        return [_serialize_row(r) for r in cur.fetchall()]


def list_expenses_for_summary(summary_id, filtros=None):
    filtros = filtros or {}
    conn = get_db()
    clauses = ['e.summary_id = %s']
    params = [summary_id]
    if filtros.get('status'):
        clauses.append('e.status = %s')
        params.append(filtros['status'])
    where = ' AND '.join(clauses)
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT e.*,
                   cat.slug AS category_slug,
                   cat.label AS category_label
            FROM finance_expenses e
            LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
            WHERE {where}
            ORDER BY e.expense_date DESC NULLS LAST, e.created_at DESC
        ''', params)
        return [_serialize_row(r) for r in cur.fetchall()]


def _summary_filter_clauses(filtros, alias='s'):
    filtros = filtros or {}
    clauses = []
    params = []
    prefix = f'{alias}.'
    if filtros.get('status'):
        clauses.append(f'{prefix}status = %s')
        params.append(filtros['status'])
    if filtros.get('user_id'):
        clauses.append(f'{prefix}user_id = %s')
        params.append(filtros['user_id'])
    if filtros.get('date_from'):
        clauses.append(f'{prefix}reference_month >= date_trunc(\'month\', %s::date)')
        params.append(filtros['date_from'])
    if filtros.get('date_to'):
        clauses.append(f'{prefix}reference_month <= date_trunc(\'month\', %s::date)')
        params.append(filtros['date_to'])
    return clauses, params


def list_all_summaries(filtros=None):
    conn = get_db()
    clauses, params = _summary_filter_clauses(filtros)
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT s.*,
                   u.nome_completo AS user_name,
                   u.email AS user_email,
                   (SELECT COUNT(*) FROM finance_expenses e WHERE e.summary_id = s.id) AS expense_count,
                   (SELECT COUNT(*) FROM finance_expenses e
                    WHERE e.summary_id = s.id AND e.status NOT IN ('approved', 'rejected')) AS pending_decision_count,
                   (SELECT COALESCE(SUM(total_amount), 0) FROM finance_expenses e
                    WHERE e.summary_id = s.id AND e.status = 'submitted') AS total_submitted
            FROM finance_summary s
            LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = s.user_id
            {where}
            ORDER BY s.created_at DESC
            LIMIT 200
        ''', params)
        return [_serialize_row(r) for r in cur.fetchall()]


def create_expense(user_id, data):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO finance_expenses (
                user_id, status, category_id, association_type, association_label,
                client_id, merchant_name, expense_date, currency, total_amount, notes,
                summary_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
            data.get('summary_id') or None,
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
                   cli.nome_fantasia AS client_name,
                   s.description AS summary_description,
                   s.status AS summary_status
            FROM finance_expenses e
            LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
            LEFT JOIN tbl_cliente cli ON cli.id_cliente = e.client_id
            LEFT JOIN finance_summary s ON s.id = e.summary_id
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
    if filtros.get('summary_id'):
        clauses.append('e.summary_id = %s')
        params.append(filtros['summary_id'])

    where = ' AND '.join(clauses)
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT e.*,
                   cat.slug AS category_slug,
                   cat.label AS category_label,
                   s.description AS summary_description
            FROM finance_expenses e
            LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
            LEFT JOIN finance_summary s ON s.id = e.summary_id
            WHERE {where}
            ORDER BY e.created_at DESC
            LIMIT 200
        ''', params)
        return [_serialize_row(r) for r in cur.fetchall()]


EDITABLE_STATUSES = ('draft', 'rejected', 'extracted', 'extraction_failed')
DELETABLE_STATUSES = EDITABLE_STATUSES
DELETABLE_BEFORE = ('approved', 'closed')


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
        'summary_id': 'summary_id',
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
    expense = get_expense(expense_id)
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('DELETE FROM finance_expenses WHERE id = %s RETURNING id', (expense_id,))
        row = cur.fetchone()
    conn.commit()
    if row and expense and expense.get('summary_id'):
        recalc_summary_totals(expense['summary_id'])
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
    """Resumo do lote aberto + totais gerais."""
    open_sum = get_open_summary(user_id)
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT status,
                   COUNT(*) AS qtd,
                   COALESCE(SUM(total_amount), 0) AS total
            FROM finance_expenses
            WHERE user_id = %s
              AND (summary_id IS NULL OR summary_id IN (
                  SELECT id FROM finance_summary WHERE user_id = %s AND status = 'open'
              ))
            GROUP BY status
        ''', (user_id, user_id))
        by_status = {_serialize_row(r)['status']: _serialize_row(r) for r in cur.fetchall()}

    return {
        'by_status': by_status,
        'open_summary': open_sum,
        'open_description': (open_sum or {}).get('description'),
        'total_payable': (open_sum or {}).get('total_payable') or 0,
        'total_rejected': (open_sum or {}).get('total_rejected') or 0,
        'draft_total': (by_status.get('draft') or {}).get('total') or 0,
        'submitted_total': (by_status.get('submitted') or {}).get('total') or 0,
        'approved_total': (open_sum or {}).get('total_payable') or 0,
        'rejected_total': (open_sum or {}).get('total_rejected') or 0,
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
    if filtros.get('summary_id'):
        clauses.append('e.summary_id = %s')
        params.append(filtros['summary_id'])
    return clauses, params


def list_all_expenses(filtros=None):
    conn = get_db()
    clauses, params = _admin_filter_clauses(filtros)
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT e.*,
                   cat.slug  AS category_slug,
                   cat.label AS category_label,
                   u.nome_completo AS user_name,
                   u.email         AS user_email,
                   s.description   AS summary_description
            FROM finance_expenses e
            LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
            LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = e.user_id
            LEFT JOIN finance_summary s ON s.id = e.summary_id
            {where}
            ORDER BY e.expense_date DESC NULLS LAST, e.created_at DESC
            LIMIT 500
        ''', params)
        return [_serialize_row(r) for r in cur.fetchall()]


def admin_summary(filtros=None):
    """Totais agregados de summaries abertos (a pagar + rejeitados + enviados)."""
    conn = get_db()
    filtros = dict(filtros or {})
    clauses, params = _summary_filter_clauses(filtros)
    clauses.append("s.status = 'open'")
    sum_where = 'WHERE ' + ' AND '.join(clauses)

    exp_clauses, exp_params = _admin_filter_clauses(filtros)
    exp_clauses = [c for c in exp_clauses if not c.startswith('e.status')]
    exp_clauses.append("s.status = 'open'")
    exp_where = ' AND '.join(exp_clauses)

    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT
                COALESCE(SUM(s.total_payable), 0) AS payable_total,
                COALESCE(SUM(s.total_rejected), 0) AS rejected_total,
                COUNT(*) AS open_qtd
            FROM finance_summary s
            {sum_where}
        ''', params)
        agg = _serialize_row(cur.fetchone()) or {}

        cur.execute(f'''
            SELECT COALESCE(SUM(e.total_amount), 0) AS total,
                   COUNT(*) AS qtd
            FROM finance_expenses e
            JOIN finance_summary s ON s.id = e.summary_id
            WHERE e.status = 'submitted' AND {exp_where}
        ''', exp_params)
        submitted = _serialize_row(cur.fetchone()) or {}

        cur.execute(f'''
            SELECT COALESCE(SUM(e.total_amount), 0) AS total,
                   COUNT(*) AS qtd
            FROM finance_expenses e
            JOIN finance_summary s ON s.id = e.summary_id
            WHERE e.status IN ('draft', 'extracted', 'extraction_failed') AND {exp_where}
        ''', exp_params)
        draft = _serialize_row(cur.fetchone()) or {}

        cur.execute('''
            SELECT COUNT(*) AS cnt FROM finance_summary WHERE status = 'paid'
        ''')
        paid_row = _serialize_row(cur.fetchone()) or {}

    return {
        'payable_total': agg.get('payable_total') or 0,
        'rejected_total': agg.get('rejected_total') or 0,
        'open_qtd': agg.get('open_qtd') or 0,
        'paid_qtd': paid_row.get('cnt') or 0,
        'submitted_total': submitted.get('total') or 0,
        'submitted_qtd': submitted.get('qtd') or 0,
        'approved_total': agg.get('payable_total') or 0,
        'approved_qtd': agg.get('open_qtd') or 0,
        'draft_total': draft.get('total') or 0,
        'draft_qtd': draft.get('qtd') or 0,
        'rejected_qtd': agg.get('open_qtd') or 0,
    }


def list_expense_users():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute('''
            SELECT DISTINCT u.id_contato_cliente AS id, u.nome_completo AS nome, u.email
            FROM finance_summary s
            JOIN tbl_contato_cliente u ON u.id_contato_cliente = s.user_id
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
