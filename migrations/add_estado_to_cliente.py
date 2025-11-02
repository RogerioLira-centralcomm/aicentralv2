"""
Migration: Adiciona campo pk_id_aux_estado à tabela tbl_cliente
"""

import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aicentralv2.db import get_db

def run_migration():
    """Adiciona campo pk_id_aux_estado à tbl_cliente"""
    conn = get_db()
    
    try:
        with conn.cursor() as cur:
            print("🔄 Verificando se o campo pk_id_aux_estado já existe...")
            
            # Verifica se a coluna já existe
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tbl_cliente' 
                AND column_name='pk_id_aux_estado'
            """)
            
            if cur.fetchone():
                print("✅ Campo pk_id_aux_estado já existe na tabela tbl_cliente")
                return
            
            print("➕ Adicionando campo pk_id_aux_estado à tbl_cliente...")
            
            # Adiciona a coluna
            cur.execute("""
                ALTER TABLE tbl_cliente 
                ADD COLUMN pk_id_aux_estado INTEGER
            """)
            
            # Adiciona a constraint de FK
            print("🔗 Adicionando constraint de FK para tbl_estado...")
            cur.execute("""
                ALTER TABLE tbl_cliente
                ADD CONSTRAINT fk_cliente_estado
                FOREIGN KEY (pk_id_aux_estado) 
                REFERENCES tbl_estado(id_estado)
            """)
            
            conn.commit()
            print("✅ Campo pk_id_aux_estado adicionado com sucesso!")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao adicionar campo pk_id_aux_estado: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRATION: Adicionar pk_id_aux_estado à tbl_cliente")
    print("=" * 60)
    run_migration()
    print("\n✅ Migration concluída!")
