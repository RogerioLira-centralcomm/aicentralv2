"""
Migration: Renomeia tbl_cliente.percentual → fee
Execução: python migrations/run_rename_percentual_to_fee_cliente.py
"""

import os
from pathlib import Path

import psycopg

DB_NAME = os.getenv('DB_NAME', 'aicentral_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')


def run_migration():
    sql_path = Path(__file__).with_name('rename_percentual_to_fee_cliente.sql')
    sql = sql_path.read_text(encoding='utf-8')
    print('\nRenomeando tbl_cliente.percentual → fee...')
    with psycopg.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print('Coluna fee pronta em tbl_cliente.')


if __name__ == '__main__':
    run_migration()
