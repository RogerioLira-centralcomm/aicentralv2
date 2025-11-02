"""
Criar tabela tbl_consumo_tokens para rastrear consumo de tokens por contato
"""

from psycopg import connect
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

def get_db_config():
    """Retorna configuração do banco de dados"""
    return {
        'dbname': os.getenv('DB_NAME', 'aicentral_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432')
    }

def criar_tbl_consumo_tokens():
    """Cria a tabela tbl_consumo_tokens"""
    conn = connect(**get_db_config())
    
    try:
        with conn.cursor() as cur:
            # Cria a tabela tbl_consumo_tokens
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tbl_consumo_tokens (
                    id_consumo_tokens SERIAL PRIMARY KEY,
                    data DATE NOT NULL DEFAULT CURRENT_DATE,
                    datahora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    contato_cliente_id INTEGER NOT NULL,
                    quant_tokens_consumidos INTEGER NOT NULL DEFAULT 0,
                    CONSTRAINT fk_contato_cliente
                        FOREIGN KEY (contato_cliente_id)
                        REFERENCES tbl_contato_cliente(id_contato_cliente)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE
                )
            ''')
            
            # Cria índices para melhorar performance das consultas
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_consumo_tokens_contato 
                ON tbl_consumo_tokens(contato_cliente_id)
            ''')
            
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_consumo_tokens_data 
                ON tbl_consumo_tokens(data)
            ''')
            
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_consumo_tokens_datahora 
                ON tbl_consumo_tokens(datahora)
            ''')
            
        conn.commit()
        print("✅ Tabela tbl_consumo_tokens criada com sucesso!")
        print("✅ Índices criados com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela tbl_consumo_tokens: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    criar_tbl_consumo_tokens()
