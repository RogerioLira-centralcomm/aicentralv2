"""
AIcentralv2 - Sistema de Autenticação
"""
from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    """Decorador para proteger rotas que exigem login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def is_logged_in():
    """Verifica se o usuário está logado"""
    return 'user_id' in session


def get_current_user():
    """Retorna o ID do usuário atual"""
    return session.get('user_id')


def get_current_username():
    """Retorna o username do usuário atual"""
    return session.get('username')


def get_current_user_fullname():
    """Retorna o nome completo do usuário atual"""
    return session.get('user_fullname')