"""
Migration: Adiciona campo id_percentual à tabela tbl_cliente com FK para tbl_percentual
Execução: python migrations/add_percentual_to_cliente.py
"""

import os
import psycopg

DB_NAME = os.getenv('DB_NAME', 'aicentral_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')


def run_migration():
    print("\n🛠️  Adicionando coluna id_percentual em tbl_cliente...")
    with psycopg.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    ) as conn:
        with conn.cursor() as cur:
            # Verifica se a coluna já existe
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tbl_cliente' AND column_name = 'id_percentual'
                """
            )
            if cur.fetchone():
                print("✅ Coluna id_percentual já existe em tbl_cliente.")
                return

            # Adiciona a coluna como opcional (NULL)
            print("➕ Adicionando coluna id_percentual (INTEGER NULL)...")
            cur.execute(
                """
                ALTER TABLE public.tbl_cliente
                ADD COLUMN id_percentual INTEGER NULL
                """
            )

            # Adiciona a FK para tbl_percentual
            print("🔗 Criando FK para tbl_percentual(id_percentual)...")
            try:
                cur.execute(
                    """
                    ALTER TABLE public.tbl_cliente
                    ADD CONSTRAINT fk_cliente_percentual
                    FOREIGN KEY (id_percentual)
                    REFERENCES public.tbl_percentual(id_percentual)
                    ON UPDATE NO ACTION
                    ON DELETE SET NULL
                    """
                )
            except Exception as e:
                # Caso a constraint já exista, apenas registra aviso
                if 'already exists' in str(e).lower():
                    print("⚠️  Constraint fk_cliente_percentual já existe.")
                else:
                    raise

            # Índice opcional para consultas
            print("📈 Criando índice opcional idx_cliente_id_percentual...")
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cliente_id_percentual
                ON public.tbl_cliente(id_percentual)
                """
            )

            conn.commit()
            print("✅ Coluna id_percentual adicionada com sucesso!")


if __name__ == '__main__':
    try:
        run_migration()
    except Exception as e:
        print(f"❌ Erro na migration: {e}")
        raise
