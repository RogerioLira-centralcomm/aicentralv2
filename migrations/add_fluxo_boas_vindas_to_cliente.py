"""
Adiciona a coluna id_fluxo_boas_vindas em tbl_cliente e cria/ajusta a FK.
Execução: python migrations/add_fluxo_boas_vindas_to_cliente.py
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


def add_column_and_fk():
    conn = connect(**get_db_config())
    try:
        with conn.cursor() as cur:
            # 1) Adicionar coluna se ainda não existir
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'tbl_cliente' AND column_name = 'id_fluxo_boas_vindas'
                    ) THEN
                        ALTER TABLE public.tbl_cliente
                        ADD COLUMN id_fluxo_boas_vindas INTEGER NULL;
                    END IF;
                END $$;
                """
            )

            # 2) Remover FK antiga se houver (nome padrão usado aqui)
            try:
                cur.execute(
                    """
                    ALTER TABLE public.tbl_cliente
                    DROP CONSTRAINT IF EXISTS fk_cliente_fluxo_boas_vindas
                    """
                )
            except Exception:
                pass

            # 3) Criar FK para tbl_fluxo_boas_vindas
            cur.execute(
                """
                ALTER TABLE public.tbl_cliente
                ADD CONSTRAINT fk_cliente_fluxo_boas_vindas
                FOREIGN KEY (id_fluxo_boas_vindas)
                REFERENCES public.tbl_fluxo_boas_vindas (id_fluxo_boas_vindas)
                ON UPDATE NO ACTION
                ON DELETE SET NULL;
                """
            )

            # 4) Índice auxiliar
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cliente_fluxo_boas_vindas
                ON public.tbl_cliente(id_fluxo_boas_vindas);
                """
            )

        conn.commit()
        print('✅ id_fluxo_boas_vindas adicionada e FK criada com sucesso!')
    except Exception as e:
        conn.rollback()
        print(f'❌ Erro: {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    add_column_and_fk()
