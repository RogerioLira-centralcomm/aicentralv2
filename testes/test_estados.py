import os
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

# Carregar .env
load_dotenv()

# Configurações
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'aicentral_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

print("🔍 Testando conexão com PostgreSQL (psycopg3)...")
print(f"   Host: {DB_CONFIG['host']}")
print(f"   Port: {DB_CONFIG['port']}")
print(f"   Database: {DB_CONFIG['dbname']}")
print(f"   User: {DB_CONFIG['user']}")
print(f"   Password: {'***' if DB_CONFIG['password'] else '(vazio)'}")
print()

try:
    # Conectar
    conn = psycopg.connect(**DB_CONFIG, row_factory=dict_row)
    print("✅ Conexão estabelecida com sucesso!")
    
    # Testar query
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as total FROM tbl_estado")
        resultado = cursor.fetchone()
        print(f"✅ Query executada: {resultado['total']} estados encontrados")
    
    # Testar query completa
    with conn.cursor() as cursor:
        query = (
            "SELECT e.id_estado, e.display, e.sigla, "
            "COUNT(c.id_cliente) as total_clientes "
            "FROM tbl_estado e "
            "LEFT JOIN tbl_cliente c ON e.id_estado = c.id_estado "
            "GROUP BY e.id_estado, e.display, e.sigla "
            "ORDER BY e.display "
            "LIMIT 5"
        )
        cursor.execute(query)
        estados = cursor.fetchall()
        
        print(f"\n✅ Estados (primeiros 5):")
        for estado in estados:
            print(f"   - {estado['display']} ({estado['sigla']}): {estado['total_clientes']} clientes")
    
    conn.close()
    print("\n✅ Conexão fechada com sucesso!")
    
except psycopg.OperationalError as e:
    print(f"❌ Erro de conexão: {e}")
    print("\n💡 Verifique:")
    print("   1. PostgreSQL está rodando?")
    print("   2. Credenciais corretas no .env?")
    print("   3. Banco 'aicentral_db' existe?")
    
except psycopg.Error as e:
    print(f"❌ Erro de banco de dados: {e}")
    
except Exception as e:
    print(f"❌ Erro inesperado: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()