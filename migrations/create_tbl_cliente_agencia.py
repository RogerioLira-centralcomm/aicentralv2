"""
Cria tbl_cliente_agencia — vínculo N:N entre cliente final e empresas-agência.
Execução: python migrations/create_tbl_cliente_agencia.py
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
                    CREATE TABLE IF NOT EXISTS tbl_cliente_agencia (
                        id SERIAL PRIMARY KEY,
                        id_cliente INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
                        id_agencia_cliente INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE RESTRICT,
                        is_principal BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
                        UNIQUE (id_cliente, id_agencia_cliente)
                    )
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_cliente_agencia_principal
                    ON tbl_cliente_agencia (id_cliente)
                    WHERE is_principal = TRUE
                """)
            conn.commit()
            print("Tabela tbl_cliente_agencia criada/verificada com sucesso.")
        except Exception as exc:
            conn.rollback()
            print(f"Erro ao criar tbl_cliente_agencia: {exc}")
            raise


if __name__ == "__main__":
    migrate()
