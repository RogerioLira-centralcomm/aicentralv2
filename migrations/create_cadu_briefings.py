"""
Migration: Cria tabela cadu_briefings para gestão de briefings de campanhas

Tabela: cadu_briefings
Campos:
- id (SERIAL PRIMARY KEY)
- cotacao_id (INTEGER) - FK para cadu_cotacoes
- cliente_id (INTEGER) - FK para tbl_cliente
- titulo (VARCHAR) - Título do briefing
- objetivo (TEXT) - Objetivo da campanha
- publico_alvo (TEXT) - Descrição do público-alvo
- mensagem_chave (TEXT) - Mensagem principal
- canais (TEXT) - Canais de comunicação
- budget (DECIMAL) - Orçamento estimado
- prazo (DATE) - Prazo de entrega
- observacoes (TEXT) - Observações adicionais
- status (VARCHAR) - Status: rascunho, aprovado, em_producao, concluido
- created_by (INTEGER) - FK para tbl_contatos (quem criou)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

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
            print("🔄 Criando tabela cadu_briefings...")
            
            # Criar tabela cadu_briefings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cadu_briefings (
                    id SERIAL PRIMARY KEY,
                    cotacao_id INTEGER REFERENCES cadu_cotacoes(id) ON DELETE SET NULL,
                    cliente_id INTEGER REFERENCES tbl_cliente(pk_id_tbl_cliente) ON DELETE CASCADE,
                    titulo VARCHAR(200) NOT NULL,
                    objetivo TEXT,
                    publico_alvo TEXT,
                    mensagem_chave TEXT,
                    canais TEXT,
                    budget DECIMAL(15,2),
                    prazo DATE,
                    observacoes TEXT,
                    status VARCHAR(30) DEFAULT 'rascunho',
                    created_by INTEGER REFERENCES tbl_contatos(pk_id_tbl_contatos) ON DELETE SET NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Criar índices
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_briefing_cotacao 
                ON cadu_briefings(cotacao_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_briefing_cliente 
                ON cadu_briefings(cliente_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_briefing_status 
                ON cadu_briefings(status);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_briefing_prazo 
                ON cadu_briefings(prazo);
            """)
            
            conn.commit()
            print("✅ Tabela cadu_briefings criada com sucesso!")
            
            # Verificar estrutura
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'cadu_briefings'
                ORDER BY ordinal_position;
            """)
            
            colunas = cursor.fetchall()
            print(f"\n📋 Estrutura da tabela ({len(colunas)} colunas):")
            for col in colunas:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                max_len = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"   ✓ {col['column_name']:<20} {col['data_type']}{max_len:<15} {nullable}{default}")
                
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao executar migração: {str(e)}")
        raise e
    finally:
        conn.close()
        print("\n✅ Migração concluída!")

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRATION: Criar tabela cadu_briefings")
    print("=" * 60)
    print("\n⚠️  ATENÇÃO: Esta migração criará a tabela cadu_briefings")
    print("Pressione ENTER para continuar ou CTRL+C para cancelar...")
    input()
    
    run_migration()
