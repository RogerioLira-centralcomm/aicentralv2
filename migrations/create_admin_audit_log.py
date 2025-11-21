"""
Migração: Criar tabela de auditoria administrativa
Descrição: Registra todas as ações realizadas por administradores no sistema
Data: 2025-11-21
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aicentralv2 import db

def criar_tabela_audit_log():
    """Cria tabela tbl_admin_audit_log para rastreamento de ações administrativas"""
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            # Criar tabela de auditoria
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tbl_admin_audit_log (
                    id_log SERIAL PRIMARY KEY,
                    fk_id_usuario INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
                    acao VARCHAR(100) NOT NULL,
                    modulo VARCHAR(50) NOT NULL,
                    descricao TEXT,
                    registro_id INTEGER,
                    registro_tipo VARCHAR(50),
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    dados_anteriores JSONB,
                    dados_novos JSONB,
                    data_acao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Criar índices para performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_usuario 
                ON tbl_admin_audit_log(fk_id_usuario)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_modulo 
                ON tbl_admin_audit_log(modulo)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_data 
                ON tbl_admin_audit_log(data_acao DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_acao 
                ON tbl_admin_audit_log(acao)
            ''')
            
            conn.commit()
            print("✅ Tabela tbl_admin_audit_log criada com sucesso!")
            print("✅ Índices criados: fk_id_usuario, modulo, data_acao, acao")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela de auditoria: {str(e)}")
        raise

if __name__ == '__main__':
    print("🔧 Iniciando migração: Criar tabela de auditoria administrativa")
    criar_tabela_audit_log()
    print("✅ Migração concluída!")
