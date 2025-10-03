"""
Script para verificar se tudo está instalado corretamente
"""
import sys

print("=" * 70)
print("🔍 Verificando instalação do psycopg3...")
print("=" * 70)

# 1. Verificar Python
print(f"\n✓ Python Version: {sys.version}")

# 2. Verificar psycopg
try:
    import psycopg
    print(f"✅ psycopg instalado: versão {psycopg.__version__}")
except ImportError as e:
    print(f"❌ psycopg NÃO instalado: {e}")
    print("\n💡 Execute: pip install 'psycopg[binary]'")
    sys.exit(1)

# 3. Verificar Flask
try:
    import flask
    print(f"✅ Flask instalado: versão {flask.__version__}")
except ImportError:
    print("❌ Flask NÃO instalado")
    sys.exit(1)

# 4. Verificar dotenv
try:
    import dotenv
    print(f"✅ python-dotenv instalado")
except ImportError:
    print("❌ python-dotenv NÃO instalado")
    sys.exit(1)

# 5. Verificar .env
import os
if os.path.exists('.env'):
    print(f"✅ Arquivo .env encontrado")
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"⚠️  Variáveis faltando no .env: {', '.join(missing)}")
    else:
        print(f"✅ Todas as variáveis necessárias estão no .env")
else:
    print("❌ Arquivo .env NÃO encontrado")

print("\n" + "=" * 70)
print("✅ Verificação concluída!")
print("=" * 70)