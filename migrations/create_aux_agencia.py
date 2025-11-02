"""
Criar tabela aux_agencia
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

def criar_aux_agencia():
    """Cria a tabela aux_agencia"""
    conn = connect(**get_db_config())
    
    try:
        with conn.cursor() as cur:
            # Cria a tabela aux_agencia se não existir
            cur.execute('''
                CREATE TABLE IF NOT EXISTS aux_agencia (
                    id_aux_agencia INTEGER PRIMARY KEY,
                    display VARCHAR(30),
                    key BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Verifica se já existem dados
            cur.execute('SELECT COUNT(*) FROM aux_agencia')
            count = cur.fetchone()[0]
            
            if count == 0:
                print("Inserindo dados iniciais em aux_agencia...")
                # Adicione aqui quaisquer dados iniciais necessários
                # Por exemplo:
                # cur.execute("INSERT INTO aux_agencia (id_aux_agencia, display, key) VALUES (1, 'Agência 1', false)")
            
        conn.commit()
        print("✅ Tabela aux_agencia criada com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela aux_agencia: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    criar_aux_agencia()