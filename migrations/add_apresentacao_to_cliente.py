"""
Adiciona a coluna id_apresentacao_executivo em tbl_cliente e cria/ajusta a FK.
Se existir a coluna antiga pk_id_tbl_apresentacao_executivo, ela será renomeada.
Execução: python migrations/add_apresentacao_to_cliente.py
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
            # 1) Renomear coluna antiga, se existir
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'tbl_cliente' AND column_name = 'pk_id_tbl_apresentacao_executivo'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'tbl_cliente' AND column_name = 'id_apresentacao_executivo'
                    ) THEN
                        ALTER TABLE public.tbl_cliente
                        RENAME COLUMN pk_id_tbl_apresentacao_executivo TO id_apresentacao_executivo;
                    END IF;
                END $$;
            """)

            # 2) Adicionar coluna correta se ainda não existir
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'tbl_cliente' AND column_name = 'id_apresentacao_executivo'
                    ) THEN
                        ALTER TABLE public.tbl_cliente
                        ADD COLUMN id_apresentacao_executivo INTEGER NULL;
                    END IF;
                END $$;
            """)

            # 3) Garantir a FK correta: remove antiga se houver e cria a nova
            # Tenta dropar constraint com nome conhecido, ignora erro se não existir
            try:
                cur.execute("""
                    ALTER TABLE public.tbl_cliente
                    DROP CONSTRAINT IF EXISTS fk_cliente_apresentacao_exec
                """)
            except Exception:
                pass

            # Cria FK apontando para a coluna correta
            cur.execute("""
                ALTER TABLE public.tbl_cliente
                ADD CONSTRAINT fk_cliente_apresentacao_exec
                FOREIGN KEY (id_apresentacao_executivo)
                REFERENCES public.tbl_apresentacao_executivo (id_tbl_apresentacao_executivo)
                ON UPDATE NO ACTION
                ON DELETE SET NULL;
            """)

            # 4) Índice auxiliar na coluna nova
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_cliente_apresentacao_exec
                ON public.tbl_cliente(id_apresentacao_executivo);
            """)

        conn.commit()
        print('✅ id_apresentacao_executivo ajustada e FK criada com sucesso!')
    except Exception as e:
        conn.rollback()
        print(f'❌ Erro: {e}')
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    add_column_and_fk()
