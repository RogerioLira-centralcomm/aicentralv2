"""
Criar tabela aux_tipo_cliente
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

def criar_aux_tipo_cliente():
    """Cria a tabela aux_tipo_cliente"""
    conn = connect(**get_db_config())
    
    try:
        with conn.cursor() as cur:
            # Cria a tabela aux_tipo_cliente
            cur.execute('''
                CREATE TABLE IF NOT EXISTS aux_tipo_cliente (
                    id_aux_tipo_cliente SERIAL PRIMARY KEY,
                    display VARCHAR(30),
                    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_modificacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Verifica se já existem dados
            cur.execute('SELECT COUNT(*) FROM aux_tipo_cliente')
            count = cur.fetchone()[0]
            
            if count == 0:
                print("Inserindo dados iniciais em aux_tipo_cliente...")
                cur.execute("""
                    INSERT INTO aux_tipo_cliente (display) VALUES 
                    ('Padrão'),
                    ('Premium'),
                    ('VIP'),
                    ('Corporativo')
                """)
            
        conn.commit()
        print("✅ Tabela aux_tipo_cliente criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela aux_tipo_cliente: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    criar_aux_tipo_cliente()
