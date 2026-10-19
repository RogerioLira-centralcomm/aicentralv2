"""
Migration: responsavel_setor em tbl_contato_cliente
Contatos marcados recebem e-mails operacionais (cotação, PI).
Regra: 1 contato ativo por empresa -> TRUE; 2+ -> todos FALSE.
"""

import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def get_db_config():
    return {
        'dbname': os.getenv('DB_NAME', 'aicentral_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'row_factory': dict_row,
    }


def run():
    conn = psycopg.connect(**get_db_config())
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                ALTER TABLE tbl_contato_cliente
                ADD COLUMN IF NOT EXISTS responsavel_setor BOOLEAN NOT NULL DEFAULT FALSE;
            ''')
            cursor.execute('''
                COMMENT ON COLUMN tbl_contato_cliente.responsavel_setor IS
                'Contato responsável por e-mails do setor (cotação/PI); auto TRUE se único ativo na empresa';
            ''')
            cursor.execute('''
                SELECT DISTINCT pk_id_tbl_cliente AS id
                  FROM tbl_contato_cliente
                 WHERE pk_id_tbl_cliente IS NOT NULL
            ''')
            cliente_ids = [row['id'] for row in cursor.fetchall()]
            for cid in cliente_ids:
                cursor.execute('''
                    SELECT id_contato_cliente
                      FROM tbl_contato_cliente
                     WHERE pk_id_tbl_cliente = %s
                       AND COALESCE(status, TRUE) = TRUE
                     ORDER BY id_contato_cliente
                ''', (cid,))
                ativos = [row['id_contato_cliente'] for row in cursor.fetchall()]
                if len(ativos) == 1:
                    cursor.execute('''
                        UPDATE tbl_contato_cliente
                           SET responsavel_setor = (id_contato_cliente = %s)
                         WHERE pk_id_tbl_cliente = %s
                    ''', (ativos[0], cid))
                elif len(ativos) > 1:
                    cursor.execute('''
                        UPDATE tbl_contato_cliente
                           SET responsavel_setor = FALSE
                         WHERE pk_id_tbl_cliente = %s
                           AND COALESCE(status, TRUE) = TRUE
                    ''', (cid,))
        conn.commit()
        print('OK: responsavel_setor aplicado e backfill concluído.')
    finally:
        conn.close()


if __name__ == '__main__':
    run()
