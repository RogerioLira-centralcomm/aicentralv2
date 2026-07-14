"""
Migração: finance_summary como entidade principal de reembolsos.
- Limpa dados das tabelas finance_*
- Remove finance_reimbursement_notes
- Cria finance_summary e vincula finance_expenses.summary_id

Execução: python migrations/refactor_finance_summary.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from aicentralv2 import create_app, db
from aicentralv2.config import DevelopmentConfig, ProductionConfig


def run_migration():
    env = os.getenv('AICENTRAL_ENV') or os.getenv('FLASK_ENV') or 'development'
    config_class = ProductionConfig if env.lower() == 'production' else DevelopmentConfig
    app = create_app(config_class)

    with app.app_context():
        conn = db.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

                # Limpar dados (somente finance_*)
                cur.execute('TRUNCATE finance_audit_log CASCADE')
                cur.execute('TRUNCATE finance_receipt_files CASCADE')
                cur.execute('TRUNCATE finance_expense_items CASCADE')
                cur.execute('TRUNCATE finance_expenses CASCADE')
                cur.execute('TRUNCATE finance_advances CASCADE')
                cur.execute('DROP TABLE IF EXISTS finance_reimbursement_notes CASCADE')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_summary (
                        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id           INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        description       TEXT NOT NULL,
                        reference_month   DATE NOT NULL,
                        seq_in_month      INT NOT NULL,
                        status            TEXT NOT NULL DEFAULT 'open',
                        total_payable     NUMERIC(12,2) NOT NULL DEFAULT 0,
                        total_rejected    NUMERIC(12,2) NOT NULL DEFAULT 0,
                        payment_date      DATE NULL,
                        paid_at           TIMESTAMPTZ NULL,
                        paid_by           INTEGER NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                        CONSTRAINT chk_finance_summary_status
                            CHECK (status IN ('open', 'paid'))
                    )
                ''')

                cur.execute('''
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_finance_summary_user_open
                    ON finance_summary (user_id)
                    WHERE status = 'open'
                ''')

                cur.execute('''
                    CREATE INDEX IF NOT EXISTS idx_finance_summary_user_status
                    ON finance_summary (user_id, status)
                ''')

                # Remover coluna antiga e adicionar summary_id
                cur.execute('''
                    ALTER TABLE finance_expenses
                    DROP COLUMN IF EXISTS reimbursement_note_id
                ''')
                cur.execute('''
                    ALTER TABLE finance_expenses
                    ADD COLUMN IF NOT EXISTS summary_id UUID NULL REFERENCES finance_summary(id)
                ''')

                cur.execute('DROP INDEX IF EXISTS idx_finance_expenses_note')
                cur.execute('''
                    CREATE INDEX IF NOT EXISTS idx_finance_expenses_summary
                    ON finance_expenses (summary_id)
                ''')

                # Atualizar finance_advances: remover FK antiga se existir
                cur.execute('''
                    ALTER TABLE finance_advances
                    DROP COLUMN IF EXISTS reimbursement_note_id
                ''')
                cur.execute('''
                    ALTER TABLE finance_advances
                    ADD COLUMN IF NOT EXISTS summary_id UUID NULL REFERENCES finance_summary(id)
                ''')

            conn.commit()
            print('OK: refactor finance_summary aplicada (dados finance_* limpos).')
        except Exception as e:
            conn.rollback()
            print(f'ERRO na migration finance_summary: {e}')
            raise


if __name__ == '__main__':
    run_migration()
