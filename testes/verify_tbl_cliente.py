"""
Verifica a tabela tbl_cliente e relacionamentos
Execução: python verify_tbl_cliente.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app

print("=" * 70)
print("🔍 VERIFICANDO ESTRUTURA: tbl_cliente")
print("=" * 70)

app = create_app()

with app.app_context():
    from aicentralv2 import db

    conn = db.get_db()

    with conn.cursor() as cursor:
        # 1. Verificar se tabela existe
        print("\n1️⃣ Verificando tabela tbl_cliente...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'tbl_cliente'
            ) as existe
        """)

        existe = cursor.fetchone()['existe']

        if existe:
            print("   ✅ Tabela tbl_cliente existe!")
        else:
            print("   ❌ Tabela tbl_cliente não existe!")
            print("\n💡 Para criar:")
            print("   python create_tbl_cliente.py")
            sys.exit(1)

        # 2. Verificar coluna id_cliente em users
        print("\n2️⃣ Verificando coluna id_cliente em users...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'id_cliente'
            ) as existe
        """)

        existe_col = cursor.fetchone()['existe']

        if existe_col:
            print("   ✅ Coluna id_cliente existe em users!")
        else:
            print("   ❌ Coluna id_cliente NÃO existe em users!")

        # 3. Verificar Foreign Keys
        print("\n3️⃣ Verificando Foreign Keys...")
        cursor.execute("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name IN ('tbl_cliente', 'users')
            ORDER BY tc.table_name, tc.constraint_name
        """)

        fks = cursor.fetchall()

        fks_tbl_cliente = [fk for fk in fks if fk['table_name'] == 'tbl_cliente']
        fks_users = [fk for fk in fks if fk['table_name'] == 'users']

        print(f"\n   📊 tbl_cliente: {len(fks_tbl_cliente)} Foreign Keys")
        for fk in fks_tbl_cliente:
            print(f"      ✅ {fk['constraint_name']}")
            print(f"         {fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")

        print(f"\n   📊 users: {len(fks_users)} Foreign Keys com tbl_cliente")
        for fk in fks_users:
            if 'cliente' in fk['constraint_name'].lower():
                print(f"      ✅ {fk['constraint_name']}")
                print(f"         {fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")

        # 4. Contar registros
        print("\n4️⃣ Contando registros...")
        cursor.execute("SELECT COUNT(*) as total FROM tbl_cliente")
        total = cursor.fetchone()['total']
        print(f"   📊 Total de clientes: {total}")

        if total > 0:
            cursor.execute("""
                SELECT 
                    id_cliente,
                    razao_social,
                    cnpj,
                    status
                FROM tbl_cliente
                ORDER BY id_cliente
                LIMIT 5
            """)

            clientes = cursor.fetchall()

            print("\n   Primeiros clientes:")
            for cliente in clientes:
                status = "✅ Ativo" if cliente['status'] else "❌ Inativo"
                print(f"   • ID {cliente['id_cliente']}: {cliente['razao_social']} - {cliente['cnpj']} ({status})")

        # 5. Verificar relacionamento users <-> clientes
        print("\n5️⃣ Verificando relacionamento users <-> clientes...")
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM users
            WHERE id_cliente IS NOT NULL
        """)

        usuarios_com_cliente = cursor.fetchone()['total']
        print(f"   📊 Usuários vinculados a clientes: {usuarios_com_cliente}")

        print("\n" + "=" * 70)
        print("✅ VERIFICAÇÃO CONCLUÍDA!")
        print("=" * 70)