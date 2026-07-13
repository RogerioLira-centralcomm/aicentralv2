"""Permissões do módulo financeiro / reembolsos."""
from functools import wraps
from flask import session, redirect, url_for, flash, jsonify


def is_finance_admin():
    """True se o usuário tem flag is_finance_admin ou é admin/superadmin."""
    if session.get('is_finance_admin'):
        return True
    return session.get('user_type') in ('admin', 'superadmin')


def finance_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        if not is_finance_admin():
            flash('Acesso restrito ao time financeiro.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


def finance_admin_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Não autenticado'}), 401
        if not is_finance_admin():
            return jsonify({'success': False, 'error': 'Acesso restrito ao time financeiro'}), 403
        return f(*args, **kwargs)
    return decorated


def user_owns_expense(expense, user_id=None):
    uid = user_id if user_id is not None else session.get('user_id')
    if not expense or not uid:
        return False
    return int(expense.get('user_id') or 0) == int(uid)


def can_access_expense(expense, user_id=None):
    if is_finance_admin():
        return True
    return user_owns_expense(expense, user_id)
