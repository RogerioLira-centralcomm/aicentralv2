"""
Cria cliente_web_info — cache do scrape (site/logo) do CRM v3.
Execução: python migrations/create_cliente_web_info.py
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
                    CREATE TABLE IF NOT EXISTS cliente_web_info (
                        id SERIAL PRIMARY KEY,
                        id_cliente INTEGER NOT NULL UNIQUE
                            REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
                        dominio VARCHAR(255) NOT NULL,
                        logo_url TEXT,
                        favicon_url TEXT,
                        titulo TEXT,
                        descricao TEXT,
                        menu_links JSONB,
                        dados_extras JSONB,
                        status VARCHAR(20) NOT NULL DEFAULT 'ok',
                        erro_mensagem TEXT,
                        atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cliente_web_info_dominio "
                    "ON cliente_web_info (dominio)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cliente_web_info_atualizado_em "
                    "ON cliente_web_info (atualizado_em)"
                )
            conn.commit()
            print("Tabela cliente_web_info criada/verificada com sucesso.")
        except Exception as exc:
            conn.rollback()
            print(f"Erro ao criar cliente_web_info: {exc}")
            raise


if __name__ == "__main__":
    migrate()
