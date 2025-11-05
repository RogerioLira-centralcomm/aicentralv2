"""
Cria a tabela tbl_fluxo_boas_vindas (infraestrutura, sem CRUD)
Execução: python migrations/create_tbl_fluxo_boas_vindas.py
"""

from psycopg import connect
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
    }


def criar_tbl_fluxo_boas_vindas():
    """Cria a tabela public.tbl_fluxo_boas_vindas."""
    conn = connect(**get_db_config())
    try:
        with conn.cursor() as cur:
            print('\n🛠️  Criando tabela tbl_fluxo_boas_vindas...')
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS public.tbl_fluxo_boas_vindas (
                    id_fluxo_boas_vindas INTEGER PRIMARY KEY,
                    display VARCHAR(30)
                )
                '''
            )

            cur.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_fluxo_boas_vindas_display
                ON public.tbl_fluxo_boas_vindas(display)
                '''
            )

        conn.commit()
        print('✅ Tabela tbl_fluxo_boas_vindas criada/verificada com sucesso!')
    except Exception as e:
        conn.rollback()
        print(f'❌ Erro ao criar tabela tbl_fluxo_boas_vindas: {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    criar_tbl_fluxo_boas_vindas()
