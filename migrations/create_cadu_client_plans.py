"""
Migração: Criar tabela de planos de clientes
Descrição: Gestão de planos (Beta Tester, Starter, Pro, Enterprise) com controle de consumo
Data: 2025-11-21
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

def criar_tabela_client_plans():
    """Cria tabela cadu_client_plans para gestão de planos e limites de consumo"""
    conn = psycopg.connect(
        dbname=os.getenv('DATABASE_NAME'),
        user=os.getenv('DATABASE_USER'),
        password=os.getenv('DATABASE_PASSWORD'),
        host=os.getenv('DATABASE_HOST'),
        port=os.getenv('DATABASE_PORT'),
        row_factory=dict_row
    )
    try:
        with conn.cursor() as cursor:
            # Criar tabela de planos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cadu_client_plans (
                    id_plan SERIAL PRIMARY KEY,
                    id_cliente INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
                    plan_type VARCHAR(50) NOT NULL,
                    plan_name VARCHAR(100),
                    
                    -- Limites de tokens
                    tokens_monthly_limit INTEGER DEFAULT 100000,
                    tokens_used_current_month INTEGER DEFAULT 0,
                    
                    -- Limites de imagens
                    image_credits_monthly INTEGER DEFAULT 50,
                    image_credits_used_current_month INTEGER DEFAULT 0,
                    
                    -- Limites de usuários
                    max_users INTEGER DEFAULT 5,
                    current_users_count INTEGER DEFAULT 0,
                    
                    -- Features (JSON)
                    features JSONB DEFAULT '{}'::jsonb,
                    
                    -- Status e datas
                    plan_status VARCHAR(20) DEFAULT 'active',
                    valid_from DATE NOT NULL DEFAULT CURRENT_DATE,
                    valid_until DATE,
                    
                    -- Auditoria
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
                    
                    -- Constraint: apenas um plano ativo por cliente
                    CONSTRAINT chk_plan_type CHECK (plan_type IN ('Plano Beta Tester', 'starter', 'pro', 'enterprise', 'custom')),
                    CONSTRAINT chk_plan_status CHECK (plan_status IN ('active', 'suspended', 'cancelled', 'expired'))
                )
            ''')
            
            # Criar índices
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_client_plan_cliente 
                ON cadu_client_plans(id_cliente)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_client_plan_status 
                ON cadu_client_plans(plan_status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_client_plan_valid 
                ON cadu_client_plans(valid_from, valid_until)
            ''')
            
            # Criar unique constraint para plano ativo por cliente
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_plan_per_client 
                ON cadu_client_plans(id_cliente) 
                WHERE plan_status = 'active'
            ''')
            
            conn.commit()
            print("✅ Tabela cadu_client_plans criada com sucesso!")
            print("✅ Índices e constraints criados")
            print("📋 Tipos de plano: 'Plano Beta Tester', starter, pro, enterprise, custom")
            print("📋 Status possíveis: active, suspended, cancelled, expired")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela de planos: {str(e)}")
        raise

if __name__ == '__main__':
    print("🔧 Iniciando migração: Criar tabela de planos de clientes")
    criar_tabela_client_plans()
    print("✅ Migração concluída!")
