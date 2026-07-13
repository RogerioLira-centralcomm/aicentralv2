"""Rotas do módulo Financeiro — Reembolsos (Fase 1)."""
from flask import (
    render_template, request, jsonify, session, send_file, current_app, abort,
)
from ..auth import login_required, login_required_api
from . import bp
from . import db_finance as fin
from .permissions import (
    is_finance_admin, finance_admin_required, can_access_expense, user_owns_expense,
)
from .storage import ReceiptStorage
from .db_finance import EDITABLE_STATUSES, DELETABLE_BEFORE


def _uid():
    return session.get('user_id')


def _expense_payload(expense):
    if not expense:
        return None
    items = fin.list_expense_items(expense['id'])
    receipts = fin.list_receipts(expense['id'])
    for r in receipts:
        r['download_url'] = f"/financeiro/api/receipts/{r['id']}/download"
    return {**expense, 'items': items, 'receipts': receipts}


# --------------- Páginas ---------------

@bp.route('/meus-reembolsos')
@login_required
def meus_reembolsos():
    return render_template(
        'financeiro/meus_reembolsos.html',
        is_finance_admin=is_finance_admin(),
    )


@bp.route('/gestao')
@finance_admin_required
def gestao_reembolsos():
    """Placeholder Fase 3 — conciliação admin."""
    return render_template('financeiro/gestao_placeholder.html')


# --------------- API colaborador ---------------

@bp.route('/api/categories')
@login_required_api
def api_categories():
    return jsonify({'success': True, 'categories': fin.list_categories()})


@bp.route('/api/clients')
@login_required_api
def api_clients():
    q = request.args.get('q', '')
    return jsonify({'success': True, 'clients': fin.search_clients(q)})


@bp.route('/api/my/summary')
@login_required_api
def api_my_summary():
    return jsonify({'success': True, 'summary': fin.summary_for_user(_uid())})


@bp.route('/api/expenses', methods=['GET'])
@login_required_api
def api_list_expenses():
    filtros = {
        'status': request.args.get('status') or None,
        'association_type': request.args.get('association_type') or None,
        'date_from': request.args.get('date_from') or None,
        'date_to': request.args.get('date_to') or None,
    }
    rows = fin.list_expenses_for_user(_uid(), filtros)
    return jsonify({'success': True, 'expenses': rows})


@bp.route('/api/expenses', methods=['POST'])
@login_required_api
def api_create_expense():
    data = request.get_json() or {}
    try:
        total = data.get('total_amount')
        if total is not None and total != '':
            data['total_amount'] = float(total)
        else:
            data['total_amount'] = None

        if data.get('category_id'):
            data['category_id'] = int(data['category_id'])
        if data.get('client_id'):
            data['client_id'] = int(data['client_id'])

        data['status'] = 'draft'
        expense = fin.create_expense(_uid(), data)

        items = data.get('items') or []
        if items:
            fin.replace_expense_items(expense['id'], items)

        fin.write_audit(_uid(), 'expense', expense['id'], 'created', {'status': 'draft'})
        return jsonify({'success': True, 'expense': _expense_payload(fin.get_expense(expense['id']))}), 201
    except Exception as e:
        current_app.logger.error(f'api_create_expense: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/expenses/<expense_id>', methods=['GET'])
@login_required_api
def api_get_expense(expense_id):
    expense = fin.get_expense(expense_id)
    if not expense:
        return jsonify({'success': False, 'error': 'Despesa não encontrada'}), 404
    if not can_access_expense(expense):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    return jsonify({'success': True, 'expense': _expense_payload(expense)})


@bp.route('/api/expenses/<expense_id>', methods=['PATCH'])
@login_required_api
def api_patch_expense(expense_id):
    expense = fin.get_expense(expense_id)
    if not expense:
        return jsonify({'success': False, 'error': 'Despesa não encontrada'}), 404
    if not user_owns_expense(expense) and not is_finance_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    if expense['status'] not in EDITABLE_STATUSES:
        return jsonify({'success': False, 'error': f'Não é possível editar despesa com status {expense["status"]}'}), 400

    data = request.get_json() or {}
    if 'total_amount' in data and data['total_amount'] not in (None, ''):
        data['total_amount'] = float(data['total_amount'])
    if 'category_id' in data and data['category_id'] not in (None, ''):
        data['category_id'] = int(data['category_id'])
    elif 'category_id' in data:
        data['category_id'] = None
    if 'client_id' in data and data['client_id'] not in (None, ''):
        data['client_id'] = int(data['client_id'])
    elif 'client_id' in data:
        data['client_id'] = None

    # colaborador não muda status via PATCH genérico
    data.pop('status', None)

    updated = fin.update_expense(expense_id, data)
    if 'items' in (request.get_json() or {}):
        fin.replace_expense_items(expense_id, request.get_json().get('items') or [])

    fin.write_audit(_uid(), 'expense', expense_id, 'updated', data)
    return jsonify({'success': True, 'expense': _expense_payload(fin.get_expense(expense_id))})


@bp.route('/api/expenses/<expense_id>/submit', methods=['POST'])
@login_required_api
def api_submit_expense(expense_id):
    expense = fin.get_expense(expense_id)
    if not expense:
        return jsonify({'success': False, 'error': 'Despesa não encontrada'}), 404
    if not user_owns_expense(expense):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    if expense['status'] not in ('draft', 'rejected', 'extracted', 'extraction_failed'):
        return jsonify({'success': False, 'error': 'Status não permite envio'}), 400

    if not expense.get('total_amount'):
        return jsonify({'success': False, 'error': 'Informe o valor total antes de enviar'}), 400
    if not expense.get('expense_date'):
        return jsonify({'success': False, 'error': 'Informe a data da despesa antes de enviar'}), 400

    receipts = fin.list_receipts(expense_id)
    if not receipts:
        return jsonify({'success': False, 'error': 'Anexe ao menos um comprovante antes de enviar'}), 400

    fin.update_expense(expense_id, {'status': 'submitted', 'rejection_reason': None})
    fin.write_audit(_uid(), 'expense', expense_id, 'submitted')
    return jsonify({'success': True, 'expense': _expense_payload(fin.get_expense(expense_id))})


@bp.route('/api/expenses/<expense_id>', methods=['DELETE'])
@login_required_api
def api_delete_expense(expense_id):
    expense = fin.get_expense(expense_id)
    if not expense:
        return jsonify({'success': False, 'error': 'Despesa não encontrada'}), 404
    if not user_owns_expense(expense) and not is_finance_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    if expense['status'] in DELETABLE_BEFORE:
        return jsonify({'success': False, 'error': 'Não é possível excluir despesa aprovada ou fechada'}), 400

    storage = ReceiptStorage()
    for r in fin.list_receipts(expense_id):
        try:
            storage.delete(r['storage_key'])
        except Exception:
            pass

    fin.delete_expense(expense_id)
    fin.write_audit(_uid(), 'expense', expense_id, 'deleted')
    return jsonify({'success': True})


@bp.route('/api/expenses/<expense_id>/receipts', methods=['POST'])
@login_required_api
def api_upload_receipt(expense_id):
    expense = fin.get_expense(expense_id)
    if not expense:
        return jsonify({'success': False, 'error': 'Despesa não encontrada'}), 404
    if not user_owns_expense(expense) and not is_finance_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    if expense['status'] not in EDITABLE_STATUSES:
        return jsonify({'success': False, 'error': 'Não é possível anexar neste status'}), 400

    file = request.files.get('file') or request.files.get('receipt')
    if not file:
        return jsonify({'success': False, 'error': 'Arquivo obrigatório (campo file)'}), 400

    storage = ReceiptStorage()
    try:
        meta = storage.save(file, expense_id)
        row = fin.add_receipt_file(expense_id, meta)
        fin.write_audit(_uid(), 'expense', expense_id, 'receipt_uploaded', {'receipt_id': row['id']})
        row['download_url'] = f"/financeiro/api/receipts/{row['id']}/download"
        return jsonify({'success': True, 'receipt': row}), 201
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f'upload receipt: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/receipts/<receipt_id>/download')
@login_required
def api_download_receipt(receipt_id):
    receipt = fin.get_receipt(receipt_id)
    if not receipt:
        abort(404)
    expense = fin.get_expense(receipt['expense_id'])
    if not can_access_expense(expense):
        abort(403)

    storage = ReceiptStorage()
    path = storage.absolute_path(receipt['storage_key'])
    if not path:
        abort(404)

    return send_file(
        path,
        mimetype=receipt.get('mime_type') or 'application/octet-stream',
        as_attachment=False,
        download_name=receipt.get('file_name') or 'comprovante',
    )
