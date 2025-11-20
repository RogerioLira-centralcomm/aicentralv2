"""
Criação da tabela tbl_interesse_produto
Armazena registros de interesse de contatos em produtos
"""

import psycopg
from psycopg.rows import dict_row
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_config():
    return {
        'dbname': os.getenv('DB_NAME', 'aicentral_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'row_factory': dict_row
    }

def create_table():
    """Cria a tabela tbl_interesse_produto"""
    conn = psycopg.connect(**get_db_config())
    
    try:
        with conn.cursor() as cursor:
            # Cria a sequência se não existir
            cursor.execute('''
                CREATE SEQUENCE IF NOT EXISTS tbl_interesse_produto_id_interesse_seq;
            ''')
            
            # Cria a tabela
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tbl_interesse_produto (
                    id_interesse integer NOT NULL DEFAULT nextval('tbl_interesse_produto_id_interesse_seq'::regclass),
                    fk_id_contato_cliente integer NOT NULL,
                    tipo_produto character varying(100) NOT NULL,
                    data_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    notificado boolean DEFAULT false,
                    data_notificacao timestamp without time zone,
                    ip_registro character varying(45),
                    user_agent text,
                    dados_adicionais jsonb,
                    CONSTRAINT tbl_interesse_produto_pkey PRIMARY KEY (id_interesse),
                    CONSTRAINT uk_interesse_unico UNIQUE (fk_id_contato_cliente, tipo_produto),
                    CONSTRAINT fk_interesse_contato FOREIGN KEY (fk_id_contato_cliente)
                        REFERENCES tbl_contato_cliente (id_contato_cliente) MATCH SIMPLE
                        ON UPDATE CASCADE
                        ON DELETE CASCADE
                );
            ''')
            
            # Cria índices para melhor performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interesse_contato 
                ON tbl_interesse_produto(fk_id_contato_cliente);
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interesse_tipo_produto 
                ON tbl_interesse_produto(tipo_produto);
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interesse_notificado 
                ON tbl_interesse_produto(notificado);
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interesse_data_registro 
                ON tbl_interesse_produto(data_registro DESC);
            ''')
            
            # Adiciona comentários
            cursor.execute('''
                COMMENT ON TABLE tbl_interesse_produto IS 
                'Registra interesse de contatos em produtos/serviços';
            ''')
            
            cursor.execute('''
                COMMENT ON COLUMN tbl_interesse_produto.tipo_produto IS 
                'Tipo do produto: ADS_GOOGLE, ADS_META, SOCIAL_MEDIA, etc';
            ''')
            
            cursor.execute('''
                COMMENT ON COLUMN tbl_interesse_produto.dados_adicionais IS 
                'Dados extras em JSON: origem, campanha, observações, etc';
            ''')
            
            conn.commit()
            print("✅ Tabela tbl_interesse_produto criada com sucesso!")
            print("✅ Índices criados")
            print("✅ Constraints aplicadas")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao criar tabela: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    create_table()
