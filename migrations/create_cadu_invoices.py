"""
Migração: Criar tabela de faturas/invoices
Descrição: Sistema de faturamento mensal baseado em consumo de recursos
Data: 2025-11-21
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aicentralv2 import db

def criar_tabela_invoices():
    """Cria tabela cadu_invoices para gestão de faturamento"""
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            # Criar tabela de faturas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cadu_invoices (
                    id_invoice SERIAL PRIMARY KEY,
                    invoice_number VARCHAR(50) UNIQUE NOT NULL,
                    id_cliente INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
                    id_plan INTEGER REFERENCES cadu_client_plans(id_plan),
                    
                    -- Período de referência
                    reference_month DATE NOT NULL,
                    
                    -- Consumo detalhado
                    tokens_consumed INTEGER DEFAULT 0,
                    tokens_cost DECIMAL(10,2) DEFAULT 0.00,
                    
                    images_generated INTEGER DEFAULT 0,
                    images_cost DECIMAL(10,2) DEFAULT 0.00,
                    
                    extra_users_count INTEGER DEFAULT 0,
                    extra_users_cost DECIMAL(10,2) DEFAULT 0.00,
                    
                    -- Valores adicionais
                    additional_charges JSONB DEFAULT '[]'::jsonb,
                    additional_charges_total DECIMAL(10,2) DEFAULT 0.00,
                    
                    -- Totais
                    subtotal DECIMAL(10,2) NOT NULL,
                    discount_percentage DECIMAL(5,2) DEFAULT 0.00,
                    discount_amount DECIMAL(10,2) DEFAULT 0.00,
                    taxes_percentage DECIMAL(5,2) DEFAULT 0.00,
                    taxes_amount DECIMAL(10,2) DEFAULT 0.00,
                    total DECIMAL(10,2) NOT NULL,
                    
                    -- Status e datas
                    invoice_status VARCHAR(20) DEFAULT 'pending',
                    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    due_date DATE NOT NULL,
                    paid_date DATE,
                    
                    -- Observações e anexos
                    notes TEXT,
                    pdf_url VARCHAR(500),
                    payment_method VARCHAR(50),
                    payment_reference VARCHAR(200),
                    
                    -- Auditoria
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
                    
                    CONSTRAINT chk_invoice_status CHECK (invoice_status IN ('pending', 'sent', 'paid', 'overdue', 'cancelled', 'refunded'))
                )
            ''')
            
            # Criar índices
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_invoice_cliente 
                ON cadu_invoices(id_cliente)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_invoice_status 
                ON cadu_invoices(invoice_status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_invoice_reference_month 
                ON cadu_invoices(reference_month DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_invoice_due_date 
                ON cadu_invoices(due_date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_invoice_number 
                ON cadu_invoices(invoice_number)
            ''')
            
            # Criar sequence para número de fatura
            cursor.execute('''
                CREATE SEQUENCE IF NOT EXISTS seq_invoice_number 
                START WITH 1000 
                INCREMENT BY 1
            ''')
            
            conn.commit()
            print("✅ Tabela cadu_invoices criada com sucesso!")
            print("✅ Índices criados")
            print("✅ Sequence seq_invoice_number criada (inicia em 1000)")
            print("📋 Status possíveis: pending, sent, paid, overdue, cancelled, refunded")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela de faturas: {str(e)}")
        raise

if __name__ == '__main__':
    print("🔧 Iniciando migração: Criar tabela de faturas")
    criar_tabela_invoices()
    print("✅ Migração concluída!")
