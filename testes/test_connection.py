"""
AIcentralv2 - Testa a conexão com PostgreSQL (psycopg3)
"""
import psycopg
from dotenv import load_dotenv
import os
import sys

load_dotenv()

def test_connection():
    """Testa a conexão com o banco de dados"""
    try:
        print("=" * 70)
        print("🤖 AIcentralv2 - Teste de Conexão PostgreSQL (psycopg3)")
        print("=" * 70)
        print(f"📍 Host: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}")
        print(f"📦 Database: {os.getenv('DB_NAME')}")
        print(f"👤 User: {os.getenv('DB_USER')}")
        print("=" * 70)
        
        conn_string = f"""
            host={os.getenv('DB_HOST')}
            port={os.getenv('DB_PORT')}
            dbname={os.getenv('DB_NAME')}
            user={os.getenv('DB_USER')}
            password={os.getenv('DB_PASSWORD')}
        """
        
        print("🔌 Conectando...")
        conn = psycopg.connect(conn_string)
        
        print("✅ Conexão com PostgreSQL bem-sucedida!")
        
        with conn.cursor() as cursor:
            cursor.execute('SELECT version()')
            version = cursor.fetchone()
            print(f"\n📦 PostgreSQL version:")
            print(f"   {version[0][:80]}...")
            
            # Listar tabelas
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            
            if tables:
                print(f"\n📊 Tabelas encontradas ({len(tables)}):")
                for table in tables:
                    print(f"   - {table[0]}")
            else:
                print("\n📊 Nenhuma tabela encontrada (banco novo)")
        
        conn.close()
        
        print("=" * 70)
        print("✅ Teste concluído com sucesso!")
        print("=" * 70)
        
    except psycopg.OperationalError as e:
        print(f"\n❌ Erro de conexão: {e}")
        print("\n💡 Dicas:")
        print("   1. Verifique se o PostgreSQL está rodando")
        print("   2. Confirme as credenciais no arquivo .env")
        print("   3. Execute: python create_database.py")
        print("   4. Verifique a porta (padrão: 5432)")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        print("=" * 70)
        sys.exit(1)


if __name__ == '__main__':
    test_connection()