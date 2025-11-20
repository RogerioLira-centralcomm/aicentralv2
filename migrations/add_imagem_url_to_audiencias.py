"""
Migration: Adicionar campo imagem_url à tabela cadu_audiencias
Armazena URL da imagem gerada por IA para a audiência (formato 16:9)
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

def add_imagem_url_column():
    """Adiciona coluna imagem_url à tabela cadu_audiencias"""
    conn = psycopg.connect(**get_db_config())
    
    try:
        with conn.cursor() as cursor:
            # Adicionar coluna imagem_url
            cursor.execute('''
                ALTER TABLE cadu_audiencias 
                ADD COLUMN IF NOT EXISTS imagem_url TEXT NULL;
            ''')
            
            # Adicionar comentário
            cursor.execute('''
                COMMENT ON COLUMN cadu_audiencias.imagem_url IS 
                'URL da imagem gerada por IA para a audiência (formato 16:9)';
            ''')
            
            conn.commit()
            print("✅ Coluna imagem_url adicionada com sucesso à tabela cadu_audiencias!")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao adicionar coluna: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    add_imagem_url_column()
