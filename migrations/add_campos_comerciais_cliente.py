"""
Adiciona campos comerciais ao cadastro de cliente.
Execução: python migrations/add_campos_comerciais_cliente.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aicentralv2 import create_app
from aicentralv2 import db


def migrate():
    app = create_app()
    with app.app_context():
        conn = db.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE tbl_cliente
                    ADD COLUMN IF NOT EXISTS opera_midia BOOLEAN DEFAULT FALSE
                """)
                cur.execute("""
                    ALTER TABLE tbl_cliente
                    ADD COLUMN IF NOT EXISTS demanda_dados BOOLEAN DEFAULT FALSE
                """)
                cur.execute("""
                    ALTER TABLE tbl_cliente
                    ADD COLUMN IF NOT EXISTS demanda_programatica_canais BOOLEAN DEFAULT FALSE
                """)
                cur.execute("""
                    ALTER TABLE tbl_cliente
                    ADD COLUMN IF NOT EXISTS observacoes_comerciais_adicionais TEXT
                """)
                cur.execute("""
                    UPDATE tbl_cliente
                    SET
                        opera_midia = COALESCE(opera_midia, FALSE),
                        demanda_dados = COALESCE(demanda_dados, FALSE),
                        demanda_programatica_canais = COALESCE(demanda_programatica_canais, FALSE)
                """)
            conn.commit()
            print("Campos comerciais garantidos em tbl_cliente.")
        except Exception as exc:
            conn.rollback()
            print(f"Erro ao adicionar campos comerciais do cliente: {exc}")
            raise


if __name__ == "__main__":
    migrate()
