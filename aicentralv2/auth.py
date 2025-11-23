"""
AIcentralv2 - Sistema de Autenticação
"""
from functools import wraps
from flask import session, redirect, url_for, flash, jsonify, request

def login_required(f):
    """Decorador para proteger rotas que exigem login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorador para proteger rotas administrativas (admin ou superadmin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        
        user_type = session.get('user_type', 'client')
        if user_type not in ['admin', 'superadmin']:
            flash('Acesso negado. Esta área é restrita a administradores.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def superadmin_required(f):
    """Decorador para proteger rotas de super administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        
        user_type = session.get('user_type', 'client')
        if user_type != 'superadmin':
            flash('Acesso negado. Esta área é restrita a super administradores.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def is_logged_in():
    """Verifica se o usuário está logado"""
    return 'user_id' in session


def is_admin():
    """Verifica se o usuário é admin ou superadmin"""
    return session.get('user_type') in ['admin', 'superadmin']


def is_superadmin():
    """Verifica se o usuário é superadmin"""
    return session.get('user_type') == 'superadmin'


def get_current_user():
    """Retorna o ID do usuário atual"""
    return session.get('user_id')


def admin_required_api(f):
    """
    Decorador para proteger rotas de API que retornam JSON
    Retorna JSON ao invés de redirect quando não autenticado
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Sessão expirada. Faça login novamente.'}), 401
        
        user_type = session.get('user_type', 'client')
        if user_type not in ['admin', 'superadmin']:
            return jsonify({'success': False, 'error': 'Acesso negado. Permissão insuficiente.'}), 403
        
        return f(*args, **kwargs)
    return decorated_function


def superadmin_required_api(f):
    """
    Decorador para proteger rotas de API de superadmin que retornam JSON
    Retorna JSON ao invés de redirect quando não autenticado
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Sessão expirada. Faça login novamente.'}), 401
        
        user_type = session.get('user_type', 'client')
        if user_type != 'superadmin':
            return jsonify({'success': False, 'error': 'Acesso negado. Apenas super administradores.'}), 403
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_username():
    """Retorna o username do usuário atual"""
    return session.get('username')


def get_current_user_fullname():
    """Retorna o nome completo do usuário atual"""
    return session.get('user_fullname')


def get_current_user_type():
    """Retorna o tipo do usuário atual"""
    return session.get('user_type', 'client')
