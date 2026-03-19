"""
=====================================================
DATABASE CONNECTION - psycopg 3
Gerenciamento de conexão com PostgreSQL
=====================================================
"""

import psycopg
from psycopg.rows import dict_row
from flask import g, current_app
import os
import hashlib
import bcrypt
from datetime import datetime, timedelta
from typing import List, Optional
import re
import secrets


# ==================== CONFIGURAÇÃO ====================

def get_db_config():
    """Retorna configuração do banco de dados"""
    return {
        'dbname': os.getenv('DB_NAME', 'aicentral_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'row_factory': dict_row
    }


# ==================== CONEXÃO ====================

def get_db():
    """
    Obtém conexão com o banco de dados
    Reutiliza conexão existente ou cria nova
    """
    if 'db' not in g:
        try:
            config = get_db_config()
            g.db = psycopg.connect(**config)
            g.db.autocommit = False
        except Exception as e:
            current_app.logger.error(f"FALHA Erro ao conectar ao banco: {e}")
            raise
    
    return g.db


def close_db(e=None):
    """Fecha a conexão com o banco de dados"""
    db = g.pop('db', None)
    
    if db is not None:
        try:
            if not db.closed:
                db.rollback()
                db.close()
                current_app.logger.debug("OK Conexão com banco fechada")
        except Exception as ex:
            current_app.logger.error(f"FALHA Erro ao fechar conexão: {ex}")


def init_db(app):
    """Inicializa o banco de dados"""
    with app.app_context():
        conn = get_db()

        with conn.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent')

            cursor.execute('''
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'tbl_contato_cliente' AND column_name = 'status'
                    ) THEN
                        ALTER TABLE tbl_contato_cliente ADD COLUMN status BOOLEAN DEFAULT TRUE;
                    END IF;
                END $$;
            ''')
            
            cursor.execute('''
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'tbl_contato_cliente' AND column_name = 'reset_token'
                    ) THEN
                        ALTER TABLE tbl_contato_cliente ADD COLUMN reset_token VARCHAR(100);
                    END IF;
                END $$;
            ''')
            
            cursor.execute('''
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'tbl_contato_cliente' AND column_name = 'reset_token_expires'
                    ) THEN
                        ALTER TABLE tbl_contato_cliente ADD COLUMN reset_token_expires TIMESTAMP;
                    END IF;
                END $$;
            ''')
            # Garantir coluna de SETOR no contato
            cursor.execute('''
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'tbl_contato_cliente' AND column_name = 'pk_id_tbl_setor'
                    ) THEN
                        ALTER TABLE tbl_contato_cliente 
                            ADD COLUMN pk_id_tbl_setor INTEGER;
                        BEGIN
                            ALTER TABLE tbl_contato_cliente 
                                ADD CONSTRAINT fk_setor_contato 
                                FOREIGN KEY (pk_id_tbl_setor) 
                                REFERENCES tbl_setor(id_setor);
                        EXCEPTION WHEN others THEN
                            -- Evita falha caso a constraint já exista com outro nome
                            NULL;
                        END;
                        COMMENT ON COLUMN tbl_contato_cliente.pk_id_tbl_setor IS 'ID do setor do contato (ref tbl_setor)';
                    END IF;
                END $$;
            ''')

            # Criar índices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contato_cliente_email ON tbl_contato_cliente(email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contato_cliente_status ON tbl_contato_cliente(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_contato_cliente_reset_token ON tbl_contato_cliente(reset_token)')

            # Garantir coluna de vendas_central_comm em tbl_cliente (inteiro 0/1)
            cursor.execute('''
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'tbl_cliente' AND column_name = 'vendas_central_comm'
                    ) THEN
                        ALTER TABLE tbl_cliente ADD COLUMN vendas_central_comm INTEGER DEFAULT 0;
                    END IF;
                END $$;
            ''')

            # Removido: pk_id_contato_vendas não faz parte do schema

            # Criar tabela cadu_user_invites
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cadu_user_invites (
                    id SERIAL PRIMARY KEY,
                    id_cliente INTEGER NOT NULL,
                    invited_by INTEGER NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    invite_token VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    role VARCHAR(50) DEFAULT 'member',
                    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    accepted_at TIMESTAMP WITHOUT TIME ZONE,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP),
                    CONSTRAINT fk_invite_cliente FOREIGN KEY (id_cliente) 
                        REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
                    CONSTRAINT fk_invite_invited_by FOREIGN KEY (invited_by) 
                        REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE
                )
            ''')

            # Criar índices para cadu_user_invites
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_invites_email ON cadu_user_invites(email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_invites_token ON cadu_user_invites(invite_token)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_invites_status ON cadu_user_invites(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_invites_cliente ON cadu_user_invites(id_cliente)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_invites_expires ON cadu_user_invites(expires_at)')

            # Criar tabela cadu_cotacao_audiencias
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cadu_cotacao_audiencias (
                    id SERIAL PRIMARY KEY,
                    cotacao_id INTEGER NOT NULL,
                    audiencia_id INTEGER NOT NULL,
                    audiencia_nome VARCHAR(500),
                    audiencia_publico VARCHAR(50),
                    audiencia_categoria VARCHAR(100),
                    audiencia_subcategoria VARCHAR(100),
                    cpm_estimado NUMERIC(10,2),
                    investimento_sugerido NUMERIC(12,2),
                    impressoes_estimadas INTEGER,
                    ordem_exibicao INTEGER DEFAULT 0,
                    incluido_proposta BOOLEAN DEFAULT true,
                    motivo_exclusao TEXT,
                    added_at TIMESTAMP WITHOUT TIME ZONE DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP),
                    CONSTRAINT fk_cotacao_audiencia_cotacao FOREIGN KEY (cotacao_id) 
                        REFERENCES cadu_cotacoes(id) ON DELETE CASCADE,
                    CONSTRAINT fk_cotacao_audiencia_audiencia FOREIGN KEY (audiencia_id) 
                        REFERENCES cadu_audiencias(id_audiencia)
                )
            ''')

            # Criar índices para cadu_cotacao_audiencias
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cotacao_audiencias_cotacao ON cadu_cotacao_audiencias(cotacao_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cotacao_audiencias_audiencia ON cadu_cotacao_audiencias(audiencia_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cotacao_audiencias_incluido ON cadu_cotacao_audiencias(incluido_proposta)')

        conn.commit()
    app.logger.info("OK Banco de dados inicializado")


def check_db_connection():
    """Verifica se a conexão com o banco está funcionando"""
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1')
            return True
    except Exception as e:
        current_app.logger.error(f"FALHA Falha na conexão com banco: {e}")
        return False


# ==================== FUNÇÕES AUXILIARES ====================

def gerar_senha_hash(senha):
    """Gera hash bcrypt da senha"""
    if isinstance(senha, str):
        senha = senha.encode('utf-8')
    return bcrypt.hashpw(senha, bcrypt.gensalt()).decode('utf-8')


def verificar_senha(senha, senha_hash):
    """
    Verifica se senha bate com hash (bcrypt ou MD5 legado)
    Suporta migração automática de MD5 para bcrypt
    """
    if isinstance(senha, str):
        senha = senha.encode('utf-8')
    
    if isinstance(senha_hash, str):
        senha_hash_bytes = senha_hash.encode('utf-8')
    else:
        senha_hash_bytes = senha_hash
    
    # Verifica se é hash bcrypt (começa com $2a$, $2b$ ou $2y$)
    if senha_hash.startswith(('$2a$', '$2b$', '$2y$')):
        try:
            return bcrypt.checkpw(senha, senha_hash_bytes)
        except Exception:
            return False
    
    # Fallback para MD5 legado (32 caracteres hexadecimais)
    if len(senha_hash) == 32 and all(c in '0123456789abcdef' for c in senha_hash.lower()):
        senha_md5 = hashlib.md5(senha).hexdigest()
        return senha_md5 == senha_hash
    
    return False


# Manter funções MD5 legadas apenas para referência (não usar em código novo)
def gerar_senha_md5(senha):
    """[DEPRECATED] Gera hash MD5 da senha - Use gerar_senha_hash() com bcrypt"""
    return hashlib.md5(senha.encode()).hexdigest()


def verificar_senha_md5(senha, senha_md5):
    """[DEPRECATED] Verifica se senha bate com hash MD5 - Use verificar_senha()"""
    return gerar_senha_md5(senha) == senha_md5


# ==================== IMAGEM/EXTRAÇÃO ====================

 


# ==================== VALIDAÇÕES DE DOCUMENTOS ====================

def validar_cpf(cpf: str) -> bool:
    """Valida CPF (Pessoa Física) pelo algoritmo oficial dos dígitos verificadores.

    Regras:
    - Deve conter 11 dígitos numéricos
    - Não pode ser uma sequência repetida (ex.: 00000000000, 11111111111, ...)
    - Dígitos verificadores calculados conforme pesos decrescentes
    """
    if not cpf:
        return False

    # Mantém apenas dígitos
    import re
    digits = re.sub(r"\D", "", str(cpf))

    # Tamanho exato
    if len(digits) != 11:
        return False

    # Rejeitar sequências repetidas
    if digits == digits[0] * 11:
        return False

    # Calcula DV1
    soma = sum(int(digits[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto

    if dv1 != int(digits[9]):
        return False

    # Calcula DV2
    soma = sum(int(digits[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto

    if dv2 != int(digits[10]):
        return False

    return True


# ==================== AUTENTICAÇÃO ====================

def verificar_credenciais(email, password):
    """
    Verifica as credenciais de login
    APENAS PERMITE ACESSO PARA CLIENTES CENTRALCOMM
    """
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.senha,
                c.status,
                c.id_centralx,
                c.pk_id_tbl_cliente,
                c.data_cadastro,
                c.user_type,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj,
                cli.status as cliente_status
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            WHERE c.email = %s
        ''', (email.lower().strip(),))
        
        user = cursor.fetchone()

        # Verificar se usuário existe e senha está correta
        if not user:
            return None
            
        # Verificar se senha está correta (suporta MD5 legado e bcrypt)
        if not verificar_senha(password, user['senha']):
            return None
        
        # Migração automática: se senha ainda é MD5, atualizar para bcrypt
        senha_hash = user['senha']
        if len(senha_hash) == 32 and all(c in '0123456789abcdef' for c in senha_hash.lower()):
            try:
                current_app.logger.info(f"Migrando senha MD5 para bcrypt - Usuário: {user['nome_completo']}")
                novo_hash = gerar_senha_hash(password)
                cursor.execute('''
                    UPDATE tbl_contato_cliente 
                    SET senha = %s 
                    WHERE id_contato_cliente = %s
                ''', (novo_hash, user['id_contato_cliente']))
                conn.commit()
                current_app.logger.info(f"Senha migrada com sucesso - Usuário: {user['nome_completo']}")
            except Exception as e:
                current_app.logger.error(f"Erro ao migrar senha: {e}")
                conn.rollback()
            
        # Verificar se usuário está ativo
        if not user['status']:
            current_app.logger.warning(
                f"Tentativa de login negada - Usuário inativo: {user['nome_completo']} "
                f"(Email: {email})"
            )
            return {'inactive_user': True}
        
        # Verificar se cliente está ativo
        if not user['cliente_status']:
            current_app.logger.warning(
                f"Tentativa de login negada - Cliente inativo: {user['razao_social']} "
                f"(Email: {email})"
            )
            return None

        return user

    return None


# ==================== SETORES E CARGOS ====================

def obter_setores(apenas_ativos=True):
    """Retorna lista de todos os setores
    
    Args:
        apenas_ativos (bool): Se True, retorna apenas setores ativos
    """
    conn = get_db()
    with conn.cursor() as cursor:
        if apenas_ativos:
            cursor.execute('''
                SELECT 
                    id_setor,
                    display,
                    display as descricao,
                    status,
                    data_cadastro,
                    data_modificacao
                FROM tbl_setor
                WHERE status = TRUE
                ORDER BY display
            ''')
        else:
            cursor.execute('''
                SELECT 
                    id_setor,
                    display,
                    display as descricao,
                    status,
                    data_cadastro,
                    data_modificacao
                FROM tbl_setor
                ORDER BY display
            ''')
        return cursor.fetchall()


def obter_vendedores_centralcomm():
    """Retorna contatos do cliente CENTRALCOMM com cargo de Executivo de Vendas (apenas ativos).

    Critérios flexíveis:
    - Cliente com nome/razão contendo 'centralcomm' (com ou sem espaço)
    - Cargo contendo as palavras 'execut' e 'vend' (para cobrir variações),
      ou exatamente a frase 'Executivo de Vendas'.
    """
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            '''
            SELECT c.id_contato_cliente, c.nome_completo
            FROM tbl_contato_cliente c
            JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            LEFT JOIN tbl_cargo_contato car ON c.pk_id_tbl_cargo = car.id_cargo_contato
            WHERE (
                cli.nome_fantasia ILIKE '%centralcomm%'
                 OR cli.razao_social ILIKE '%centralcomm%'
                 OR cli.nome_fantasia ILIKE '%central comm%'
                 OR cli.razao_social ILIKE '%central comm%'
            )
              AND c.status = TRUE
              AND COALESCE(cli.status, TRUE) = TRUE
              AND (
                car.descricao ILIKE '%Executivo de Vendas%'
                 OR (
                    car.descricao ILIKE '%execut%'
                AND car.descricao ILIKE '%vend%'
                )
              )
            ORDER BY c.nome_completo
            '''
        )
        return cur.fetchall()



# ==================== CONTATOS - LISTAR ====================

def obter_contatos():
    """Retorna todos os contatos com informações do cliente"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.status,
                c.id_centralx,
                c.pk_id_tbl_cliente,
                c.data_cadastro,
                c.data_modificacao,
                c.cohorts,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj,
                cli.status as cliente_status,
                cargo.descricao as cargo_descricao
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            LEFT JOIN tbl_cargo_contato cargo ON c.pk_id_tbl_cargo = cargo.id_cargo_contato
            ORDER BY c.data_cadastro DESC
        ''')
        return cursor.fetchall()


def obter_contatos_ativos():
    """Retorna apenas contatos ativos"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.status,
                c.pk_id_tbl_cliente,
                c.pk_id_tbl_cargo,
                cli.nome_fantasia,
                cli.razao_social,
                car.descricao as cargo_descricao
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            LEFT JOIN tbl_cargo_contato car ON c.pk_id_tbl_cargo = car.id_cargo_contato
            WHERE c.status = TRUE AND cli.status = TRUE
            ORDER BY c.nome_completo
        ''')
        return cursor.fetchall()


def obter_contato_por_id(contato_id):
    """Retorna um contato específico"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.status,
                c.id_centralx,
                c.pk_id_tbl_cliente,
                c.pk_id_tbl_cargo,
                c.pk_id_tbl_setor,
                c.data_cadastro,
                c.data_modificacao,
                c.cohorts,
                c.user_type,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj,
                cli.status as cliente_status,
                car.descricao as cargo_descricao,
                car.status as cargo_status,
                car.pk_id_aux_setor,
                s.display as setor_display
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            LEFT JOIN tbl_cargo_contato car ON c.pk_id_tbl_cargo = car.id_cargo_contato
            LEFT JOIN tbl_setor s ON s.id_setor = c.pk_id_tbl_setor
            WHERE c.id_contato_cliente = %s
        ''', (contato_id,))
        return cursor.fetchone()


def obter_contato_por_email(email):
    """Retorna um contato pelo email"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.senha,
                c.status,
                c.id_centralx,
                c.pk_id_tbl_cliente,
                c.data_cadastro,
                c.data_modificacao,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            WHERE c.email = %s
        ''', (email.lower().strip(),))
        return cursor.fetchone()


def obter_contatos_por_cliente(id_cliente):
    """Retorna todos os contatos de um cliente específico, incluindo status de convite"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.status,
                c.data_cadastro,
                c.pk_id_tbl_setor,
                c.pk_id_tbl_cargo,
                s.display as setor,
                cg.descricao as cargo,
                inv.status as invite_status,
                inv.expires_at as invite_expires_at
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_setor s ON c.pk_id_tbl_setor = s.id_setor
            LEFT JOIN tbl_cargo_contato cg ON c.pk_id_tbl_cargo = cg.id_cargo_contato
            LEFT JOIN (
                SELECT email, status, expires_at,
                       ROW_NUMBER() OVER (PARTITION BY email ORDER BY created_at DESC) as rn
                FROM cadu_user_invites
                WHERE id_cliente = %s
            ) inv ON inv.email = c.email AND inv.rn = 1
            WHERE c.pk_id_tbl_cliente = %s
            ORDER BY c.nome_completo
        ''', (id_cliente, id_cliente))
        return cursor.fetchall()


def obter_contatos_ativos_por_cliente(id_cliente):
    """Retorna apenas os contatos ativos de um cliente específico"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                id_contato_cliente,
                email,
                nome_completo,
                telefone,
                data_cadastro
            FROM tbl_contato_cliente
            WHERE pk_id_tbl_cliente = %s AND status = TRUE
            ORDER BY nome_completo
        ''', (id_cliente,))
        return cursor.fetchall()


# ==================== CLIENTES - CRUD ====================

def obter_cliente_por_id(id_cliente):
    """Retorna um cliente específico com informações do plano e agência"""
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_cliente,
                c.razao_social,
                c.nome_fantasia,
                c.pessoa,
                c.cnpj,
                c.inscricao_estadual,
                c.inscricao_municipal,
                c.status,
                c.id_centralx,
                c.bairro,
                c.cidade,
                c.logradouro,
                c.numero,
                c.complemento,
                c.cep,
                c.pk_id_tbl_agencia,
                c.id_tipo_cliente,
                c.pk_id_aux_estado,
                c.vendas_central_comm,
                c.percentual,
                c.data_cadastro,
                c.data_modificacao,
                c.pk_id_tbl_agencia as pk_id_aux_agencia,
                c.pk_id_aux_estado as estado,
                ag.display as agencia_display,
                ag.key as agencia_key,
                tc.display as tipo_cliente_display,
                est.descricao as estado_nome,
                vend.nome_completo as executivo_nome
            FROM tbl_cliente c
            LEFT JOIN tbl_agencia ag ON c.pk_id_tbl_agencia = ag.id_agencia
            LEFT JOIN tbl_tipo_cliente tc ON c.id_tipo_cliente = tc.id_tipo_cliente
            LEFT JOIN tbl_estado est ON c.pk_id_aux_estado = est.id_estado
            LEFT JOIN tbl_contato_cliente vend ON c.vendas_central_comm = vend.id_contato_cliente
            WHERE c.id_cliente = %s
        ''', (id_cliente,))
        return cursor.fetchone()

def criar_cliente(razao_social, nome_fantasia, id_tipo_cliente, pessoa='J', cnpj=None, inscricao_municipal=None, inscricao_estadual=None, 
                status=True, id_centralx=None, bairro=None, cidade=None, rua=None, numero=None, complemento=None, cep=None, pk_id_aux_agencia=None,
                pk_id_aux_estado=None, vendas_central_comm=None, percentual=None):
    """Cria um novo cliente"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO tbl_cliente (
                    razao_social, nome_fantasia, pessoa, cnpj, inscricao_municipal, 
                    inscricao_estadual, status, id_centralx, bairro, cidade, logradouro, numero, 
                    complemento, cep, pk_id_tbl_agencia, id_tipo_cliente, pk_id_aux_estado, vendas_central_comm,
                    percentual
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s
                ) RETURNING id_cliente
            ''', (
                razao_social, nome_fantasia, pessoa, cnpj, inscricao_municipal,
                inscricao_estadual, status, id_centralx, bairro, cidade, rua, numero,
                complemento, cep, pk_id_aux_agencia, id_tipo_cliente, pk_id_aux_estado, vendas_central_comm,
                percentual
            ))
            
            id_cliente = cursor.fetchone()['id_cliente']
            conn.commit()
            return id_cliente

    except Exception as e:
        conn.rollback()
        raise e

def atualizar_cliente(id_cliente, razao_social, nome_fantasia, id_tipo_cliente, pessoa='J', cnpj=None, inscricao_municipal=None, 
                     inscricao_estadual=None, status=True, id_centralx=None, bairro=None, cidade=None, rua=None, 
                     numero=None, complemento=None, cep=None, pk_id_aux_agencia=None, pk_id_aux_estado=None, vendas_central_comm=None,
                     percentual=None):
    """Atualiza um cliente existente"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_cliente SET
                    razao_social = %s,
                    nome_fantasia = %s,
                    pessoa = %s,
                    cnpj = %s,
                    inscricao_municipal = %s,
                    inscricao_estadual = %s,
                    status = %s,
                    id_centralx = %s,
                    bairro = %s,
                    cidade = %s,
                    logradouro = %s,
                    numero = %s,
                    complemento = %s,
                    cep = %s,
                    pk_id_tbl_agencia = %s,
                    pk_id_aux_estado = %s,
                    id_tipo_cliente = %s,
                    percentual = %s,
                    vendas_central_comm = %s,
                    data_modificacao = NOW()
                WHERE id_cliente = %s
            ''', (
                razao_social, nome_fantasia, pessoa, cnpj, inscricao_municipal,
                inscricao_estadual, status, id_centralx, bairro, cidade, rua, numero,
                complemento, cep, pk_id_aux_agencia, pk_id_aux_estado, id_tipo_cliente,
                percentual, vendas_central_comm, id_cliente
            ))
            
            conn.commit()
            return True

    except Exception as e:
        conn.rollback()
        raise e

# ==================== PERCENTUAL (CTA) ====================

# ==================== CONTATOS - CRIAR/ATUALIZAR ====================

def criar_contato(nome_completo, email, senha=None, pk_id_tbl_cliente=None, telefone=None, id_centralx=None, status=True, pk_id_tbl_cargo=None, pk_id_tbl_setor=None, cohorts=1, user_type='client'):
    """Cria um novo contato"""
    conn = get_db()
    senha_hash = gerar_senha_hash(senha) if senha else None

    try:
        if email_existe(email):
            raise ValueError('Email já cadastrado!')

        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO tbl_contato_cliente 
                (nome_completo, email, senha, pk_id_tbl_cliente, telefone, id_centralx, status, pk_id_tbl_cargo, pk_id_tbl_setor, cohorts, user_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_contato_cliente
            ''', (nome_completo, email.lower().strip(), senha_hash, pk_id_tbl_cliente, telefone, id_centralx, status, pk_id_tbl_cargo, pk_id_tbl_setor, cohorts, user_type))

            novo_id = cursor.fetchone()['id_contato_cliente']

        conn.commit()
        return novo_id

    except Exception as e:
        conn.rollback()
        raise


def atualizar_contato(contato_id, nome_completo, email, telefone=None, pk_id_tbl_cliente=None):
    """Atualiza dados de um contato"""
    conn = get_db()

    try:
        if email_existe(email, excluir_id=contato_id):
            raise ValueError('Email já está sendo usado por outro contato!')

        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET nome_completo = %s, 
                    email = %s, 
                    telefone = %s,
                    pk_id_tbl_cliente = %s,
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_contato_cliente = %s
            ''', (nome_completo, email.lower().strip(), telefone, pk_id_tbl_cliente, contato_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def atualizar_contato_com_senha(contato_id, nome_completo, senha_hash):
    """Atualiza contato existente com nome e senha ao aceitar invite"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET nome_completo = %s, senha = %s, data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_contato_cliente = %s
            ''', (nome_completo, senha_hash, contato_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise


def atualizar_senha_contato(contato_id, nova_senha):
    """Atualiza a senha de um contato"""
    conn = get_db()

    senha_hash = gerar_senha_hash(nova_senha)

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET senha = %s, 
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_contato_cliente = %s
            ''', (senha_hash, contato_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


# ==================== RECUPERAÇÃO DE SENHA ====================

def atualizar_reset_token(email, token, expires):
    """Atualiza token de reset de senha"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente c
                SET reset_token = %s, 
                    reset_token_expires = %s,
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                FROM tbl_cliente cli
                WHERE c.email = %s
                  AND c.pk_id_tbl_cliente = cli.id_cliente
                  AND c.status = TRUE  -- Apenas usuários ativos
                  AND cli.status = TRUE  -- Apenas clientes ativos
            ''', (token, expires, email.lower().strip()))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def buscar_contato_por_token(token):
    """Busca contato por reset_token válido"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.status,
                c.reset_token,
                c.reset_token_expires,
                c.pk_id_tbl_cliente,
                cli.nome_fantasia
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            WHERE c.reset_token = %s 
              AND c.reset_token_expires > NOW()
              AND c.status = TRUE  -- Garantir que o usuário esteja ativo
              AND cli.status = TRUE  -- Garantir que o cliente esteja ativo também
        ''', (token,))
        return cursor.fetchone()


def limpar_reset_token(contato_id):
    """Limpa token de reset após uso"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET reset_token = NULL,
                    reset_token_expires = NULL,
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_contato_cliente = %s
            ''', (contato_id,))
        
        conn.commit()
    
    except Exception as e:
        conn.rollback()
        raise


# ==================== STATUS ====================

def alternar_status_contato(contato_id):
    """Alterna o status de um contato"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT status FROM tbl_contato_cliente WHERE id_contato_cliente = %s',
                (contato_id,)
            )
            contato = cursor.fetchone()
            
            if not contato:
                raise ValueError('Contato não encontrado!')
            
            novo_status = not contato['status']
            
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET status = %s, 
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_contato_cliente = %s
            ''', (novo_status, contato_id))

        conn.commit()
        return novo_status

    except Exception as e:
        conn.rollback()
        raise


def ativar_contato(contato_id):
    """Ativa um contato"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET status = TRUE, 
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_contato_cliente = %s
            ''', (contato_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def desativar_contato(contato_id):
    """Desativa um contato"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET status = FALSE, 
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_contato_cliente = %s
            ''', (contato_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def deletar_contato(contato_id):
    """Deleta permanentemente um contato"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (contato_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


# ==================== ESTATÍSTICAS ====================

def contar_contatos_total():
    """Retorna total de contatos"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) as total FROM tbl_contato_cliente')
        return cursor.fetchone()['total']


def contar_contatos_ativos():
    """Retorna total de contatos ativos"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) as total FROM tbl_contato_cliente WHERE status = TRUE')
        return cursor.fetchone()['total']


def contar_contatos_inativos():
    """Retorna total de contatos inativos"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) as total FROM tbl_contato_cliente WHERE status = FALSE')
        return cursor.fetchone()['total']


def contar_contatos_por_cliente(id_cliente):
    """Retorna total de contatos de um cliente"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) as total FROM tbl_contato_cliente WHERE pk_id_tbl_cliente = %s',
            (id_cliente,)
        )
        return cursor.fetchone()['total']


def obter_estatisticas_contatos():
    """Retorna estatísticas completas dos contatos"""
    return {
        'total': contar_contatos_total(),
        'ativos': contar_contatos_ativos(),
        'inativos': contar_contatos_inativos()
    }


# ==================== VALIDAÇÕES ====================

def email_existe(email, excluir_id=None):
    """Verifica se email já está cadastrado"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        if excluir_id:
            cursor.execute(
                'SELECT COUNT(*) as total FROM tbl_contato_cliente WHERE email = %s AND id_contato_cliente != %s',
                (email.lower().strip(), excluir_id)
            )
        else:
            cursor.execute(
                'SELECT COUNT(*) as total FROM tbl_contato_cliente WHERE email = %s',
                (email.lower().strip(),)
            )
        
        return cursor.fetchone()['total'] > 0


def email_tem_acesso(email):
    """Verifica se email já tem acesso ao sistema (tem senha cadastrada)"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) as total FROM tbl_contato_cliente WHERE email = %s AND senha IS NOT NULL',
            (email.lower().strip(),)
        )
        
        return cursor.fetchone()['total'] > 0


def validar_senha_atual(contato_id, senha_atual):
    """Valida se a senha atual está correta"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('SELECT senha FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (contato_id,))
        contato = cursor.fetchone()
        
        if not contato:
            return False
        
        return verificar_senha(senha_atual, contato['senha'])


def validar_email_formato(email):
    """Valida formato de email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ==================== VALIDAÇÕES CLIENTE (CNPJ/RAZÃO/NOME FANTASIA) ====================

def normalizar_cnpj(cnpj: Optional[str]) -> Optional[str]:
    """Remove caracteres não numéricos do CNPJ."""
    if not cnpj:
        return None
    digits = re.sub(r'\D', '', str(cnpj))
    return digits or None


def cliente_existe_por_cnpj(cnpj: Optional[str], excluir_id: Optional[int] = None) -> bool:
    """Verifica se já existe cliente com este CNPJ (comparando apenas dígitos)."""
    cnpj_digits = normalizar_cnpj(cnpj)
    if not cnpj_digits:
        return False
    conn = get_db()
    with conn.cursor() as cur:
        if excluir_id:
            cur.execute(
                """
                SELECT 1
                FROM tbl_cliente
                WHERE regexp_replace(COALESCE(cnpj, ''), '\\D', '', 'g') = %s
                  AND id_cliente <> %s
                LIMIT 1
                """,
                (cnpj_digits, excluir_id),
            )
        else:
            cur.execute(
                """
                SELECT 1
                FROM tbl_cliente
                WHERE regexp_replace(COALESCE(cnpj, ''), '\\D', '', 'g') = %s
                LIMIT 1
                """,
                (cnpj_digits,),
            )
        return cur.fetchone() is not None


def cliente_existe_por_razao_social(razao_social: Optional[str], excluir_id: Optional[int] = None) -> bool:
    """Verifica duplicidade de Razão Social (case-insensitive, trim)."""
    if not razao_social:
        return False
    conn = get_db()
    with conn.cursor() as cur:
        if excluir_id:
            cur.execute(
                """
                SELECT 1
                FROM tbl_cliente
                WHERE LOWER(TRIM(COALESCE(razao_social, ''))) = LOWER(TRIM(%s))
                  AND id_cliente <> %s
                LIMIT 1
                """,
                (razao_social, excluir_id),
            )
        else:
            cur.execute(
                """
                SELECT 1
                FROM tbl_cliente
                WHERE LOWER(TRIM(COALESCE(razao_social, ''))) = LOWER(TRIM(%s))
                LIMIT 1
                """,
                (razao_social,),
            )
        return cur.fetchone() is not None


def cliente_existe_por_nome_fantasia(nome_fantasia: Optional[str], excluir_id: Optional[int] = None) -> bool:
    """Verifica duplicidade de Nome Fantasia (case-insensitive, trim)."""
    if not nome_fantasia:
        return False
    conn = get_db()
    with conn.cursor() as cur:
        if excluir_id:
            cur.execute(
                """
                SELECT 1
                FROM tbl_cliente
                WHERE LOWER(TRIM(COALESCE(nome_fantasia, ''))) = LOWER(TRIM(%s))
                  AND id_cliente <> %s
                LIMIT 1
                """,
                (nome_fantasia, excluir_id),
            )
        else:
            cur.execute(
                """
                SELECT 1
                FROM tbl_cliente
                WHERE LOWER(TRIM(COALESCE(nome_fantasia, ''))) = LOWER(TRIM(%s))
                LIMIT 1
                """,
                (nome_fantasia,),
            )
        return cur.fetchone() is not None


# ==================== BUSCA E FILTROS ====================

def buscar_contatos(termo):
    """Busca contatos por nome ou email"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.status,
                cli.nome_fantasia
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            WHERE c.nome_completo ILIKE %s OR c.email ILIKE %s
            ORDER BY c.nome_completo
        ''', (f'%{termo}%', f'%{termo}%'))
        return cursor.fetchall()


def filtrar_contatos(status=None, id_cliente=None):
    """Filtra contatos por múltiplos critérios"""
    conn = get_db()
    
    query = '''
        SELECT 
            c.id_contato_cliente,
            c.email,
            c.nome_completo,
            c.telefone,
            c.status,
            c.pk_id_tbl_cliente,
            c.data_cadastro,
            cli.nome_fantasia,
            cli.razao_social
        FROM tbl_contato_cliente c
        LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
        WHERE 1=1
    '''
    params = []
    
    if status is not None:
        query += ' AND c.status = %s'
        params.append(status)
    
    if id_cliente is not None:
        query += ' AND c.pk_id_tbl_cliente = %s'
        params.append(id_cliente)
    
    query += ' ORDER BY c.nome_completo'
    
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


# ==================== PERFIL DO CONTATO ====================

def atualizar_perfil(contato_id, nome_completo, email, telefone=None):
    """Atualiza perfil do contato"""
    return atualizar_contato(contato_id, nome_completo, email, telefone)


def alterar_senha_com_validacao(contato_id, senha_atual, nova_senha):
    """Altera senha validando a senha atual"""
    try:
        if not validar_senha_atual(contato_id, senha_atual):
            return False, 'Senha atual incorreta!'
        
        if len(nova_senha) < 6:
            return False, 'Nova senha deve ter no mínimo 6 caracteres!'
        
        atualizar_senha_contato(contato_id, nova_senha)
        
        return True, 'Senha alterada com sucesso!'
    
    except Exception as e:
        return False, f'Erro ao alterar senha: {str(e)}'

# ==================== SETORES ====================

def obter_setor_por_id(id_setor):
    """Retorna um setor específico por ID"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id_setor,
                display,
                status,
                data_cadastro,
                data_modificacao
            FROM tbl_setor
            WHERE id_setor = %s
        """, (id_setor,))
        return cur.fetchone()

def criar_setor(display, status=True):
    """Cria um novo setor"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO tbl_setor (display, status)
            VALUES (%s, %s)
            RETURNING id_setor
        """, (display, status))
        conn.commit()
        return cur.fetchone()['id_setor']

def atualizar_setor(id_setor, display, status):
    """Atualiza um setor existente"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tbl_setor
            SET display = %s,
                status = %s,
                data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            WHERE id_setor = %s
        """, (display, status, id_setor))
        conn.commit()
        return cur.rowcount > 0

def toggle_status_setor(id_setor):
    """Alterna o status de um setor"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tbl_setor
            SET status = NOT status,
                data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            WHERE id_setor = %s
            RETURNING status
        """, (id_setor,))
        conn.commit()
        result = cur.fetchone()
        return result['status'] if result else None

# ==================== CARGOS ====================

def obter_cargos(setor_id=None):
    """Retorna lista de todos os cargos, opcionalmente filtrados por setor"""
    conn = get_db()
    with conn.cursor() as cur:
        if setor_id:
            cur.execute("""
                SELECT 
                    c.id_cargo_contato,
                    c.descricao,
                    c.pk_id_aux_setor,
                    c.id_centralx,
                    c.indice,
                    c.status,
                    c.data_cadastro,
                    c.data_modificacao,
                    s.display as setor_display
                FROM tbl_cargo_contato c
                LEFT JOIN tbl_setor s ON s.id_setor = c.pk_id_aux_setor
                WHERE c.pk_id_aux_setor = %s
                ORDER BY c.descricao
            """, (setor_id,))
        else:
            cur.execute("""
                SELECT 
                    c.id_cargo_contato,
                    c.descricao,
                    c.pk_id_aux_setor,
                    c.id_centralx,
                    c.indice,
                    c.status,
                    c.data_cadastro,
                    c.data_modificacao,
                    s.display as setor_display
                FROM tbl_cargo_contato c
                LEFT JOIN tbl_setor s ON s.id_setor = c.pk_id_aux_setor
                ORDER BY c.descricao
            """)
        return cur.fetchall()

def obter_cargo_por_id(id_cargo):
    """Retorna um cargo específico por ID"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                c.id_cargo_contato,
                c.descricao,
                c.pk_id_aux_setor,
                c.id_centralx,
                c.indice,
                c.status,
                c.data_cadastro,
                c.data_modificacao,
                s.display as setor_display
            FROM tbl_cargo_contato c
            LEFT JOIN tbl_setor s ON s.id_setor = c.pk_id_aux_setor
            WHERE c.id_cargo_contato = %s
        """, (id_cargo,))
        return cur.fetchone()

def criar_cargo(descricao, pk_id_aux_setor, id_centralx=None, indice=None, status=True):
    """Cria um novo cargo"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO tbl_cargo_contato 
                (descricao, pk_id_aux_setor, id_centralx, indice, status, data_cadastro)
            VALUES 
                (%s, %s, %s, %s, %s, DATE_TRUNC('second', CURRENT_TIMESTAMP))
            RETURNING id_cargo_contato
        """, (descricao, pk_id_aux_setor, id_centralx, indice, status))
        conn.commit()
        return cur.fetchone()['id_cargo_contato']

def atualizar_cargo(id_cargo, descricao, pk_id_aux_setor, id_centralx=None, indice=None, status=True):
    """Atualiza um cargo existente"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tbl_cargo_contato
            SET descricao = %s,
                pk_id_aux_setor = %s,
                id_centralx = %s,
                indice = %s,
                status = %s,
                data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            WHERE id_cargo_contato = %s
        """, (descricao, pk_id_aux_setor, id_centralx, indice, status, id_cargo))
        conn.commit()
        return cur.rowcount > 0

def toggle_status_cargo(id_cargo):
    """Alterna o status de um cargo"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tbl_cargo_contato
            SET status = NOT status,
                data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            WHERE id_cargo_contato = %s
            RETURNING status
        """, (id_cargo,))
        conn.commit()
        result = cur.fetchone()
        return result['status'] if result else None


# ==================== AGÊNCIAS ====================

def obter_aux_agencia(apenas_ativos=True):
    """Retorna todas as agências"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_agencia,
                    display,
                    key
                FROM tbl_agencia
                ORDER BY display
            ''')
            return cursor.fetchall()
            
    except Exception as e:
        conn.rollback()
        raise e

def obter_aux_agencia_por_id(id_aux_agencia: int):
    """Retorna uma agência específica por ID"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_agencia,
                    display,
                    key
                FROM tbl_agencia
                WHERE id_agencia = %s
            ''', (id_aux_agencia,))
            return cursor.fetchone()
            
    except Exception as e:
        conn.rollback()
        raise e


# ==================== AUX TIPO CLIENTE - CRUD ====================

def obter_tipos_cliente():
    """Retorna todos os tipos de cliente"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_tipo_cliente,
                    display,
                    data_cadastro,
                    data_modificacao
                FROM tbl_tipo_cliente
                ORDER BY display
            ''')
            return cursor.fetchall()
            
    except Exception as e:
        conn.rollback()
        raise e

def obter_tipo_cliente_por_id(id_tipo_cliente: int):
    """Retorna um tipo de cliente específico por ID"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_tipo_cliente,
                    display,
                    data_cadastro,
                    data_modificacao
                FROM tbl_tipo_cliente
                WHERE id_tipo_cliente = %s
            ''', (id_tipo_cliente,))
            return cursor.fetchone()
            
    except Exception as e:
        conn.rollback()
        raise e

def criar_tipo_cliente(display):
    """Cria um novo tipo de cliente"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO tbl_tipo_cliente (display, data_cadastro, data_modificacao)
                VALUES (%s, DATE_TRUNC('second', CURRENT_TIMESTAMP), DATE_TRUNC('second', CURRENT_TIMESTAMP))
                RETURNING id_tipo_cliente
            ''', (display,))
            
            result = cursor.fetchone()
            conn.commit()
            return result['id_tipo_cliente'] if result else None
            
    except Exception as e:
        conn.rollback()
        raise e

def atualizar_tipo_cliente(id_tipo_cliente, display):
    """Atualiza um tipo de cliente existente"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_tipo_cliente
                SET display = %s,
                    data_modificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_tipo_cliente = %s
            ''', (display, id_tipo_cliente))
            
            conn.commit()
            return cursor.rowcount > 0
            
    except Exception as e:
        conn.rollback()
        raise e

def excluir_tipo_cliente(id_tipo_cliente):
    """Exclui um tipo de cliente"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM tbl_tipo_cliente
                WHERE id_tipo_cliente = %s
            ''', (id_tipo_cliente,))
            
            conn.commit()
            return cursor.rowcount > 0
            
    except Exception as e:
        conn.rollback()
        raise e


# ==================== ESTADO - LEITURA ====================

def obter_estados():
    """Retorna todos os estados ordenados por descrição"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_estado,
                    descricao,
                    sigla,
                    id_centralx,
                    indice
                FROM tbl_estado
                ORDER BY descricao
            ''')
            return cursor.fetchall()
            
    except Exception as e:
        conn.rollback()
        raise e

def obter_estado_por_id(id_estado: int):
    """Retorna um estado específico por ID"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_estado,
                    descricao,
                    sigla,
                    id_centralx,
                    indice
                FROM tbl_estado
                WHERE id_estado = %s
            ''', (id_estado,))
            return cursor.fetchone()
            
    except Exception as e:
        conn.rollback()
        raise e

def obter_estado_por_sigla(sigla: str):
    """Retorna um estado específico por sigla"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_estado,
                    descricao,
                    sigla,
                    id_centralx,
                    indice
                FROM tbl_estado
                WHERE sigla = %s
            ''', (sigla.upper(),))
            return cursor.fetchone()
            
    except Exception as e:
        conn.rollback()
        raise e

# ==================== CATEGORIAS AUDIÊNCIA - CRUD ====================

def obter_cadu_categorias():
    """Retorna todas as categorias de audiência com contagem dinâmica"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.id, 
                    c.nome, 
                    c.slug, 
                    c.descricao, 
                    c.icone, 
                    c.cor_hex, 
                    c.ordem_exibicao, 
                    c.is_active, 
                    c.is_featured, 
                    COUNT(a.id) as total_audiencias,
                    c.meta_titulo, 
                    c.meta_descricao, 
                    c.created_at, 
                    c.updated_at
                FROM cadu_categorias c
                LEFT JOIN cadu_audiencias a ON c.id = a.categoria_id
                GROUP BY c.id, c.nome, c.slug, c.descricao, c.icone, c.cor_hex, 
                         c.ordem_exibicao, c.is_active, c.is_featured, c.meta_titulo, 
                         c.meta_descricao, c.created_at, c.updated_at
                ORDER BY c.ordem_exibicao, c.nome
            ''')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e

def obter_cadu_categoria_por_id(id_categoria):
    """Retorna uma categoria de audiência por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, nome, slug, descricao, icone, cor_hex, ordem_exibicao, is_active, is_featured, total_audiencias, meta_titulo, meta_descricao, created_at, updated_at
                FROM cadu_categorias
                WHERE id = %s
            ''', (id_categoria,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e

def criar_cadu_categoria(data):
    """Cria uma nova categoria de audiência"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_categorias (
                    nome, slug, descricao, icone, cor_hex, ordem_exibicao, is_active, is_featured, total_audiencias, meta_titulo, meta_descricao
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            ''', (
                data.get('nome'),
                data.get('slug'),
                data.get('descricao'),
                data.get('icone'),
                data.get('cor_hex'),
                data.get('ordem_exibicao', 0),
                data.get('is_active', True),
                data.get('is_featured', False),
                data.get('total_audiencias', 0),
                data.get('meta_titulo'),
                data.get('meta_descricao')
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        conn.rollback()
        raise e

def atualizar_cadu_categoria(id_categoria, data):
    """Atualiza uma categoria de audiência existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_categorias
                SET nome = %s,
                    slug = %s,
                    descricao = %s,
                    icone = %s,
                    cor_hex = %s,
                    ordem_exibicao = %s,
                    is_active = %s,
                    is_featured = %s,
                    meta_titulo = %s,
                    meta_descricao = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
            ''', (
                data.get('nome'),
                data.get('slug'),
                data.get('descricao'),
                data.get('icone'),
                data.get('cor_hex'),
                data.get('ordem_exibicao', 0),
                data.get('is_active', True),
                data.get('is_featured', False),
                data.get('meta_titulo'),
                data.get('meta_descricao'),
                id_categoria
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e

def excluir_cadu_categoria(id_categoria):
    """Exclui uma categoria de audiência"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_categorias WHERE id = %s
            ''', (id_categoria,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e

# ==================== CADU SUBCATEGORIAS ====================

def obter_cadu_subcategorias(categoria_id=None):
    """Obtém todas as subcategorias ou filtra por categoria"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if categoria_id:
                cursor.execute('''
                    SELECT s.*, c.nome as categoria_nome
                    FROM cadu_subcategorias s
                    LEFT JOIN cadu_categorias c ON s.categoria_id = c.id
                    WHERE s.categoria_id = %s
                    ORDER BY s.ordem_exibicao, s.nome
                ''', (categoria_id,))
            else:
                cursor.execute('''
                    SELECT s.*, c.nome as categoria_nome
                    FROM cadu_subcategorias s
                    LEFT JOIN cadu_categorias c ON s.categoria_id = c.id
                    ORDER BY c.nome, s.ordem_exibicao, s.nome
                ''')
            return cursor.fetchall()
    except Exception as e:
        raise e

def obter_cadu_subcategoria_por_id(id_subcategoria):
    """Obtém uma subcategoria por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT s.*, c.nome as categoria_nome
                FROM cadu_subcategorias s
                LEFT JOIN cadu_categorias c ON s.categoria_id = c.id
                WHERE s.id = %s
            ''', (id_subcategoria,))
            return cursor.fetchone()
    except Exception as e:
        raise e

def criar_cadu_subcategoria(dados):
    """Cria uma nova subcategoria"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_subcategorias 
                (categoria_id, nome, slug, descricao, icone, ordem_exibicao, is_active, meta_titulo, meta_descricao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                dados.get('categoria_id'),
                dados.get('nome'),
                dados.get('slug'),
                dados.get('descricao'),
                dados.get('icone'),
                dados.get('ordem_exibicao', 0),
                dados.get('is_active', True),
                dados.get('meta_titulo'),
                dados.get('meta_descricao')
            ))
            result = cursor.fetchone()
            novo_id = result['id'] if result else None
            conn.commit()
            return novo_id
    except Exception as e:
        conn.rollback()
        raise e

def atualizar_cadu_subcategoria(id_subcategoria, dados):
    """Atualiza uma subcategoria existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_subcategorias
                SET categoria_id = %s,
                    nome = %s,
                    slug = %s,
                    descricao = %s,
                    icone = %s,
                    ordem_exibicao = %s,
                    is_active = %s,
                    meta_titulo = %s,
                    meta_descricao = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
            ''', (
                dados.get('categoria_id'),
                dados.get('nome'),
                dados.get('slug'),
                dados.get('descricao'),
                dados.get('icone'),
                dados.get('ordem_exibicao', 0),
                dados.get('is_active', True),
                dados.get('meta_titulo'),
                dados.get('meta_descricao'),
                id_subcategoria
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e

def excluir_cadu_subcategoria(id_subcategoria):
    """Exclui uma subcategoria"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_subcategorias WHERE id = %s
            ''', (id_subcategoria,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    
# ==================== CADU AUDIÊNCIAS - MODELO ====================

class CaduAudiencias:
    """Modelo da tabela cadu_audiencias - Catálogo de Audiências"""
    
    def __init__(self, id, id_audiencia_plataforma, fonte, nome, slug, 
                 categoria_id, subcategoria_id=None,
                 titulo_chamativo=None, descricao=None, descricao_curta=None, 
                 descricao_comercial=None, descricao_ia=None,
                 storytelling=None, caso_uso_principal=None, 
                 insights_planejamento=None, diferenciais_competitivos=None,
                 tags=None, publico_estimado=None, publico_numero=None, 
                 tamanho='media',
                 # Demografia
                 demografia_homens=50, demografia_mulheres=50,
                 idade_18_24=18, idade_25_34=20, idade_35_44=19, idade_45_mais=43,
                 # Dispositivos
                 dispositivo_mobile=60, dispositivo_desktop=35, dispositivo_tablet=5,
                 # Perfil Socioeconômico
                 perfil_socioeconomico='BC', grau_instrucao='Não especificado',
                 estado_civil_predominante='Não especificado',
                 # Pricing
                 cpm_custo=None, cpm_venda=None, cpm_minimo=None, cpm_maximo=None,
                 # Performance e Consumo
                 perfil_consumo=None, momentos_chave=None, interesses_correlatos=None,
                 ctr_medio_estimado=None, taxa_conversao_estimada=None,
                 cpa_estimado_min=None, cpa_estimado_max=None,
                 categorias_alto_desempenho=None, tamanho_mercado_brl=None,
                 ticket_medio_estimado=None, propensao_compra='media', sazonalidade=None,
                 # Métricas e Overlaps
                 relevancia_score=0, overlap_facebook=0, overlap_google=0,
                 alcance_incremental=None,
                 # Status e Flags
                 is_premium=False, is_active=True,
                 views_count=0, added_to_cart_count=0, quoted_count=0,
                 # Validação e Qualidade
                 confiabilidade_score=0, dados_validos=True,
                 campos_estimados_total=0, campos_com_dados_reais=0,
                 versao_pipeline='1.0', validacao_final=None,
                 # Metadados
                 metadados_geracao=None, pipeline_tracking=None,
                 data_processamento=None, created_at=None, updated_at=None):
        
        # Identificação
        self.id = id
        self.id_audiencia_plataforma = id_audiencia_plataforma
        self.fonte = fonte
        self.nome = nome
        self.slug = slug
        
        # Textos e Descrições
        self.titulo_chamativo = titulo_chamativo
        self.descricao = descricao
        self.descricao_curta = descricao_curta
        self.descricao_comercial = descricao_comercial
        self.descricao_ia = descricao_ia
        self.storytelling = storytelling
        self.caso_uso_principal = caso_uso_principal
        self.insights_planejamento = insights_planejamento
        self.diferenciais_competitivos = diferenciais_competitivos
        
        # Categorização
        self.categoria_id = categoria_id
        self.subcategoria_id = subcategoria_id
        self.tags = tags or []
        
        # Público
        self.publico_estimado = publico_estimado
        self.publico_numero = publico_numero
        self.tamanho = tamanho
        
        # Demografia
        self.demografia_homens = demografia_homens
        self.demografia_mulheres = demografia_mulheres
        self.idade_18_24 = idade_18_24
        self.idade_25_34 = idade_25_34
        self.idade_35_44 = idade_35_44
        self.idade_45_mais = idade_45_mais
        
        # Dispositivos
        self.dispositivo_mobile = dispositivo_mobile
        self.dispositivo_desktop = dispositivo_desktop
        self.dispositivo_tablet = dispositivo_tablet
        
        # Perfil Socioeconômico
        self.perfil_socioeconomico = perfil_socioeconomico
        self.grau_instrucao = grau_instrucao
        self.estado_civil_predominante = estado_civil_predominante
        
        # Pricing
        self.cpm_custo = cpm_custo
        self.cpm_venda = cpm_venda
        self.cpm_minimo = cpm_minimo
        self.cpm_maximo = cpm_maximo
        
        # Performance e Consumo
        self.perfil_consumo = perfil_consumo
        self.momentos_chave = momentos_chave or []
        self.interesses_correlatos = interesses_correlatos or []
        self.ctr_medio_estimado = ctr_medio_estimado
        self.taxa_conversao_estimada = taxa_conversao_estimada
        self.cpa_estimado_min = cpa_estimado_min
        self.cpa_estimado_max = cpa_estimado_max
        self.categorias_alto_desempenho = categorias_alto_desempenho or []
        self.tamanho_mercado_brl = tamanho_mercado_brl
        self.ticket_medio_estimado = ticket_medio_estimado
        self.propensao_compra = propensao_compra
        self.sazonalidade = sazonalidade
        
        # Métricas e Overlaps
        self.relevancia_score = relevancia_score
        self.overlap_facebook = overlap_facebook
        self.overlap_google = overlap_google
        self.alcance_incremental = alcance_incremental
        
        # Status e Flags
        self.is_premium = is_premium
        self.is_active = is_active
        self.views_count = views_count
        self.added_to_cart_count = added_to_cart_count
        self.quoted_count = quoted_count
        
        # Validação e Qualidade
        self.confiabilidade_score = confiabilidade_score
        self.dados_validos = dados_validos
        self.campos_estimados_total = campos_estimados_total
        self.campos_com_dados_reais = campos_com_dados_reais
        self.versao_pipeline = versao_pipeline
        self.validacao_final = validacao_final
        
        # Metadados
        self.metadados_geracao = metadados_geracao
        self.pipeline_tracking = pipeline_tracking
        self.data_processamento = data_processamento
        self.created_at = created_at
        self.updated_at = updated_at
    
    def to_dict(self):
        """Converte a instância para dicionário"""
        return {
            'id': self.id,
            'id_audiencia_plataforma': self.id_audiencia_plataforma,
            'fonte': self.fonte,
            'nome': self.nome,
            'slug': self.slug,
            'titulo_chamativo': self.titulo_chamativo,
            'descricao': self.descricao,
            'descricao_curta': self.descricao_curta,
            'descricao_comercial': self.descricao_comercial,
            'descricao_ia': self.descricao_ia,
            'storytelling': self.storytelling,
            'caso_uso_principal': self.caso_uso_principal,
            'insights_planejamento': self.insights_planejamento,
            'diferenciais_competitivos': self.diferenciais_competitivos,
            'categoria_id': self.categoria_id,
            'subcategoria_id': self.subcategoria_id,
            'tags': self.tags,
            'publico_estimado': self.publico_estimado,
            'publico_numero': self.publico_numero,
            'tamanho': self.tamanho,
            'demografia_homens': self.demografia_homens,
            'demografia_mulheres': self.demografia_mulheres,
            'idade_18_24': self.idade_18_24,
            'idade_25_34': self.idade_25_34,
            'idade_35_44': self.idade_35_44,
            'idade_45_mais': self.idade_45_mais,
            'dispositivo_mobile': self.dispositivo_mobile,
            'dispositivo_desktop': self.dispositivo_desktop,
            'dispositivo_tablet': self.dispositivo_tablet,
            'perfil_socioeconomico': self.perfil_socioeconomico,
            'grau_instrucao': self.grau_instrucao,
            'estado_civil_predominante': self.estado_civil_predominante,
            'cpm_custo': float(self.cpm_custo) if self.cpm_custo else None,
            'cpm_venda': float(self.cpm_venda) if self.cpm_venda else None,
            'cpm_minimo': float(self.cpm_minimo) if self.cpm_minimo else None,
            'cpm_maximo': float(self.cpm_maximo) if self.cpm_maximo else None,
            'perfil_consumo': self.perfil_consumo,
            'momentos_chave': self.momentos_chave,
            'interesses_correlatos': self.interesses_correlatos,
            'ctr_medio_estimado': float(self.ctr_medio_estimado) if self.ctr_medio_estimado else None,
            'taxa_conversao_estimada': float(self.taxa_conversao_estimada) if self.taxa_conversao_estimada else None,
            'cpa_estimado_min': float(self.cpa_estimado_min) if self.cpa_estimado_min else None,
            'cpa_estimado_max': float(self.cpa_estimado_max) if self.cpa_estimado_max else None,
            'categorias_alto_desempenho': self.categorias_alto_desempenho,
            'tamanho_mercado_brl': self.tamanho_mercado_brl,
            'ticket_medio_estimado': float(self.ticket_medio_estimado) if self.ticket_medio_estimado else None,
            'propensao_compra': self.propensao_compra,
            'sazonalidade': self.sazonalidade,
            'relevancia_score': self.relevancia_score,
            'overlap_facebook': self.overlap_facebook,
            'overlap_google': self.overlap_google,
            'alcance_incremental': self.alcance_incremental,
            'is_premium': self.is_premium,
            'is_active': self.is_active,
            'views_count': self.views_count,
            'added_to_cart_count': self.added_to_cart_count,
            'quoted_count': self.quoted_count,
            'confiabilidade_score': self.confiabilidade_score,
            'dados_validos': self.dados_validos,
            'campos_estimados_total': self.campos_estimados_total,
            'campos_com_dados_reais': self.campos_com_dados_reais,
            'versao_pipeline': self.versao_pipeline,
            'validacao_final': self.validacao_final,
            'metadados_geracao': self.metadados_geracao,
            'pipeline_tracking': self.pipeline_tracking,
            'data_processamento': self.data_processamento,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

# ==================== CADU AUDIÊNCIAS - CRUD ====================

def obter_cadu_audiencias(plataforma_id=None):
    """Retorna audiências do catálogo, opcionalmente filtradas por plataforma"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    a.id,
                    a.id_audiencia_plataforma,
                    a.plataforma_id,
                    a.fonte,
                    a.nome,
                    a.slug,
                    a.perfil_socioeconomico,
                    a.titulo_chamativo,
                    a.categoria_id,
                    a.subcategoria_id,
                    a.campos_com_dados_reais,
                    a.cpm_custo,
                    a.cpm_venda,
                    a.is_active,
                    a.created_at,
                    a.updated_at,
                    a.imagem_url,
                    cat.nome as categoria_nome,
                    sub.nome as subcategoria_nome
                FROM cadu_audiencias a
                LEFT JOIN cadu_categorias cat ON a.categoria_id = cat.id
                LEFT JOIN cadu_subcategorias sub ON a.subcategoria_id = sub.id
            '''
            params = []
            if plataforma_id is not None:
                query += ' WHERE a.plataforma_id = %s'
                params.append(plataforma_id)
            query += ' ORDER BY a.created_at DESC'
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e

def buscar_audiencias(termo, limite=20):
    """Busca audiências por nome"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id,
                    nome,
                    perfil_socioeconomico,
                    cpm_custo,
                    cpm_venda,
                    imagem_url
                FROM cadu_audiencias
                WHERE is_active = true
                  AND LOWER(nome) LIKE LOWER(%s)
                ORDER BY nome
                LIMIT %s
            ''', (f'%{termo}%', limite))
            return cursor.fetchall()
    except Exception as e:
        raise e

def obter_audiencia_completa(audiencia_id):
    """Retorna dados completos de uma audiência por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    a.id,
                    a.nome,
                    a.perfil_socioeconomico,
                    a.cpm_custo,
                    a.cpm_venda,
                    a.categoria_id,
                    a.subcategoria_id,
                    cat.categoria,
                    cat.subcategoria
                FROM cadu_audiencias a
                LEFT JOIN cadu_categorias_audiencia cat ON a.categoria_id = cat.id
                WHERE a.id = %s
            ''', (audiencia_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e

def obter_cadu_audiencia_por_id(id_audiencia):
    """Retorna uma audiência específica por ID com todas as informações"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    a.*,
                    c.nome as categoria_nome,
                    s.nome as subcategoria_nome
                FROM cadu_audiencias a
                LEFT JOIN cadu_categorias c ON a.categoria_id = c.id
                LEFT JOIN cadu_subcategorias s ON a.subcategoria_id = s.id
                WHERE a.id = %s
            ''', (id_audiencia,))
            return cursor.fetchone()
    except Exception as e:
        raise e

def criar_cadu_audiencia(dados):
    """Cria uma nova audiência no catálogo"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_audiencias (
                    id_audiencia_plataforma, fonte, nome, slug, perfil_socioeconomico,
                    titulo_chamativo, descricao, descricao_curta, descricao_comercial,
                    cpm_custo, cpm_venda, cpm_minimo, cpm_maximo,
                    categoria_id, subcategoria_id, is_active
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            ''', (
                dados.get('id_audiencia_plataforma'),
                dados.get('fonte'),
                dados.get('nome'),
                dados.get('slug'),
                dados.get('perfil_socioeconomico'),
                dados.get('titulo_chamativo'),
                dados.get('descricao'),
                dados.get('descricao_curta'),
                dados.get('descricao_comercial'),
                dados.get('cpm_custo'),
                dados.get('cpm_venda'),
                dados.get('cpm_minimo'),
                dados.get('cpm_maximo'),
                dados.get('categoria_id'),
                dados.get('subcategoria_id'),
                dados.get('is_active', True)
            ))
            novo_id = cursor.fetchone()['id']
            conn.commit()
            return novo_id
    except Exception as e:
        conn.rollback()
        raise e

def atualizar_cadu_audiencia(id_audiencia, dados):
    """Atualiza uma audiência existente (não atualiza is_active - usar toggle)"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_audiencias
                SET id_audiencia_plataforma = %s,
                    fonte = %s,
                    nome = %s,
                    slug = %s,
                    perfil_socioeconomico = %s,
                    titulo_chamativo = %s,
                    descricao = %s,
                    descricao_curta = %s,
                    descricao_comercial = %s,
                    cpm_custo = %s,
                    cpm_venda = %s,
                    cpm_minimo = %s,
                    cpm_maximo = %s,
                    categoria_id = %s,
                    subcategoria_id = %s,
                    publico_estimado = %s,
                    publico_numero = %s,
                    tamanho = %s,
                    propensao_compra = %s,
                    demografia_homens = %s,
                    demografia_mulheres = %s,
                    idade_18_24 = %s,
                    idade_25_34 = %s,
                    idade_35_44 = %s,
                    idade_45_mais = %s,
                    dispositivo_mobile = %s,
                    dispositivo_desktop = %s,
                    dispositivo_tablet = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
            ''', (
                dados.get('id_audiencia_plataforma'),
                dados.get('fonte'),
                dados.get('nome'),
                dados.get('slug'),
                dados.get('perfil_socioeconomico'),
                dados.get('titulo_chamativo'),
                dados.get('descricao'),
                dados.get('descricao_curta'),
                dados.get('descricao_comercial'),
                dados.get('cpm_custo'),
                dados.get('cpm_venda'),
                dados.get('cpm_minimo'),
                dados.get('cpm_maximo'),
                dados.get('categoria_id'),
                dados.get('subcategoria_id'),
                dados.get('publico_estimado'),
                dados.get('publico_numero'),
                dados.get('tamanho'),
                dados.get('propensao_compra'),
                dados.get('demografia_homens'),
                dados.get('demografia_mulheres'),
                dados.get('idade_18_24'),
                dados.get('idade_25_34'),
                dados.get('idade_35_44'),
                dados.get('idade_45_mais'),
                dados.get('dispositivo_mobile'),
                dados.get('dispositivo_desktop'),
                dados.get('dispositivo_tablet'),
                id_audiencia
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e

def excluir_cadu_audiencia(id_audiencia):
    """Exclui uma audiência do catálogo"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM cadu_audiencias WHERE id = %s', (id_audiencia,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e

def toggle_status_cadu_audiencia(id_audiencia):
    """Alterna o status ativo/inativo de uma audiência"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_audiencias
                SET is_active = NOT is_active,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
                RETURNING is_active
            ''', (id_audiencia,))
            result = cursor.fetchone()
            conn.commit()
            return result['is_active'] if result else None
    except Exception as e:
        conn.rollback()
        raise e
# ============================================================================
# INTERESSE PRODUTO - Gestao de interesses de contatos em produtos
# ============================================================================

def obter_interesses_produto(contato_id=None, tipo_produto=None, notificado=None, cliente_id=None):
    """
    Retorna interesses de produto com filtros opcionais
    
    Args:
        contato_id: Filtrar por ID do contato
        tipo_produto: Filtrar por tipo de produto
        notificado: Filtrar por status de notifica��o (True/False/None)
        cliente_id: Filtrar por ID do cliente
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    i.*,
                    c.nome_completo,
                    c.email,
                    c.pk_id_tbl_cliente as id_cliente,
                    cli.nome_fantasia,
                    cli.razao_social
                FROM tbl_interesse_produto i
                INNER JOIN tbl_contato_cliente c ON i.fk_id_contato_cliente = c.id_contato_cliente
                LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                WHERE 1=1
            '''
            params = []
            
            if contato_id is not None:
                query += ' AND i.fk_id_contato_cliente = %s'
                params.append(contato_id)
            
            if tipo_produto:
                query += ' AND i.tipo_produto = %s'
                params.append(tipo_produto)
            
            if notificado is not None:
                query += ' AND i.notificado = %s'
                params.append(notificado)
            
            if cliente_id is not None:
                query += ' AND c.pk_id_tbl_cliente = %s'
                params.append(cliente_id)
            
            query += ' ORDER BY i.data_registro DESC'
            
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e

def obter_interesse_produto_por_id(id_interesse):
    """Retorna um interesse de produto especifico por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    i.*,
                    c.nome_completo,
                    c.email,
                    cli.nome_fantasia,
                    cli.razao_social
                FROM tbl_interesse_produto i
                INNER JOIN tbl_contato_cliente c ON i.fk_id_contato_cliente = c.id_contato_cliente
                LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                WHERE i.id_interesse = %s
            ''', (id_interesse,))
            return cursor.fetchone()
    except Exception as e:
        raise e

def criar_interesse_produto(fk_id_contato_cliente, tipo_produto, ip_registro=None, user_agent=None, dados_adicionais=None):
    """
    Cria um novo registro de interesse em produto
    
    Args:
        fk_id_contato_cliente: ID do contato cliente
        tipo_produto: Tipo do produto de interesse
        ip_registro: IP do registro (opcional)
        user_agent: User agent do navegador (opcional)
        dados_adicionais: Dados adicionais em formato dict (opcional)
    
    Returns:
        ID do interesse criado ou None se ja existir
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # Verifica se ja existe (constraint uk_interesse_unico)
            cursor.execute('''
                SELECT id_interesse 
                FROM tbl_interesse_produto 
                WHERE fk_id_contato_cliente = %s AND tipo_produto = %s
            ''', (fk_id_contato_cliente, tipo_produto))
            
            existe = cursor.fetchone()
            if existe:
                return None  # Ja existe, nao cria duplicado
            
            # Converte dados_adicionais para JSON se fornecido
            import json
            dados_json = json.dumps(dados_adicionais) if dados_adicionais else None
            
            cursor.execute('''
                INSERT INTO tbl_interesse_produto (
                    fk_id_contato_cliente,
                    tipo_produto,
                    ip_registro,
                    user_agent,
                    dados_adicionais
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id_interesse
            ''', (fk_id_contato_cliente, tipo_produto, ip_registro, user_agent, dados_json))
            
            result = cursor.fetchone()
            conn.commit()
            return result['id_interesse'] if result else None
    except Exception as e:
        conn.rollback()
        raise e

def marcar_interesse_notificado(id_interesse):
    """Marca um interesse como notificado"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_interesse_produto
                SET notificado = true,
                    data_notificacao = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_interesse = %s
                RETURNING id_interesse
            ''', (id_interesse,))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e

def excluir_interesse_produto(id_interesse):
    """Exclui um interesse de produto"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM tbl_interesse_produto
                WHERE id_interesse = %s
                RETURNING id_interesse
            ''', (id_interesse,))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e

def obter_tipos_produto_com_interesse():
    """Retorna lista de tipos de produto que tem pelo menos um interesse registrado"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT tipo_produto, COUNT(*) as total_interesses
                FROM tbl_interesse_produto
                GROUP BY tipo_produto
                ORDER BY tipo_produto
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e

def obter_interesses_nao_notificados():
    """Retorna todos os interesses que ainda nao foram notificados"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    i.*,
                    c.nome_completo,
                    c.email,
                    c.telefone,
                    cli.nome_fantasia,
                    cli.razao_social
                FROM tbl_interesse_produto i
                INNER JOIN tbl_contato_cliente c ON i.fk_id_contato_cliente = c.id_contato_cliente
                LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                WHERE i.notificado = false
                ORDER BY i.data_registro ASC
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e

# ============================================================================
# GERAÇÃO DE IMAGENS PARA AUDIÊNCIAS
# ============================================================================

def atualizar_imagem_audiencia(audiencia_id, imagem_url):
    """Atualiza a URL da imagem de uma audiência"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_audiencias
                SET imagem_url = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
                RETURNING id
            ''', (imagem_url, audiencia_id))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


# ==================== FUNÇÕES ADMINISTRATIVAS ====================

def obter_usuarios_sistema(filtros=None):
    """
    Retorna todos os usuários do sistema com informações de cliente
    
    Args:
        filtros (dict): Filtros opcionais (user_type, status, cliente_id, search)
    
    Returns:
        list: Lista de usuários
    """
    conn = get_db()
    try:
        query = '''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.telefone,
                c.status,
                c.user_type,
                c.pk_id_tbl_cliente,
                c.data_cadastro,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj,
                cli.status as cliente_status
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            WHERE 1=1
        '''
        
        params = []
        
        if filtros:
            if filtros.get('user_type'):
                query += ' AND c.user_type = %s'
                params.append(filtros['user_type'])
            
            if filtros.get('status') is not None:
                query += ' AND c.status = %s'
                params.append(filtros['status'])
            
            if filtros.get('cliente_id'):
                query += ' AND c.pk_id_tbl_cliente = %s'
                params.append(filtros['cliente_id'])
            
            if filtros.get('search'):
                query += ' AND (c.nome_completo ILIKE %s OR c.email ILIKE %s)'
                search_term = f"%{filtros['search']}%"
                params.extend([search_term, search_term])
        
        query += ' ORDER BY c.data_cadastro DESC'
        
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_usuario_por_id(user_id):
    """Retorna informações completas de um usuário específico"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.*,
                    cli.nome_fantasia,
                    cli.razao_social,
                    cli.cnpj,
                    cli.status as cliente_status,
                    s.nome as setor_nome,
                    car.nome as cargo_nome
                FROM tbl_contato_cliente c
                LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                LEFT JOIN tbl_setor s ON c.fk_id_setor = s.id_setor
                LEFT JOIN tbl_cargo car ON c.fk_id_cargo = car.id_cargo
                WHERE c.id_contato_cliente = %s
            ''', (user_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def atualizar_user_type(user_id, novo_tipo):
    """
    Atualiza o tipo de usuário
    
    Args:
        user_id (int): ID do usuário
        novo_tipo (str): Novo tipo (client, admin, superadmin, readonly)
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET user_type = %s
                WHERE id_contato_cliente = %s
                RETURNING id_contato_cliente
            ''', (novo_tipo, user_id))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


def obter_clientes_sistema(filtros=None, vendedor_id=None):
    """
    Retorna todos os clientes do sistema
    
    Args:
        filtros (dict): Filtros opcionais (status, tipo_cliente, search)
        vendedor_id (int): ID do vendedor para filtrar clientes
    
    Returns:
        list: Lista de clientes com contagem de usuários
    """
    conn = get_db()
    try:
        query = '''
            SELECT 
                cli.*,
                tc.display as tipo_cliente_nome,
                e.descricao as estado_nome,
                COUNT(DISTINCT c.id_contato_cliente) as total_usuarios,
                COUNT(DISTINCT c.id_contato_cliente) FILTER (WHERE c.status = true) as usuarios_ativos
            FROM tbl_cliente cli
            LEFT JOIN tbl_tipo_cliente tc ON cli.id_tipo_cliente = tc.id_tipo_cliente
            LEFT JOIN tbl_estado e ON cli.pk_id_aux_estado = e.id_estado
            LEFT JOIN tbl_contato_cliente c ON cli.id_cliente = c.pk_id_tbl_cliente
            WHERE 1=1
        '''
        
        params = []
        
        if filtros:
            if filtros.get('status') is not None:
                query += ' AND cli.status = %s'
                params.append(filtros['status'])
            
            if filtros.get('tipo_cliente'):
                query += ' AND cli.id_tipo_cliente = %s'
                params.append(filtros['tipo_cliente'])
            
            if filtros.get('search'):
                query += ' AND (unaccent(cli.nome_fantasia) ILIKE unaccent(%s) OR unaccent(cli.razao_social) ILIKE unaccent(%s) OR cli.cnpj ILIKE %s)'
                search_term = f"%{filtros['search']}%"
                params.extend([search_term, search_term, search_term])
        
        # Filtrar por vendedor se especificado
        if vendedor_id:
            query += ' AND cli.vendas_central_comm = %s'
            params.append(vendedor_id)
        
        query += '''
            GROUP BY cli.id_cliente, tc.display, e.descricao
            ORDER BY cli.nome_fantasia ASC
        '''
        
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_clientes_simples():
    """Retorna lista simples de clientes para selects"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_cliente,
                    nome_fantasia,
                    razao_social,
                    cnpj
                FROM tbl_cliente
                WHERE status = true
                ORDER BY nome_fantasia ASC
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_contatos_comercial_operacoes():
    """Retorna lista de contatos de clientes dos setores Comercial e Operações"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.id_contato_cliente,
                    c.nome_completo,
                    c.email,
                    cli.nome_fantasia as cliente_nome,
                    s.display as setor
                FROM tbl_contato_cliente c
                INNER JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                LEFT JOIN tbl_setor s ON c.pk_id_tbl_setor = s.id_setor
                WHERE c.status = true
                AND s.display IN ('Comercial', 'Operações')
                ORDER BY cli.nome_fantasia ASC, c.nome_completo ASC
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_contatos_comerciais_por_cliente(cliente_id):
    """Retorna lista de contatos de um cliente específico dos setores Comercial e Operações"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.id_contato_cliente,
                    c.nome_completo,
                    c.email,
                    s.display as setor
                FROM tbl_contato_cliente c
                LEFT JOIN tbl_setor s ON c.pk_id_tbl_setor = s.id_setor
                WHERE c.status = true
                AND c.pk_id_tbl_cliente = %s
                AND s.display IN ('Comercial', 'Operações')
                ORDER BY c.nome_completo ASC
            ''', (cliente_id,))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_vendedores():
    """Retorna lista de vendedores (contatos) do cliente CENTRALCOMM com setor Comercial e cargo Executivo Vendas"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.id_contato_cliente,
                    c.nome_completo,
                    c.email
                FROM tbl_contato_cliente c
                INNER JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                INNER JOIN tbl_setor s ON c.pk_id_tbl_setor = s.id_setor
                INNER JOIN tbl_cargo_contato car ON c.pk_id_tbl_cargo = car.id_cargo_contato
                WHERE c.status = true
                AND cli.nome_fantasia = 'CENTRALCOMM'
                AND s.display = 'Comercial'
                AND car.descricao = 'Executivo Vendas'
                ORDER BY c.nome_completo ASC
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_system_settings():
    """Retorna todas as configurações do sistema"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    setting_key,
                    setting_value,
                    setting_type,
                    description,
                    is_public,
                    updated_at
                FROM tbl_system_settings
                ORDER BY setting_key
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_system_setting(key):
    """Retorna uma configuração específica do sistema"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT setting_value, setting_type
                FROM tbl_system_settings
                WHERE setting_key = %s
            ''', (key,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            # Converter para tipo correto
            if result['setting_type'] == 'boolean':
                return result['setting_value'].lower() == 'true'
            elif result['setting_type'] == 'integer':
                return int(result['setting_value'])
            elif result['setting_type'] == 'float':
                return float(result['setting_value'])
            else:
                return result['setting_value']
    except Exception as e:
        raise e


def atualizar_system_setting(key, value, updated_by=None):
    """
    Atualiza uma configuração do sistema
    
    Args:
        key (str): Chave da configuração
        value: Novo valor
        updated_by (int): ID do usuário que atualizou
    """
    conn = get_db()
    try:
        # Converter valor para string
        if isinstance(value, bool):
            value_str = 'true' if value else 'false'
        else:
            value_str = str(value)
        
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_system_settings
                SET setting_value = %s,
                    updated_by = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE setting_key = %s
                RETURNING setting_key
            ''', (value_str, updated_by, key))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


def obter_plan_definitions(apenas_ativos=True):
    """Retorna todas as definições de plano da tabela cadu_plan_definitions"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = 'SELECT * FROM cadu_plan_definitions'
            if apenas_ativos:
                query += ' WHERE is_active = true'
            query += ' ORDER BY display_order'
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_planos_clientes(filtros=None):
    """
    Retorna planos de todos os clientes
    
    Args:
        filtros (dict): Filtros opcionais (plan_status, id_plan_definition, cliente_id)
    
    Returns:
        list: Lista de planos
    """
    conn = get_db()
    try:
        query = '''
            SELECT 
                p.*,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj,
                pd.plan_name as plan_definition_name,
                pd.max_users as pd_max_users,
                pd.tokens_monthly_limit as pd_tokens_monthly_limit,
                pd.limit_image_generation as pd_limit_image_generation,
                CASE 
                    WHEN COALESCE(pd.tokens_monthly_limit, p.tokens_monthly_limit) > 0 THEN 
                        ROUND((p.tokens_used_current_month::decimal / COALESCE(pd.tokens_monthly_limit, p.tokens_monthly_limit)) * 100, 1)
                    ELSE 0 
                END as tokens_usage_percentage,
                CASE 
                    WHEN COALESCE(pd.limit_image_generation, p.image_credits_monthly) > 0 THEN 
                        ROUND((p.image_credits_used_current_month::decimal / COALESCE(pd.limit_image_generation, p.image_credits_monthly)) * 100, 1)
                    ELSE 0 
                END as images_usage_percentage
            FROM cadu_client_plans p
            INNER JOIN tbl_cliente cli ON p.id_cliente = cli.id_cliente
            LEFT JOIN cadu_plan_definitions pd ON p.id_plan_definition = pd.id
            WHERE 1=1
        '''
        
        params = []
        
        if filtros:
            if filtros.get('plan_status'):
                query += ' AND p.plan_status = %s'
                params.append(filtros['plan_status'])
            
            if filtros.get('id_plan_definition'):
                query += ' AND p.id_plan_definition = %s'
                params.append(filtros['id_plan_definition'])
            
            if filtros.get('cliente_id'):
                query += ' AND p.id_cliente = %s'
                params.append(filtros['cliente_id'])
        
        query += ' ORDER BY p.created_at DESC'
        
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_plano_por_id(plan_id):
    """Retorna informações de um plano específico"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    p.*,
                    cli.nome_fantasia,
                    cli.razao_social,
                    u.nome_completo as created_by_name,
                    pd.plan_name as plan_definition_name
                FROM cadu_client_plans p
                INNER JOIN tbl_cliente cli ON p.id_cliente = cli.id_cliente
                LEFT JOIN tbl_contato_cliente u ON p.created_by = u.id_contato_cliente
                LEFT JOIN cadu_plan_definitions pd ON p.id_plan_definition = pd.id
                WHERE p.id = %s
            ''', (plan_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def criar_client_plan(dados):
    """
    Cria um novo plano para cliente
    
    Args:
        dados (dict): Dados do plano
    
    Returns:
        int: ID do plano criado
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_client_plans (
                    id_cliente, id_plan_definition,
                    tokens_monthly_limit, image_credits_monthly, max_users,
                    features, plan_status, plan_start_date, plan_end_date,
                    valid_from, valid_until
                ) VALUES (
                    %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s
                ) RETURNING id
            ''', (
                dados['id_cliente'],
                dados['id_plan_definition'],
                dados.get('tokens_monthly_limit', 100000),
                dados.get('image_credits_monthly', 50),
                dados.get('max_users', 5),
                dados.get('features', '{}'),
                dados.get('plan_status', 'active'),
                dados.get('plan_start_date'),
                dados.get('plan_end_date'),
                dados.get('valid_from'),
                dados.get('valid_until')
            ))
            
            plan_id = cursor.fetchone()['id']
            conn.commit()
            return plan_id
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_client_plan(plan_id, dados):
    """Atualiza dados de um plano existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_client_plans
                SET id_plan_definition = %s,
                    tokens_monthly_limit = %s,
                    image_credits_monthly = %s,
                    max_users = %s,
                    features = %s::jsonb,
                    plan_status = %s,
                    valid_from = %s,
                    valid_until = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
                RETURNING id
            ''', (
                dados['id_plan_definition'],
                dados['tokens_monthly_limit'],
                dados['image_credits_monthly'],
                dados['max_users'],
                dados.get('features', '{}'),
                dados['plan_status'],
                dados['valid_from'],
                dados.get('valid_until'),
                plan_id
            ))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_consumo_tokens(plan_id, tokens_usados, imagens_usadas=0):
    """
    Incrementa o consumo de tokens e imagens de um plano
    
    Args:
        plan_id (int): ID do plano
        tokens_usados (int): Quantidade de tokens consumidos
        imagens_usadas (int): Quantidade de imagens geradas
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_client_plans
                SET tokens_used_current_month = tokens_used_current_month + %s,
                    image_credits_used_current_month = image_credits_used_current_month + %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
                RETURNING id
            ''', (tokens_usados, imagens_usadas, plan_id))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


def resetar_contadores_mensais(plan_id=None):
    """
    Reseta contadores mensais de consumo
    
    Args:
        plan_id (int, optional): ID do plano específico, ou None para todos
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if plan_id:
                cursor.execute('''
                    UPDATE cadu_client_plans
                    SET tokens_used_current_month = 0,
                        image_credits_used_current_month = 0,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                    RETURNING id
                ''', (plan_id,))
            else:
                cursor.execute('''
                    UPDATE cadu_client_plans
                    SET tokens_used_current_month = 0,
                        image_credits_used_current_month = 0,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE plan_status = 'active'
                ''')
            
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        raise e


def criar_plano_beta_tester(cliente_id, created_by=None, valid_until=None):
    """
    Cria um plano Beta Tester para um cliente específico
    
    Args:
        cliente_id (int): ID do cliente
        created_by (int, optional): ID do usuário que criou o plano (não usado, mantido para compatibilidade)
        valid_until (datetime, optional): Data de validade do plano
    
    Returns:
        int: ID do plano criado
    """
    from datetime import datetime, timedelta
    import json
    
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM cadu_plan_definitions WHERE plan_type = %s LIMIT 1",
            ('Beta Tester',)
        )
        row = cursor.fetchone()
        id_plan_definition = row['id'] if row else None
    
    plan_start_date = datetime.now()
    plan_end_date = plan_start_date + timedelta(days=90)
    
    dados = {
        'id_cliente': cliente_id,
        'id_plan_definition': id_plan_definition,
        'plan_status': 'active',
        'tokens_monthly_limit': 100000,
        'image_credits_monthly': 50,
        'max_users': 10,
        'plan_start_date': plan_start_date,
        'plan_end_date': valid_until or plan_end_date,
        'valid_from': plan_start_date,
        'valid_until': valid_until or plan_end_date,
        'features': json.dumps({
            "all_modes": True,
            "unlimited_docs": True,
            "unlimited_conversations": True
        })
    }
    
    return criar_client_plan(dados)


# ==================== CONTADOR DE TOKENS ====================

def registrar_uso_token(conversation_id, tipo, quantidade, id_cliente=None, id_contato_cliente=None, 
                       message_id=None, modelo=None, custo_estimado=0):
    """
    Registra o uso de tokens na tabela cadu_token_usage
    
    Args:
        conversation_id (str): ID da conversa
        tipo (str): Tipo de uso (ex: 'chat', 'completion', 'embedding', etc)
        quantidade (int): Quantidade de tokens usados
        id_cliente (int, optional): ID do cliente
        id_contato_cliente (int, optional): ID do contato/usuário
        message_id (str, optional): ID da mensagem
        modelo (str, optional): Nome do modelo usado
        custo_estimado (float, optional): Custo estimado do uso
    
    Returns:
        int: ID do registro criado
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_token_usage (
                    conversation_id, message_id, tipo, quantidade,
                    modelo, custo_estimado, id_cliente, id_contato_cliente
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            ''', (
                conversation_id,
                message_id,
                tipo,
                quantidade,
                modelo,
                custo_estimado,
                id_cliente,
                id_contato_cliente
            ))
            
            registro_id = cursor.fetchone()['id']
            conn.commit()
            return registro_id
    except Exception as e:
        conn.rollback()
        raise e


def obter_uso_tokens_cliente(id_cliente, data_inicio=None, data_fim=None):
    """
    Obtém o total de tokens usados por um cliente em um período
    
    Args:
        id_cliente (int): ID do cliente
        data_inicio (datetime, optional): Data inicial do período
        data_fim (datetime, optional): Data final do período
    
    Returns:
        dict: Totais por tipo de uso
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    tipo,
                    SUM(quantidade) as total_tokens,
                    SUM(custo_estimado) as total_custo,
                    COUNT(*) as total_registros
                FROM cadu_token_usage
                WHERE id_cliente = %s
            '''
            params = [id_cliente]
            
            if data_inicio:
                query += ' AND created_at >= %s'
                params.append(data_inicio)
            
            if data_fim:
                query += ' AND created_at <= %s'
                params.append(data_fim)
            
            query += ' GROUP BY tipo ORDER BY total_tokens DESC'
            
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_uso_tokens_mes_atual(id_cliente=None):
    """
    Obtém o total de tokens usados no mês atual
    Considera apenas clientes com planos ativos e válidos
    
    Args:
        id_cliente (int, optional): ID do cliente. Se None, retorna total de todos os clientes
    
    Returns:
        int: Total de tokens do mês
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if id_cliente:
                cursor.execute('''
                    SELECT COALESCE(SUM(t.quantidade), 0) as total
                    FROM cadu_token_usage t
                    INNER JOIN cadu_client_plans p ON t.id_cliente = p.id_cliente
                    WHERE t.id_cliente = %s
                    AND p.plan_status = 'active'
                    AND p.valid_until >= CURRENT_DATE
                    AND EXTRACT(YEAR FROM t.created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
                    AND EXTRACT(MONTH FROM t.created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
                ''', (id_cliente,))
            else:
                cursor.execute('''
                    SELECT COALESCE(SUM(t.quantidade), 0) as total
                    FROM cadu_token_usage t
                    INNER JOIN cadu_client_plans p ON t.id_cliente = p.id_cliente
                    WHERE p.plan_status = 'active'
                    AND p.valid_until >= CURRENT_DATE
                    AND EXTRACT(YEAR FROM t.created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
                    AND EXTRACT(MONTH FROM t.created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
                ''')
            
            return cursor.fetchone()['total']
    except Exception as e:
        raise e


def obter_dashboard_stats():
    """Retorna estatísticas para o dashboard administrativo"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    AVISO_PLAN = int(os.getenv('AVISO_PLAN', '20'))
    ALERTA_CONSUMO_TOKEN = int(os.getenv('ALERTA_CONSUMO_TOKEN', '80'))
    limite_alerta = ALERTA_CONSUMO_TOKEN / 100.0
    
    conn = get_db()
    try:
        stats = {}
        
        with conn.cursor() as cursor:
            # Total de clientes ativos
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM tbl_cliente
                WHERE status = true
            ''')
            stats['total_clientes_ativos'] = cursor.fetchone()['total']
            
            # Total de usuários
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM tbl_contato_cliente
                WHERE status = true
            ''')
            stats['total_usuarios'] = cursor.fetchone()['total']
            
            # Tokens consumidos no mês atual (usando cadu_token_usage)
            stats['tokens_mes_atual'] = obter_uso_tokens_mes_atual()
            
            # Nome do mês atual em português
            from datetime import datetime
            
            # Mapeamento manual de meses em português
            meses_pt = {
                1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
                5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
                9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
            }
            
            agora = datetime.now()
            mes_nome = meses_pt[agora.month]
            stats['mes_atual'] = f"{mes_nome}/{agora.year}"
            
            # Tokens do mês anterior
            mes_anterior_num = agora.month - 1 if agora.month > 1 else 12
            ano_anterior = agora.year if agora.month > 1 else agora.year - 1
            cursor.execute('''
                SELECT COALESCE(SUM(quantidade), 0) as total
                FROM cadu_token_usage
                WHERE EXTRACT(YEAR FROM created_at) = %s
                AND EXTRACT(MONTH FROM created_at) = %s
            ''', (ano_anterior, mes_anterior_num))
            stats['tokens_mes_anterior'] = cursor.fetchone()['total']
            mes_anterior_nome = meses_pt[mes_anterior_num]
            stats['mes_anterior'] = f"{mes_anterior_nome}/{ano_anterior}"
            
            # Imagens geradas no mês atual
            cursor.execute('''
                SELECT COALESCE(SUM(image_credits_used_current_month), 0) as total
                FROM cadu_client_plans
                WHERE plan_status = 'active'
            ''')
            stats['imagens_mes_atual'] = cursor.fetchone()['total']
            
            # Planos próximos do limite (usar ALERTA_CONSUMO_TOKEN do .env)
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM cadu_client_plans
                WHERE plan_status = 'active'
                AND valid_until >= CURRENT_DATE
                AND (
                    (tokens_used_current_month::decimal / NULLIF(tokens_monthly_limit, 0)) >= %s
                    OR
                    (image_credits_used_current_month::decimal / NULLIF(image_credits_monthly, 0)) >= %s
                )
            ''', (limite_alerta, limite_alerta))
            stats['planos_proximo_limite'] = cursor.fetchone()['total']
            
            # Planos próximos do vencimento (usar AVISO_PLAN do .env)
            cursor.execute(f'''
                SELECT COUNT(*) as total
                FROM cadu_client_plans
                WHERE plan_status = 'active'
                AND valid_until IS NOT NULL
                AND valid_until BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '{AVISO_PLAN} days'
            ''')
            stats['planos_vencendo'] = cursor.fetchone()['total']
            
        return stats
    except Exception as e:
        raise e


def obter_invoices(filtros=None):
    """
    Retorna faturas do sistema
    
    Args:
        filtros (dict): Filtros opcionais (invoice_status, cliente_id, reference_month)
    
    Returns:
        list: Lista de faturas
    """
    conn = get_db()
    try:
        query = '''
            SELECT 
                i.*,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj
            FROM cadu_invoices i
            INNER JOIN tbl_cliente cli ON i.id_cliente = cli.id_cliente
            WHERE 1=1
        '''
        
        params = []
        
        if filtros:
            if filtros.get('invoice_status'):
                query += ' AND i.invoice_status = %s'
                params.append(filtros['invoice_status'])
            
            if filtros.get('cliente_id'):
                query += ' AND i.id_cliente = %s'
                params.append(filtros['cliente_id'])
            
            if filtros.get('reference_month'):
                query += ' AND i.reference_month = %s'
                params.append(filtros['reference_month'])
        
        query += ' ORDER BY i.reference_month DESC, i.issue_date DESC'
        
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def criar_invoice(dados):
    """
    Cria uma nova fatura
    
    Args:
        dados (dict): Dados da fatura
    
    Returns:
        int: ID da fatura criada
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # Gerar número de fatura
            cursor.execute("SELECT nextval('seq_invoice_number')")
            invoice_number = f"INV-{cursor.fetchone()['nextval']:06d}"
            
            cursor.execute('''
                INSERT INTO cadu_invoices (
                    invoice_number, id_cliente, id, reference_month,
                    tokens_consumed, tokens_cost,
                    images_generated, images_cost,
                    extra_users_count, extra_users_cost,
                    subtotal, taxes_amount, total,
                    invoice_status, issue_date, due_date,
                    created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id_invoice
            ''', (
                invoice_number,
                dados['id_cliente'],
                dados.get('id'),
                dados['reference_month'],
                dados.get('tokens_consumed', 0),
                dados.get('tokens_cost', 0),
                dados.get('images_generated', 0),
                dados.get('images_cost', 0),
                dados.get('extra_users_count', 0),
                dados.get('extra_users_cost', 0),
                dados['subtotal'],
                dados.get('taxes_amount', 0),
                dados['total'],
                dados.get('invoice_status', 'pending'),
                dados.get('issue_date'),
                dados['due_date'],
                dados.get('created_by')
            ))
            
            invoice_id = cursor.fetchone()['id_invoice']
            conn.commit()
            return invoice_id
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_invoice_status(invoice_id, novo_status, paid_date=None):
    """
    Atualiza status de uma fatura
    
    Args:
        invoice_id (int): ID da fatura
        novo_status (str): Novo status (pending, sent, paid, overdue, cancelled)
        paid_date (date, optional): Data de pagamento
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_invoices
                SET invoice_status = %s,
                    paid_date = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_invoice = %s
                RETURNING id_invoice
            ''', (novo_status, paid_date, invoice_id))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


# ==================== INVOICES - FUNÇÕES ADICIONAIS ====================

def obter_invoice_por_id(invoice_id):
    """
    Retorna uma invoice específica com detalhes do cliente
    
    Args:
        invoice_id (int): ID da invoice
    
    Returns:
        dict: Dados da invoice com informações do cliente
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    i.*,
                    cli.nome_fantasia,
                    cli.razao_social,
                    cli.cnpj
                FROM cadu_invoices i
                INNER JOIN tbl_cliente cli ON i.id_cliente = cli.id_cliente
                WHERE i.id = %s
            ''', (invoice_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def obter_invoices_cliente(cliente_id, limit=12):
    """
    Retorna as últimas invoices de um cliente
    
    Args:
        cliente_id (int): ID do cliente
        limit (int): Número máximo de registros
    
    Returns:
        list: Lista de invoices do cliente
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT *
                FROM cadu_invoices
                WHERE id_cliente = %s
                ORDER BY billing_month DESC, created_at DESC
                LIMIT %s
            ''', (cliente_id, limit))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_invoices_pendentes():
    """
    Retorna todas as invoices com status pending ou overdue
    
    Returns:
        list: Lista de invoices pendentes
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    i.*,
                    cli.nome_fantasia,
                    cli.razao_social,
                    cli.cnpj
                FROM cadu_invoices i
                INNER JOIN tbl_cliente cli ON i.id_cliente = cli.id_cliente
                WHERE i.status IN ('pending', 'overdue')
                ORDER BY i.due_date ASC, i.created_at DESC
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e


def marcar_invoice_paga(invoice_id, data_pagamento=None):
    """
    Marca uma invoice como paga
    
    Args:
        invoice_id (int): ID da invoice
        data_pagamento (datetime, optional): Data do pagamento (default: agora)
    
    Returns:
        bool: True se atualizado com sucesso
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_invoices
                SET status = 'paid',
                    paid_at = COALESCE(%s, DATE_TRUNC('second', CURRENT_TIMESTAMP))
                WHERE id = %s
                RETURNING id
            ''', (data_pagamento, invoice_id))
            
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


def calcular_total_invoice(tokens_used, tokens_cost, image_credits_used, image_credits_cost, 
                          extra_users, extra_users_cost, tax_percentage=0):
    """
    Calcula os totais de uma invoice
    
    Args:
        tokens_used (int): Tokens utilizados
        tokens_cost (float): Custo dos tokens
        image_credits_used (int): Créditos de imagem utilizados
        image_credits_cost (float): Custo das imagens
        extra_users (int): Usuários extras
        extra_users_cost (float): Custo de usuários extras
        tax_percentage (float): Percentual de impostos (default: 0)
    
    Returns:
        dict: Dicionário com subtotal, tax, total
    """
    subtotal = float(tokens_cost) + float(image_credits_cost) + float(extra_users_cost)
    tax = subtotal * (float(tax_percentage) / 100)
    total = subtotal + tax
    
    return {
        'subtotal': round(subtotal, 2),
        'tax': round(tax, 2),
        'total': round(total, 2)
    }


def gerar_numero_invoice():
    """
    Gera próximo número de invoice no formato INV-XXXXXX
    
    Returns:
        str: Número da invoice (ex: INV-001234)
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT COALESCE(MAX(
                    CAST(SUBSTRING(invoice_number FROM 5) AS INTEGER)
                ), 0) + 1 as next_number
                FROM cadu_invoices
                WHERE invoice_number LIKE 'INV-%'
            ''')
            
            result = cursor.fetchone()
            next_num = result['next_number'] if result else 1
            return f'INV-{next_num:06d}'
    except Exception as e:
        raise e


# ==================== ASSINATURAS / SUBSCRIPTION ====================

def criar_invoice_assinatura(dados):
    """
    Cria uma fatura do tipo subscription com billing_data JSON.

    Args:
        dados (dict): Deve conter id_cliente, plan_type, total, due_date, billing_data (dict),
                      opcionalmente invoice_number, id_plan, created_by.
    Returns:
        dict: {id_invoice, invoice_number}
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            invoice_number = dados.get('invoice_number')
            if not invoice_number:
                from datetime import datetime as _dt
                import secrets as _sec
                suffix = _sec.token_hex(3).upper()
                invoice_number = f"INV-{_dt.now().strftime('%Y%m%d')}-{suffix}"

            billing_json = dados.get('billing_data')
            if isinstance(billing_json, dict):
                import json
                billing_json = json.dumps(billing_json, ensure_ascii=False)

            cursor.execute('''
                INSERT INTO cadu_invoices (
                    invoice_number, id_cliente, id_plan,
                    invoice_type, plan_type, total, subtotal,
                    invoice_status, issue_date, due_date,
                    billing_data, created_by
                ) VALUES (
                    %s, %s, %s,
                    'subscription', %s, %s, %s,
                    'pending', CURRENT_DATE, %s,
                    %s::jsonb, %s
                ) RETURNING id_invoice, invoice_number
            ''', (
                invoice_number,
                dados['id_cliente'],
                dados.get('id_plan'),
                dados['plan_type'],
                dados['total'],
                dados.get('subtotal', dados['total']),
                dados['due_date'],
                billing_json,
                dados.get('created_by')
            ))

            row = cursor.fetchone()
            conn.commit()
            return {'id_invoice': row['id_invoice'], 'invoice_number': row['invoice_number']}
    except Exception as e:
        conn.rollback()
        raise e


def obter_invoices_assinatura_pendentes():
    """
    Retorna faturas de assinatura com status pending, ordenadas por criacao desc.
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    i.id_invoice,
                    i.invoice_number,
                    i.plan_type,
                    i.total,
                    i.due_date,
                    i.billing_data,
                    i.created_at,
                    c.nome_fantasia,
                    c.razao_social,
                    c.cnpj
                FROM cadu_invoices i
                JOIN tbl_cliente c ON c.id_cliente = i.id_cliente
                WHERE i.invoice_status = 'pending'
                  AND i.invoice_type = 'subscription'
                ORDER BY i.created_at DESC
            ''')
            return cursor.fetchall()
    except Exception as e:
        raise e


def aprovar_invoice_assinatura(invoice_id):
    """
    Marca uma fatura de assinatura como paga.

    Args:
        invoice_id (int): ID da fatura (id_invoice)
    Returns:
        bool: True se atualizado
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_invoices
                SET invoice_status = 'paid',
                    paid_date = CURRENT_DATE,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_invoice = %s
                  AND invoice_type = 'subscription'
                RETURNING id_invoice
            ''', (invoice_id,))
            result = cursor.fetchone()
            conn.commit()
            return result is not None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_dados_billing_cliente(cliente_id, dados):
    """
    Atualiza dados de faturamento em tbl_cliente (CNPJ, razao social, endereco, etc.).
    Apenas atualiza campos fornecidos no dict.

    Args:
        cliente_id (int): ID do cliente
        dados (dict): Campos a atualizar — chaves aceitas:
            cnpj, razao_social, nome_fantasia, cep, cidade,
            logradouro, bairro, numero, complemento, pk_id_aux_estado
    Returns:
        bool
    """
    campos_permitidos = {
        'cnpj': 'cnpj',
        'razao_social': 'razao_social',
        'nome_fantasia': 'nome_fantasia',
        'cep': 'cep',
        'cidade': 'cidade',
        'logradouro': 'logradouro',
        'bairro': 'bairro',
        'numero': 'numero',
        'complemento': 'complemento',
        'pk_id_aux_estado': 'pk_id_aux_estado',
    }

    sets = []
    params = []
    for chave, coluna in campos_permitidos.items():
        if chave in dados and dados[chave] is not None:
            sets.append(f"{coluna} = %s")
            params.append(dados[chave])

    if not sets:
        return True

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = f"UPDATE tbl_cliente SET {', '.join(sets)} WHERE id_cliente = %s"
            params.append(cliente_id)
            cursor.execute(query, params)
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        raise e


# ==================== AUDIT LOG - FUNÇÕES ====================

def registrar_audit_log(fk_id_usuario, acao, modulo, descricao=None, registro_id=None, 
                       registro_tipo=None, ip_address=None, user_agent=None, 
                       dados_anteriores=None, dados_novos=None):
    """
    Registra uma ação administrativa no log de auditoria
    
    Args:
        fk_id_usuario (int): ID do usuário que realizou a ação
        acao (str): Tipo de ação (criar, editar, deletar, visualizar, etc)
        modulo (str): Módulo do sistema (usuarios, clientes, planos, etc)
        descricao (str, optional): Descrição detalhada da ação
        registro_id (int, optional): ID do registro afetado
        registro_tipo (str, optional): Tipo do registro (cliente, usuario, plano, etc)
        ip_address (str, optional): Endereço IP do usuário
        user_agent (str, optional): User agent do navegador
        dados_anteriores (dict, optional): Dados antes da alteração (convertido para JSONB)
        dados_novos (dict, optional): Dados depois da alteração (convertido para JSONB)
    
    Returns:
        int: ID do log criado
    """
    import json
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # Converter dicts para JSON string se necessário
            dados_ant_json = json.dumps(dados_anteriores) if dados_anteriores else None
            dados_nov_json = json.dumps(dados_novos) if dados_novos else None
            
            cursor.execute('''
                INSERT INTO tbl_admin_audit_log 
                (fk_id_usuario, acao, modulo, descricao, registro_id, registro_tipo,
                 ip_address, user_agent, dados_anteriores, dados_novos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING id_log
            ''', (fk_id_usuario, acao, modulo, descricao, registro_id, registro_tipo,
                  ip_address, user_agent, dados_ant_json, dados_nov_json))
            
            result = cursor.fetchone()
            conn.commit()
            return result['id_log'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def obter_audit_logs(filtros=None, limit=100, offset=0):
    """
    Retorna logs de auditoria com filtros opcionais
    
    Args:
        filtros (dict, optional): Filtros (modulo, acao, usuario_id, data_inicio, data_fim)
        limit (int): Número máximo de registros
        offset (int): Offset para paginação
    
    Returns:
        list: Lista de logs de auditoria
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    l.*,
                    u.nome_completo as usuario_nome,
                    u.email as usuario_email
                FROM tbl_admin_audit_log l
                INNER JOIN tbl_contato_cliente u ON l.fk_id_usuario = u.id_contato_cliente
                WHERE 1=1
            '''
            
            params = []
            
            if filtros:
                if filtros.get('modulo'):
                    query += ' AND l.modulo = %s'
                    params.append(filtros['modulo'])
                
                if filtros.get('acao'):
                    query += ' AND l.acao = %s'
                    params.append(filtros['acao'])
                
                if filtros.get('usuario_id'):
                    query += ' AND l.fk_id_usuario = %s'
                    params.append(filtros['usuario_id'])
                
                if filtros.get('data_inicio'):
                    query += ' AND l.data_acao >= %s'
                    params.append(filtros['data_inicio'])
                
                if filtros.get('data_fim'):
                    query += ' AND l.data_acao <= %s'
                    params.append(filtros['data_fim'])
                
                if filtros.get('registro_id') and filtros.get('registro_tipo'):
                    query += ' AND l.registro_id = %s AND l.registro_tipo = %s'
                    params.append(filtros['registro_id'])
                    params.append(filtros['registro_tipo'])
            
            query += ' ORDER BY l.data_acao DESC LIMIT %s OFFSET %s'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_audit_log_por_id(log_id):
    """
    Retorna um log de auditoria específico
    
    Args:
        log_id (int): ID do log
    
    Returns:
        dict: Dados do log com informações do usuário
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    l.*,
                    u.nome_completo as usuario_nome,
                    u.email as usuario_email
                FROM tbl_admin_audit_log l
                INNER JOIN tbl_contato_cliente u ON l.fk_id_usuario = u.id_contato_cliente
                WHERE l.id_log = %s
            ''', (log_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def obter_audit_logs_usuario(usuario_id, limit=50):
    """
    Retorna os últimos logs de um usuário específico
    
    Args:
        usuario_id (int): ID do usuário
        limit (int): Número máximo de registros
    
    Returns:
        list: Lista de logs do usuário
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT *
                FROM tbl_admin_audit_log
                WHERE fk_id_usuario = %s
                ORDER BY data_acao DESC
                LIMIT %s
            ''', (usuario_id, limit))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_audit_logs_registro(registro_id, registro_tipo, limit=50):
    """
    Retorna todos os logs relacionados a um registro específico
    
    Args:
        registro_id (int): ID do registro
        registro_tipo (str): Tipo do registro (cliente, usuario, plano, etc)
        limit (int): Número máximo de registros
    
    Returns:
        list: Lista de logs do registro
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    l.*,
                    u.nome_completo as usuario_nome,
                    u.email as usuario_email
                FROM tbl_admin_audit_log l
                INNER JOIN tbl_contato_cliente u ON l.fk_id_usuario = u.id_contato_cliente
                WHERE l.registro_id = %s AND l.registro_tipo = %s
                ORDER BY l.data_acao DESC
                LIMIT %s
            ''', (registro_id, registro_tipo, limit))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_estatisticas_audit_log(dias=30):
    """
    Retorna estatísticas do log de auditoria
    
    Args:
        dias (int): Número de dias para análise
    
    Returns:
        dict: Estatísticas (total_acoes, por_modulo, por_acao, usuarios_ativos)
    """
    from datetime import datetime, timedelta
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            stats = {}
            
            # Calcular data de corte
            data_corte = datetime.now() - timedelta(days=dias)
            
            # Total de ações nos últimos N dias
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM tbl_admin_audit_log
                WHERE data_acao >= %s
            ''', (data_corte,))
            stats['total_acoes'] = cursor.fetchone()['total']
            
            # Ações por módulo
            cursor.execute('''
                SELECT modulo, COUNT(*) as total
                FROM tbl_admin_audit_log
                WHERE data_acao >= %s
                GROUP BY modulo
                ORDER BY total DESC
            ''', (data_corte,))
            stats['por_modulo'] = cursor.fetchall()
            
            # Ações por tipo
            cursor.execute('''
                SELECT acao, COUNT(*) as total
                FROM tbl_admin_audit_log
                WHERE data_acao >= %s
                GROUP BY acao
                ORDER BY total DESC
            ''', (data_corte,))
            stats['por_acao'] = cursor.fetchall()
            
            # Usuários mais ativos
            cursor.execute('''
                SELECT 
                    u.nome_completo,
                    u.email,
                    COUNT(*) as total_acoes
                FROM tbl_admin_audit_log l
                INNER JOIN tbl_contato_cliente u ON l.fk_id_usuario = u.id_contato_cliente
                WHERE l.data_acao >= %s
                GROUP BY u.id_contato_cliente, u.nome_completo, u.email
                ORDER BY total_acoes DESC
                LIMIT 10
            ''', (data_corte,))
            stats['usuarios_ativos'] = cursor.fetchall()
            
            return stats
    except Exception as e:
        raise e


# ==================== INVITES ====================

def obter_invites_cliente(id_cliente):
    """Retorna todos os invites de um cliente"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                id,
                id_cliente,
                invited_by,
                email,
                invite_token,
                status,
                role,
                expires_at,
                accepted_at,
                created_at
            FROM cadu_user_invites
            WHERE id_cliente = %s
            ORDER BY created_at DESC
        ''', (id_cliente,))
        return cursor.fetchall()


def verificar_convite_pendente(email, id_cliente=None):
    """
    Verifica se já existe um convite pendente (não expirado) para o email
    
    Args:
        email: Email a verificar
        id_cliente: ID do cliente (opcional, para verificar convite específico)
    
    Returns:
        dict: Dados do convite pendente se existir, None caso contrário
    """
    from datetime import datetime
    conn = get_db()
    
    with conn.cursor() as cursor:
        if id_cliente:
            cursor.execute('''
                SELECT id, email, id_cliente, status, expires_at
                FROM cadu_user_invites
                WHERE email = %s 
                  AND id_cliente = %s
                  AND status = 'pending'
                  AND expires_at > %s
            ''', (email.lower().strip(), id_cliente, datetime.now()))
        else:
            cursor.execute('''
                SELECT id, email, id_cliente, status, expires_at
                FROM cadu_user_invites
                WHERE email = %s 
                  AND status = 'pending'
                  AND expires_at > %s
            ''', (email.lower().strip(), datetime.now()))
        
        return cursor.fetchone()


def obter_invite_por_id(invite_id):
    """Retorna um invite por ID"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                id,
                id_cliente,
                invited_by,
                email,
                invite_token,
                status,
                role,
                expires_at,
                accepted_at,
                created_at
            FROM cadu_user_invites
            WHERE id = %s
        ''', (invite_id,))
        return cursor.fetchone()


def obter_invite_por_token(token):
    """Retorna um invite por token"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                i.id,
                i.id_cliente,
                i.invited_by,
                i.email,
                i.invite_token,
                i.status,
                i.role,
                i.expires_at,
                i.accepted_at,
                i.created_at,
                c.nome_fantasia as cliente_nome,
                c.razao_social as cliente_razao
            FROM cadu_user_invites i
            LEFT JOIN tbl_cliente c ON i.id_cliente = c.id_cliente
            WHERE i.invite_token = %s
        ''', (token,))
        return cursor.fetchone()


def aceitar_invite(invite_id, contato_id):
    """Marca um invite como aceito"""
    conn = get_db()
    from datetime import datetime
    
    with conn.cursor() as cursor:
        cursor.execute('''
            UPDATE cadu_user_invites 
            SET status = 'accepted', accepted_at = %s
            WHERE id = %s AND status = 'pending'
        ''', (datetime.now(), invite_id))
        conn.commit()
        return cursor.rowcount > 0


def criar_invite(id_cliente, invited_by, email, role='member'):
    """Cria um novo convite"""
    import secrets
    from datetime import datetime, timedelta
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"criar_invite: id_cliente={id_cliente}, invited_by={invited_by}, email={email}, role={role}")
    
    conn = get_db()
    
    try:
        # Gerar token único (64 caracteres hex)
        invite_token = secrets.token_hex(32)
        
        # Convite expira em 7 dias
        expires_at = datetime.now() + timedelta(days=7)
        
        logger.info(f"criar_invite: token gerado, expires_at={expires_at}")
        
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_user_invites (
                    id_cliente,
                    invited_by,
                    email,
                    invite_token,
                    status,
                    role,
                    expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (id_cliente, invited_by, email.lower().strip(), invite_token, 'pending', role, expires_at))
            
            invite_id = cursor.fetchone()['id']
            logger.info(f"criar_invite: invite_id={invite_id}")
        
        conn.commit()
        return invite_id
        
    except Exception as e:
        logger.error(f"criar_invite ERROR: {e}")
        conn.rollback()
        raise e


def reenviar_invite(invite_id):
    """Atualiza a data de expiração de um convite pendente"""
    from datetime import datetime, timedelta
    
    conn = get_db()
    
    try:
        # Nova data de expiração: 7 dias a partir de agora
        new_expires_at = datetime.now() + timedelta(days=7)
        
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_user_invites
                SET expires_at = %s,
                    status = 'pending'
                WHERE id = %s 
                  AND status = 'pending'
                RETURNING id
            ''', (new_expires_at, invite_id))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result is not None
        
    except Exception as e:
        conn.rollback()
        raise e


def cancelar_invite(invite_id):
    """Cancela um convite (atualiza status para 'cancelled')"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_user_invites
                SET status = 'cancelled'
                WHERE id = %s AND status = 'pending'
                RETURNING id
            ''', (invite_id,))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result is not None
        
    except Exception as e:
        conn.rollback()
        raise e


# ==================== COTAÇÕES ====================

def obter_cotacoes_cliente(cliente_id):
    """Retorna todas as cotações de um cliente"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                c.*,
                cont.nome_completo as contato_nome,
                vend.nome_completo as vendedor_nome,
                st.descricao as status_descricao
            FROM cadu_cotacoes c
            LEFT JOIN tbl_contato_cliente cont ON c.contato_cliente_id = cont.id_contato_cliente
            LEFT JOIN tbl_contato_cliente vend ON c.vendas_central_comm = vend.id_contato_cliente
            LEFT JOIN cadu_cotacoes_status st ON c.status = st.id
            WHERE c.cliente_id = %s
            ORDER BY c.created_at DESC
        ''', (cliente_id,))
        return cursor.fetchall()


def obter_todas_cotacoes():
    """Retorna todas as cotações do sistema"""
    conn = get_db()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                id,
                titulo,
                cliente_id,
                status
            FROM cadu_cotacoes
            ORDER BY id DESC
        ''')
        return cursor.fetchall()
    except Exception as e:
        print(f"Erro ao buscar cotações: {e}")
        return []

def obter_cotacoes_filtradas(vendedor_id=None, cliente_id=None, status_id=None, nome_campanha=None):
    """Retorna cotações com filtros opcionais"""
    conn = get_db()
    
    query = '''
        SELECT 
            c.*,
            cli.nome_fantasia,
            cli.razao_social,
            cont.nome_completo as contato_nome,
            vend.nome_completo as vendedor_nome,
            st.descricao as status_descricao
        FROM cadu_cotacoes c
        LEFT JOIN tbl_cliente cli ON c.cliente_id = cli.id_cliente
        LEFT JOIN tbl_contato_cliente cont ON c.contato_cliente_id = cont.id_contato_cliente
        LEFT JOIN tbl_contato_cliente vend ON c.vendas_central_comm = vend.id_contato_cliente
        LEFT JOIN cadu_cotacoes_status st ON c.status = st.id
        WHERE 1=1
    '''
    
    params = []
    
    if vendedor_id:
        query += ' AND c.vendas_central_comm = %s'
        params.append(vendedor_id)
    
    if cliente_id:
        query += ' AND c.cliente_id = %s'
        params.append(cliente_id)
    
    if status_id:
        query += ' AND c.status = %s'
        params.append(status_id)
    
    if nome_campanha:
        query += ' AND c.nome_campanha ILIKE %s'
        params.append(f'%{nome_campanha}%')
    
    query += ' ORDER BY c.created_at DESC'
    
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def obter_status_cotacoes():
    """Retorna todos os status de cotações"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('SELECT id, descricao FROM cadu_cotacoes_status ORDER BY id')
        return cursor.fetchall()
        return cursor.fetchall()


def atualizar_cotacao(cotacao_id, nome_campanha, periodo_meses, praca, objetivo, observacoes=None, status=None, vendas_central_comm=None):
    """Atualiza uma cotação existente"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_cotacoes
                SET nome_campanha = %s,
                    periodo_meses = %s,
                    praca = %s,
                    objetivo = %s,
                    observacoes = %s,
                    status = %s,
                    vendas_central_comm = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
                RETURNING id
            ''', (nome_campanha, periodo_meses, praca, objetivo, observacoes, status, vendas_central_comm, cotacao_id))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result is not None
        
    except Exception as e:
        conn.rollback()
        raise e


def deletar_cotacao(cotacao_id):
    """Deleta uma cotação"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_cotacoes
                WHERE id = %s
                RETURNING id
            ''', (cotacao_id,))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result is not None
        
    except Exception as e:
        conn.rollback()
        raise e


# ==================== FUNÇÕES COTAÇÃO AUDIÊNCIAS ====================

def obter_audiencias_cotacao(cotacao_id):
    """Retorna todas as audiências de uma cotação"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                ca.id,
                ca.cotacao_id,
                ca.audiencia_id,
                ca.audiencia_nome,
                ca.audiencia_publico,
                ca.audiencia_categoria,
                ca.audiencia_subcategoria,
                ca.cpm_estimado,
                ca.investimento_sugerido,
                ca.impressoes_estimadas,
                ca.ordem_exibicao,
                ca.incluido_proposta,
                ca.motivo_exclusao,
                ca.added_at,
                a.id_audiencia_plataforma,
                a.fonte
            FROM cadu_cotacao_audiencias ca
            LEFT JOIN cadu_audiencias a ON ca.audiencia_id = a.id
            WHERE ca.cotacao_id = %s
            AND ca.incluido_proposta = TRUE
            ORDER BY ca.ordem_exibicao, ca.added_at
        ''', (cotacao_id,))
        return cursor.fetchall()


def obter_audiencia_cotacao_por_id(audiencia_cotacao_id):
    """Retorna uma audiência específica de uma cotação"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                id,
                cotacao_id,
                audiencia_id,
                audiencia_nome,
                audiencia_publico,
                audiencia_categoria,
                audiencia_subcategoria,
                cpm_estimado,
                investimento_sugerido,
                impressoes_estimadas,
                ordem_exibicao,
                incluido_proposta,
                motivo_exclusao,
                added_at
            FROM cadu_cotacao_audiencias
            WHERE id = %s
        ''', (audiencia_cotacao_id,))
        return cursor.fetchone()


def adicionar_audiencia_cotacao(cotacao_id, audiencia_nome, audiencia_id=None, audiencia_publico=None,
                                audiencia_categoria=None, audiencia_subcategoria=None,
                                cpm_estimado=None, investimento_sugerido=None, impressoes_estimadas=None,
                                ordem_exibicao=0, incluido_proposta=True):
    """Adiciona uma audiência à cotação"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_cotacao_audiencias 
                (cotacao_id, audiencia_id, audiencia_nome, audiencia_publico, 
                 audiencia_categoria, audiencia_subcategoria,
                 cpm_estimado, investimento_sugerido, impressoes_estimadas,
                 ordem_exibicao, incluido_proposta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (cotacao_id, audiencia_id, audiencia_nome, audiencia_publico,
                  audiencia_categoria, audiencia_subcategoria,
                  cpm_estimado, investimento_sugerido, impressoes_estimadas,
                  ordem_exibicao, incluido_proposta))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result['id'] if result else None
        
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_audiencia_cotacao(audiencia_cotacao_id, cpm_estimado=None, investimento_sugerido=None, 
                                impressoes_estimadas=None, ordem_exibicao=None, incluido_proposta=None, 
                                motivo_exclusao=None):
    """Atualiza uma audiência da cotação"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            # Construir query dinamicamente apenas com campos fornecidos
            updates = []
            params = []
            
            if cpm_estimado is not None:
                updates.append('cpm_estimado = %s')
                params.append(cpm_estimado)
            
            if investimento_sugerido is not None:
                updates.append('investimento_sugerido = %s')
                params.append(investimento_sugerido)
            
            if impressoes_estimadas is not None:
                updates.append('impressoes_estimadas = %s')
                params.append(impressoes_estimadas)
            
            if ordem_exibicao is not None:
                updates.append('ordem_exibicao = %s')
                params.append(ordem_exibicao)
            
            if incluido_proposta is not None:
                updates.append('incluido_proposta = %s')
                params.append(incluido_proposta)
            
            if motivo_exclusao is not None:
                updates.append('motivo_exclusao = %s')
                params.append(motivo_exclusao)
            
            if not updates:
                return False
            
            params.append(audiencia_cotacao_id)
            query = f"UPDATE cadu_cotacao_audiencias SET {', '.join(updates)} WHERE id = %s RETURNING id"
            
            cursor.execute(query, params)
            result = cursor.fetchone()
        
        conn.commit()
        return result is not None
        
    except Exception as e:
        conn.rollback()
        raise e


def remover_audiencia_cotacao(audiencia_cotacao_id):
    """Remove uma audiência da cotação"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_cotacao_audiencias
                WHERE id = %s
                RETURNING id
            ''', (audiencia_cotacao_id,))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result is not None
        
    except Exception as e:
        conn.rollback()
        raise e


# ==================== COMENTÁRIOS DE COTAÇÃO ====================

def obter_comentarios_cotacao(cotacao_id):
    """Obtém todos os comentários de uma cotação"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.id,
                    c.cotacao_id,
                    c.user_id,
                    c.user_type,
                    c.comentario,
                    c.created_at,
                    COALESCE(u.nome_completo, 'Usuário Desconhecido') as usuario_nome
                FROM cadu_cotacao_comentarios c
                LEFT JOIN tbl_contato_cliente u ON c.user_id = u.id_contato_cliente
                WHERE c.cotacao_id = %s
                ORDER BY c.created_at ASC
            ''', (cotacao_id,))
            
            return cursor.fetchall()
            
    except Exception as e:
        current_app.logger.error(f"Erro ao obter comentários da cotação {cotacao_id}: {e}")
        raise e


def adicionar_comentario_cotacao(cotacao_id, user_id, user_type, comentario):
    """Adiciona um comentário à cotação"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_cotacao_comentarios 
                (cotacao_id, user_id, user_type, comentario)
                VALUES (%s, %s, %s, %s)
                RETURNING id, created_at
            ''', (cotacao_id, user_id, user_type, comentario))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro ao adicionar comentário: {e}")
        raise e


def remover_comentario_cotacao(comentario_id, user_id, user_type):
    """Remove um comentário (apenas o próprio usuário ou admin pode remover)"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            # Verificar se o usuário pode remover este comentário
            if user_type == 'admin':
                # Admin pode remover qualquer comentário
                cursor.execute('''
                    DELETE FROM cadu_cotacao_comentarios
                    WHERE id = %s
                    RETURNING id
                ''', (comentario_id,))
            else:
                # Cliente só pode remover seus próprios comentários
                cursor.execute('''
                    DELETE FROM cadu_cotacao_comentarios
                    WHERE id = %s AND user_id = %s AND user_type = %s
                    RETURNING id
                ''', (comentario_id, user_id, user_type))
            
            result = cursor.fetchone()
        
        conn.commit()
        return result is not None
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro ao remover comentário: {e}")
        raise e


def obter_historico_cotacao(cotacao_id):
    """Obtém o histórico de alterações de uma cotação via audit log"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    a.id,
                    a.acao,
                    a.descricao,
                    a.created_at,
                    COALESCE(u.nome_completo, 'Sistema') as usuario_nome
                FROM tbl_admin_audit_log a
                LEFT JOIN tbl_contato_cliente u ON a.user_id = u.id_contato_cliente
                WHERE a.registro_tipo = 'cadu_cotacoes' 
                  AND a.registro_id = %s
                ORDER BY a.created_at DESC
                LIMIT 50
            ''', (cotacao_id,))
            
            return cursor.fetchall()
            
    except Exception as e:
        current_app.logger.error(f"Erro ao obter histórico da cotação {cotacao_id}: {e}")
        raise e


# ==================== GESTÃO DE BRIEFINGS ====================

def obter_todos_briefings(filtros=None):
    """
    Retorna todos os briefings com filtros opcionais
    
    Args:
        filtros (dict): {'status': str, 'cliente_id': int, 'busca': str, 'projeto_id': int, 'responsavel_id': int, 'sem_responsavel': bool}
    
    Returns:
        list: Lista de briefings com dados relacionados
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    b.*,
                    c.nome_fantasia as cliente_nome,
                    cont.nome_completo as contato_nome,
                    cont.email as contato_email,
                    p.nome as projeto_nome,
                    resp.nome_completo as responsavel_nome
                FROM cadu_briefings b
                LEFT JOIN tbl_cliente c ON b.id_cliente = c.id_cliente
                LEFT JOIN tbl_contato_cliente cont ON b.id_contato_cliente = cont.id_contato_cliente
                LEFT JOIN cadu_projetos p ON b.id_projeto = p.id
                LEFT JOIN tbl_contato_cliente resp ON b.responsavel_centralcomm::integer = resp.id_contato_cliente
                WHERE b.deleted_at IS NULL
            '''
            params = []
            
            if filtros:
                if 'status' in filtros and filtros['status']:
                    query += ' AND b.status = %s'
                    params.append(filtros['status'])
                
                if 'cliente_id' in filtros and filtros['cliente_id']:
                    query += ' AND b.id_cliente = %s'
                    params.append(filtros['cliente_id'])
                
                if 'projeto_id' in filtros and filtros['projeto_id']:
                    query += ' AND b.id_projeto = %s'
                    params.append(filtros['projeto_id'])
                
                if 'plataforma' in filtros and filtros['plataforma']:
                    query += ' AND b.plataforma = %s'
                    params.append(filtros['plataforma'])
                
                if filtros.get('sem_responsavel'):
                    query += ' AND (b.responsavel_centralcomm IS NULL OR b.responsavel_centralcomm = \'\')'
                elif 'responsavel_id' in filtros and filtros['responsavel_id']:
                    query += ' AND b.responsavel_centralcomm = %s'
                    params.append(str(filtros['responsavel_id']))
                
                if 'busca' in filtros and filtros['busca']:
                    query += ' AND (b.titulo ILIKE %s OR b.objetivo ILIKE %s OR b.briefing_original ILIKE %s)'
                    busca = f"%{filtros['busca']}%"
                    params.extend([busca, busca, busca])
                
                if 'mes' in filtros and filtros['mes']:
                    query += ' AND EXTRACT(MONTH FROM b.created_at) = %s'
                    params.append(filtros['mes'])
                
                if 'ano' in filtros and filtros['ano']:
                    query += ' AND EXTRACT(YEAR FROM b.created_at) = %s'
                    params.append(filtros['ano'])
            
            query += ' ORDER BY b.created_at DESC'
            
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_briefing_por_id(briefing_id):
    """
    Retorna um briefing específico por ID
    
    Args:
        briefing_id (int): ID do briefing
    
    Returns:
        dict: Dados completos do briefing
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    b.*,
                    c.nome_fantasia as cliente_nome,
                    cont.nome_completo as contato_nome,
                    cont.email as contato_email,
                    cont.telefone as contato_telefone,
                    p.nome as projeto_nome,
                    resp.nome_completo as responsavel_nome
                FROM cadu_briefings b
                LEFT JOIN tbl_cliente c ON b.id_cliente = c.id_cliente
                LEFT JOIN tbl_contato_cliente cont ON b.id_contato_cliente = cont.id_contato_cliente
                LEFT JOIN cadu_projetos p ON b.id_projeto = p.id
                LEFT JOIN tbl_contato_cliente resp ON b.responsavel_centralcomm::integer = resp.id_contato_cliente
                WHERE b.id = %s AND b.deleted_at IS NULL
            ''', (briefing_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def obter_briefing_por_uuid(uuid):
    """
    Retorna um briefing específico por UUID
    
    Args:
        uuid (str): UUID do briefing
    
    Returns:
        dict: Dados completos do briefing
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    b.*,
                    c.nome_fantasia as cliente_nome,
                    cont.nome_completo as contato_nome,
                    cont.email as contato_email,
                    p.nome as projeto_nome
                FROM cadu_briefings b
                LEFT JOIN tbl_cliente c ON b.id_cliente = c.id_cliente
                LEFT JOIN tbl_contato_cliente cont ON b.id_contato_cliente = cont.id_contato_cliente
                LEFT JOIN cadu_projetos p ON b.id_projeto = p.id
                WHERE b.uuid = %s AND b.deleted_at IS NULL
            ''', (uuid,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def obter_briefings_por_cliente(cliente_id):
    """
    Retorna briefings de um cliente específico
    
    Args:
        cliente_id (int): ID do cliente
    
    Returns:
        list: Lista de briefings do cliente
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    b.id,
                    b.uuid,
                    b.titulo,
                    b.objetivo,
                    b.status,
                    b.progresso,
                    b.plataforma,
                    b.created_at,
                    p.nome as projeto_nome
                FROM cadu_briefings b
                LEFT JOIN cadu_projetos p ON b.id_projeto = p.id
                WHERE b.id_cliente = %s AND b.deleted_at IS NULL
                ORDER BY b.created_at DESC
            ''', (cliente_id,))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_briefings_por_projeto(projeto_id):
    """
    Retorna briefings de um projeto específico
    
    Args:
        projeto_id (int): ID do projeto
    
    Returns:
        list: Lista de briefings do projeto
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    b.*,
                    c.nome_fantasia as cliente_nome
                FROM cadu_briefings b
                LEFT JOIN tbl_cliente c ON b.id_cliente = c.id_cliente
                WHERE b.id_projeto = %s AND b.deleted_at IS NULL
                ORDER BY b.created_at DESC
            ''', (projeto_id,))
            return cursor.fetchall()
    except Exception as e:
        raise e


def criar_briefing(dados):
    """
    Cria um novo briefing
    
    Args:
        dados (dict): Dados do briefing (incluindo novos campos: uuid, id_projeto, plataforma, etc.)
    
    Returns:
        dict: {'id': int, 'uuid': str}
    """
    conn = get_db()
    try:
        import uuid
        briefing_uuid = str(uuid.uuid4())
        
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_briefings (
                    uuid, id_cliente, id_contato_cliente, titulo, status,
                    progresso, briefing_original, briefing_melhorado, analise_ia,
                    objetivo, budget, prazo, responsavel, responsavel_centralcomm,
                    link_publico_token, link_publico_ativo, enviado_para_centralcomm,
                    data_envio, id_projeto, plataforma
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id, uuid
            ''', (
                briefing_uuid,
                dados.get('id_cliente') or dados.get('cliente_id'),
                dados.get('id_contato_cliente'),
                dados.get('titulo'),
                dados.get('status', 'rascunho'),
                dados.get('progresso', 0),
                dados.get('briefing_original'),
                dados.get('briefing_melhorado'),
                dados.get('analise_ia'),
                dados.get('objetivo'),
                dados.get('budget'),
                dados.get('prazo'),
                dados.get('responsavel'),
                dados.get('responsavel_centralcomm'),
                dados.get('link_publico_token'),
                dados.get('link_publico_ativo', False),
                dados.get('enviado_para_centralcomm', False),
                dados.get('data_envio'),
                dados.get('id_projeto'),
                dados.get('plataforma')
            ))
            
            result = cursor.fetchone()
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_briefing(briefing_id, dados):
    """
    Atualiza dados de um briefing
    
    Args:
        briefing_id (int): ID do briefing
        dados (dict): Dados para atualizar
    
    Returns:
        bool: True se atualizado com sucesso
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # Construir query dinamicamente com campos presentes
            campos = []
            valores = []
            
            campos_mapeamento = {
                'id_cliente': 'id_cliente',
                'cliente_id': 'id_cliente',
                'id_contato_cliente': 'id_contato_cliente',
                'id_cotacao': 'id_cotacao',
                'titulo': 'titulo',
                'status': 'status',
                'progresso': 'progresso',
                'briefing_original': 'briefing_original',
                'briefing_melhorado': 'briefing_melhorado',
                'analise_ia': 'analise_ia',
                'objetivo': 'objetivo',
                'budget': 'budget',
                'prazo': 'prazo',
                'responsavel': 'responsavel',
                'responsavel_centralcomm': 'responsavel_centralcomm',
                'link_publico_token': 'link_publico_token',
                'link_publico_ativo': 'link_publico_ativo',
                'enviado_para_centralcomm': 'enviado_para_centralcomm',
                'data_envio': 'data_envio',
                'id_projeto': 'id_projeto',
                'plataforma': 'plataforma',
                'observacoes': 'observacoes'
            }
            
            for key, db_field in campos_mapeamento.items():
                if key in dados:
                    campos.append(f'{db_field} = %s')
                    valores.append(dados[key])
            
            if not campos:
                return False
            
            # Sempre atualizar updated_at
            campos.append("updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)")
            valores.append(briefing_id)
            
            query = f"UPDATE cadu_briefings SET {', '.join(campos)} WHERE id = %s"
            
            cursor.execute(query, valores)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_briefing(briefing_id, soft_delete=True):
    """
    Exclui um briefing (soft delete por padrão)
    
    Args:
        briefing_id (int): ID do briefing
        soft_delete (bool): Se True, apenas marca como deletado
    
    Returns:
        bool: True se excluído com sucesso
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if soft_delete:
                cursor.execute('''
                    UPDATE cadu_briefings
                    SET deleted_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                ''', (briefing_id,))
            else:
                cursor.execute('DELETE FROM cadu_briefings WHERE id = %s', (briefing_id,))
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_status_briefing(briefing_id, novo_status, progresso=None):
    """
    Atualiza status e progresso de um briefing
    
    Args:
        briefing_id (int): ID do briefing
        novo_status (str): Novo status
        progresso (int): Progresso opcional (0-100)
    
    Returns:
        bool: True se atualizado com sucesso
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if progresso is not None:
                cursor.execute('''
                    UPDATE cadu_briefings
                    SET status = %s,
                        progresso = %s,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                ''', (novo_status, progresso, briefing_id))
            else:
                cursor.execute('''
                    UPDATE cadu_briefings
                    SET status = %s,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                ''', (novo_status, briefing_id))
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e

# ==================== COTAÇÕES ====================

def criar_tabela_cotacoes():
    """Verifica se a tabela cadu_cotacoes existe no banco de dados"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # Apenas verificar se a tabela existe
            cursor.execute('''
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'cadu_cotacoes'
                )
            ''')
            result = cursor.fetchone()
            # Para RealDictCursor, acessamos pela chave 'exists'
            table_exists = result['exists'] if isinstance(result, dict) else result[0]
            
            if not table_exists:
                raise Exception("Tabela 'cadu_cotacoes' não existe no banco de dados!")
            
            return True
    except Exception as e:
        raise e


def obter_cotacoes(cliente_id=None, status=None):
    """Obtém cotações com filtros opcionais"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    c.*,
                    cli.nome_fantasia as cliente_nome,
                    resp.nome_completo as responsavel_nome,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_linhas WHERE cotacao_id = c.id AND is_deleted = false AND is_subtotal = false AND is_header = false), 0) as total_linhas,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_audiencias WHERE cotacao_id = c.id), 0) as total_audiencias,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_anexos WHERE cotacao_id = c.id), 0) as total_anexos
                FROM cadu_cotacoes c
                LEFT JOIN tbl_cliente cli ON c.client_id = cli.id_cliente
                LEFT JOIN tbl_contato_cliente resp ON c.responsavel_comercial = resp.id_contato_cliente
                WHERE c.deleted_at IS NULL
            '''
            params = []
            
            if cliente_id:
                query += ' AND c.client_id = %s'
                params.append(cliente_id)
            
            if status:
                query += ' AND c.status = %s'
                params.append(status)
            
            query += ' ORDER BY c.periodo_inicio DESC'
            
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_cotacoes_por_vendedor(vendedor_id):
    """Obtém cotações filtradas por vendedor responsável"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.*,
                    cli.nome_fantasia as cliente_nome,
                    resp.nome_completo as responsavel_nome,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_linhas WHERE cotacao_id = c.id AND is_deleted = false AND is_subtotal = false AND is_header = false), 0) as total_linhas,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_audiencias WHERE cotacao_id = c.id), 0) as total_audiencias,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_anexos WHERE cotacao_id = c.id), 0) as total_anexos
                FROM cadu_cotacoes c
                LEFT JOIN tbl_cliente cli ON c.client_id = cli.id_cliente
                LEFT JOIN tbl_contato_cliente resp ON c.responsavel_comercial = resp.id_contato_cliente
                WHERE c.responsavel_comercial = %s AND c.deleted_at IS NULL
                ORDER BY c.periodo_inicio DESC
            ''', (vendedor_id,))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_cotacoes_filtradas(cliente_id=None, responsavel_id=None, mes=None, busca=None, status=None):
    """Obtém cotações com filtros avançados para listagem"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    c.*,
                    cli.nome_fantasia as cliente_nome,
                    resp.nome_completo as responsavel_nome,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_linhas WHERE cotacao_id = c.id AND is_deleted = false AND is_subtotal = false AND is_header = false), 0) as total_linhas,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_audiencias WHERE cotacao_id = c.id), 0) as total_audiencias,
                    COALESCE((SELECT COUNT(*) FROM cadu_cotacao_anexos WHERE cotacao_id = c.id), 0) as total_anexos,
                    COALESCE((SELECT SUM(COALESCE(investimento_bruto, 0)) FROM cadu_cotacao_linhas WHERE cotacao_id = c.id AND is_deleted = false AND is_subtotal = false AND is_header = false), 0) 
                        + COALESCE((SELECT SUM(COALESCE(investimento_sugerido, 0)) FROM cadu_cotacao_audiencias WHERE cotacao_id = c.id AND incluido_proposta = true), 0) as valor_total_bruto,
                    COALESCE((SELECT SUM(COALESCE(investimento_liquido, 0)) FROM cadu_cotacao_linhas WHERE cotacao_id = c.id AND is_deleted = false AND is_subtotal = false AND is_header = false), 0) 
                        + COALESCE((SELECT SUM(COALESCE(investimento_sugerido, 0)) FROM cadu_cotacao_audiencias WHERE cotacao_id = c.id AND incluido_proposta = true), 0) as valor_total_liquido
                FROM cadu_cotacoes c
                LEFT JOIN tbl_cliente cli ON c.client_id = cli.id_cliente
                LEFT JOIN tbl_contato_cliente resp ON c.responsavel_comercial = resp.id_contato_cliente
                WHERE c.deleted_at IS NULL
            '''
            params = []
            
            if cliente_id:
                query += ' AND c.client_id = %s'
                params.append(cliente_id)
            
            if responsavel_id:
                query += ' AND c.responsavel_comercial = %s'
                params.append(responsavel_id)
            
            if mes:
                query += ' AND EXTRACT(MONTH FROM c.created_at) = %s'
                params.append(int(mes))
            
            if busca:
                query += ' AND (unaccent(cli.nome_fantasia) ILIKE unaccent(%s) OR unaccent(c.nome_campanha) ILIKE unaccent(%s) OR c.numero_cotacao ILIKE %s)'
                busca_param = f'%{busca}%'
                params.extend([busca_param, busca_param, busca_param])
            
            if status:
                if status == 'Rascunho':
                    query += " AND (c.status = 'Rascunho' OR c.status = 'Pendente' OR c.status IS NULL)"
                else:
                    query += ' AND c.status = %s'
                    params.append(status)
            
            # Ordenar: Enviadas primeiro (prioridade), depois por data de período
            query += '''
                ORDER BY 
                    CASE WHEN c.status = 'Enviada' THEN 0 ELSE 1 END,
                    c.periodo_inicio DESC NULLS LAST,
                    c.created_at DESC
            '''
            
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_cotacao_por_id(cotacao_id):
    """Obtém uma cotação por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    c.*,
                    cli.nome_fantasia as cliente_nome,
                    resp.nome_completo as responsavel_nome,
                    cont.nome_completo as contato_cliente_nome,
                    cont.email as contato_cliente_email,
                    cont.telefone as contato_cliente_telefone,
                    ag.nome_fantasia as agencia_nome,
                    cont_ag.nome_completo as agencia_user_nome,
                    br.titulo as briefing_titulo,
                    br.status as briefing_status,
                    parc.nome_fantasia as parceiro_nome,
                    cont_parc.nome_completo as parceiro_user_nome,
                    ag.percentual as agencia_percentual,
                    parc.percentual as parceiro_percentual
                FROM cadu_cotacoes c
                LEFT JOIN tbl_cliente cli ON c.client_id = cli.id_cliente
                LEFT JOIN tbl_contato_cliente resp ON c.responsavel_comercial = resp.id_contato_cliente
                LEFT JOIN tbl_contato_cliente cont ON c.client_user_id = cont.id_contato_cliente
                LEFT JOIN tbl_cliente ag ON c.agencia_id = ag.id_cliente
                LEFT JOIN tbl_contato_cliente cont_ag ON c.agencia_user_id = cont_ag.id_contato_cliente
                LEFT JOIN cadu_briefings br ON c.briefing_id = br.id
                LEFT JOIN tbl_cliente parc ON c.id_parceiro = parc.id_cliente
                LEFT JOIN tbl_contato_cliente cont_parc ON c.parceiro_user_id = cont_parc.id_contato_cliente
                WHERE c.id = %s AND c.deleted_at IS NULL
            ''', (cotacao_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def criar_cotacao(client_id, nome_campanha, periodo_inicio, **kwargs):
    """Cria uma nova cotação"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # Gerar número de cotação único
            numero_cotacao = f"COT-{datetime.now().strftime('%Y%m')}-{secrets.token_hex(3).upper()}"
            
            # Preparar campos dinamicamente
            campos = ['numero_cotacao', 'client_id', 'nome_campanha', 'periodo_inicio', 'created_at', 'updated_at']
            valores = [numero_cotacao, client_id, nome_campanha, periodo_inicio, "DATE_TRUNC('second', CURRENT_TIMESTAMP)", "DATE_TRUNC('second', CURRENT_TIMESTAMP)"]
            placeholders = ['%s', '%s', '%s', '%s', "DATE_TRUNC('second', CURRENT_TIMESTAMP)", "DATE_TRUNC('second', CURRENT_TIMESTAMP)"]
            params = [numero_cotacao, client_id, nome_campanha, periodo_inicio]
            
            # Adicionar campos opcionais
            campos_opcionais = [
                'objetivo_campanha', 'periodo_fim', 'status', 'client_user_id', 
                'responsavel_comercial', 'briefing_id', 'tipo_peca', 
                'budget_estimado', 'valor_total_proposta', 
                'observacoes', 'observacoes_internas', 'origem',
                'link_publico_ativo', 'link_publico_token', 'link_publico_expires_at',
                'agencia_id', 'agencia_user_id',
                'id_parceiro', 'parceiro_user_id'
            ]
            
            for campo in campos_opcionais:
                if campo in kwargs and kwargs[campo] is not None:
                    campos.append(campo)
                    valores.append('%s')
                    placeholders.append('%s')
                    params.append(kwargs[campo])
            
            query = f"INSERT INTO cadu_cotacoes ({', '.join(campos)}) VALUES ({', '.join(placeholders)}) RETURNING id, numero_cotacao"
            cursor.execute(query, params)
            
            resultado = cursor.fetchone()
            conn.commit()
            return resultado
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_cotacao(cotacao_id, **kwargs):
    """Atualiza uma cotação existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            updates = ["updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)"]
            params = []
            
            # Campos permitidos para atualização
            campos_permitidos = [
                'nome_campanha', 'objetivo_campanha', 'periodo_inicio', 'periodo_fim',
                'status', 'client_id', 'client_user_id', 'responsavel_comercial', 'briefing_id',
                'tipo_peca', 'budget_estimado', 'valor_total_proposta',
                'observacoes', 'observacoes_internas', 'origem', 'apresentacao_dados',
                'link_publico_ativo', 'link_publico_token', 'link_publico_expires_at', 'proposta_enviada_em',
                'aprovada_em', 'desconto_percentual', 'desconto_total', 'condicoes_comerciais', 'expires_at',
                'agencia_id', 'agencia_user_id',
                'id_parceiro', 'parceiro_user_id'
            ]
            
            # Campos que podem ser setados para NULL explicitamente
            campos_nullable = ['client_id', 'client_user_id', 'responsavel_comercial', 'briefing_id', 'periodo_fim', 'link_publico_expires_at', 'expires_at', 'agencia_id', 'agencia_user_id', 'id_parceiro', 'parceiro_user_id']
            
            # Campos booleanos que podem ser False
            campos_booleanos = ['link_publico_ativo']
            
            for campo in campos_permitidos:
                if campo in kwargs:
                    # Para campos nullable e booleanos, incluir mesmo se for None/False
                    if kwargs[campo] is not None or campo in campos_nullable or campo in campos_booleanos:
                        updates.append(f'{campo} = %s')
                        params.append(kwargs[campo])
            
            params.append(cotacao_id)
            
            query = f"UPDATE cadu_cotacoes SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def deletar_cotacao(cotacao_id, soft_delete=True):
    """Deleta uma cotação e seus registros relacionados (soft delete por padrão)"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if soft_delete:
                cursor.execute("""
                    UPDATE cadu_cotacao_linhas
                    SET is_deleted = true, updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE cotacao_id = %s AND (is_deleted IS NULL OR is_deleted = false)
                """, (cotacao_id,))

                cursor.execute("""
                    UPDATE cadu_cotacao_anexos
                    SET is_deleted = true
                    WHERE cotacao_id = %s AND (is_deleted IS NULL OR is_deleted = false)
                """, (cotacao_id,))

                cursor.execute("""
                    DELETE FROM cadu_cotacao_audiencias WHERE cotacao_id = %s
                """, (cotacao_id,))

                cursor.execute("""
                    UPDATE cadu_cotacoes
                    SET deleted_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                """, (cotacao_id,))
            else:
                cursor.execute('DELETE FROM cadu_cotacoes WHERE id = %s', (cotacao_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== LINHAS DE COTAÇÕES ====================

def criar_linha_cotacao(cotacao_id, pedido_sugestao=None, target=None, veiculo=None, plataforma=None,
                        produto=None, detalhamento=None, formato=None, formato_compra=None, periodo=None,
                        viewability_minimo=70, volume_contratado=None, valor_unitario=None, valor_total=None,
                        ordem=0, is_subtotal=False, subtotal_label=None, is_header=False, dados_extras=None,
                        meio=None, tipo_peca=None, segmentacao=None, formatos=None, canal=None,
                        objetivo_kpi=None, data_inicio=None, data_fim=None, investimento_bruto=None,
                        especificacoes=None, praca=None, desconto_percentual=None, valor_unitario_tabela=None,
                        valor_unitario_negociado=None, investimento_liquido=None):
    """Cria uma nova linha de cotação"""
    import json
    
    # Converter campos JSON/dict para string ANTES de passar para o cursor
    def safe_value(valor):
        """Converte qualquer dict/list/set para JSON string, mantém outros tipos"""
        if valor is None:
            return None
        if isinstance(valor, (dict, list, set, tuple)):
            return json.dumps(valor) if not isinstance(valor, tuple) else json.dumps(list(valor))
        if isinstance(valor, (str, int, float, bool)):
            return valor
        # Para qualquer outro tipo de objeto, tentar converter para string
        return str(valor)
    
    # Garantir que dados_extras não seja None (usar '{}' como default)
    dados_extras_final = dados_extras if dados_extras is not None else '{}'
    
    # Preparar todos os valores de forma segura
    valores = tuple([
        cotacao_id,  # Não aplicar safe_value no ID (deve ser int)
        safe_value(pedido_sugestao),
        safe_value(target),
        safe_value(veiculo),
        safe_value(plataforma),
        safe_value(produto),
        safe_value(detalhamento),
        safe_value(formato),
        safe_value(formato_compra),
        safe_value(periodo),
        safe_value(viewability_minimo),
        safe_value(volume_contratado),
        safe_value(valor_unitario),
        safe_value(valor_total),
        ordem,
        is_subtotal,
        safe_value(subtotal_label),
        is_header,
        safe_value(dados_extras_final),
        safe_value(meio),
        safe_value(tipo_peca),
        safe_value(segmentacao),
        safe_value(formatos),
        safe_value(canal),
        safe_value(objetivo_kpi),
        safe_value(data_inicio),
        safe_value(data_fim),
        safe_value(investimento_bruto),
        safe_value(especificacoes),
        safe_value(praca),
        safe_value(desconto_percentual),
        safe_value(valor_unitario_tabela),
        safe_value(valor_unitario_negociado),
        safe_value(investimento_liquido)
    ])
    
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_cotacao_linhas (
                    cotacao_id, pedido_sugestao, target, veiculo, plataforma, produto, detalhamento,
                    formato, formato_compra, periodo, viewability_minimo, volume_contratado,
                    valor_unitario, valor_total, ordem, is_subtotal, subtotal_label, is_header, dados_extras,
                    meio, tipo_peca, segmentacao, formatos, canal, objetivo_kpi, data_inicio, data_fim,
                    investimento_bruto, especificacoes, praca, desconto_percentual, valor_unitario_tabela,
                    valor_unitario_negociado, investimento_liquido
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', valores)
            linha_id = cursor.fetchone()['id']
            conn.commit()
            return linha_id
    except Exception as e:
        conn.rollback()
        raise e


def obter_linhas_cotacao(cotacao_id):
    """Obtém todas as linhas de uma cotação"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM cadu_cotacao_linhas
                WHERE cotacao_id = %s AND is_deleted = false
                ORDER BY ordem ASC
            ''', (cotacao_id,))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_linha_cotacao(linha_id):
    """Obtém uma linha de cotação por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM cadu_cotacao_linhas WHERE id = %s AND is_deleted = false', (linha_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def atualizar_linha_cotacao(linha_id, **kwargs):
    """Atualiza uma linha de cotação"""
    import json
    
    # Converter campos JSON/dict para string
    def to_json_string(valor):
        if valor is None:
            return None
        if isinstance(valor, (dict, list)):
            return json.dumps(valor)
        if isinstance(valor, str):
            return valor
        return None
    
    # Campos que devem ser convertidos para JSON string
    json_fields = {'produto', 'formatos', 'canal', 'dados_extras'}
    
    conn = get_db()
    try:
        campos_permitidos = {
            'pedido_sugestao', 'target', 'veiculo', 'plataforma', 'produto', 'detalhamento',
            'formato', 'formato_compra', 'periodo', 'viewability_minimo', 'volume_contratado',
            'valor_unitario', 'valor_total', 'ordem', 'is_subtotal', 'subtotal_label',
            'is_header', 'dados_extras', 'meio', 'tipo_peca', 'segmentacao', 'formatos',
            'canal', 'objetivo_kpi', 'data_inicio', 'data_fim', 'investimento_bruto',
            'especificacoes', 'praca', 'desconto_percentual', 'valor_unitario_tabela',
            'valor_unitario_negociado', 'investimento_liquido'
        }
        
        campos_atualizacao = {}
        for k, v in kwargs.items():
            if k in campos_permitidos and v is not None:
                # Converter campos JSON
                if k in json_fields:
                    campos_atualizacao[k] = to_json_string(v)
                else:
                    campos_atualizacao[k] = v
        
        if not campos_atualizacao:
            return False
        
        set_clause = ', '.join([f'{k} = %s' for k in campos_atualizacao.keys()])
        valores = list(campos_atualizacao.values()) + [linha_id]
        
        with conn.cursor() as cursor:
            cursor.execute(f'''
                UPDATE cadu_cotacao_linhas
                SET {set_clause}, updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s AND is_deleted = false
            ''', valores)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def deletar_linha_cotacao(linha_id, hard_delete=False):
    """Deleta uma linha de cotação (soft delete por padrão)"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if hard_delete:
                cursor.execute('DELETE FROM cadu_cotacao_linhas WHERE id = %s', (linha_id,))
            else:
                cursor.execute('''
                    UPDATE cadu_cotacao_linhas
                    SET is_deleted = true, updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                ''', (linha_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def gerar_link_publico_cotacao(cotacao_uuid, dias_validade=30):
    """Gera token único para compartilhamento público da cotação"""
    import secrets
    conn = get_db()
    try:
        # Gerar token aleatório de 64 caracteres hex
        novo_token = secrets.token_hex(32)
        
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_cotacoes 
                SET 
                    link_publico_token = %s,
                    link_publico_ativo = TRUE,
                    link_publico_expires_at = DATE_TRUNC('second', CURRENT_TIMESTAMP) + INTERVAL '%s days',
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE cotacao_uuid = %s 
                AND deleted_at IS NULL
            ''', (novo_token, dias_validade, cotacao_uuid))
            conn.commit()
            
            if cursor.rowcount > 0:
                return novo_token
            return None
    except Exception as e:
        conn.rollback()
        raise e


def renovar_link_publico_cotacao(cotacao_uuid, dias_validade=30):
    """Renova a validade de um link público existente"""
    from datetime import datetime, timedelta
    conn = get_db()
    try:
        nova_expiracao = datetime.now() + timedelta(days=dias_validade)
        
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_cotacoes 
                SET 
                    link_publico_ativo = TRUE,
                    link_publico_expires_at = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE cotacao_uuid = %s 
                AND deleted_at IS NULL
            ''', (nova_expiracao, cotacao_uuid))
            conn.commit()
            
            if cursor.rowcount > 0:
                return nova_expiracao
            return None
    except Exception as e:
        conn.rollback()
        raise e


def calcular_valor_total_cotacao(cotacao_id):
    """Calcula e atualiza o valor total da cotação baseado nas linhas, audiências e desconto"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # 1. Calcular total das linhas (investimento_bruto) - excluindo subtotais e headers
            cursor.execute('''
                SELECT COALESCE(SUM(investimento_bruto), 0) AS total_linhas
                FROM cadu_cotacao_linhas
                WHERE cotacao_id = %s 
                AND is_subtotal = FALSE 
                AND is_header = FALSE
                AND (is_deleted IS NULL OR is_deleted = FALSE)
            ''', (cotacao_id,))
            
            result_linhas = cursor.fetchone()
            total_linhas = float(result_linhas['total_linhas']) if result_linhas and result_linhas['total_linhas'] else 0.0
            
            # 2. Calcular total das audiências (investimento_sugerido) - apenas as incluídas na proposta
            cursor.execute('''
                SELECT COALESCE(SUM(investimento_sugerido), 0) AS total_audiencias
                FROM cadu_cotacao_audiencias
                WHERE cotacao_id = %s 
                AND incluido_proposta = TRUE
            ''', (cotacao_id,))
            
            result_audiencias = cursor.fetchone()
            total_audiencias = float(result_audiencias['total_audiencias']) if result_audiencias and result_audiencias['total_audiencias'] else 0.0
            
            # 3. Obter desconto total da cotação
            cursor.execute('''
                SELECT COALESCE(desconto_total, 0) AS desconto
                FROM cadu_cotacoes
                WHERE id = %s
            ''', (cotacao_id,))
            
            result_desconto = cursor.fetchone()
            desconto = float(result_desconto['desconto']) if result_desconto and result_desconto['desconto'] else 0.0
            
            # 4. Calcular valor total: subtotal - desconto
            subtotal = total_linhas + total_audiencias
            valor_total = subtotal - desconto
            
            # Garantir que não fique negativo
            if valor_total < 0:
                valor_total = 0.0
            
            # 5. Atualizar o valor na cotação
            cursor.execute('''
                UPDATE cadu_cotacoes 
                SET valor_total_proposta = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
            ''', (valor_total, cotacao_id))
            
            conn.commit()
            return valor_total
    except Exception as e:
        conn.rollback()
        raise Exception(f"Erro ao calcular total da cotação {cotacao_id}: {type(e).__name__} - {str(e)}")


# =====================================================
# FUNÇÕES PARA ANEXOS DE COTAÇÕES
# =====================================================

def obter_anexos_cotacao(cotacao_id):
    """Retorna todos os anexos de uma cotação"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM cadu_cotacao_anexos
                WHERE cotacao_id = %s 
                AND (is_deleted IS NULL OR is_deleted = FALSE)
                ORDER BY created_at DESC
            ''', (cotacao_id,))
            return cursor.fetchall()
    except Exception as e:
        raise e


def criar_anexo_cotacao(cotacao_id, nome_original, nome_arquivo, url_arquivo, 
                        mime_type=None, tamanho_bytes=None, descricao=None, uploaded_by=None):
    """Cria um novo anexo para a cotação"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_cotacao_anexos 
                (cotacao_id, nome_original, nome_arquivo, url_arquivo, mime_type, 
                 tamanho_bytes, descricao, uploaded_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, DATE_TRUNC('second', CURRENT_TIMESTAMP))
                RETURNING id
            ''', (cotacao_id, nome_original, nome_arquivo, url_arquivo, mime_type, 
                  tamanho_bytes, descricao, uploaded_by))
            anexo_id = cursor.fetchone()['id']
            conn.commit()
            return anexo_id
    except Exception as e:
        conn.rollback()
        raise e


def obter_anexo_por_id(anexo_id):
    """Retorna um anexo específico pelo ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM cadu_cotacao_anexos
                WHERE id = %s 
                AND (is_deleted IS NULL OR is_deleted = FALSE)
            ''', (anexo_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def atualizar_anexo_cotacao(anexo_id, **kwargs):
    """Atualiza um anexo da cotação"""
    conn = get_db()
    try:
        campos_permitidos = {'nome_original', 'descricao'}
        campos_atualizacao = {k: v for k, v in kwargs.items() if k in campos_permitidos and v is not None}
        
        if not campos_atualizacao:
            return False
        
        set_clause = ', '.join([f'{k} = %s' for k in campos_atualizacao.keys()])
        valores = list(campos_atualizacao.values()) + [anexo_id]
        
        with conn.cursor() as cursor:
            cursor.execute(f'''
                UPDATE cadu_cotacao_anexos
                SET {set_clause}
                WHERE id = %s AND (is_deleted IS NULL OR is_deleted = FALSE)
            ''', valores)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def deletar_anexo_cotacao(anexo_id, hard_delete=False):
    """Deleta um anexo da cotação (soft delete por padrão)"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if hard_delete:
                cursor.execute('DELETE FROM cadu_cotacao_anexos WHERE id = %s', (anexo_id,))
            else:
                cursor.execute('''
                    UPDATE cadu_cotacao_anexos
                    SET is_deleted = true
                    WHERE id = %s
                ''', (anexo_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== PROJETOS ====================

def obter_projetos_por_cliente(id_cliente):
    """Obtém todos os projetos de um cliente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id,
                    uuid,
                    id_cliente,
                    nome,
                    status,
                    created_at,
                    updated_at
                FROM cadu_projetos
                WHERE id_cliente = %s
                ORDER BY created_at DESC
            ''', (id_cliente,))
            return cursor.fetchall()
    except Exception as e:
        raise e


def obter_projeto_por_id(projeto_id):
    """Obtém um projeto por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    p.id,
                    p.uuid,
                    p.id_cliente,
                    p.nome,
                    p.status,
                    p.created_at,
                    p.updated_at,
                    c.nome_fantasia as cliente_nome
                FROM cadu_projetos p
                LEFT JOIN tbl_cliente c ON p.id_cliente = c.id_cliente
                WHERE p.id = %s
            ''', (projeto_id,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def obter_projeto_por_uuid(projeto_uuid):
    """Obtém um projeto por UUID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    p.id,
                    p.uuid,
                    p.id_cliente,
                    p.nome,
                    p.status,
                    p.created_at,
                    p.updated_at,
                    c.nome_fantasia as cliente_nome
                FROM cadu_projetos p
                LEFT JOIN tbl_cliente c ON p.id_cliente = c.id_cliente
                WHERE p.uuid = %s
            ''', (projeto_uuid,))
            return cursor.fetchone()
    except Exception as e:
        raise e


def listar_projetos(filtros=None):
    """Lista projetos com filtros opcionais"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    p.id,
                    p.uuid,
                    p.id_cliente,
                    p.nome,
                    p.status,
                    p.created_at,
                    p.updated_at,
                    c.nome_fantasia as cliente_nome
                FROM cadu_projetos p
                LEFT JOIN tbl_cliente c ON p.id_cliente = c.id_cliente
                WHERE 1=1
            '''
            params = []
            
            if filtros:
                if filtros.get('status'):
                    query += ' AND p.status = %s'
                    params.append(filtros['status'])
                
                if filtros.get('id_cliente'):
                    query += ' AND p.id_cliente = %s'
                    params.append(filtros['id_cliente'])
                
                if filtros.get('busca'):
                    query += ' AND p.nome ILIKE %s'
                    params.append(f"%{filtros['busca']}%")
            
            query += ' ORDER BY p.created_at DESC'
            
            if filtros and filtros.get('limit'):
                query += ' LIMIT %s'
                params.append(filtros['limit'])
            
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        raise e


# ==================== ANALYTICS - MÉTRICAS E DASHBOARD ====================

def get_analytics_overview():
    """
    Obtém métricas principais do dashboard: DAU, MAU, Sessões, etc.
    Usa a view v_analytics_dau_mau
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # DAU/MAU da view
            cursor.execute('''
                SELECT 
                    dau_today,
                    dau_yesterday,
                    wau,
                    mau,
                    sessions_today,
                    avg_session_duration_today,
                    avg_pages_per_session_today
                FROM v_analytics_dau_mau
            ''')
            dau_mau = cursor.fetchone()
            
            # Métricas de hoje - Briefings
            cursor.execute('''
                SELECT 
                    COUNT(*) FILTER (WHERE event_type = 'briefing_created' AND DATE(created_at) = CURRENT_DATE) AS criados_hoje,
                    COUNT(*) FILTER (WHERE event_type = 'briefing_submitted' AND DATE(created_at) = CURRENT_DATE) AS enviados_hoje,
                    COUNT(*) FILTER (WHERE event_type = 'briefing_viewed' AND DATE(created_at) = CURRENT_DATE) AS visualizados_hoje
                FROM cadu_analytics_events
                WHERE event_category = 'briefing'
            ''')
            briefings = cursor.fetchone()
            
            # Métricas de hoje - Cotações
            cursor.execute('''
                SELECT 
                    COUNT(*) FILTER (WHERE event_type = 'cotacao_created' AND DATE(created_at) = CURRENT_DATE) AS criadas_hoje,
                    COALESCE(SUM((metadata->>'valor_total')::DECIMAL) FILTER (WHERE DATE(created_at) = CURRENT_DATE), 0) AS valor_total_hoje
                FROM cadu_analytics_events
                WHERE event_category = 'cotacao'
            ''')
            cotacoes = cursor.fetchone()
            
            # Pageviews hoje
            cursor.execute('''
                SELECT COUNT(*) as pageviews_hoje
                FROM cadu_analytics_pageviews
                WHERE DATE(viewed_at) = CURRENT_DATE
            ''')
            pageviews = cursor.fetchone()
            
            # Audiências visualizadas hoje
            cursor.execute('''
                SELECT COUNT(*) as audiencias_hoje
                FROM cadu_analytics_events
                WHERE event_type = 'audiencia_viewed' AND DATE(created_at) = CURRENT_DATE
            ''')
            audiencias = cursor.fetchone()
            
            return {
                'dau': {
                    'value': dau_mau.get('dau_today', 0) if dau_mau else 0,
                    'previous': dau_mau.get('dau_yesterday', 0) if dau_mau else 0,
                    'change_percent': round(((dau_mau.get('dau_today', 0) - dau_mau.get('dau_yesterday', 1)) / max(dau_mau.get('dau_yesterday', 1), 1)) * 100, 1) if dau_mau else 0
                },
                'mau': {
                    'value': dau_mau.get('mau', 0) if dau_mau else 0
                },
                'wau': {
                    'value': dau_mau.get('wau', 0) if dau_mau else 0
                },
                'sessions_today': dau_mau.get('sessions_today', 0) if dau_mau else 0,
                'avg_session_duration': dau_mau.get('avg_session_duration_today', 0) if dau_mau else 0,
                'avg_pages_per_session': dau_mau.get('avg_pages_per_session_today', 0) if dau_mau else 0,
                'briefings_criados_hoje': briefings.get('criados_hoje', 0) if briefings else 0,
                'briefings_enviados_hoje': briefings.get('enviados_hoje', 0) if briefings else 0,
                'cotacoes_criadas_hoje': cotacoes.get('criadas_hoje', 0) if cotacoes else 0,
                'cotacoes_valor_hoje': float(cotacoes.get('valor_total_hoje', 0)) if cotacoes else 0,
                'pageviews_hoje': pageviews.get('pageviews_hoje', 0) if pageviews else 0,
                'audiencias_hoje': audiencias.get('audiencias_hoje', 0) if audiencias else 0
            }
    except Exception as e:
        # Se as tabelas não existem, retornar dados zerados
        return {
            'dau': {'value': 0, 'previous': 0, 'change_percent': 0},
            'mau': {'value': 0},
            'wau': {'value': 0},
            'sessions_today': 0,
            'avg_session_duration': 0,
            'avg_pages_per_session': 0,
            'briefings_criados_hoje': 0,
            'briefings_enviados_hoje': 0,
            'cotacoes_criadas_hoje': 0,
            'cotacoes_valor_hoje': 0,
            'pageviews_hoje': 0,
            'audiencias_hoje': 0
        }


def get_analytics_sessions_daily(days=30):
    """
    Obtém sessões por dia para gráfico
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    date,
                    total_sessions,
                    unique_users,
                    avg_duration,
                    total_pageviews,
                    mobile_sessions,
                    desktop_sessions
                FROM v_analytics_sessions_daily
                WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date ASC
            ''', (days,))
            return cursor.fetchall()
    except Exception:
        return []


def get_analytics_top_audiencias(limit=20):
    """
    Obtém top audiências mais visualizadas
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    audiencia_id,
                    audiencia_nome,
                    categoria,
                    total_views,
                    unique_users,
                    unique_clients
                FROM v_analytics_top_audiencias
                ORDER BY total_views DESC
                LIMIT %s
            ''', (limit,))
            return cursor.fetchall()
    except Exception:
        return []


def get_analytics_top_pages(limit=20):
    """
    Obtém top páginas mais visitadas
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    page_path,
                    page_type,
                    total_views,
                    unique_users,
                    avg_time_on_page
                FROM v_analytics_top_pages
                ORDER BY total_views DESC
                LIMIT %s
            ''', (limit,))
            return cursor.fetchall()
    except Exception:
        return []


def get_analytics_user_engagement(limit=50):
    """
    Obtém usuários mais ativos
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    user_id,
                    user_name,
                    user_email,
                    client_name,
                    total_sessions,
                    total_time_seconds,
                    avg_session_duration,
                    total_pageviews,
                    active_days,
                    last_session
                FROM v_analytics_user_engagement
                ORDER BY total_sessions DESC
                LIMIT %s
            ''', (limit,))
            return cursor.fetchall()
    except Exception:
        return []


def get_analytics_briefings_metrics(days=30):
    """
    Obtém métricas diárias de briefings
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    date,
                    briefings_created,
                    briefings_submitted,
                    briefings_viewed,
                    conversion_rate
                FROM v_analytics_briefings_metrics
                WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date ASC
            ''', (days,))
            return cursor.fetchall()
    except Exception:
        return []


def get_analytics_cotacoes_metrics(days=30):
    """
    Obtém métricas diárias de cotações
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    date,
                    cotacoes_created,
                    cotacoes_sent,
                    total_value,
                    avg_value
                FROM v_analytics_cotacoes_metrics
                WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date ASC
            ''', (days,))
            return cursor.fetchall()
    except Exception:
        return []


def get_analytics_briefing_platforms():
    """
    Obtém briefings por plataforma
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    plataforma,
                    total,
                    unique_users,
                    unique_clients
                FROM v_analytics_briefing_platforms
                ORDER BY total DESC
            ''')
            return cursor.fetchall()
    except Exception:
        return []


def get_analytics_audiencias_funnel(days=30):
    """
    Obtém funil de conversão de audiências
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    COUNT(*) FILTER (WHERE event_type = 'audiencia_viewed') AS visualizadas,
                    COUNT(*) FILTER (WHERE event_type = 'audiencia_added_to_cart') AS adicionadas_carrinho,
                    COUNT(*) FILTER (WHERE event_type = 'audiencia_quoted') AS cotadas,
                    ROUND(
                        COUNT(*) FILTER (WHERE event_type = 'audiencia_added_to_cart')::DECIMAL / 
                        NULLIF(COUNT(*) FILTER (WHERE event_type = 'audiencia_viewed'), 0) * 100, 
                        1
                    ) AS taxa_carrinho,
                    ROUND(
                        COUNT(*) FILTER (WHERE event_type = 'audiencia_quoted')::DECIMAL / 
                        NULLIF(COUNT(*) FILTER (WHERE event_type = 'audiencia_viewed'), 0) * 100, 
                        1
                    ) AS taxa_cotacao
                FROM cadu_analytics_events
                WHERE event_category = 'audiencia'
                  AND created_at >= CURRENT_DATE - INTERVAL '%s days'
            ''', (days,))
            return cursor.fetchone()
    except Exception:
        return {
            'visualizadas': 0,
            'adicionadas_carrinho': 0,
            'cotadas': 0,
            'taxa_carrinho': 0,
            'taxa_cotacao': 0
        }


# ==================== CLIENTES - LISTAGEM OTIMIZADA ====================

def obter_clientes_paginado(page=1, per_page=25, filtros=None):
    """
    Retorna clientes com paginação server-side e métricas mensais agregadas.
    
    Args:
        page (int): Número da página (1-indexed)
        per_page (int): Itens por página
        filtros (dict): Filtros opcionais:
            - executivo_id
            - status
            - search
            - categoria_abc
            - tem_agencia (True para clientes com agência, False para sem agência)
    
    Returns:
        dict: {
            'clientes': lista de clientes com métricas,
            'total': total de registros,
            'pages': total de páginas,
            'page': página atual
        }
    """
    conn = get_db()
    filtros = filtros or {}
    offset = (page - 1) * per_page
    
    try:
        # Query base com métricas agregadas do mês atual
        base_query = '''
            WITH metricas_mes AS (
                SELECT 
                    cli.id_cliente,
                    -- Cotações do mês
                    COUNT(DISTINCT cot.id) FILTER (
                        WHERE cot.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                    ) AS cotacoes_mes,
                    -- Cotações aprovadas do mês (status = '3' = Aprovada)
                    COUNT(DISTINCT cot.id) FILTER (
                        WHERE cot.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                        AND cot.status = '3'
                    ) AS cotacoes_aprovadas_mes,
                    -- Valor total aprovado no mês
                    COALESCE(SUM(cot.valor_total_proposta) FILTER (
                        WHERE cot.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                        AND cot.status = '3'
                    ), 0) AS valor_aprovado_mes,
                    -- Briefings do mês
                    COUNT(DISTINCT b.id) FILTER (
                        WHERE b.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                    ) AS briefings_mes,
                    -- Briefings aceitos do mês (status = 'accepted' ou similar)
                    COUNT(DISTINCT b.id) FILTER (
                        WHERE b.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                        AND b.status IN ('accepted', 'aprovado', 'aceito')
                    ) AS briefings_aceitos_mes
                FROM tbl_cliente cli
                LEFT JOIN cadu_cotacoes cot ON cot.client_id = cli.id_cliente
                LEFT JOIN cadu_briefings b ON b.cliente = cli.nome_fantasia
                GROUP BY cli.id_cliente
            )
            SELECT 
                cli.id_cliente,
                cli.nome_fantasia,
                cli.razao_social,
                cli.cnpj,
                cli.status,
                cli.categoria_abc,
                cli.vendas_central_comm,
                cli.pk_id_tbl_agencia,
                cli.id_tipo_cliente,
                tc.display AS tipo_cliente_display,
                ag.key AS agencia_key,
                vend.nome_completo AS executivo_nome,
                COUNT(DISTINCT cont.id_contato_cliente) AS total_usuarios,
                COALESCE(m.cotacoes_mes, 0) AS cotacoes_mes,
                COALESCE(m.cotacoes_aprovadas_mes, 0) AS cotacoes_aprovadas_mes,
                COALESCE(m.valor_aprovado_mes, 0) AS valor_aprovado_mes,
                COALESCE(m.briefings_mes, 0) AS briefings_mes,
                COALESCE(m.briefings_aceitos_mes, 0) AS briefings_aceitos_mes
            FROM tbl_cliente cli
            LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
            LEFT JOIN tbl_contato_cliente cont ON cont.pk_id_tbl_cliente = cli.id_cliente
            LEFT JOIN metricas_mes m ON m.id_cliente = cli.id_cliente
            LEFT JOIN tbl_agencia ag ON ag.id_agencia = cli.pk_id_tbl_agencia
            LEFT JOIN tbl_tipo_cliente tc ON tc.id_tipo_cliente = cli.id_tipo_cliente
            WHERE 1=1
        '''
        
        params = []
        count_params = []
        
        # Construir cláusulas WHERE
        where_clauses = []
        
        if filtros.get('executivo_id'):
            where_clauses.append('cli.vendas_central_comm = %s')
            params.append(filtros['executivo_id'])
            count_params.append(filtros['executivo_id'])
        
        if filtros.get('status') is not None:
            where_clauses.append('cli.status = %s')
            params.append(filtros['status'])
            count_params.append(filtros['status'])
        
        if filtros.get('search'):
            where_clauses.append('(unaccent(cli.nome_fantasia) ILIKE unaccent(%s) OR unaccent(cli.razao_social) ILIKE unaccent(%s))')
            search_term = f"%{filtros['search']}%"
            params.extend([search_term, search_term])
            count_params.extend([search_term, search_term])
        
        if filtros.get('categoria_abc'):
            where_clauses.append('cli.categoria_abc = %s')
            params.append(filtros['categoria_abc'])
            count_params.append(filtros['categoria_abc'])
        
        # Filtro por agência: ag.key = true significa "é agência", false/NULL significa "é cliente"
        if filtros.get('agencia') == 'sim':
            # Mostrar apenas agências (ag.key = true)
            where_clauses.append('ag.key = true')
        elif filtros.get('agencia') == 'nao':
            # Mostrar apenas clientes (ag.key = false ou NULL)
            where_clauses.append('(ag.key = false OR ag.key IS NULL)')
        # Se não especificado ou 'todos', não aplica filtro
        
        # Aplicar cláusulas WHERE
        where_sql = ''
        if where_clauses:
            where_sql = ' AND ' + ' AND '.join(where_clauses)
        
        # Query principal com paginação
        query = base_query + where_sql + '''
            GROUP BY cli.id_cliente, cli.nome_fantasia, cli.razao_social, cli.cnpj, 
                     cli.status, cli.categoria_abc, cli.vendas_central_comm, cli.pk_id_tbl_agencia,
                     cli.id_tipo_cliente, tc.display,
                     ag.key, vend.nome_completo, m.cotacoes_mes, m.cotacoes_aprovadas_mes,
                     m.valor_aprovado_mes, m.briefings_mes, m.briefings_aceitos_mes
            ORDER BY cli.nome_fantasia ASC
            LIMIT %s OFFSET %s
        '''
        params.extend([per_page, offset])
        
        # Query de contagem
        count_query = f'''
            SELECT COUNT(*) FROM tbl_cliente cli 
            LEFT JOIN tbl_agencia ag ON ag.id_agencia = cli.pk_id_tbl_agencia
            WHERE 1=1 {where_sql}
        '''
        
        with conn.cursor() as cursor:
            # Obter total
            cursor.execute(count_query, count_params)
            total = cursor.fetchone()['count']
            
            # Obter clientes
            cursor.execute(query, params)
            clientes = cursor.fetchall()
        
        pages = (total + per_page - 1) // per_page  # Ceiling division
        
        return {
            'clientes': clientes,
            'total': total,
            'pages': pages,
            'page': page,
            'per_page': per_page
        }
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter clientes paginados: {e}")
        raise


def recategorizar_clientes_abc():
    """
    Recategoriza todos os clientes conforme regras ABC:
    - A: aprovações >= R$200.000/mês
    - B: ativo (tem briefings/cotações), < R$200k
    - C: sem briefings/cotações no mês
    
    Returns:
        dict: Resumo da recategorização {a: count, b: count, c: count}
    """
    conn = get_db()
    LIMITE_A = 200000  # R$ 200.000,00
    
    try:
        with conn.cursor() as cursor:
            # 1. Calcular métricas do mês para cada cliente
            cursor.execute('''
                WITH metricas AS (
                    SELECT 
                        cli.id_cliente,
                        COALESCE(SUM(cot.valor_total_proposta) FILTER (
                            WHERE cot.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                            AND cot.status = '3'
                        ), 0) AS valor_aprovado_mes,
                        COUNT(DISTINCT cot.id) FILTER (
                            WHERE cot.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                        ) AS cotacoes_mes,
                        COUNT(DISTINCT b.id) FILTER (
                            WHERE b.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                        ) AS briefings_mes
                    FROM tbl_cliente cli
                    LEFT JOIN cadu_cotacoes cot ON cot.client_id = cli.id_cliente
                    LEFT JOIN cadu_briefings b ON b.cliente = cli.nome_fantasia
                    GROUP BY cli.id_cliente
                )
                UPDATE tbl_cliente cli
                SET categoria_abc = CASE
                    WHEN m.valor_aprovado_mes >= %s THEN 'A'
                    WHEN m.cotacoes_mes > 0 OR m.briefings_mes > 0 THEN 'B'
                    ELSE 'C'
                END
                FROM metricas m
                WHERE cli.id_cliente = m.id_cliente
            ''', (LIMITE_A,))
            
            conn.commit()
            
            # 2. Contar resultado
            cursor.execute('''
                SELECT 
                    categoria_abc,
                    COUNT(*) as total
                FROM tbl_cliente
                GROUP BY categoria_abc
                ORDER BY categoria_abc
            ''')
            resultados = cursor.fetchall()
            
            resumo = {'A': 0, 'B': 0, 'C': 0}
            for r in resultados:
                cat = r.get('categoria_abc') or 'C'
                resumo[cat] = r.get('total', 0)
            
            return resumo
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro ao recategorizar clientes: {e}")
        raise


def obter_executivos_comerciais():
    """
    Retorna lista de executivos comerciais (vendedores da CentralComm)
    para uso no filtro de clientes.
    
    Returns:
        list: Lista de dicts com id e nome dos executivos
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT
                    c.id_contato_cliente,
                    c.nome_completo
                FROM tbl_contato_cliente c
                INNER JOIN tbl_cliente cli ON cli.id_cliente = c.pk_id_tbl_cliente
                WHERE cli.nome_fantasia ILIKE '%centralcomm%'
                  AND c.status = true
                ORDER BY c.nome_completo
            ''')
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter executivos: {e}")
        return []


# ==================== CRM PIPELINE - KANBAN ====================

def obter_cotacoes_pipeline(filtros=None):
    """
    Retorna cotações para o pipeline Kanban, agrupadas por status.
    
    Args:
        filtros (dict): Filtros opcionais:
            - executivo_id: ID do responsável comercial
            - cliente_id: ID do cliente
            - periodo_inicio: Data início
            - periodo_fim: Data fim
            - valor_min: Valor mínimo
            - valor_max: Valor máximo
            - mes: Mês de criação (01-12)
            - status: Status específico
    
    Returns:
        dict: Cotações agrupadas por status (colunas do Kanban)
    """
    conn = get_db()
    filtros = filtros or {}
    
    try:
        with conn.cursor() as cursor:
            # Query base com cálculo de dias na fase
            sql = '''
                SELECT 
                    cot.id,
                    cot.numero_cotacao,
                    cot.nome_campanha,
                    cot.status,
                    cot.valor_total_proposta,
                    cot.responsavel_comercial,
                    cot.client_id,
                    cot.briefing_id,
                    cot.created_at,
                    cot.updated_at,
                    cot.proposta_enviada_em,
                    cot.aprovada_em,
                    cot.periodo_inicio,
                    cot.periodo_fim,
                    -- Calcular dias na fase atual
                    EXTRACT(DAY FROM (NOW() - COALESCE(cot.updated_at, cot.created_at)))::INTEGER as dias_na_fase,
                    -- Dados do cliente
                    cli.nome_fantasia as cliente_nome,
                    cli.razao_social as cliente_razao,
                    -- Dados do executivo
                    exec.nome_completo as executivo_nome,
                    -- Verificar se tem briefing
                    CASE WHEN cot.briefing_id IS NOT NULL THEN true ELSE false END as tem_briefing
                FROM cadu_cotacoes cot
                LEFT JOIN tbl_cliente cli ON cli.id_cliente = cot.client_id
                LEFT JOIN tbl_contato_cliente exec ON exec.id_contato_cliente = cot.responsavel_comercial
                WHERE cot.deleted_at IS NULL
            '''
            
            params = []
            
            # Aplicar filtros
            if filtros.get('executivo_id'):
                sql += ' AND cot.responsavel_comercial = %s'
                params.append(int(filtros['executivo_id']))
            
            if filtros.get('cliente_id'):
                sql += ' AND cot.client_id = %s'
                params.append(int(filtros['cliente_id']))
            
            if filtros.get('periodo_inicio'):
                sql += ' AND cot.created_at >= %s'
                params.append(filtros['periodo_inicio'])
            
            if filtros.get('periodo_fim'):
                sql += ' AND cot.created_at <= %s'
                params.append(filtros['periodo_fim'])
            
            if filtros.get('valor_min'):
                sql += ' AND COALESCE(cot.valor_total_proposta, 0) >= %s'
                params.append(float(filtros['valor_min']))
            
            if filtros.get('valor_max'):
                sql += ' AND COALESCE(cot.valor_total_proposta, 0) <= %s'
                params.append(float(filtros['valor_max']))
            
            if filtros.get('mes'):
                sql += ' AND EXTRACT(MONTH FROM cot.created_at) = %s'
                params.append(int(filtros['mes']))
            
            if filtros.get('status'):
                status_filtro = filtros['status']
                # Aceitar tanto 'Em Análise' quanto 'em_analise'
                if status_filtro in ['Em Análise', 'em_analise']:
                    sql += ' AND cot.status IN (%s, %s)'
                    params.extend(['Em Análise', 'em_analise'])
                else:
                    sql += ' AND cot.status = %s'
                    params.append(status_filtro)
            
            # Ordenar por data de atualização (mais recentes primeiro)
            sql += ' ORDER BY cot.updated_at DESC NULLS LAST'
            
            cursor.execute(sql, params)
            cotacoes = cursor.fetchall()
            
            # Agrupar por status (colunas do Kanban)
            colunas = {
                'Rascunho': [],
                'Em Análise': [],
                'Enviada': [],
                'Negociação': [],
                'Aprovada': [],
                'Rejeitada': []
            }
            
            for cot in cotacoes:
                status = cot.get('status') or 'Rascunho'
                # Tratar status antigo 'Pendente' como 'Rascunho'
                if status == 'Pendente':
                    status = 'Rascunho'
                # Tratar 'em_analise' como 'Em Análise'
                if status == 'em_analise':
                    status = 'Em Análise'
                # Ignorar 'Expirada' no pipeline (opcional: pode adicionar coluna)
                if status in colunas:
                    colunas[status].append(cot)
            
            return colunas
            
    except Exception as e:
        current_app.logger.error(f"Erro ao obter cotações pipeline: {e}")
        return {
            'Rascunho': [],
            'Em Análise': [],
            'Enviada': [],
            'Negociação': [],
            'Aprovada': [],
            'Rejeitada': []
        }


def obter_cotacao_detalhes_pipeline(cotacao_id):
    """
    Retorna detalhes completos de uma cotação para o modal do pipeline.
    Inclui itens, briefing, histórico e anexos.
    
    Args:
        cotacao_id (int): ID da cotação
    
    Returns:
        dict: Dados completos da cotação
    """
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            # Dados principais da cotação
            cursor.execute('''
                SELECT 
                    cot.*,
                    cli.nome_fantasia as cliente_nome,
                    cli.razao_social as cliente_razao,
                    exec.nome_completo as executivo_nome,
                    exec.email as executivo_email,
                    contact.nome_completo as contato_nome,
                    contact.email as contato_email
                FROM cadu_cotacoes cot
                LEFT JOIN tbl_cliente cli ON cli.id_cliente = cot.client_id
                LEFT JOIN tbl_contato_cliente exec ON exec.id_contato_cliente = cot.responsavel_comercial
                LEFT JOIN tbl_contato_cliente contact ON contact.id_contato_cliente = cot.client_user_id
                WHERE cot.id = %s AND cot.deleted_at IS NULL
            ''', (cotacao_id,))
            cotacao = cursor.fetchone()
            
            if not cotacao:
                return None
            
            # Itens da cotação
            cursor.execute('''
                SELECT * FROM cadu_cotacao_linhas
                WHERE cotacao_id = %s
                ORDER BY id
            ''', (cotacao_id,))
            cotacao['itens'] = cursor.fetchall()
            
            # Briefing vinculado (se houver)
            if cotacao.get('briefing_id'):
                cursor.execute('''
                    SELECT id, nome, status, created_at
                    FROM cadu_briefings
                    WHERE id = %s
                ''', (cotacao['briefing_id'],))
                cotacao['briefing'] = cursor.fetchone()
            else:
                cotacao['briefing'] = None
            
            # Anexos
            cursor.execute('''
                SELECT * FROM cadu_cotacao_anexos
                WHERE cotacao_id = %s
                ORDER BY created_at DESC
            ''', (cotacao_id,))
            cotacao['anexos'] = cursor.fetchall()
            
            # Audiências vinculadas
            cursor.execute('''
                SELECT 
                    ca.id,
                    ca.cotacao_id,
                    ca.audiencia_id,
                    ca.audiencia_nome as nome,
                    ca.audiencia_publico as publico,
                    ca.audiencia_categoria as categoria,
                    ca.audiencia_subcategoria as subcategoria,
                    ca.cpm_estimado,
                    ca.investimento_sugerido,
                    ca.impressoes_estimadas,
                    ca.incluido_proposta
                FROM cadu_cotacao_audiencias ca
                WHERE ca.cotacao_id = %s AND ca.incluido_proposta = true
                ORDER BY ca.ordem_exibicao, ca.id
            ''', (cotacao_id,))
            cotacao['audiencias'] = cursor.fetchall()
            
            return cotacao
            
    except Exception as e:
        current_app.logger.error(f"Erro ao obter detalhes cotação pipeline: {e}")
        return None


def obter_clientes_para_filtro():
    """
    Retorna lista simplificada de clientes para uso em filtros.
    
    Returns:
        list: Lista de dicts com id e nome dos clientes
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    id_cliente,
                    nome_fantasia,
                    razao_social
                FROM tbl_cliente
                ORDER BY nome_fantasia
            ''')
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter clientes para filtro: {e}")
        return []


# ==================== MÉTRICAS SEMANAIS ====================

def obter_kpis_semanais(semana_inicio, semana_fim, executivo_id=None, cliente_id=None):
    """
    Retorna KPIs agregados para uma semana específica.
    
    Args:
        semana_inicio: Data início da semana (segunda-feira)
        semana_fim: Data fim da semana (domingo)
        executivo_id: Filtro opcional por executivo
        cliente_id: Filtro opcional por cliente
    
    Returns:
        dict: KPIs da semana {cotacoes_criadas, valor_total, aprovadas, taxa_conversao, ticket_medio, ciclo_medio}
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            params = [semana_inicio, semana_fim]
            filtros_sql = ''
            
            if executivo_id:
                filtros_sql += ' AND responsavel_comercial = %s'
                params.append(int(executivo_id))
            
            if cliente_id:
                filtros_sql += ' AND client_id = %s'
                params.append(int(cliente_id))
            
            cursor.execute(f'''
                SELECT 
                    COUNT(*) as cotacoes_criadas,
                    COALESCE(SUM(valor_total_proposta), 0) as valor_total,
                    COUNT(*) FILTER (WHERE status = 'Aprovada') as aprovadas,
                    COUNT(*) FILTER (WHERE status = 'Rejeitada') as rejeitadas,
                    COUNT(*) FILTER (WHERE status = 'Enviada') as enviadas,
                    COUNT(*) FILTER (WHERE status = 'Negociação') as negociacao,
                    ROUND(
                        COUNT(*) FILTER (WHERE status = 'Aprovada')::DECIMAL / 
                        NULLIF(COUNT(*) FILTER (WHERE status IN ('Aprovada', 'Rejeitada')), 0) * 100, 
                        1
                    ) as taxa_conversao,
                    ROUND(
                        COALESCE(SUM(valor_total_proposta) FILTER (WHERE status = 'Aprovada'), 0) / 
                        NULLIF(COUNT(*) FILTER (WHERE status = 'Aprovada'), 0),
                        2
                    ) as ticket_medio,
                    ROUND(
                        AVG(EXTRACT(DAY FROM (aprovada_em - created_at))) FILTER (WHERE status = 'Aprovada' AND aprovada_em IS NOT NULL),
                        1
                    ) as ciclo_medio_dias
                FROM cadu_cotacoes
                WHERE deleted_at IS NULL
                  AND (status IS NULL OR status != 'Rascunho')
                  AND created_at >= %s
                  AND created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
            ''', params)
            
            result = cursor.fetchone()
            return dict(result) if result else {
                'cotacoes_criadas': 0, 'valor_total': 0, 'aprovadas': 0,
                'rejeitadas': 0, 'enviadas': 0, 'negociacao': 0,
                'taxa_conversao': 0, 'ticket_medio': 0, 'ciclo_medio_dias': 0
            }
    except Exception as e:
        current_app.logger.error(f"Erro ao obter KPIs semanais: {e}")
        return {}


def obter_cotacoes_por_executivo_semana(semana_inicio, semana_fim, executivo_id=None, cliente_id=None):
    """
    Retorna cotações agrupadas por executivo para uma semana.
    
    Returns:
        list: Lista de dicts com executivo_id, executivo_nome, total, valor, aprovadas
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            params = [semana_inicio, semana_fim]
            filtros_sql = ''
            
            if executivo_id:
                filtros_sql += ' AND c.responsavel_comercial = %s'
                params.append(int(executivo_id))
            
            if cliente_id:
                filtros_sql += ' AND c.client_id = %s'
                params.append(int(cliente_id))
            
            cursor.execute(f'''
                SELECT 
                    c.responsavel_comercial as executivo_id,
                    COALESCE(e.nome_completo, 'Não atribuído') as executivo_nome,
                    COUNT(*) as total_cotacoes,
                    COALESCE(SUM(c.valor_total_proposta), 0) as valor_total,
                    COUNT(*) FILTER (WHERE c.status = 'Aprovada') as aprovadas,
                    COUNT(*) FILTER (WHERE c.status = 'Rejeitada') as rejeitadas,
                    ROUND(
                        COUNT(*) FILTER (WHERE c.status = 'Aprovada')::DECIMAL / 
                        NULLIF(COUNT(*), 0) * 100, 
                        1
                    ) as taxa_conversao
                FROM cadu_cotacoes c
                LEFT JOIN tbl_contato_cliente e ON e.id_contato_cliente = c.responsavel_comercial
                WHERE c.deleted_at IS NULL
                  AND (c.status IS NULL OR c.status != 'Rascunho')
                  AND c.created_at >= %s
                  AND c.created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
                GROUP BY c.responsavel_comercial, e.nome_completo
                ORDER BY total_cotacoes DESC
            ''', params)
            
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter cotações por executivo: {e}")
        return []


def obter_evolucao_diaria_semana(semana_inicio, semana_fim, executivo_id=None, cliente_id=None):
    """
    Retorna evolução diária de cotações na semana.
    
    Returns:
        list: Lista de dicts com data, total, valor, aprovadas
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            params = [semana_inicio, semana_fim]
            filtros_sql = ''
            
            if executivo_id:
                filtros_sql += ' AND responsavel_comercial = %s'
                params.append(int(executivo_id))
            
            if cliente_id:
                filtros_sql += ' AND client_id = %s'
                params.append(int(cliente_id))
            
            cursor.execute(f'''
                SELECT 
                    DATE(created_at) as data,
                    COUNT(*) as total_cotacoes,
                    COALESCE(SUM(valor_total_proposta), 0) as valor_total,
                    COUNT(*) FILTER (WHERE status = 'Aprovada') as aprovadas,
                    COUNT(*) FILTER (WHERE status = 'Enviada' OR status = 'Negociação') as em_andamento
                FROM cadu_cotacoes
                WHERE deleted_at IS NULL
                  AND (status IS NULL OR status != 'Rascunho')
                  AND created_at >= %s
                  AND created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at)
            ''', params)
            
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter evolução diária: {e}")
        return []


def obter_distribuicao_status_semana(semana_inicio, semana_fim, executivo_id=None, cliente_id=None):
    """
    Retorna distribuição de cotações por status na semana.
    
    Returns:
        list: Lista de dicts com status, total, valor
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            params = [semana_inicio, semana_fim]
            filtros_sql = ''
            
            if executivo_id:
                filtros_sql += ' AND responsavel_comercial = %s'
                params.append(int(executivo_id))
            
            if cliente_id:
                filtros_sql += ' AND client_id = %s'
                params.append(int(cliente_id))
            
            cursor.execute(f'''
                SELECT 
                    COALESCE(status, 'Rascunho') as status,
                    COUNT(*) as total,
                    COALESCE(SUM(valor_total_proposta), 0) as valor
                FROM cadu_cotacoes
                WHERE deleted_at IS NULL
                  AND (status IS NULL OR status != 'Rascunho')
                  AND created_at >= %s
                  AND created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
                GROUP BY status
                ORDER BY total DESC
            ''', params)
            
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter distribuição por status: {e}")
        return []


def obter_comparativo_semanal(semana_inicio, semana_fim, executivo_id=None, cliente_id=None):
    """
    Compara métricas da semana atual com a semana anterior.
    
    Returns:
        dict: {atual: {...}, anterior: {...}, variacao: {...}}
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # Calcula semana anterior
            from datetime import timedelta
            semana_ant_inicio = semana_inicio - timedelta(days=7)
            semana_ant_fim = semana_fim - timedelta(days=7)
            
            params_atual = [semana_inicio, semana_fim]
            params_anterior = [semana_ant_inicio, semana_ant_fim]
            filtros_sql = ''
            
            if executivo_id:
                filtros_sql += ' AND responsavel_comercial = %s'
                params_atual.append(int(executivo_id))
                params_anterior.append(int(executivo_id))
            
            if cliente_id:
                filtros_sql += ' AND client_id = %s'
                params_atual.append(int(cliente_id))
                params_anterior.append(int(cliente_id))
            
            # Semana atual
            cursor.execute(f'''
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(valor_total_proposta), 0) as valor,
                    COUNT(*) FILTER (WHERE status = 'Aprovada') as aprovadas
                FROM cadu_cotacoes
                WHERE deleted_at IS NULL
                  AND (status IS NULL OR status != 'Rascunho')
                  AND created_at >= %s
                  AND created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
            ''', params_atual)
            atual = cursor.fetchone()
            
            # Semana anterior
            cursor.execute(f'''
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(valor_total_proposta), 0) as valor,
                    COUNT(*) FILTER (WHERE status = 'Aprovada') as aprovadas
                FROM cadu_cotacoes
                WHERE deleted_at IS NULL
                  AND (status IS NULL OR status != 'Rascunho')
                  AND created_at >= %s
                  AND created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
            ''', params_anterior)
            anterior = cursor.fetchone()
            
            # Calcular variações
            def calc_var(atual_val, anterior_val):
                if not anterior_val or anterior_val == 0:
                    return 100 if atual_val else 0
                return round(((atual_val - anterior_val) / anterior_val) * 100, 1)
            
            variacao = {
                'total': calc_var(atual['total'], anterior['total']),
                'valor': calc_var(float(atual['valor'] or 0), float(anterior['valor'] or 0)),
                'aprovadas': calc_var(atual['aprovadas'], anterior['aprovadas'])
            }
            
            return {
                'atual': dict(atual),
                'anterior': dict(anterior),
                'variacao': variacao
            }
    except Exception as e:
        current_app.logger.error(f"Erro ao obter comparativo semanal: {e}")
        return {'atual': {}, 'anterior': {}, 'variacao': {}}


def obter_cotacoes_detalhadas_semana(semana_inicio, semana_fim, executivo_id=None, cliente_id=None, busca=None):
    """
    Retorna lista detalhada de cotações da semana para a tabela.
    
    Returns:
        list: Lista de cotações com todos os campos necessários
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            params = [semana_inicio, semana_fim]
            filtros_sql = ''
            
            if executivo_id:
                filtros_sql += ' AND c.responsavel_comercial = %s'
                params.append(int(executivo_id))
            
            if cliente_id:
                filtros_sql += ' AND c.client_id = %s'
                params.append(int(cliente_id))
            
            if busca:
                filtros_sql += ''' AND (
                    c.numero_cotacao ILIKE %s
                    OR cli.nome_fantasia ILIKE %s
                    OR cli.razao_social ILIKE %s
                    OR c.nome_campanha ILIKE %s
                )'''
                termo = f'%{busca}%'
                params.extend([termo, termo, termo, termo])
            
            cursor.execute(f'''
                SELECT 
                    c.id,
                    c.numero_cotacao,
                    c.nome_campanha,
                    c.status,
                    c.valor_total_proposta,
                    c.created_at,
                    c.updated_at,
                    c.aprovada_em,
                    EXTRACT(DAY FROM (NOW() - c.created_at))::INTEGER as dias_aberto,
                    cli.nome_fantasia as cliente_nome,
                    COALESCE(e.nome_completo, 'Não atribuído') as executivo_nome
                FROM cadu_cotacoes c
                LEFT JOIN tbl_cliente cli ON cli.id_cliente = c.client_id
                LEFT JOIN tbl_contato_cliente e ON e.id_contato_cliente = c.responsavel_comercial
                LEFT JOIN tbl_agencia ag ON cli.pk_id_tbl_agencia = ag.id_agencia
                WHERE c.deleted_at IS NULL
                  AND (c.status IS NULL OR c.status != 'Rascunho')
                  AND c.created_at >= %s
                  AND c.created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
                ORDER BY cli.nome_fantasia, ag.display, e.nome_completo, c.nome_campanha
            ''', params)
            
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter cotações detalhadas: {e}")
        return []


def obter_kpis_mensais_por_semana(mes_inicio, mes_fim, executivo_id=None, cliente_id=None):
    """
    Retorna KPIs quebrados por semana dentro do mês.
    Semana 1: dias 1-7, Semana 2: dias 8-14, Semana 3: dias 15-21, Semana 4+: dias 22+
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            params = [mes_inicio, mes_fim]
            filtros_sql = ''
            
            if executivo_id:
                filtros_sql += ' AND responsavel_comercial = %s'
                params.append(int(executivo_id))
            
            if cliente_id:
                filtros_sql += ' AND client_id = %s'
                params.append(int(cliente_id))
            
            cursor.execute(f'''
                SELECT 
                    CASE 
                        WHEN EXTRACT(DAY FROM created_at) <= 7 THEN 'Semana 1'
                        WHEN EXTRACT(DAY FROM created_at) <= 14 THEN 'Semana 2'
                        WHEN EXTRACT(DAY FROM created_at) <= 21 THEN 'Semana 3'
                        ELSE 'Semana 4'
                    END as semana,
                    COUNT(*) as cotacoes_criadas,
                    COALESCE(SUM(valor_total_proposta), 0) as valor_total,
                    COUNT(*) FILTER (WHERE status = 'Aprovada') as aprovadas,
                    COUNT(*) FILTER (WHERE status = 'Rejeitada') as rejeitadas,
                    ROUND(
                        COUNT(*) FILTER (WHERE status = 'Aprovada')::DECIMAL / 
                        NULLIF(COUNT(*) FILTER (WHERE status IN ('Aprovada', 'Rejeitada')), 0) * 100, 
                        1
                    ) as taxa_conversao
                FROM cadu_cotacoes
                WHERE deleted_at IS NULL
                  AND (status IS NULL OR status != 'Rascunho')
                  AND created_at >= %s
                  AND created_at < %s + INTERVAL '1 day'
                  {filtros_sql}
                GROUP BY 
                    CASE 
                        WHEN EXTRACT(DAY FROM created_at) <= 7 THEN 'Semana 1'
                        WHEN EXTRACT(DAY FROM created_at) <= 14 THEN 'Semana 2'
                        WHEN EXTRACT(DAY FROM created_at) <= 21 THEN 'Semana 3'
                        ELSE 'Semana 4'
                    END
                ORDER BY semana
            ''', params)
            
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter KPIs mensais por semana: {e}")
        return []


def obter_novos_clientes_periodo(inicio, fim):
    """Conta novos clientes cadastrados no período."""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM tbl_cliente
                WHERE data_cadastro >= %s
                  AND data_cadastro < %s + INTERVAL '1 day'
            ''', [inicio, fim])
            result = cursor.fetchone()
            return result['total'] if result else 0
    except Exception as e:
        current_app.logger.error(f"Erro ao obter novos clientes: {e}")
        return 0


def obter_novos_contatos_periodo(inicio, fim):
    """Conta novos contatos cadastrados no período."""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM tbl_contato_cliente
                WHERE data_cadastro >= %s
                  AND data_cadastro < %s + INTERVAL '1 day'
            ''', [inicio, fim])
            result = cursor.fetchone()
            return result['total'] if result else 0
    except Exception as e:
        current_app.logger.error(f"Erro ao obter novos contatos: {e}")
        return 0


def obter_executivos_ativos():
    """
    Retorna lista de executivos que têm cotações.
    
    Returns:
        list: Lista de dicts com id e nome dos executivos
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT
                    e.id_contato_cliente as id,
                    e.nome_completo as nome
                FROM tbl_contato_cliente e
                INNER JOIN cadu_cotacoes c ON c.responsavel_comercial = e.id_contato_cliente
                WHERE c.deleted_at IS NULL
                ORDER BY e.nome_completo
            ''')
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Erro ao obter executivos ativos: {e}")
        return []


def obter_cadu_plataformas():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, nome
                FROM cadu_audiencias_plataformas
                ORDER BY ordem
            ''')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


# ==================== CADU PI ====================

def obter_status_pi():
    """Retorna todos os status de PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM cadu_pi_aux_status ORDER BY id')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_sub_status_pi():
    """Retorna todos os sub-status de PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM cadu_pi_sub_status ORDER BY key')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_nota_fiscal_status():
    """Retorna todos os status de nota fiscal"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, descricao FROM cadu_pi_nota_fiscal_status ORDER BY id')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_notas_fiscais_por_pi(id_pi):
    """Retorna todas as notas fiscais de um PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    nf.id,
                    nf.valor,
                    nf.data_emissao,
                    nf.data_pag_prevista as data_pagamento_previsto,
                    nf.data_pag_realizado as data_pagamento_realizado,
                    nf.numero_nota,
                    nf.mes_ref_comp,
                    nf.id_pi,
                    nf.created_at,
                    nf.updated_at,
                    nf.status,
                    nfs.descricao as status_descricao
                FROM cadu_pi_nota_fiscal nf
                LEFT JOIN cadu_pi_nota_fiscal_status nfs ON nf.status = nfs.id
                WHERE nf.id_pi = %s
                ORDER BY nf.created_at DESC
            ''', (id_pi,))
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_nota_fiscal_por_id(id_nota):
    """Retorna uma nota fiscal por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    id,
                    valor,
                    data_emissao,
                    data_pag_prevista as data_pagamento_previsto,
                    data_pag_realizado as data_pagamento_realizado,
                    numero_nota,
                    mes_ref_comp,
                    id_pi,
                    created_at,
                    updated_at,
                    status
                FROM cadu_pi_nota_fiscal
                WHERE id = %s
            ''', (id_nota,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_nota_fiscal(data):
    """Cria uma nova nota fiscal"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi_nota_fiscal (
                    valor, data_emissao, data_pag_prevista, data_pag_realizado,
                    numero_nota, mes_ref_comp, id_pi, status,
                    googled_pi_arq_ass, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    DATE_TRUNC('second', CURRENT_TIMESTAMP),
                    DATE_TRUNC('second', CURRENT_TIMESTAMP)
                ) RETURNING id
            ''', (
                data.get('valor'),
                data.get('data_emissao'),
                data.get('data_pagamento_previsto'),
                data.get('data_pagamento_realizado'),
                data.get('numero_nota'),
                data.get('mes_ref_comp'),
                data.get('id_pi'),
                data.get('status'),
                data.get('googled_pi_arq_ass')
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_nota_fiscal(id_nota, data):
    """Atualiza uma nota fiscal existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi_nota_fiscal
                SET valor = %s,
                    data_emissao = %s,
                    data_pag_prevista = %s,
                    data_pag_realizado = %s,
                    numero_nota = %s,
                    mes_ref_comp = %s,
                    id_pi = %s,
                    status = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
            ''', (
                data.get('valor'),
                data.get('data_emissao'),
                data.get('data_pagamento_previsto'),
                data.get('data_pagamento_realizado'),
                data.get('numero_nota'),
                data.get('mes_ref_comp'),
                data.get('id_pi'),
                data.get('status'),
                id_nota
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_nota_fiscal(id_nota):
    """Exclui uma nota fiscal"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_pi_nota_fiscal WHERE id = %s
            ''', (id_nota,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def obter_notas_fiscais_lista(filtros=None):
    """Retorna notas fiscais com filtros e JOINs para dados do PI/cliente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT
                    nf.id,
                    nf.valor,
                    nf.data_emissao,
                    nf.data_pag_prevista as data_pagamento_previsto,
                    nf.data_pag_realizado as data_pagamento_realizado,
                    nf.numero_nota,
                    nf.mes_ref_comp,
                    nf.id_pi,
                    nf.created_at,
                    nf.updated_at,
                    nf.status,
                    nfs.descricao as status_descricao,
                    p.codigo_pi_cc,
                    p.titulo_pi,
                    cli.nome_fantasia as cliente_nome,
                    cli_ag.nome_fantasia as agencia_nome,
                    rc.nome_completo as resp_comercial_nome
                FROM cadu_pi_nota_fiscal nf
                LEFT JOIN cadu_pi_nota_fiscal_status nfs ON nf.status = nfs.id
                LEFT JOIN cadu_pi p ON nf.id_pi = p.id_pi
                LEFT JOIN tbl_cliente cli ON p.id_cliente = cli.id_cliente
                LEFT JOIN tbl_cliente cli_ag ON p.id_agencia = cli_ag.id_cliente
                LEFT JOIN tbl_contato_cliente rc ON p.id_resp_comercial = rc.id_contato_cliente
                WHERE 1=1
            '''
            params = []

            if filtros:
                if filtros.get('status'):
                    query += ' AND nf.status = %s'
                    params.append(filtros['status'])

                if filtros.get('resp_comercial'):
                    query += ' AND p.id_resp_comercial = %s'
                    params.append(filtros['resp_comercial'])

                if filtros.get('id_cliente'):
                    query += ' AND p.id_cliente = %s'
                    params.append(filtros['id_cliente'])

                if filtros.get('id_agencia'):
                    query += ' AND p.id_agencia = %s'
                    params.append(filtros['id_agencia'])

                if filtros.get('mes_ref_comp'):
                    query += ' AND nf.mes_ref_comp = %s'
                    params.append(filtros['mes_ref_comp'])

                if filtros.get('data_inicio'):
                    query += ' AND nf.data_emissao >= %s'
                    params.append(filtros['data_inicio'])

                if filtros.get('data_fim'):
                    query += ' AND nf.data_emissao <= %s'
                    params.append(filtros['data_fim'])

                if filtros.get('search'):
                    query += ''' AND (
                        nf.numero_nota ILIKE %s
                        OR p.codigo_pi_cc ILIKE %s
                        OR unaccent(cli.nome_fantasia) ILIKE unaccent(%s)
                        OR unaccent(cli_ag.nome_fantasia) ILIKE unaccent(%s)
                    )'''
                    search_term = f"%{filtros['search']}%"
                    params.extend([search_term, search_term, search_term, search_term])

            query += ' ORDER BY nf.created_at DESC'

            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_meses_ref_nf():
    """Retorna valores distintos de mes_ref_comp de notas fiscais"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT mes_ref_comp,
                    CAST(SPLIT_PART(mes_ref_comp, '/', 2) AS INTEGER) as ano,
                    CAST(SPLIT_PART(mes_ref_comp, '/', 1) AS INTEGER) as mes
                FROM cadu_pi_nota_fiscal
                WHERE mes_ref_comp IS NOT NULL AND mes_ref_comp != ''
                GROUP BY mes_ref_comp
                ORDER BY ano DESC, mes DESC
            ''')
            return [r['mes_ref_comp'] for r in cursor.fetchall()]
    except Exception as e:
        conn.rollback()
        raise e


def obter_tipos_pi():
    """Retorna todos os tipos de PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, descricao FROM cadu_pi_tipo ORDER BY id')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_meses_ref_pi(id_sub_status_pi=None):
    """Retorna valores distintos de mes_ref_comp, filtrados por sub_status se informado"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT mes_ref_comp,
                    CAST(SPLIT_PART(mes_ref_comp, '/', 2) AS INTEGER) as ano,
                    CAST(SPLIT_PART(mes_ref_comp, '/', 1) AS INTEGER) as mes
                FROM cadu_pi
                WHERE mes_ref_comp IS NOT NULL AND mes_ref_comp != ''
            '''
            params = []
            if id_sub_status_pi:
                query += ' AND id_sub_status_pi = %s'
                params.append(id_sub_status_pi)
            query += ' GROUP BY mes_ref_comp ORDER BY ano DESC, mes DESC'
            cursor.execute(query, params)
            return [r['mes_ref_comp'] for r in cursor.fetchall()]
    except Exception as e:
        conn.rollback()
        raise e


def obter_cadu_pi_lista(filtros=None):
    """Retorna PIs com filtros opcionais e JOINs para nomes relacionados"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT 
                    p.*,
                    p.vr_bruto_pi as valor_bruto,
                    p.vr_liquido_pi as valor_liquido,
                    p.vr_cms_agencia as comissao_agencia,
                    p.vr_cms_parc_com as comissao_parceiro,
                    p.vr_liquido_pr_pi as valor_liquido_pr,
                    p.vr_platafor_max_pi as valor_plataformas,
                    cli.nome_fantasia as cliente_nome,
                    cli.cnpj as cliente_cnpj,
                    cli_ag.nome_fantasia as agencia_nome,
                    cli_parc.nome_fantasia as parceiro_nome,
                    sp.descricao as status_descricao,
                    ssp.display as sub_status_descricao,
                    rc.nome_completo as resp_comercial_nome,
                    (SELECT COUNT(*) FROM cadu_pi_link_destinos ld WHERE ld.id_pi = p.id_pi) as total_links,
                    (SELECT COUNT(*) FROM cadu_pi_campanha ca WHERE ca.id_pi = p.id_pi) as total_campanhas,
                    nf_sub.nf_id,
                    nf_sub.nf_numero_nota,
                    nf_sub.nf_valor,
                    nf_sub.nf_status,
                    nf_sub.nf_status_descricao
                FROM cadu_pi p
                LEFT JOIN tbl_cliente cli ON p.id_cliente = cli.id_cliente
                LEFT JOIN tbl_cliente cli_ag ON p.id_agencia = cli_ag.id_cliente
                LEFT JOIN tbl_cliente cli_parc ON p."Id_parc_reg" = cli_parc.id_cliente
                LEFT JOIN cadu_pi_aux_status sp ON p.id_status_pi = sp.id
                LEFT JOIN cadu_pi_sub_status ssp ON p.id_sub_status_pi = ssp.key
                LEFT JOIN tbl_contato_cliente rc ON p.id_resp_comercial = rc.id_contato_cliente
                LEFT JOIN LATERAL (
                    SELECT
                        nf.id as nf_id,
                        nf.numero_nota as nf_numero_nota,
                        nf.valor as nf_valor,
                        nf.status as nf_status,
                        nfs.descricao as nf_status_descricao
                    FROM cadu_pi_nota_fiscal nf
                    LEFT JOIN cadu_pi_nota_fiscal_status nfs ON nf.status = nfs.id
                    WHERE nf.id_pi = p.id_pi
                    ORDER BY nf.created_at DESC
                    LIMIT 1
                ) nf_sub ON true
                WHERE 1=1
            '''
            params = []

            if filtros:
                if filtros.get('id_cliente'):
                    query += ' AND p.id_cliente = %s'
                    params.append(filtros['id_cliente'])

                if filtros.get('id_status_pi'):
                    query += ' AND p.id_status_pi = %s'
                    params.append(filtros['id_status_pi'])

                if filtros.get('id_sub_status_pi'):
                    query += ' AND p.id_sub_status_pi = %s'
                    params.append(filtros['id_sub_status_pi'])

                if filtros.get('id_agencia'):
                    query += ' AND p.id_agencia = %s'
                    params.append(filtros['id_agencia'])

                if filtros.get('mes_ref_comp'):
                    query += ' AND p.mes_ref_comp = %s'
                    params.append(filtros['mes_ref_comp'])

                if filtros.get('resp_comercial'):
                    query += ' AND p.id_resp_comercial = %s'
                    params.append(filtros['resp_comercial'])

                if filtros.get('search'):
                    query += ' AND (unaccent(p.titulo_pi) ILIKE unaccent(%s) OR p.codigo_pi_cc ILIKE %s OR p.codigo_pi_ag ILIKE %s OR unaccent(cli.nome_fantasia) ILIKE unaccent(%s) OR unaccent(cli_ag.nome_fantasia) ILIKE unaccent(%s))'
                    search_term = f"%{filtros['search']}%"
                    params.extend([search_term, search_term, search_term, search_term, search_term])

            query += ' ORDER BY p.created_at DESC'

            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_cadu_pi_por_id(id_pi):
    """Retorna um PI pelo ID com JOINs"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    p.*,
                    p."Id_parc_reg" as id_parceiro,
                    p.perc_cms_agencia as perc_comissao_agencia,
                    p.perc_cms_parc_reg as perc_comissao_parceiro,
                    p.vr_bruto_pi as valor_bruto,
                    p.vr_liquido_pi as valor_liquido,
                    p.vr_cms_agencia as comissao_agencia,
                    p.vr_cms_parc_com as comissao_parceiro,
                    p.vr_liquido_pr_pi as valor_liquido_pr,
                    p.vr_platafor_max_pi as valor_plataformas,
                    p.id_cont_cliente_financ as contato_fin_cliente,
                    p.id_cont_cliente_midia as contato_midia_cliente,
                    p.id_cont_agen_financ as contato_fin_agencia,
                    p.id_cont_agen_midia as contato_midia_agencia,
                    p.id_cont_parc_reg_financ as contato_fin_parceiro,
                    p.id_cont_parc_reg_midia as contato_midia_parceiro,
                    p.observacoes_financeiro as obs_financeiro,
                    p.observacoes_operacao as obs_operacao,
                    cli.nome_fantasia as cliente_nome,
                    cli.razao_social as cliente_razao_social,
                    cli_ag.nome_fantasia as agencia_nome,
                    cli_ag.razao_social as agencia_razao_social,
                    cli_parc.nome_fantasia as parceiro_nome,
                    sp.descricao as status_descricao,
                    ssp.display as sub_status_descricao,
                    rc.nome_completo as resp_comercial_nome,
                    rc.email as resp_comercial_email,
                    (SELECT COUNT(*) FROM cadu_pi_link_destinos ld WHERE ld.id_pi = p.id_pi) as total_links
                FROM cadu_pi p
                LEFT JOIN tbl_cliente cli ON p.id_cliente = cli.id_cliente
                LEFT JOIN tbl_cliente cli_ag ON p.id_agencia = cli_ag.id_cliente
                LEFT JOIN tbl_cliente cli_parc ON p."Id_parc_reg" = cli_parc.id_cliente
                LEFT JOIN cadu_pi_aux_status sp ON p.id_status_pi = sp.id
                LEFT JOIN cadu_pi_sub_status ssp ON p.id_sub_status_pi = ssp.key
                LEFT JOIN tbl_contato_cliente rc ON p.id_resp_comercial = rc.id_contato_cliente
                WHERE p.id_pi = %s
            ''', (id_pi,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_cadu_pi(data):
    """Cria um novo PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi (
                    id_cliente, titulo_pi, codigo_pi_cc, id_pi_tipo,
                    pi_tem_agencia, id_agencia, perc_cms_agencia,
                    "Id_parc_reg", perc_cms_parc_reg,
                    vr_bruto_pi, vr_liquido_pi, vr_cms_agencia, vr_cms_parc_com,
                    vr_liquido_pr_pi, vr_platafor_max_pi, total_platafor_max_pi,
                    periodo_inicio, periodo_fim, mes_ref, mes_ref_comp,
                    id_resp_comercial,
                    id_cont_cliente_financ, id_cont_cliente_midia,
                    id_cont_agen_financ, id_cont_agen_midia,
                    id_cont_parc_reg_financ, id_cont_parc_reg_midia,
                    id_status_pi, id_sub_status_pi,
                    observacoes_financeiro, observacoes_operacao,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    DATE_TRUNC('second', CURRENT_TIMESTAMP), DATE_TRUNC('second', CURRENT_TIMESTAMP)
                ) RETURNING id_pi
            ''', (
                data.get('id_cliente'),
                data.get('titulo_pi'),
                data.get('codigo_pi_cc'),
                data.get('id_pi_tipo'),
                data.get('tem_agencia', False),
                data.get('id_agencia'),
                data.get('perc_comissao_agencia'),
                data.get('id_parceiro'),
                data.get('perc_comissao_parceiro'),
                data.get('valor_bruto'),
                data.get('valor_liquido'),
                data.get('comissao_agencia'),
                data.get('comissao_parceiro'),
                data.get('valor_liquido_pr'),
                data.get('valor_plataformas'),
                data.get('valor_plataformas'),
                data.get('periodo_inicio'),
                data.get('periodo_fim'),
                data.get('mes_ref'),
                data.get('mes_ref_comp'),
                data.get('resp_comercial'),
                data.get('contato_fin_cliente'),
                data.get('contato_midia_cliente'),
                data.get('contato_fin_agencia'),
                data.get('contato_midia_agencia'),
                data.get('contato_fin_parceiro'),
                data.get('contato_midia_parceiro'),
                data.get('id_status_pi'),
                data.get('id_sub_status_pi'),
                data.get('obs_financeiro'),
                data.get('obs_operacao'),
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id_pi'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_cadu_pi(id_pi, data):
    """Atualiza um PI existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi SET
                    id_cliente = %s,
                    titulo_pi = %s,
                    codigo_pi_cc = %s,
                    id_pi_tipo = %s,
                    pi_tem_agencia = %s,
                    id_agencia = %s,
                    perc_cms_agencia = %s,
                    "Id_parc_reg" = %s,
                    perc_cms_parc_reg = %s,
                    vr_bruto_pi = %s,
                    vr_liquido_pi = %s,
                    vr_cms_agencia = %s,
                    vr_cms_parc_com = %s,
                    vr_liquido_pr_pi = %s,
                    vr_platafor_max_pi = %s,
                    total_platafor_max_pi = %s,
                    periodo_inicio = %s,
                    periodo_fim = %s,
                    mes_ref = %s,
                    mes_ref_comp = %s,
                    id_resp_comercial = %s,
                    id_cont_cliente_financ = %s,
                    id_cont_cliente_midia = %s,
                    id_cont_agen_financ = %s,
                    id_cont_agen_midia = %s,
                    id_cont_parc_reg_financ = %s,
                    id_cont_parc_reg_midia = %s,
                    id_status_pi = %s,
                    id_sub_status_pi = %s,
                    observacoes_financeiro = %s,
                    observacoes_operacao = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_pi = %s
                RETURNING id_pi
            ''', (
                data.get('id_cliente'),
                data.get('titulo_pi'),
                data.get('codigo_pi_cc'),
                data.get('id_pi_tipo'),
                data.get('tem_agencia', False),
                data.get('id_agencia'),
                data.get('perc_comissao_agencia'),
                data.get('id_parceiro'),
                data.get('perc_comissao_parceiro'),
                data.get('valor_bruto'),
                data.get('valor_liquido'),
                data.get('comissao_agencia'),
                data.get('comissao_parceiro'),
                data.get('valor_liquido_pr'),
                data.get('valor_plataformas'),
                data.get('valor_plataformas'),
                data.get('periodo_inicio'),
                data.get('periodo_fim'),
                data.get('mes_ref'),
                data.get('mes_ref_comp'),
                data.get('resp_comercial'),
                data.get('contato_fin_cliente'),
                data.get('contato_midia_cliente'),
                data.get('contato_fin_agencia'),
                data.get('contato_midia_agencia'),
                data.get('contato_fin_parceiro'),
                data.get('contato_midia_parceiro'),
                data.get('id_status_pi'),
                data.get('id_sub_status_pi'),
                data.get('obs_financeiro'),
                data.get('obs_operacao'),
                id_pi,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_cadu_pi(id_pi):
    """Exclui um PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM cadu_pi WHERE id_pi = %s', (id_pi,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_cadu_pi_gdrive(id_pi, princ, financ, pecas, arq_ass):
    """Atualiza os 4 campos de Google Drive do PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi
                SET googled_pi_princ = %s,
                    googled_pi_financ = %s,
                    googled_pi_pecas = %s,
                    googled_pi_arq_ass = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id_pi = %s
            ''', (princ, financ, pecas, arq_ass, id_pi))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== OBJETIVOS CAMPANHA PI - CRUD ====================

def obter_objetivos_campanha():
    """Retorna todos os objetivos de campanha ordenados por índice"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    id_objetivos_campanha,
                    descricao,
                    indice,
                    id_centralx,
                    cor,
                    status
                FROM cadu_pi_camp_objetivos
                ORDER BY indice
            ''')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_objetivo_campanha_por_id(id_objetivos_campanha):
    """Retorna um objetivo de campanha específico por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    id_objetivos_campanha,
                    descricao,
                    indice,
                    id_centralx,
                    cor,
                    status
                FROM cadu_pi_camp_objetivos
                WHERE id_objetivos_campanha = %s
            ''', (id_objetivos_campanha,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_objetivo_campanha(data):
    """Cria um novo objetivo de campanha"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi_camp_objetivos (descricao, indice, id_centralx, cor, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id_objetivos_campanha
            ''', (
                data.get('descricao'),
                data.get('indice'),
                data.get('id_centralx'),
                data.get('cor'),
                data.get('status', True),
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id_objetivos_campanha'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_objetivo_campanha(id_objetivos_campanha, data):
    """Atualiza um objetivo de campanha existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi_camp_objetivos
                SET descricao = %s,
                    indice = %s,
                    id_centralx = %s,
                    cor = %s,
                    status = %s
                WHERE id_objetivos_campanha = %s
            ''', (
                data.get('descricao'),
                data.get('indice'),
                data.get('id_centralx'),
                data.get('cor'),
                data.get('status', True),
                id_objetivos_campanha,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_objetivo_campanha(id_objetivos_campanha):
    """Exclui um objetivo de campanha"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_pi_camp_objetivos
                WHERE id_objetivos_campanha = %s
            ''', (id_objetivos_campanha,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== PLATAFORMA CAMPANHA PI - CRUD ====================

def obter_plataformas_campanha():
    """Retorna todas as plataformas de campanha ordenadas por índice"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    id_plataforma,
                    descricao,
                    indice,
                    id_centralx,
                    cor,
                    status
                FROM cadu_pi_camp_plataforma
                ORDER BY indice
            ''')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_plataforma_campanha_por_id(id_plataforma):
    """Retorna uma plataforma de campanha específica por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    id_plataforma,
                    descricao,
                    indice,
                    id_centralx,
                    cor,
                    status
                FROM cadu_pi_camp_plataforma
                WHERE id_plataforma = %s
            ''', (id_plataforma,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_plataforma_campanha(data):
    """Cria uma nova plataforma de campanha"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi_camp_plataforma (descricao, indice, id_centralx, cor, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id_plataforma
            ''', (
                data.get('descricao'),
                data.get('indice'),
                data.get('id_centralx'),
                data.get('cor'),
                data.get('status', True),
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id_plataforma'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_plataforma_campanha(id_plataforma, data):
    """Atualiza uma plataforma de campanha existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi_camp_plataforma
                SET descricao = %s,
                    indice = %s,
                    id_centralx = %s,
                    cor = %s,
                    status = %s
                WHERE id_plataforma = %s
            ''', (
                data.get('descricao'),
                data.get('indice'),
                data.get('id_centralx'),
                data.get('cor'),
                data.get('status', True),
                id_plataforma,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_plataforma_campanha(id_plataforma):
    """Exclui uma plataforma de campanha"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_pi_camp_plataforma
                WHERE id_plataforma = %s
            ''', (id_plataforma,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== LINK DESTINOS PI - CRUD ====================

def obter_link_destinos_por_pi(id_pi):
    """Retorna links de destino de um PI específico"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    ld.id_link_destino,
                    ld.id_pi,
                    ld.link,
                    ld.descricao,
                    ld.status,
                    ld.created_at,
                    ld.updated_at,
                    ld.id_cliente,
                    cli.nome_fantasia AS cliente_nome
                FROM cadu_pi_link_destinos ld
                LEFT JOIN tbl_cliente cli ON ld.id_cliente = cli.id_cliente
                WHERE ld.id_pi = %s
                ORDER BY ld.id_link_destino DESC
            ''', (id_pi,))
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_link_destinos():
    """Retorna todos os links de destino com nomes de PI e cliente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    ld.id_link_destino,
                    ld.id_pi,
                    ld.link,
                    ld.descricao,
                    ld.status,
                    ld.created_at,
                    ld.updated_at,
                    ld.id_cliente,
                    cli.nome_fantasia AS cliente_nome
                FROM cadu_pi_link_destinos ld
                LEFT JOIN tbl_cliente cli ON ld.id_cliente = cli.id_cliente
                ORDER BY ld.id_link_destino DESC
            ''')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_link_destino_por_id(id_link_destino):
    """Retorna um link de destino específico por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    ld.id_link_destino,
                    ld.id_pi,
                    ld.link,
                    ld.descricao,
                    ld.status,
                    ld.created_at,
                    ld.updated_at,
                    ld.id_cliente,
                    cli.nome_fantasia AS cliente_nome
                FROM cadu_pi_link_destinos ld
                LEFT JOIN tbl_cliente cli ON ld.id_cliente = cli.id_cliente
                WHERE ld.id_link_destino = %s
            ''', (id_link_destino,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_link_destino(data):
    """Cria um novo link de destino"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi_link_destinos
                    (id_pi, link, descricao, status, created_at, updated_at, id_cliente)
                VALUES (%s, %s, %s, %s, DATE_TRUNC('second', CURRENT_TIMESTAMP), DATE_TRUNC('second', CURRENT_TIMESTAMP), %s)
                RETURNING id_link_destino
            ''', (
                data.get('id_pi'),
                data.get('link'),
                data.get('descricao'),
                data.get('status', True),
                data.get('id_cliente'),
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id_link_destino'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_link_destino(id_link_destino, data):
    """Atualiza um link de destino existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi_link_destinos
                SET id_pi = %s,
                    link = %s,
                    descricao = %s,
                    status = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP),
                    id_cliente = %s
                WHERE id_link_destino = %s
            ''', (
                data.get('id_pi'),
                data.get('link'),
                data.get('descricao'),
                data.get('status', True),
                data.get('id_cliente'),
                id_link_destino,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_link_destino(id_link_destino):
    """Exclui um link de destino"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_pi_link_destinos
                WHERE id_link_destino = %s
            ''', (id_link_destino,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== STATUS CAMPANHA PI - CRUD ====================

def obter_status_campanha():
    """Retorna todos os status de campanha ordenados por descrição"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, descricao
                FROM cadu_pi_camp_status
                ORDER BY descricao
            ''')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_criativos_validados_campanha():
    """Retorna todos os criativos validados ordenados por descrição"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, descricao FROM cadu_pi_camp_criativos_validados ORDER BY descricao')
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_status_campanha_por_id(id_status):
    """Retorna um status de campanha específico por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, descricao
                FROM cadu_pi_camp_status
                WHERE id = %s
            ''', (id_status,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_status_campanha(data):
    """Cria um novo status de campanha"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi_camp_status (id, descricao)
                VALUES (%s, %s)
                RETURNING id
            ''', (
                data.get('id'),
                data.get('descricao'),
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_status_campanha(id_status, data):
    """Atualiza um status de campanha existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi_camp_status
                SET descricao = %s
                WHERE id = %s
            ''', (
                data.get('descricao'),
                id_status,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_status_campanha(id_status):
    """Exclui um status de campanha"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_pi_camp_status
                WHERE id = %s
            ''', (id_status,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== CAMPANHA PI - CRUD ====================

def obter_campanhas_pi(filtros=None):
    """Retorna campanhas PI com JOINs para nomes relacionados"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT
                    c.id_campanha,
                    c.id_pi,
                    c.id_cliente,
                    c.link_dash,
                    c.mes_ref,
                    c.mes_ref_comp,
                    c.nome_campanha,
                    c.obj_contratados,
                    c.id_centralx,
                    c.created_at,
                    c.updated_at,
                    c.under,
                    c.id_objetivos_campanha,
                    c.periodo_inicio,
                    c.periodo_fim,
                    c.id_status,
                    c.totalizador_atingido,
                    c.totalizador_gasto,
                    c.valor_plataforma,
                    c.valor_total_plataforma,
                    c.id_plataforma,
                    c.id_criativos_validados,
                    cli.nome_fantasia AS cliente_nome,
                    obj.descricao AS objetivo_nome,
                    st.descricao AS status_nome,
                    plt.descricao AS plataforma_nome,
                    cv.descricao AS criativos_validados_nome,
                    pi.codigo_pi_cc AS codigo_pi,
                    pi.titulo_pi,
                    pi.googled_pi_princ,
                    vend.nome_completo AS executivo_nome,
                    pi.vr_liquido_pi AS valor_liquido_pi,
                    pi.vr_platafor_max_pi AS valor_plataformas_pi,
                    (SELECT COUNT(*) FROM cadu_pi_camp_diarios d WHERE d.id_campanha = c.id_campanha) AS qtd_diarios
                FROM cadu_pi_campanha c
                LEFT JOIN tbl_cliente cli ON c.id_cliente = cli.id_cliente
                LEFT JOIN cadu_pi_camp_objetivos obj ON c.id_objetivos_campanha = obj.id_objetivos_campanha
                LEFT JOIN cadu_pi_camp_status st ON c.id_status = st.id
                LEFT JOIN cadu_pi_camp_plataforma plt ON c.id_plataforma = plt.id_plataforma
                LEFT JOIN cadu_pi_camp_criativos_validados cv ON c.id_criativos_validados = cv.id
                LEFT JOIN cadu_pi pi ON c.id_pi = pi.id_pi
                LEFT JOIN tbl_contato_cliente vend ON cli.vendas_central_comm = vend.id_contato_cliente
                WHERE 1=1
            '''
            params = []

            if filtros:
                if filtros.get('id_cliente'):
                    query += ' AND c.id_cliente = %s'
                    params.append(filtros['id_cliente'])
                if filtros.get('id_status'):
                    query += ' AND c.id_status = %s'
                    params.append(filtros['id_status'])
                if filtros.get('id_plataforma'):
                    query += ' AND c.id_plataforma = %s'
                    params.append(filtros['id_plataforma'])
                if filtros.get('id_pi'):
                    query += ' AND c.id_pi = %s'
                    params.append(filtros['id_pi'])
                if filtros.get('mes_ref_comp'):
                    query += ' AND c.mes_ref_comp = %s'
                    params.append(filtros['mes_ref_comp'])
                if filtros.get('resp_comercial'):
                    query += ' AND cli.vendas_central_comm = %s'
                    params.append(filtros['resp_comercial'])
                if filtros.get('id_sub_status_pi'):
                    query += ' AND pi.id_sub_status_pi = %s'
                    params.append(filtros['id_sub_status_pi'])

            query += ' ORDER BY c.mes_ref_comp DESC, c.id_campanha DESC'
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_campanha_pi_por_id(id_campanha):
    """Retorna uma campanha PI específica por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    c.id_campanha,
                    c.id_pi,
                    c.id_cliente,
                    c.link_dash,
                    c.mes_ref,
                    c.mes_ref_comp,
                    c.nome_campanha,
                    c.obj_contratados,
                    c.id_centralx,
                    c.created_at,
                    c.updated_at,
                    c.under,
                    c.id_objetivos_campanha,
                    c.periodo_inicio,
                    c.periodo_fim,
                    c.id_status,
                    c.totalizador_atingido,
                    c.totalizador_gasto,
                    c.valor_plataforma,
                    c.valor_total_plataforma,
                    c.id_plataforma,
                    c.id_criativos_validados,
                    cli.nome_fantasia AS cliente_nome,
                    obj.descricao AS objetivo_nome,
                    st.descricao AS status_nome,
                    plt.descricao AS plataforma_nome,
                    pi.codigo_pi_cc AS codigo_pi
                FROM cadu_pi_campanha c
                LEFT JOIN tbl_cliente cli ON c.id_cliente = cli.id_cliente
                LEFT JOIN cadu_pi_camp_objetivos obj ON c.id_objetivos_campanha = obj.id_objetivos_campanha
                LEFT JOIN cadu_pi_camp_status st ON c.id_status = st.id
                LEFT JOIN cadu_pi_camp_plataforma plt ON c.id_plataforma = plt.id_plataforma
                LEFT JOIN cadu_pi pi ON c.id_pi = pi.id_pi
                WHERE c.id_campanha = %s
            ''', (id_campanha,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_campanha_pi(data):
    """Cria uma nova campanha PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi_campanha (
                    id_pi, id_cliente, link_dash, mes_ref, mes_ref_comp,
                    nome_campanha, obj_contratados, id_centralx,
                    created_at, updated_at, under, id_objetivos_campanha,
                    periodo_inicio, periodo_fim, id_status,
                    totalizador_atingido, totalizador_gasto,
                    valor_plataforma, id_plataforma,
                    id_criativos_validados
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    DATE_TRUNC('second', CURRENT_TIMESTAMP), DATE_TRUNC('second', CURRENT_TIMESTAMP), %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s
                )
                RETURNING id_campanha
            ''', (
                data.get('id_pi'),
                data.get('id_cliente'),
                data.get('link_dash'),
                data.get('mes_ref'),
                data.get('mes_ref_comp'),
                data.get('nome_campanha'),
                data.get('obj_contratados'),
                data.get('id_centralx'),
                data.get('under', False),
                data.get('id_objetivos_campanha'),
                data.get('periodo_inicio'),
                data.get('periodo_fim'),
                data.get('id_status'),
                data.get('totalizador_atingido'),
                data.get('totalizador_gasto'),
                data.get('valor_plataforma'),
                data.get('id_plataforma'),
                data.get('id_criativos_validados'),
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id_campanha'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def obter_pi_valores_plataforma(id_pi):
    """Retorna vr_liquido_pi e total_platafor_max_pi de um PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT vr_liquido_pi, total_platafor_max_pi FROM cadu_pi WHERE id_pi = %s',
                (id_pi,)
            )
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_pi_valores_plataforma(id_pi, vr_liquido_pi, total_platafor_max_pi):
    """Atualiza vr_liquido_pi e total_platafor_max_pi do PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi
                SET vr_liquido_pi = %s,
                    total_platafor_max_pi = %s
                WHERE id_pi = %s
            ''', (vr_liquido_pi, total_platafor_max_pi, id_pi))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_campanha_pi(id_campanha, data):
    """Atualiza uma campanha PI existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi_campanha
                SET id_pi = %s,
                    id_cliente = %s,
                    link_dash = %s,
                    mes_ref = %s,
                    mes_ref_comp = %s,
                    nome_campanha = %s,
                    obj_contratados = %s,
                    id_centralx = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP),
                    under = %s,
                    id_objetivos_campanha = %s,
                    periodo_inicio = %s,
                    periodo_fim = %s,
                    id_status = %s,
                    totalizador_atingido = %s,
                    totalizador_gasto = %s,
                    valor_plataforma = %s,
                    id_plataforma = %s,
                    id_criativos_validados = %s
                WHERE id_campanha = %s
            ''', (
                data.get('id_pi'),
                data.get('id_cliente'),
                data.get('link_dash'),
                data.get('mes_ref'),
                data.get('mes_ref_comp'),
                data.get('nome_campanha'),
                data.get('obj_contratados'),
                data.get('id_centralx'),
                data.get('under', False),
                data.get('id_objetivos_campanha'),
                data.get('periodo_inicio'),
                data.get('periodo_fim'),
                data.get('id_status'),
                data.get('totalizador_atingido'),
                data.get('totalizador_gasto'),
                data.get('valor_plataforma'),
                data.get('id_plataforma'),
                data.get('id_criativos_validados'),
                id_campanha,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_campanha_pi(id_campanha):
    """Exclui uma campanha PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_pi_campanha
                WHERE id_campanha = %s
            ''', (id_campanha,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def obter_meses_ref_campanha_pi():
    """Retorna valores distintos de mes_ref_comp das campanhas PI ordenados desc"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT mes_ref_comp,
                    CAST(SPLIT_PART(mes_ref_comp, '/', 2) AS INTEGER) as ano,
                    CAST(SPLIT_PART(mes_ref_comp, '/', 1) AS INTEGER) as mes
                FROM cadu_pi_campanha
                WHERE mes_ref_comp IS NOT NULL
                  AND mes_ref_comp != ''
                  AND mes_ref_comp LIKE '%%/%%'
                GROUP BY mes_ref_comp
                ORDER BY ano DESC, mes DESC
            ''')
            return [r['mes_ref_comp'] for r in cursor.fetchall()]
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_campanhas_massa(updates):
    """Atualiza totalizador_atingido e totalizador_gasto em batch.
    updates: list of dicts com id_campanha, totalizador_atingido, totalizador_gasto"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            for u in updates:
                cursor.execute('''
                    UPDATE cadu_pi_campanha
                    SET totalizador_atingido = %s,
                        totalizador_gasto = %s,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id_campanha = %s
                ''', (u.get('totalizador_atingido'), u.get('totalizador_gasto'), u['id_campanha']))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        raise e


def obter_diarios_campanha_chart(id_campanha):
    """Retorna diários formatados para chart (atingido e gasto ao longo do tempo)"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT data_evento, atingido, gasto
                FROM cadu_pi_camp_diarios
                WHERE id_campanha = %s
                ORDER BY data_evento ASC
            ''', (id_campanha,))
            rows = cursor.fetchall()
            labels = []
            atingido_data = []
            gasto_data = []
            def _parse_varchar_num(val):
                if not val:
                    return 0
                s = str(val).replace('R$', '').strip().replace('.', '').replace(',', '.')
                try:
                    return float(s)
                except (ValueError, TypeError):
                    return 0

            for r in rows:
                labels.append(r['data_evento'].strftime('%d/%m') if r['data_evento'] else '')
                atingido_data.append(_parse_varchar_num(r['atingido']))
                gasto_data.append(_parse_varchar_num(r['gasto']))
            return {'labels': labels, 'atingido': atingido_data, 'gasto': gasto_data}
    except Exception as e:
        conn.rollback()
        raise e


# ==================== DIÁRIOS DE CAMPANHA PI ====================


def obter_diarios_campanha(id_campanha):
    """Retorna diários de uma campanha PI ordenados por data_evento DESC"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, id_pi, id_campanha, atingido, gasto,
                       dif_atingido, dif_gasto, data_evento,
                       created_at, updated_at
                FROM cadu_pi_camp_diarios
                WHERE id_campanha = %s
                ORDER BY data_evento DESC
            ''', (id_campanha,))
            return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        raise e


def obter_diario_por_id(id_diario):
    """Retorna um diário por ID"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, id_pi, id_campanha, atingido, gasto,
                       dif_atingido, dif_gasto, data_evento,
                       created_at, updated_at
                FROM cadu_pi_camp_diarios
                WHERE id = %s
            ''', (id_diario,))
            return cursor.fetchone()
    except Exception as e:
        conn.rollback()
        raise e


def criar_diario_campanha(data):
    """Cria um novo diário de campanha PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cadu_pi_camp_diarios (
                    id_pi, id_campanha, atingido, gasto,
                    dif_atingido, dif_gasto, data_evento, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, DATE_TRUNC('second', CURRENT_TIMESTAMP))
                RETURNING id
            ''', (
                data.get('id_pi'),
                data.get('id_campanha'),
                data.get('atingido'),
                data.get('gasto'),
                data.get('dif_atingido'),
                data.get('dif_gasto'),
                data.get('data_evento'),
            ))
            result = cursor.fetchone()
            conn.commit()
            return result['id'] if result else None
    except Exception as e:
        conn.rollback()
        raise e


def atualizar_diario_campanha(id_diario, data):
    """Atualiza um diário de campanha PI existente"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cadu_pi_camp_diarios
                SET atingido = %s,
                    gasto = %s,
                    dif_atingido = %s,
                    dif_gasto = %s,
                    data_evento = %s,
                    updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                WHERE id = %s
            ''', (
                data.get('atingido'),
                data.get('gasto'),
                data.get('dif_atingido'),
                data.get('dif_gasto'),
                data.get('data_evento'),
                id_diario,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


def excluir_diario_campanha(id_diario):
    """Exclui um diário de campanha PI"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cadu_pi_camp_diarios
                WHERE id = %s
            ''', (id_diario,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e


# ==================== DASHBOARD INÍCIO ====================

def get_dashboard_carteira_clientes(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    COALESCE(vend.nome_completo, 'Sem Executivo') AS executivo,
                    COUNT(cli.id_cliente) AS total_clientes,
                    COUNT(cli.id_cliente) FILTER (WHERE cli.status = true) AS clientes_ativos
                FROM tbl_cliente cli
                LEFT JOIN tbl_contato_cliente vend ON cli.vendas_central_comm = vend.id_contato_cliente
                GROUP BY COALESCE(vend.nome_completo, 'Sem Executivo')
                ORDER BY total_clientes DESC
            ''')
            por_executivo = cursor.fetchall()

            cursor.execute('''
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = true) AS ativos,
                    COUNT(*) FILTER (WHERE status = false) AS inativos,
                    COUNT(*) FILTER (WHERE data_cadastro >= CURRENT_DATE - %s * INTERVAL '1 day') AS novos_periodo
                FROM tbl_cliente
            ''', (days,))
            resumo = cursor.fetchone()

            cursor.execute('''
                SELECT
                    DATE_TRUNC('week', data_cadastro)::date AS semana,
                    COUNT(*) AS novos
                FROM tbl_cliente
                WHERE data_cadastro >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY DATE_TRUNC('week', data_cadastro)
                ORDER BY semana
            ''', (days,))
            evolucao = cursor.fetchall()

            return {
                'por_executivo': por_executivo,
                'resumo': resumo,
                'evolucao': evolucao
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard carteira clientes: {e}")
        return {'por_executivo': [], 'resumo': {}, 'evolucao': []}


def get_dashboard_cotacoes_status(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    COALESCE(c.status, 'Sem Status') AS status_nome,
                    COUNT(*) AS total,
                    COALESCE(SUM(c.valor_total_proposta), 0) AS valor_total
                FROM cadu_cotacoes c
                WHERE c.deleted_at IS NULL
                  AND c.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY COALESCE(c.status, 'Sem Status')
                ORDER BY total DESC
            ''', (days,))
            por_status = cursor.fetchall()

            cursor.execute('''
                SELECT
                    DATE_TRUNC('week', c.created_at)::date AS semana,
                    COALESCE(c.status, 'Sem Status') AS status_nome,
                    COUNT(*) AS total
                FROM cadu_cotacoes c
                WHERE c.deleted_at IS NULL
                  AND c.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY DATE_TRUNC('week', c.created_at), COALESCE(c.status, 'Sem Status')
                ORDER BY semana
            ''', (days,))
            evolucao = cursor.fetchall()

            cursor.execute('''
                SELECT COUNT(*) AS total
                FROM cadu_cotacoes
                WHERE deleted_at IS NULL
                  AND created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
            ''', (days,))
            resumo = cursor.fetchone()

            return {
                'por_status': por_status,
                'evolucao': evolucao,
                'total': resumo.get('total', 0) if resumo else 0
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard cotacoes: {e}")
        return {'por_status': [], 'evolucao': [], 'total': 0}


def get_dashboard_acessos_cadu(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            dau = mau = wau = sessions_today = 0
            avg_duration = 0
            try:
                cursor.execute('SELECT * FROM v_analytics_dau_mau LIMIT 1')
                row = cursor.fetchone()
                if row:
                    dau = row.get('dau', 0) or 0
                    wau = row.get('wau', 0) or 0
                    mau = row.get('mau', 0) or 0
                    sessions_today = row.get('sessions_today', 0) or 0
                    avg_duration = float(row.get('avg_session_duration_today', 0) or 0)
            except Exception:
                pass

            sessoes_diarias = []
            try:
                cursor.execute('''
                    SELECT * FROM v_analytics_sessions_daily
                    WHERE date >= CURRENT_DATE - %s * INTERVAL '1 day'
                    ORDER BY date
                ''', (days,))
                sessoes_diarias = cursor.fetchall()
            except Exception:
                pass

            return {
                'dau': dau,
                'wau': wau,
                'mau': mau,
                'sessions_today': sessions_today,
                'avg_duration': avg_duration,
                'sessoes_diarias': sessoes_diarias
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard acessos: {e}")
        return {'dau': 0, 'wau': 0, 'mau': 0, 'sessions_today': 0, 'avg_duration': 0, 'sessoes_diarias': []}


def get_dashboard_pis_por_mes(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    COALESCE(p.mes_ref_comp, TO_CHAR(p.created_at, 'MM/YY')) AS mes,
                    COALESCE(sp.descricao, 'Sem Status') AS status_nome,
                    COUNT(*) AS total
                FROM cadu_pi p
                LEFT JOIN cadu_pi_aux_status sp ON p.id_status_pi = sp.id
                WHERE p.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY COALESCE(p.mes_ref_comp, TO_CHAR(p.created_at, 'MM/YY')),
                         COALESCE(sp.descricao, 'Sem Status')
                ORDER BY mes
            ''', (days,))
            por_mes = cursor.fetchall()

            cursor.execute('''
                WITH parsed AS (
                    SELECT
                        NULLIF(REGEXP_REPLACE(vr_liquido_pi, '[^0-9.,]', '', 'g'), '') AS liq_raw,
                        NULLIF(REGEXP_REPLACE(vr_bruto_pi, '[^0-9.,]', '', 'g'), '') AS bruto_raw
                    FROM cadu_pi
                    WHERE created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                )
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(
                        CASE
                            WHEN liq_raw ~ '^[0-9]+,[0-9]+$' THEN REPLACE(liq_raw, ',', '.')::numeric
                            WHEN liq_raw ~ '^[0-9.]+,[0-9]+$' THEN REPLACE(REPLACE(liq_raw, '.', ''), ',', '.')::numeric
                            WHEN liq_raw ~ '^[0-9.]+$' THEN liq_raw::numeric
                            ELSE 0
                        END
                    ), 0) AS valor_total,
                    COALESCE(SUM(
                        CASE
                            WHEN bruto_raw ~ '^[0-9]+,[0-9]+$' THEN REPLACE(bruto_raw, ',', '.')::numeric
                            WHEN bruto_raw ~ '^[0-9.]+,[0-9]+$' THEN REPLACE(REPLACE(bruto_raw, '.', ''), ',', '.')::numeric
                            WHEN bruto_raw ~ '^[0-9.]+$' THEN bruto_raw::numeric
                            ELSE 0
                        END
                    ), 0) AS valor_bruto
                FROM parsed
            ''', (days,))
            resumo = cursor.fetchone()

            return {
                'por_mes': por_mes,
                'resumo': resumo or {'total': 0, 'valor_total': 0, 'valor_bruto': 0}
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard PIs: {e}")
        return {'por_mes': [], 'resumo': {'total': 0, 'valor_total': 0, 'valor_bruto': 0}}


def get_dashboard_campanhas(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    COALESCE(st.descricao, 'Sem Status') AS status_nome,
                    COUNT(*) AS total,
                    COALESCE(SUM(c.valor_plataforma), 0) AS valor_plataforma,
                    COALESCE(SUM(c.totalizador_gasto), 0) AS gasto_total,
                    COALESCE(SUM(c.totalizador_atingido), 0) AS atingido_total
                FROM cadu_pi_campanha c
                LEFT JOIN cadu_pi_camp_status st ON c.id_status = st.id
                WHERE c.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY COALESCE(st.descricao, 'Sem Status')
                ORDER BY total DESC
            ''', (days,))
            por_status = cursor.fetchall()

            cursor.execute('''
                SELECT
                    COUNT(*) AS total_campanhas,
                    COALESCE(SUM(c.valor_plataforma), 0) AS faturamento,
                    COALESCE(SUM(c.totalizador_gasto), 0) AS gasto,
                    COALESCE(SUM(c.totalizador_atingido), 0) AS atingido
                FROM cadu_pi_campanha c
                WHERE c.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
            ''', (days,))
            resumo = cursor.fetchone()

            return {
                'por_status': por_status,
                'resumo': resumo or {'total_campanhas': 0, 'faturamento': 0, 'gasto': 0, 'atingido': 0}
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard campanhas: {e}")
        return {'por_status': [], 'resumo': {'total_campanhas': 0, 'faturamento': 0, 'gasto': 0, 'atingido': 0}}


def get_dashboard_audiencias(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            top_audiencias = []
            evolucao = []
            total_acessos = 0
            try:
                cursor.execute('''
                    SELECT
                        COALESCE(a.nome, e.metadata->>'audiencia_nome') AS audiencia_nome,
                        COUNT(*) AS total_views,
                        COUNT(DISTINCT e.user_id) AS unique_users
                    FROM cadu_analytics_events e
                    LEFT JOIN cadu_audiencias a ON (e.metadata->>'audiencia_id')::int = a.id
                    WHERE e.event_type = 'audiencia_viewed'
                      AND e.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                    GROUP BY COALESCE(a.nome, e.metadata->>'audiencia_nome')
                    ORDER BY total_views DESC
                    LIMIT 10
                ''', (days,))
                top_audiencias = cursor.fetchall()

                cursor.execute('''
                    SELECT
                        DATE_TRUNC('week', e.created_at)::date AS semana,
                        COUNT(*) AS total_views
                    FROM cadu_analytics_events e
                    WHERE e.event_type = 'audiencia_viewed'
                      AND e.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                    GROUP BY DATE_TRUNC('week', e.created_at)
                    ORDER BY semana
                ''', (days,))
                evolucao = cursor.fetchall()

                cursor.execute('''
                    SELECT COUNT(*) AS total
                    FROM cadu_analytics_events
                    WHERE event_type = 'audiencia_viewed'
                      AND created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                ''', (days,))
                r = cursor.fetchone()
                total_acessos = r.get('total', 0) if r else 0
            except Exception:
                pass

            top_canais = []
            try:
                cursor.execute('''
                    SELECT
                        COALESCE(p.nome, 'Desconhecido') AS canal,
                        COUNT(a.id) AS total_audiencias,
                        COALESCE(SUM(a.cpm_venda), 0) AS cpm_total
                    FROM cadu_audiencias a
                    LEFT JOIN cadu_audiencias_plataformas p ON a.plataforma_id = p.id
                    WHERE a.is_active = true
                    GROUP BY COALESCE(p.nome, 'Desconhecido')
                    ORDER BY total_audiencias DESC
                    LIMIT 10
                ''')
                top_canais = cursor.fetchall()
            except Exception:
                pass

            return {
                'top_audiencias': top_audiencias,
                'top_canais': top_canais,
                'evolucao': evolucao,
                'total_acessos': total_acessos
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard audiencias: {e}")
        return {'top_audiencias': [], 'top_canais': [], 'evolucao': [], 'total_acessos': 0}


def get_dashboard_briefings_por_cliente(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    cli.nome_fantasia AS cliente,
                    COUNT(b.id) AS total_briefings,
                    COUNT(b.id) FILTER (WHERE b.status = 'enviado') AS enviados,
                    COUNT(b.id) FILTER (WHERE b.status = 'rascunho') AS rascunhos
                FROM cadu_briefings b
                INNER JOIN tbl_cliente cli ON b.id_cliente = cli.id_cliente
                WHERE b.deleted_at IS NULL
                  AND b.created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY cli.nome_fantasia
                ORDER BY total_briefings DESC
                LIMIT 10
            ''', (days,))
            top_clientes = cursor.fetchall()

            cursor.execute('''
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'enviado') AS enviados,
                    COUNT(*) FILTER (WHERE status = 'rascunho') AS rascunhos,
                    COUNT(*) FILTER (WHERE enviado_para_centralcomm = true) AS enviados_centralcomm
                FROM cadu_briefings
                WHERE deleted_at IS NULL
                  AND created_at >= CURRENT_DATE - %s * INTERVAL '1 day'
            ''', (days,))
            resumo = cursor.fetchone()

            return {
                'top_clientes': top_clientes,
                'resumo': resumo or {'total': 0, 'enviados': 0, 'rascunhos': 0, 'enviados_centralcomm': 0}
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard briefings: {e}")
        return {'top_clientes': [], 'resumo': {'total': 0, 'enviados': 0, 'rascunhos': 0, 'enviados_centralcomm': 0}}


def get_dashboard_leads(days=90):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT
                    COALESCE(vend.nome_completo, 'Sem Executivo') AS executivo,
                    COUNT(i.id_interesse) AS total_leads,
                    COUNT(i.id_interesse) FILTER (WHERE i.notificado = true) AS notificados,
                    COUNT(i.id_interesse) FILTER (WHERE i.notificado = false) AS pendentes
                FROM tbl_interesse_produto i
                INNER JOIN tbl_contato_cliente c ON i.fk_id_contato_cliente = c.id_contato_cliente
                LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                LEFT JOIN tbl_contato_cliente vend ON cli.vendas_central_comm = vend.id_contato_cliente
                WHERE i.data_registro >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY COALESCE(vend.nome_completo, 'Sem Executivo')
                ORDER BY total_leads DESC
            ''', (days,))
            por_executivo = cursor.fetchall()

            cursor.execute('''
                SELECT
                    tipo_produto,
                    COUNT(*) AS total
                FROM tbl_interesse_produto
                WHERE data_registro >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY tipo_produto
                ORDER BY total DESC
            ''', (days,))
            por_origem = cursor.fetchall()

            cursor.execute('''
                SELECT
                    DATE_TRUNC('week', data_registro)::date AS semana,
                    COUNT(*) AS total
                FROM tbl_interesse_produto
                WHERE data_registro >= CURRENT_DATE - %s * INTERVAL '1 day'
                GROUP BY DATE_TRUNC('week', data_registro)
                ORDER BY semana
            ''', (days,))
            evolucao = cursor.fetchall()

            cursor.execute('''
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE notificado = true) AS notificados,
                    COUNT(*) FILTER (WHERE notificado = false) AS pendentes
                FROM tbl_interesse_produto
                WHERE data_registro >= CURRENT_DATE - %s * INTERVAL '1 day'
            ''', (days,))
            resumo = cursor.fetchone()

            return {
                'por_executivo': por_executivo,
                'por_origem': por_origem,
                'evolucao': evolucao,
                'resumo': resumo or {'total': 0, 'notificados': 0, 'pendentes': 0}
            }
    except Exception as e:
        current_app.logger.error(f"Erro dashboard leads: {e}")
        return {'por_executivo': [], 'por_origem': [], 'evolucao': [], 'resumo': {'total': 0, 'notificados': 0, 'pendentes': 0}}
