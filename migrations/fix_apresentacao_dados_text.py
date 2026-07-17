"""
Migration: apresentacao_dados em cadu_cotacoes como TEXT.

Execução: python migrations/fix_apresentacao_dados_text.py
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

SQL_PATH = Path(__file__).with_name('fix_apresentacao_dados_text.sql')


def run_migration():
    sql = SQL_PATH.read_text(encoding='utf-8')
    conn = psycopg.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'aicentralv2'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
    )
    try:
        with conn.cursor() as cursor:
            print('Aplicando fix_apresentacao_dados_text.sql...')
            cursor.execute(sql)
        conn.commit()
        print('Coluna apresentacao_dados ajustada para TEXT.')
    except Exception as exc:
        conn.rollback()
        print(f'Erro na migração: {exc}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
