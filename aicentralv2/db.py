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