"""Rotas do módulo Financeiro — Reembolsos (Fase 1)."""
from flask import (
    render_template, request, jsonify, session, send_file, current_app, abort,
)
import os

from ..auth import login_required, login_required_api
from . import bp
from . import db_finance as fin
from .permissions import (
    is_finance_admin, finance_admin_required, finance_admin_required_api,
    can_access_expense, user_owns_expense,
)
from .storage import ReceiptStorage, validate_upload
from .db_finance import EDITABLE_STATUSES, DELETABLE_STATUSES
from .extraction import extract_receipt


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


MAX_IMPORT_BATCH = 20
MAX_SUBMIT_BATCH = 50


def _import_single_receipt(file, user_id):
    """Importa um comprovante: cria rascunho, salva arquivo e roda OCR.

    Retorna dict com success, expense, ai_ok, error, filename.
    """
    filename = file.filename or 'comprovante'
    ok, err = validate_upload(file)
    if not ok:
        return {'success': False, 'error': err, 'filename': filename}

    try:
        file.stream.seek(0)
        file_bytes = file.stream.read()
        file.stream.seek(0)
    except Exception:
        file_bytes = None

    ext = os.path.splitext(filename)[1].lower()

    try:
        expense = fin.create_expense(user_id, {'status': 'processing'})
    except Exception as e:
        current_app.logger.error(f'_import_single_receipt create: {e}', exc_info=True)
        return {'success': False, 'error': 'Falha ao criar rascunho', 'filename': filename}

    expense_id = expense['id']
    storage = ReceiptStorage()
    try:
        meta = storage.save(file, expense_id)
        fin.add_receipt_file(expense_id, meta)
    except ValueError as ve:
        fin.update_expense(expense_id, {'status': 'draft', 'needs_review': True})
        return {'success': False, 'error': str(ve), 'filename': filename}
    except Exception as e:
        current_app.logger.error(f'_import_single_receipt save: {e}', exc_info=True)
        fin.update_expense(expense_id, {'status': 'draft', 'needs_review': True})
        return {'success': False, 'error': 'Falha ao salvar comprovante', 'filename': filename}

    extracted = None
    if file_bytes:
        try:
            extracted = extract_receipt(file_bytes, ext, filename)
        except Exception as e:
            current_app.logger.error(f'_import_single_receipt ocr: {e}', exc_info=True)
            extracted = None

    update = {'status': 'draft'}
    if extracted:
        if extracted.get('expense_date'):
            update['expense_date'] = extracted['expense_date']
        if extracted.get('total_amount') is not None:
            update['total_amount'] = extracted['total_amount']
        if extracted.get('merchant_name'):
            update['merchant_name'] = extracted['merchant_name']
        cat_id = fin.get_category_id_by_slug(extracted.get('suggested_category_slug'))
        if cat_id:
            update['category_id'] = cat_id
        conf = extracted.get('confidence')
        update['ai_confidence'] = conf
        update['needs_review'] = bool(conf is None or conf < 0.7)
        update['ai_raw_response'] = extracted
    else:
        update['needs_review'] = True

    try:
        fin.update_expense(expense_id, update)
        if extracted and extracted.get('items'):
            fin.replace_expense_items(expense_id, extracted['items'])
    except Exception as e:
        current_app.logger.error(f'_import_single_receipt update: {e}', exc_info=True)

    fin.write_audit(user_id, 'expense', expense_id, 'imported', {
        'status': update.get('status'),
        'ai': bool(extracted),
    })

    result = fin.get_expense(expense_id)
    return {
        'success': True,
        'expense': _expense_payload(result),
        'ai_ok': bool(extracted),
        'error': None,
        'filename': filename,
    }


def _try_submit_expense(expense_id, user_id):
    """Valida e envia uma despesa. Retorna (success, error_msg)."""
    expense = fin.get_expense(expense_id)
    if not expense:
        return False, 'Despesa não encontrada'
    if not user_owns_expense(expense, user_id):
        return False, 'Acesso negado'
    if expense['status'] not in EDITABLE_STATUSES:
        return False, 'Status não permite envio'
    if not expense.get('total_amount'):
        return False, 'Informe o valor total antes de enviar'
    if not expense.get('expense_date'):
        return False, 'Informe a data da despesa antes de enviar'
    receipts = fin.list_receipts(expense_id)
    if not receipts:
        return False, 'Anexe ao menos um comprovante antes de enviar'

    fin.update_expense(expense_id, {'status': 'submitted', 'rejection_reason': None})
    fin.write_audit(user_id, 'expense', expense_id, 'submitted')
    return True, None


def _try_review_expense(expense_id, action, reviewer_id, rejection_reason=None):
    """Aprova ou reprova despesa enviada. Retorna (success, error_msg)."""
    expense = fin.get_expense(expense_id)
    if not expense:
        return False, 'Despesa não encontrada'
    if expense['status'] != 'submitted':
        return False, 'Só é possível revisar despesas com status enviado'

    if action == 'approve':
        fin.update_expense(expense_id, {'status': 'approved', 'rejection_reason': None})
        fin.write_audit(reviewer_id, 'expense', expense_id, 'approved')
        return True, None

    if action == 'reject':
        reason = (rejection_reason or '').strip()
        if not reason:
            return False, 'Informe o motivo da reprovação'
        fin.update_expense(expense_id, {'status': 'rejected', 'rejection_reason': reason})
        fin.write_audit(reviewer_id, 'expense', expense_id, 'rejected', {'reason': reason})
        return True, None

    return False, 'Ação inválida'


# --------------- Páginas ---------------

@bp.route('/meus-reembolsos')
@login_required
def meus_reembolsos():
    return render_template('financeiro/meus_reembolsos.html')


@bp.route('/gestao')
@finance_admin_required
def gestao_reembolsos():
    """Painel admin — listagem de reembolsos (data/valor/usuário/categoria/status)."""
    return render_template('financeiro/gestao.html')


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


@bp.route('/api/expenses/import', methods=['POST'])
@login_required_api
def api_import_expense():
    """Importa um comprovante (compatibilidade com fluxo unitário)."""
    file = request.files.get('file') or request.files.get('receipt')
    if not file:
        return jsonify({'success': False, 'error': 'Arquivo obrigatório (campo file)'}), 400

    result = _import_single_receipt(file, _uid())
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 400

    return jsonify({
        'success': True,
        'expense': result['expense'],
        'ai_ok': result['ai_ok'],
    }), 201


@bp.route('/api/expenses/import-bulk', methods=['POST'])
@login_required_api
def api_import_expense_bulk():
    """Importa vários comprovantes de uma vez (1 arquivo = 1 rascunho)."""
    files = request.files.getlist('file') or request.files.getlist('files')
    if not files:
        single = request.files.get('file') or request.files.get('receipt')
        files = [single] if single else []

    if not files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado (campo file)'}), 400
    if len(files) > MAX_IMPORT_BATCH:
        return jsonify({
            'success': False,
            'error': f'Máximo de {MAX_IMPORT_BATCH} arquivos por importação. Divida em lotes menores.',
        }), 400

    user_id = _uid()
    expenses = []
    failed = []

    for f in files:
        result = _import_single_receipt(f, user_id)
        if result['success']:
            expenses.append(result['expense'])
        else:
            failed.append({'filename': result['filename'], 'error': result['error']})

    return jsonify({
        'success': True,
        'total': len(files),
        'created': len(expenses),
        'failed': failed,
        'expenses': expenses,
    }), 201


@bp.route('/api/expenses/submit-bulk', methods=['POST'])
@login_required_api
def api_submit_expense_bulk():
    """Envia vários reembolsos de uma vez (sucesso parcial)."""
    data = request.get_json() or {}
    expense_ids = data.get('expense_ids') or []
    if not isinstance(expense_ids, list) or not expense_ids:
        return jsonify({'success': False, 'error': 'Informe expense_ids (lista de UUIDs)'}), 400
    if len(expense_ids) > MAX_SUBMIT_BATCH:
        return jsonify({
            'success': False,
            'error': f'Máximo de {MAX_SUBMIT_BATCH} reembolsos por envio.',
        }), 400

    user_id = _uid()
    submitted = []
    failed = []

    for eid in expense_ids:
        ok, err = _try_submit_expense(str(eid), user_id)
        if ok:
            submitted.append(str(eid))
        else:
            failed.append({'id': str(eid), 'error': err})

    return jsonify({'success': True, 'submitted': submitted, 'failed': failed})


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
    ok, err = _try_submit_expense(expense_id, _uid())
    if not ok:
        status = 404 if err == 'Despesa não encontrada' else 403 if err == 'Acesso negado' else 400
        return jsonify({'success': False, 'error': err}), status
    return jsonify({'success': True, 'expense': _expense_payload(fin.get_expense(expense_id))})


@bp.route('/api/expenses/<expense_id>', methods=['DELETE'])
@login_required_api
def api_delete_expense(expense_id):
    expense = fin.get_expense(expense_id)
    if not expense:
        return jsonify({'success': False, 'error': 'Despesa não encontrada'}), 404
    if not user_owns_expense(expense) and not is_finance_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    if expense['status'] not in DELETABLE_STATUSES:
        return jsonify({'success': False, 'error': 'Não é possível excluir uma despesa já enviada.'}), 400

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


# --------------- API admin (gestão) ---------------

def _admin_filtros():
    filtros = {
        'status': request.args.get('status') or None,
        'category_id': request.args.get('category_id') or None,
        'user_id': request.args.get('user_id') or None,
        'date_from': request.args.get('date_from') or None,
        'date_to': request.args.get('date_to') or None,
    }
    if filtros['category_id']:
        try:
            filtros['category_id'] = int(filtros['category_id'])
        except (TypeError, ValueError):
            filtros['category_id'] = None
    if filtros['user_id']:
        try:
            filtros['user_id'] = int(filtros['user_id'])
        except (TypeError, ValueError):
            filtros['user_id'] = None
    return filtros


@bp.route('/api/admin/expenses', methods=['GET'])
@finance_admin_required_api
def api_admin_expenses():
    rows = fin.list_all_expenses(_admin_filtros())
    return jsonify({'success': True, 'expenses': rows})


@bp.route('/api/admin/summary', methods=['GET'])
@finance_admin_required_api
def api_admin_summary():
    return jsonify({'success': True, 'summary': fin.admin_summary(_admin_filtros())})


@bp.route('/api/admin/users', methods=['GET'])
@finance_admin_required_api
def api_admin_users():
    return jsonify({'success': True, 'users': fin.list_expense_users()})


@bp.route('/api/admin/expenses/<expense_id>/approve', methods=['POST'])
@finance_admin_required_api
def api_admin_approve_expense(expense_id):
    ok, err = _try_review_expense(expense_id, 'approve', _uid())
    if not ok:
        status = 404 if err == 'Despesa não encontrada' else 400
        return jsonify({'success': False, 'error': err}), status
    return jsonify({'success': True, 'expense': _expense_payload(fin.get_expense(expense_id))})


@bp.route('/api/admin/expenses/<expense_id>/reject', methods=['POST'])
@finance_admin_required_api
def api_admin_reject_expense(expense_id):
    data = request.get_json() or {}
    ok, err = _try_review_expense(
        expense_id, 'reject', _uid(), data.get('rejection_reason'),
    )
    if not ok:
        status = 404 if err == 'Despesa não encontrada' else 400
        return jsonify({'success': False, 'error': err}), status
    return jsonify({'success': True, 'expense': _expense_payload(fin.get_expense(expense_id))})
