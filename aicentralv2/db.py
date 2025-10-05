"""
Módulo de banco de dados - PostgreSQL
"""
import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash, check_password_hash
from flask import g, current_app


def get_db():
    """
    Retorna a conexão com o banco de dados
    Usa g para manter a conexão durante o request
    """
    if 'db' not in g:
        # Construir URL de conexão a partir das configurações
        db_config = current_app.config

        DATABASE_URL = (
            f"postgresql://"
            f"{db_config['DB_USER']}:{db_config['DB_PASSWORD']}@"
            f"{db_config['DB_HOST']}:{db_config['DB_PORT']}/"
            f"{db_config['DB_NAME']}"
        )

        g.db = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            autocommit=False
        )

    return g.db


def close_db(e=None):
    """
    Fecha a conexão com o banco de dados
    """
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db(app):
    """
    Inicializa o banco de dados
    Cria as tabelas se não existirem
    """
    with app.app_context():
        conn = get_db()

        with conn.cursor() as cursor:
            # Criar tabela de usuários
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    nome_completo VARCHAR(200) NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    idade INTEGER NOT NULL,
                    id_cliente INTEGER,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_users_cliente
                        FOREIGN KEY (id_cliente)
                        REFERENCES tbl_cliente (id_cliente)
                        ON UPDATE NO ACTION
                        ON DELETE SET NULL
                )
            ''')

            # Criar índices
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)
            ''')

        conn.commit()


def criar_usuario_admin_padrao():
    """
    Cria um usuário admin padrão se não existir
    Email: admin@admin.com
    Senha: admin123
    """
    conn = get_db()

    with conn.cursor() as cursor:
        # Verificar se já existe algum admin
        cursor.execute('SELECT COUNT(*) as total FROM users WHERE is_admin = TRUE')
        resultado = cursor.fetchone()

        if resultado['total'] == 0:
            # Criar admin padrão
            password_hash = generate_password_hash('admin123')

            cursor.execute('''
                INSERT INTO users 
                    (username, password_hash, nome_completo, email, idade, is_active, is_admin)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', ('admin', password_hash, 'Administrador', 'admin@admin.com', 30, True, True))

            conn.commit()
            return True

    return False


# ==================== FUNÇÕES DE AUTENTICAÇÃO ====================

def verificar_credenciais(email, password):
    """
    Verifica as credenciais de login
    Retorna o usuário se válido, None se inválido
    """
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT * FROM users 
            WHERE email = %s AND is_active = TRUE
        ''', (email,))

        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            return user

    return None


# ==================== FUNÇÕES DE USUÁRIOS ====================

def obter_usuarios():
    """
    Retorna todos os usuários com informações do cliente vinculado
    """
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                u.id,
                u.username,
                u.nome_completo,
                u.email,
                u.idade,
                u.is_active,
                u.is_admin,
                u.created_at,
                u.updated_at,
                u.id_cliente,
                c.nome_fantasia,
                c.razao_social,
                c.cnpj,
                c.status as cliente_status
            FROM users u
            LEFT JOIN tbl_cliente c ON u.id_cliente = c.id_cliente
            ORDER BY u.created_at DESC
        ''')
        return cursor.fetchall()


def obter_usuario_por_id(user_id):
    """
    Retorna um usuário específico
    """
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        return cursor.fetchone()


def obter_usuario_por_id_com_cliente(user_id):
    """
    Retorna um usuário específico com informações do cliente
    """
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                u.id,
                u.username,
                u.nome_completo,
                u.email,
                u.idade,
                u.is_active,
                u.is_admin,
                u.created_at,
                u.updated_at,
                u.id_cliente,
                c.nome_fantasia,
                c.razao_social,
                c.cnpj,
                c.status as cliente_status
            FROM users u
            LEFT JOIN tbl_cliente c ON u.id_cliente = c.id_cliente
            WHERE u.id = %s
        ''', (user_id,))
        return cursor.fetchone()


def obter_usuario_por_email(email):
    """
    Retorna um usuário pelo email
    """
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        return cursor.fetchone()


def criar_usuario(username, password, nome, email, idade, id_cliente=None):
    """
    Cria um novo usuário com cliente vinculado
    """
    conn = get_db()
    password_hash = generate_password_hash(password)

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO users 
                    (username, password_hash, nome_completo, email, idade, id_cliente, is_active, is_admin)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, FALSE)
                RETURNING id
            ''', (username, password_hash, nome, email, idade, id_cliente))

            novo_id = cursor.fetchone()['id']

        conn.commit()
        return novo_id

    except Exception as e:
        conn.rollback()
        raise


def atualizar_usuario(user_id, nome, email, idade, id_cliente=None):
    """
    Atualiza dados de um usuário
    """
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE users
                SET nome_completo = %s,
                    email = %s,
                    idade = %s,
                    id_cliente = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (nome, email, idade, id_cliente, user_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def atualizar_senha(user_id, nova_senha):
    """
    Atualiza a senha de um usuário
    """
    conn = get_db()
    password_hash = generate_password_hash(nova_senha)

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE users
                SET password_hash = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (password_hash, user_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def alternar_status_usuario(user_id, novo_status):
    """
    Ativa ou desativa um usuário
    """
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE users
                SET is_active = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (novo_status, user_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def deletar_usuario(user_id):
    """
    Deleta permanentemente um usuário
    """
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def gerar_username(nome_completo):
    """
    Gera um username único baseado no nome completo
    """
    import re
    import random

    # Pegar primeiro nome e remover caracteres especiais
    primeiro_nome = nome_completo.split()[0].lower()
    username_base = re.sub(r'[^a-z0-9]', '', primeiro_nome)

    conn = get_db()

    # Tentar username base
    with conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) as total FROM users WHERE username = %s', (username_base,))
        resultado = cursor.fetchone()

        if resultado['total'] == 0:
            return username_base

    # Se já existe, adicionar número
    for i in range(1, 1000):
        username = f"{username_base}{i}"

        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as total FROM users WHERE username = %s', (username,))
            resultado = cursor.fetchone()

            if resultado['total'] == 0:
                return username

    # Se não conseguiu, usar random
    username = f"{username_base}{random.randint(1000, 9999)}"
    return username


# ==================== FUNÇÕES DE CLIENTES ====================

def obter_clientes_ativos():
    """
    Retorna todos os clientes ativos para seleção
    """
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                id_cliente,
                nome_fantasia,
                razao_social,
                cnpj
            FROM tbl_cliente
            WHERE status = TRUE
            ORDER BY nome_fantasia
        ''')
        return cursor.fetchall()
    

def buscar_usuario_por_email(email):
    """
    Busca usuário por email
    Retorna o usuário se encontrado, None caso contrário
    """
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT * FROM users 
            WHERE email = %s
        ''', (email,))
        
        user = cursor.fetchone()
        return user
    
    return None


def buscar_usuario_por_token(token):
    """
    Busca usuário por reset_token
    Retorna o usuário se encontrado, None caso contrário
    """
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT * FROM users 
            WHERE reset_token = %s
        ''', (token,))
        
        user = cursor.fetchone()
        return user
    
    return None


def atualizar_reset_token(email, token, expires):
    """
    Atualiza token de reset de senha do usuário
    """
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            UPDATE users 
            SET reset_token = %s, 
                reset_token_expires = %s
            WHERE email = %s
        ''', (token, expires, email))
        
        conn.commit()


def atualizar_senha(user_id, nova_senha_hash):
    """
    Atualiza senha do usuário e limpa token de reset
    """
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            UPDATE users 
            SET password_hash = %s, 
                reset_token = NULL, 
                reset_token_expires = NULL
            WHERE id = %s
        ''', (nova_senha_hash, user_id))
        
        conn.commit()