"""
Adicionar coluna pk_id_aux_tipo_cliente na tabela tbl_cliente
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

def add_tipo_cliente_to_cliente():
    """Adiciona a coluna pk_id_aux_tipo_cliente na tabela tbl_cliente"""
    conn = connect(**get_db_config())
    
    try:
        with conn.cursor() as cur:
            # Verifica se a coluna já existe
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tbl_cliente' 
                AND column_name='pk_id_aux_tipo_cliente'
            """)
            
            if cur.fetchone() is None:
                print("Adicionando coluna pk_id_aux_tipo_cliente...")
                
                # Adiciona a coluna
                cur.execute("""
                    ALTER TABLE tbl_cliente 
                    ADD COLUMN pk_id_aux_tipo_cliente INTEGER
                """)
                
                # Adiciona a constraint de foreign key
                cur.execute("""
                    ALTER TABLE tbl_cliente
                    ADD CONSTRAINT fk_tipo_cliente
                    FOREIGN KEY (pk_id_aux_tipo_cliente)
                    REFERENCES aux_tipo_cliente(id_aux_tipo_cliente)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE
                """)
                
                print("✅ Coluna pk_id_aux_tipo_cliente adicionada com sucesso!")
            else:
                print("⚠️  Coluna pk_id_aux_tipo_cliente já existe!")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao adicionar coluna: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    add_tipo_cliente_to_cliente()
