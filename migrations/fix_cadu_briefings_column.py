"""
Migration: Corrige nome da coluna cliente para cliente_id na tabela cadu_briefings

Data: 2025-12-15
"""

import psycopg
from psycopg.rows import dict_row
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def run_migration():
    """Executa a migração"""
    
    # Conectar ao banco de dados
    conn = psycopg.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'aicentralv2'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        row_factory=dict_row
    )
    
    try:
        with conn.cursor() as cursor:
            print("🔄 Verificando estrutura da tabela cadu_briefings...")
            
            # Verificar se a coluna 'cliente' existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cadu_briefings' AND column_name = 'cliente';
            """)
            
            if cursor.fetchone():
                print("🔄 Renomeando coluna 'cliente' para 'cliente_id'...")
                cursor.execute("""
                    ALTER TABLE cadu_briefings 
                    RENAME COLUMN cliente TO cliente_id;
                """)
                print("✅ Coluna renomeada com sucesso!")
            else:
                print("ℹ️  Coluna 'cliente' não encontrada. Verificando 'cliente_id'...")
                
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'cadu_briefings' AND column_name = 'cliente_id';
                """)
                
                if cursor.fetchone():
                    print("✅ Coluna 'cliente_id' já existe corretamente!")
                else:
                    print("❌ Nenhuma coluna de cliente encontrada. Criando 'cliente_id'...")
                    cursor.execute("""
                        ALTER TABLE cadu_briefings 
                        ADD COLUMN cliente_id INTEGER REFERENCES tbl_cliente(pk_id_tbl_cliente) ON DELETE CASCADE;
                    """)
                    print("✅ Coluna 'cliente_id' criada!")
            
            conn.commit()
            
            # Verificar estrutura final
            print("\n📋 Estrutura atual da tabela:")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'cadu_briefings'
                ORDER BY ordinal_position;
            """)
            
            for col in cursor.fetchall():
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"   ✓ {col['column_name']:<20} {col['data_type']:<15} {nullable}")
                
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao executar migração: {str(e)}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        conn.close()
        print("\n✅ Migração concluída!")

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRATION: Corrigir coluna cliente_id")
    print("=" * 60)
    print("\n⚠️  ATENÇÃO: Esta migração corrigirá a coluna cliente na tabela cadu_briefings")
    print("Pressione ENTER para continuar ou CTRL+C para cancelar...")
    input()
    
    run_migration()
