"""
Criar tabela tbl_estado
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

def criar_tbl_estado():
    """Cria a tabela tbl_estado"""
    conn = connect(**get_db_config())
    
    try:
        with conn.cursor() as cur:
            # Cria a tabela tbl_estado
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tbl_estado (
                    id_estado SERIAL PRIMARY KEY,
                    descricao VARCHAR(60),
                    sigla VARCHAR(2),
                    id_centralx VARCHAR(100),
                    indice INTEGER
                )
            ''')
            
            # Verifica se já existem dados
            cur.execute('SELECT COUNT(*) FROM tbl_estado')
            count = cur.fetchone()[0]
            
            if count == 0:
                print("Inserindo estados brasileiros...")
                cur.execute("""
                    INSERT INTO tbl_estado (descricao, sigla, indice) VALUES 
                    ('Acre', 'AC', 1),
                    ('Alagoas', 'AL', 2),
                    ('Amapá', 'AP', 3),
                    ('Amazonas', 'AM', 4),
                    ('Bahia', 'BA', 5),
                    ('Ceará', 'CE', 6),
                    ('Distrito Federal', 'DF', 7),
                    ('Espírito Santo', 'ES', 8),
                    ('Goiás', 'GO', 9),
                    ('Maranhão', 'MA', 10),
                    ('Mato Grosso', 'MT', 11),
                    ('Mato Grosso do Sul', 'MS', 12),
                    ('Minas Gerais', 'MG', 13),
                    ('Pará', 'PA', 14),
                    ('Paraíba', 'PB', 15),
                    ('Paraná', 'PR', 16),
                    ('Pernambuco', 'PE', 17),
                    ('Piauí', 'PI', 18),
                    ('Rio de Janeiro', 'RJ', 19),
                    ('Rio Grande do Norte', 'RN', 20),
                    ('Rio Grande do Sul', 'RS', 21),
                    ('Rondônia', 'RO', 22),
                    ('Roraima', 'RR', 23),
                    ('Santa Catarina', 'SC', 24),
                    ('São Paulo', 'SP', 25),
                    ('Sergipe', 'SE', 26),
                    ('Tocantins', 'TO', 27)
                """)
            
            # Cria índice para melhorar performance
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_estado_sigla 
                ON tbl_estado(sigla)
            ''')
            
        conn.commit()
        print("✅ Tabela tbl_estado criada com sucesso!")
        print("✅ Estados brasileiros inseridos!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela tbl_estado: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    criar_tbl_estado()
