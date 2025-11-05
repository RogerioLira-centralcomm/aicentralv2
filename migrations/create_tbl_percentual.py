"""
Cria a tabela tbl_percentual para cadastro de CTAs de percentual.
Execução: python migrations/create_tbl_percentual.py
"""

import os
import psycopg

DB_NAME = os.getenv('DB_NAME', 'aicentral_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')


def criar_tbl_percentual():
    print('\n🛠️  Criando tabela tbl_percentual...')
    try:
        with psycopg.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    CREATE TABLE IF NOT EXISTS public.tbl_percentual (
                        id_percentual INTEGER PRIMARY KEY,
                        display VARCHAR(30) NOT NULL,
                        status BOOLEAN NOT NULL DEFAULT TRUE
                    );
                    '''
                )
                cur.execute(
                    '''
                    CREATE INDEX IF NOT EXISTS idx_percentual_display
                    ON public.tbl_percentual(display);
                    '''
                )
                cur.execute(
                    '''
                    CREATE INDEX IF NOT EXISTS idx_percentual_status
                    ON public.tbl_percentual(status);
                    '''
                )
                conn.commit()
        print('✅ Tabela tbl_percentual pronta!')
    except Exception as e:
        print(f'❌ Erro ao criar tbl_percentual: {e}')
        raise


if __name__ == '__main__':
    criar_tbl_percentual()
