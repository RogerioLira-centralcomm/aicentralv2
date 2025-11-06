
"""
Cria as tabelas para o sistema de inteligência do CADU
Execução: python migrations/create_intelligence_tables.py
"""

import os
from psycopg import connect
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

def get_db_config():
    """Retorna configuração do banco de dados a partir do .env."""
    return {
        'dbname': os.getenv('DB_NAME', 'aicentral_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
    }


def create_tables():
    conn = connect(**get_db_config())
    try:
        with conn.cursor() as cursor:
            # Criar extensão para vetores se não existir
            cursor.execute("""
                CREATE EXTENSION IF NOT EXISTS vector;
            """)

            # Criar tabela de documentos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intelligence_documents (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    original_text TEXT,
                    processed_text TEXT,
                    document_type VARCHAR(50), -- pdf, text, etc
                    requires_cadu_format BOOLEAN DEFAULT false,
                    status VARCHAR(50), -- pending, processing, completed, error
                    pinecone_ids TEXT[], -- array de IDs no Pinecone
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Criar tabela de chunks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intelligence_chunks (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER REFERENCES intelligence_documents(id) ON DELETE CASCADE,
                    chunk_text TEXT NOT NULL,
                    chunk_embedding vector(1536), -- dimensão do embedding
                    pinecone_id VARCHAR(255),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Criar índices
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_intelligence_documents_status 
                ON intelligence_documents(status);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_intelligence_documents_created 
                ON intelligence_documents(created_at DESC);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_intelligence_chunks_document 
                ON intelligence_chunks(document_id);
            """)

            # Criar trigger para atualização de updated_at
            cursor.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)

            cursor.execute("""
                DROP TRIGGER IF EXISTS update_intelligence_documents_updated_at 
                ON intelligence_documents;
            """)
            cursor.execute("""
                CREATE TRIGGER update_intelligence_documents_updated_at
                    BEFORE UPDATE ON intelligence_documents
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """)

        conn.commit()
        print("Tabelas intelligence criadas com sucesso!")
    except Exception as e:
        conn.rollback()
        print(f'❌ Erro ao criar tabelas intelligence: {e}')
        raise
    finally:
        conn.close()


def drop_tables():
    conn = connect(**get_db_config())
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DROP TABLE IF EXISTS intelligence_chunks;
                DROP TABLE IF EXISTS intelligence_documents;
            """)
        conn.commit()
        print("Tabelas intelligence removidas!")
    except Exception as e:
        conn.rollback()
        print(f'❌ Erro ao remover tabelas intelligence: {e}')
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        if input("Tem certeza que deseja remover as tabelas? [y/N] ").lower() == 'y':
            drop_tables()
    else:
        create_tables()