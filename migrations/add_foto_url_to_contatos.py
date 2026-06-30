"""
Migration: Adicionar campo foto_url à tabela tbl_contato_cliente
Armazena a URL/caminho da foto do colaborador (usada no perfil e por outro app que consome a base)
"""

import psycopg
from psycopg.rows import dict_row
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_config():
    return {
        'dbname': os.getenv('DB_NAME', 'aicentral_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'row_factory': dict_row
    }

def add_foto_url_column():
    """Adiciona coluna foto_url à tabela tbl_contato_cliente"""
    conn = psycopg.connect(**get_db_config())

    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                ALTER TABLE tbl_contato_cliente
                ADD COLUMN IF NOT EXISTS foto_url TEXT NULL;
            ''')

            cursor.execute('''
                COMMENT ON COLUMN tbl_contato_cliente.foto_url IS
                'URL/caminho da foto do colaborador (usada no perfil e por aplicativos externos)';
            ''')

            conn.commit()
            print("OK: Coluna foto_url adicionada com sucesso a tabela tbl_contato_cliente!")

    except Exception as e:
        conn.rollback()
        print(f"ERRO ao adicionar coluna: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    add_foto_url_column()
