"""
Adiciona classificação comercial independente em tbl_cliente.
Execução: python migrations/add_classificacao_cliente_to_cliente.py
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
                    ADD COLUMN IF NOT EXISTS classificacao_cliente VARCHAR(20) DEFAULT 'Prospecção'
                """)
                cur.execute("""
                    UPDATE tbl_cliente
                    SET classificacao_cliente = 'Prospecção'
                    WHERE classificacao_cliente IS NULL
                """)
            conn.commit()
            print("Coluna classificacao_cliente garantida em tbl_cliente.")
        except Exception as exc:
            conn.rollback()
            print(f"Erro ao adicionar classificacao_cliente: {exc}")
            raise


if __name__ == "__main__":
    migrate()
