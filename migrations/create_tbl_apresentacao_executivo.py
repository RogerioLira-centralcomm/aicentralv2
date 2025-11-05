"""
Cria a tabela tbl_apresentacao_executivo
Execução: python migrations/create_tbl_apresentacao_executivo.py
"""

from psycopg import connect
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()


def get_db_config():
    """Retorna configuração do banco de dados a partir do .env."""
    return {
        'dbname': os.getenv('DB_NAME', 'aicentral_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
    }


def criar_tbl_apresentacao_executivo():
    """Cria a tabela tbl_apresentacao_executivo (infraestrutura, sem CRUD)."""
    conn = connect(**get_db_config())

    try:
        with conn.cursor() as cur:
            print('\n🛠️  Criando tabela tbl_apresentacao_executivo...')
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS public.tbl_apresentacao_executivo (
                    id_tbl_apresentacao_executivo SERIAL PRIMARY KEY,
                    display VARCHAR(30)
                )
                '''
            )

            # Índice opcional em display para facilitar buscas/ordenções
            cur.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_apresentacao_executivo_display
                ON public.tbl_apresentacao_executivo(display)
                '''
            )

        conn.commit()
        print('✅ Tabela tbl_apresentacao_executivo criada/verificada com sucesso!')

    except Exception as e:
        conn.rollback()
        print(f'❌ Erro ao criar tabela tbl_apresentacao_executivo: {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    criar_tbl_apresentacao_executivo()
