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
from datetime import datetime, timedelta
from typing import List, Optional
import re


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
            # Adicionar campos necessários
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

def gerar_senha_md5(senha):
    """Gera hash MD5 da senha"""
    return hashlib.md5(senha.encode()).hexdigest()


def verificar_senha_md5(senha, senha_md5):
    """Verifica se senha bate com hash MD5"""
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
            
        # Verificar se senha está correta
        if not verificar_senha_md5(password, user['senha']):
            return None
            
        # Verificar se usuário está ativo
        if not user['status']:
            current_app.logger.warning(
                f"Tentativa de login negada - Usuário inativo: {user['nome_completo']} "
                f"(Email: {email})"
            )
            return {'inactive_user': True}
        
        # ==================== RESTRIÇÃO CENTRALCOMM ====================
        # APENAS clientes CENTRALCOMM podem acessar
        if not user['razao_social'] or user['razao_social'].upper() != 'CENTRALCOMM':
            current_app.logger.warning(
                f"Tentativa de login negada - Cliente não autorizado: {user['razao_social']} "
                f"(Email: {email})"
            )
            return None  # Retorna None como se as credenciais estivessem erradas
        # ===============================================================
        
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
                c.data_cadastro,
                c.data_modificacao,
                c.cohorts,
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
            LEFT JOIN tbl_setor s ON s.id_setor = car.pk_id_aux_setor
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
    """Retorna todos os contatos de um cliente específico"""
    conn = get_db()

    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                id_contato_cliente,
                email,
                nome_completo,
                telefone,
                status,
                data_cadastro
            FROM tbl_contato_cliente
            WHERE pk_id_tbl_cliente = %s
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
                c.*,
                c.pk_id_tbl_agencia as pk_id_aux_agencia,
                p.descricao as plano_descricao,
                p.tokens as plano_tokens,
                p.status as plano_status,
                ag.display as agencia_display,
                ag.key as agencia_key,
                tc.display as tipo_cliente_display,
                ae.display as apresentacao_executivo_display,
                fb.display as fluxo_boas_vindas_display,
                pr.display as percentual_display
            FROM tbl_cliente c
            LEFT JOIN tbl_plano p ON c.pk_id_tbl_plano = p.id_plano
            LEFT JOIN tbl_agencia ag ON c.pk_id_tbl_agencia = ag.id_agencia
            LEFT JOIN tbl_tipo_cliente tc ON c.id_tipo_cliente = tc.id_tipo_cliente
            LEFT JOIN tbl_apresentacao_executivo ae ON c.id_apresentacao_executivo = ae.id_tbl_apresentacao_executivo
            LEFT JOIN tbl_fluxo_boas_vindas fb ON c.id_fluxo_boas_vindas = fb.id_fluxo_boas_vindas
            LEFT JOIN tbl_percentual pr ON pr.id_percentual = c.id_percentual
            WHERE c.id_cliente = %s
        ''', (id_cliente,))
        return cursor.fetchone()

def criar_cliente(razao_social, nome_fantasia, id_tipo_cliente, pessoa='J', cnpj=None, inscricao_municipal=None, inscricao_estadual=None, 
                status=True, id_centralx=None, bairro=None, cidade=None, rua=None, numero=None, complemento=None, cep=None, pk_id_tbl_plano=None, pk_id_aux_agencia=None,
                pk_id_aux_estado=None, vendas_central_comm=None, id_apresentacao_executivo=None, id_fluxo_boas_vindas=None, id_percentual=None):
    """Cria um novo cliente"""
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO tbl_cliente (
                    razao_social, nome_fantasia, pessoa, cnpj, inscricao_municipal, 
                    inscricao_estadual, status, id_centralx, bairro, cidade, logradouro, numero, 
                    complemento, cep, pk_id_tbl_plano, pk_id_tbl_agencia, id_tipo_cliente, pk_id_aux_estado, vendas_central_comm,
                    id_apresentacao_executivo, id_fluxo_boas_vindas, id_percentual
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                ) RETURNING id_cliente
            ''', (
                razao_social, nome_fantasia, pessoa, cnpj, inscricao_municipal,
                inscricao_estadual, status, id_centralx, bairro, cidade, rua, numero,
                complemento, cep, pk_id_tbl_plano, pk_id_aux_agencia, id_tipo_cliente, pk_id_aux_estado, vendas_central_comm,
                id_apresentacao_executivo, id_fluxo_boas_vindas, id_percentual
            ))
            
            id_cliente = cursor.fetchone()['id_cliente']
            conn.commit()
            return id_cliente

    except Exception as e:
        conn.rollback()
        raise e

def atualizar_cliente(id_cliente, razao_social, nome_fantasia, id_tipo_cliente, pessoa='J', cnpj=None, inscricao_municipal=None, 
                     inscricao_estadual=None, status=True, id_centralx=None, bairro=None, cidade=None, rua=None, 
                     numero=None, complemento=None, cep=None, pk_id_tbl_plano=None, pk_id_aux_agencia=None, pk_id_aux_estado=None, vendas_central_comm=None,
                     id_apresentacao_executivo=None, id_fluxo_boas_vindas=None, id_percentual=None):
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
                    pk_id_tbl_plano = %s,
                    pk_id_tbl_agencia = %s,
                    pk_id_aux_estado = %s,
                    id_tipo_cliente = %s,
                    id_apresentacao_executivo = %s,
                    id_fluxo_boas_vindas = %s,
                    id_percentual = %s,
                    vendas_central_comm = %s,
                    data_modificacao = NOW()
                WHERE id_cliente = %s
            ''', (
                razao_social, nome_fantasia, pessoa, cnpj, inscricao_municipal,
                inscricao_estadual, status, id_centralx, bairro, cidade, rua, numero,
                complemento, cep, pk_id_tbl_plano, pk_id_aux_agencia, pk_id_aux_estado, id_tipo_cliente,
                id_apresentacao_executivo, id_fluxo_boas_vindas, id_percentual, vendas_central_comm, id_cliente
            ))
            
            conn.commit()
            return True

    except Exception as e:
        conn.rollback()
        raise e

# ==================== PERCENTUAL (CTA) ====================

def obter_percentuais():
    """Retorna todos os percentuais (CTA) ordenados pelo índice (ID)."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT 
                    id_percentual,
                    display,
                    status
                FROM tbl_percentual
                ORDER BY id_percentual
            ''')
            return cur.fetchall()
    except Exception as e:
        conn.rollback()
        raise e

def obter_percentuais_ativos():
    """Retorna apenas percentuais ativos, ordenados pelo índice (ID)."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT id_percentual, display, status
                FROM tbl_percentual
                WHERE status = TRUE
                ORDER BY id_percentual
                '''
            )
            return cur.fetchall()
    except Exception as e:
        conn.rollback()
        raise e

def obter_percentual_por_id(id_percentual: int):
    """Retorna um percentual específico pelo ID."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            '''
            SELECT id_percentual, display, status
            FROM tbl_percentual
            WHERE id_percentual = %s
            ''',
            (id_percentual,)
        )
        return cur.fetchone()

def criar_percentual(id_percentual: int, display: str, status: bool = True) -> int:
    """Cria um novo percentual com ID explícito e retorna o ID criado."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                INSERT INTO tbl_percentual (id_percentual, display, status)
                VALUES (%s, %s, %s)
                RETURNING id_percentual
                ''',
                (id_percentual, display.strip(), bool(status))
            )
            novo_id = cur.fetchone()['id_percentual']
        conn.commit()
        return novo_id
    except Exception as e:
        conn.rollback()
        raise e

def atualizar_percentual(id_percentual: int, display: str, status: bool) -> bool:
    """Atualiza o display e status de um percentual existente."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                UPDATE tbl_percentual
                SET display = %s,
                    status = %s
                WHERE id_percentual = %s
                ''',
                (display.strip(), bool(status), id_percentual)
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e

def deletar_percentual(id_percentual: int) -> bool:
    """Exclui um percentual. Retorna False se não existir."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM tbl_percentual WHERE id_percentual = %s',
                (id_percentual,)
            )
            apagados = cur.rowcount
        conn.commit()
        return apagados > 0
    except Exception as e:
        conn.rollback()
        raise e

# ==================== CONTATOS - CRIAR/ATUALIZAR ====================

def criar_contato(nome_completo, email, senha, pk_id_tbl_cliente, telefone=None, id_centralx=None, status=True, pk_id_tbl_cargo=None, pk_id_tbl_setor=None, cohorts=1):
    """Cria um novo contato"""
    conn = get_db()
    senha_md5 = gerar_senha_md5(senha)

    try:
        if email_existe(email):
            raise ValueError('Email já cadastrado!')

        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO tbl_contato_cliente 
                (nome_completo, email, senha, pk_id_tbl_cliente, telefone, id_centralx, status, pk_id_tbl_cargo, pk_id_tbl_setor, cohorts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_contato_cliente
            ''', (nome_completo, email.lower().strip(), senha_md5, pk_id_tbl_cliente, telefone, id_centralx, status, pk_id_tbl_cargo, pk_id_tbl_setor, cohorts))

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
                    data_modificacao = CURRENT_TIMESTAMP
                WHERE id_contato_cliente = %s
            ''', (nome_completo, email.lower().strip(), telefone, pk_id_tbl_cliente, contato_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise


def atualizar_senha_contato(contato_id, nova_senha):
    """Atualiza a senha de um contato"""
    conn = get_db()

    senha_md5 = gerar_senha_md5(nova_senha)

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE tbl_contato_cliente
                SET senha = %s, 
                    data_modificacao = CURRENT_TIMESTAMP
                WHERE id_contato_cliente = %s
            ''', (senha_md5, contato_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise

# ==================== CLIENTE - TOKENS ====================

def atualizar_tokens_cliente(id_cliente: int, total_token_plano: Optional[int] = None, total_token_gasto: Optional[int] = None) -> bool:
    """Atualiza campos de tokens do cliente, quando existirem.

    - total_token_plano: Quantidade total de tokens do plano vigente a ser registrada no cliente
    - total_token_gasto: Quantidade já consumida pelo cliente
    """
    conn = get_db()
    sets = []
    params = []
    if total_token_plano is not None:
        sets.append("total_token_plano = %s")
        params.append(total_token_plano)
    if total_token_gasto is not None:
        sets.append("total_token_gasto = %s")
        params.append(total_token_gasto)
    if not sets:
        return False
    params.append(id_cliente)
    query = f"UPDATE tbl_cliente SET {', '.join(sets)}, data_modificacao = NOW() WHERE id_cliente = %s"
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, tuple(params))
        conn.commit()
        return True
    except Exception:
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
                    data_modificacao = CURRENT_TIMESTAMP
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
                    data_modificacao = CURRENT_TIMESTAMP
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
                    data_modificacao = CURRENT_TIMESTAMP
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
                    data_modificacao = CURRENT_TIMESTAMP
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
                    data_modificacao = CURRENT_TIMESTAMP
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


def validar_senha_atual(contato_id, senha_atual):
    """Valida se a senha atual está correta"""
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute('SELECT senha FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (contato_id,))
        contato = cursor.fetchone()
        
        if not contato:
            return False
        
        return verificar_senha_md5(senha_atual, contato['senha'])


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
                data_modificacao = CURRENT_TIMESTAMP
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
                data_modificacao = CURRENT_TIMESTAMP
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
                (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
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
                data_modificacao = CURRENT_TIMESTAMP
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
                data_modificacao = CURRENT_TIMESTAMP
            WHERE id_cargo_contato = %s
            RETURNING status
        """, (id_cargo,))
        conn.commit()
        result = cur.fetchone()
        return result['status'] if result else None


# ==================== PLANOS ====================

def obter_planos() -> List[dict]:
    """Retorna todos os planos cadastrados."""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id_plano, descricao, tokens, data_criacao, 
                   data_atualizacao, status
            FROM tbl_plano
            ORDER BY descricao;
        """)
        planos = cur.fetchall()
        
        return [
            {
                'id_plano': plano['id_plano'],
                'descricao': plano['descricao'].strip() if plano['descricao'] else '',
                'tokens': plano['tokens'],
                'data_criacao': plano['data_criacao'][0] if plano['data_criacao'] else None,  # Pega o primeiro item do array
                'data_atualizacao': plano['data_atualizacao'],
                'status': plano['status']
            }
            for plano in planos
        ]
    finally:
        cur.close()

def obter_plano(id_plano: int) -> Optional[dict]:
    """Retorna um plano específico pelo ID."""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id_plano, descricao, tokens, data_criacao, 
                   data_atualizacao, status
            FROM tbl_plano
            WHERE id_plano = %s;
        """, (id_plano,))
        plano = cur.fetchone()
        
        if plano:
            return {
                'id_plano': plano['id_plano'],
                'descricao': plano['descricao'].strip() if plano['descricao'] else '',
                'tokens': plano['tokens'],
                'data_criacao': plano['data_criacao'][0] if plano['data_criacao'] else None,  # Pega o primeiro item do array
                'data_atualizacao': plano['data_atualizacao'],
                'status': plano['status']
            }
        return None
    finally:
        cur.close()

def criar_plano(descricao: str, tokens: int) -> int:
    """Cria um novo plano e retorna seu ID."""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO tbl_plano (descricao, tokens, data_criacao, status)
            VALUES (%s, %s, ARRAY[CURRENT_TIMESTAMP], true)
            RETURNING id_plano;
        """, (descricao, tokens))
        id_plano = cur.fetchone()['id_plano']
        conn.commit()
        return id_plano
    finally:
        cur.close()

def atualizar_plano(id_plano: int, descricao: str, tokens: int) -> bool:
    """Atualiza um plano existente."""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE tbl_plano
            SET descricao = %s,
                tokens = %s,
                data_atualizacao = CURRENT_TIMESTAMP
            WHERE id_plano = %s;
        """, (descricao, tokens, id_plano))
        conn.commit()
        return cur.rowcount > 0
    finally:
        cur.close()

def toggle_status_plano(id_plano: int) -> bool:
    """Alterna o status de um plano."""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE tbl_plano
            SET status = NOT status,
                data_atualizacao = CURRENT_TIMESTAMP
            WHERE id_plano = %s;
        """, (id_plano,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        cur.close()

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
                VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                    data_modificacao = CURRENT_TIMESTAMP
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

# ==================== APRESENTAÇÃO EXECUTIVO - LEITURA ====================

def obter_apresentacoes_executivo():
    """Retorna todas as opções de apresentação do executivo."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT 
                    id_tbl_apresentacao_executivo,
                    display
                FROM tbl_apresentacao_executivo
                ORDER BY display
            ''')
            return cur.fetchall()
    except Exception as e:
        conn.rollback()
        raise e

# ==================== FLUXO DE BOAS-VINDAS - LEITURA ====================

def obter_fluxos_boas_vindas():
    """Retorna todas as opções de fluxo de boas-vindas."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT id_fluxo_boas_vindas, display
                FROM tbl_fluxo_boas_vindas
                ORDER BY id_fluxo_boas_vindas
                '''
            )
            return cur.fetchall()
    except Exception as e:
        conn.rollback()
        raise e

# ==================== CATEGORIAS AUDIÊNCIA - CRUD ====================

def obter_cadu_categorias():
    """Retorna todas as categorias de audiência"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, nome, slug, descricao, icone, cor_hex, ordem_exibicao, is_active, is_featured, total_audiencias, meta_titulo, meta_descricao, created_at, updated_at
                FROM cadu_categorias
                ORDER BY ordem_exibicao, nome
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
                    updated_at = CURRENT_TIMESTAMP
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
            novo_id = cursor.fetchone()[0]
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
                    updated_at = CURRENT_TIMESTAMP
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

def obter_cadu_audiencias():
    """Retorna todas as audiências do catálogo com informações de categoria e subcategoria"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    a.id,
                    a.id_audiencia_plataforma,
                    a.fonte,
                    a.nome,
                    a.slug,
                    a.categoria_id,
                    a.subcategoria_id,
                    a.campos_com_dados_reais,
                    a.cpm_custo,
                    a.is_active,
                    a.created_at,
                    a.updated_at,
                    c.nome as categoria_nome,
                    s.nome as subcategoria_nome
                FROM cadu_audiencias a
                LEFT JOIN cadu_categorias c ON a.categoria_id = c.id
                LEFT JOIN cadu_subcategorias s ON a.subcategoria_id = s.id
                ORDER BY a.created_at DESC
            ''')
            return cursor.fetchall()
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
                    id_audiencia_plataforma, fonte, nome, slug, 
                    titulo_chamativo, descricao, descricao_curta, descricao_comercial,
                    cpm_custo, cpm_venda, cpm_minimo, cpm_maximo,
                    categoria_id, subcategoria_id, is_active
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            ''', (
                dados.get('id_audiencia_plataforma'),
                dados.get('fonte'),
                dados.get('nome'),
                dados.get('slug'),
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
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (
                dados.get('id_audiencia_plataforma'),
                dados.get('fonte'),
                dados.get('nome'),
                dados.get('slug'),
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
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING is_active
            ''', (id_audiencia,))
            result = cursor.fetchone()
            conn.commit()
            return result['is_active'] if result else None
    except Exception as e:
        conn.rollback()
        raise e