"""
Migração: Módulo de Reembolsos e Adiantamentos (Fase 1)
- Coluna is_finance_admin em tbl_contato_cliente
- Tabelas finance_*
- Seed de categorias e finance admins
Execução: python migrations/create_finance_reimbursements.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from aicentralv2 import create_app, db
from aicentralv2.config import DevelopmentConfig, ProductionConfig

FINANCE_ADMIN_EMAIL_PREFIXES = (
    'financeiro@',
    'apolo@',
    'alexandre@',
)

CATEGORIES = (
    ('alimentacao', 'Alimentação'),
    ('transporte', 'Transporte'),
    ('hospedagem', 'Hospedagem'),
    ('combustivel', 'Combustível'),
    ('pedagio', 'Pedágio'),
    ('material', 'Material'),
    ('software', 'Software'),
    ('outros', 'Outros'),
)


def run_migration():
    env = os.getenv('AICENTRAL_ENV') or os.getenv('FLASK_ENV') or 'development'
    config_class = ProductionConfig if env.lower() == 'production' else DevelopmentConfig
    app = create_app(config_class)

    with app.app_context():
        conn = db.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

                cur.execute('''
                    ALTER TABLE tbl_contato_cliente
                    ADD COLUMN IF NOT EXISTS is_finance_admin BOOLEAN NOT NULL DEFAULT FALSE
                ''')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_expense_categories (
                        id          SERIAL PRIMARY KEY,
                        slug        TEXT UNIQUE NOT NULL,
                        label       TEXT NOT NULL,
                        active      BOOLEAN NOT NULL DEFAULT TRUE
                    )
                ''')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_reimbursement_notes (
                        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id               INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        created_by            INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        status                TEXT NOT NULL DEFAULT 'closed',
                        total_expenses        NUMERIC(12,2) NOT NULL,
                        total_advances        NUMERIC(12,2) NOT NULL DEFAULT 0,
                        total_payable         NUMERIC(12,2) NOT NULL,
                        expected_payment_date DATE NOT NULL,
                        paid_at               TIMESTAMPTZ NULL,
                        closed_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
                        notes                 TEXT,
                        CONSTRAINT chk_finance_note_status
                            CHECK (status IN ('closed', 'paid', 'reopened'))
                    )
                ''')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_expenses (
                        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id               INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        status                TEXT NOT NULL DEFAULT 'draft',
                        category_id           INT REFERENCES finance_expense_categories(id),
                        association_type      TEXT,
                        association_label     TEXT,
                        client_id             INTEGER NULL REFERENCES tbl_cliente(id_cliente),
                        merchant_name         TEXT,
                        expense_date          DATE,
                        currency              TEXT NOT NULL DEFAULT 'BRL',
                        total_amount          NUMERIC(12,2),
                        notes                 TEXT,
                        ai_raw_response       JSONB,
                        ai_confidence         NUMERIC(3,2),
                        needs_review          BOOLEAN NOT NULL DEFAULT FALSE,
                        rejection_reason      TEXT,
                        reimbursement_note_id UUID NULL REFERENCES finance_reimbursement_notes(id),
                        created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
                        CONSTRAINT chk_finance_expense_status CHECK (status IN (
                            'processing', 'extracted', 'extraction_failed', 'draft',
                            'submitted', 'approved', 'rejected', 'closed'
                        )),
                        CONSTRAINT chk_finance_association_type CHECK (
                            association_type IS NULL OR association_type IN (
                                'cliente', 'evento', 'viagem', 'outros'
                            )
                        )
                    )
                ''')

                cur.execute('''
                    CREATE INDEX IF NOT EXISTS idx_finance_expenses_user_status
                    ON finance_expenses(user_id, status)
                ''')
                cur.execute('''
                    CREATE INDEX IF NOT EXISTS idx_finance_expenses_note
                    ON finance_expenses(reimbursement_note_id)
                ''')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_expense_items (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        expense_id  UUID NOT NULL REFERENCES finance_expenses(id) ON DELETE CASCADE,
                        description TEXT NOT NULL,
                        quantity    NUMERIC(10,3) DEFAULT 1,
                        unit_amount NUMERIC(12,2),
                        amount      NUMERIC(12,2) NOT NULL,
                        position    INT NOT NULL DEFAULT 0
                    )
                ''')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_receipt_files (
                        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        expense_id   UUID NOT NULL REFERENCES finance_expenses(id) ON DELETE CASCADE,
                        storage_key  TEXT NOT NULL,
                        file_name    TEXT NOT NULL,
                        mime_type    TEXT NOT NULL,
                        file_size    BIGINT NOT NULL,
                        uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                ''')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_advances (
                        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id               INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        created_by            INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        amount                NUMERIC(12,2) NOT NULL,
                        description           TEXT NOT NULL,
                        association_type      TEXT,
                        association_label     TEXT,
                        advance_date          DATE NOT NULL,
                        status                TEXT NOT NULL DEFAULT 'open',
                        reimbursement_note_id UUID NULL REFERENCES finance_reimbursement_notes(id),
                        created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
                        CONSTRAINT chk_finance_advance_status
                            CHECK (status IN ('open', 'settled', 'cancelled'))
                    )
                ''')

                cur.execute('''
                    CREATE TABLE IF NOT EXISTS finance_audit_log (
                        id          BIGSERIAL PRIMARY KEY,
                        user_id     INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                        entity_type TEXT NOT NULL,
                        entity_id   TEXT NOT NULL,
                        action      TEXT NOT NULL,
                        payload     JSONB,
                        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                ''')

                for slug, label in CATEGORIES:
                    cur.execute('''
                        INSERT INTO finance_expense_categories (slug, label, active)
                        VALUES (%s, %s, TRUE)
                        ON CONFLICT (slug) DO NOTHING
                    ''', (slug, label))

                for prefix in FINANCE_ADMIN_EMAIL_PREFIXES:
                    cur.execute('''
                        UPDATE tbl_contato_cliente
                        SET is_finance_admin = TRUE
                        WHERE LOWER(email) LIKE %s
                    ''', (prefix.lower() + '%',))

            conn.commit()
            print('OK: finance reimbursements migration aplicada.')
        except Exception as e:
            conn.rollback()
            print(f'ERRO na migration finance: {e}')
            raise


if __name__ == '__main__':
    run_migration()
