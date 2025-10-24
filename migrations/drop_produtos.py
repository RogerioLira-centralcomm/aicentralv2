"""
Remove a tabela produtos do banco de dados (se existir)
Execução: python drop_produtos.py
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Carregar variáveis de ambiente
from dotenv import load_dotenv

load_dotenv()

from aicentralv2 import create_app


def remover_tabela_produtos():
    """Remove a tabela produtos e relacionadas"""
    print("=" * 70)
    print("🗑️  REMOVENDO TABELAS: produtos e relacionadas")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        from aicentralv2 import db
        conn = db.get_db()

        try:
            with conn.cursor() as cursor:
                # Lista de tabelas para remover
                tabelas_para_remover = [
                    'produtos',
                    'produto_categorias',
                    'produto_estoque',
                    'produto_precos',
                    'produto_fornecedores'
                ]

                tabelas_removidas = []

                print("\n1️⃣ Verificando tabelas existentes...\n")

                for tabela in tabelas_para_remover:
                    # Verificar se existe
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public'
                            AND table_name = %s
                        ) as existe
                    """, (tabela,))

                    resultado = cursor.fetchone()

                    if resultado['existe']:
                        # Contar registros
                        try:
                            cursor.execute(f"SELECT COUNT(*) as total FROM {tabela}")
                            total = cursor.fetchone()['total']
                            print(f"   📋 Tabela '{tabela}' encontrada ({total} registros)")
                            tabelas_removidas.append((tabela, total))
                        except:
                            print(f"   📋 Tabela '{tabela}' encontrada")
                            tabelas_removidas.append((tabela, 0))
                    else:
                        print(f"   ℹ️  Tabela '{tabela}' não existe")

                if not tabelas_removidas:
                    print("\n✅ Nenhuma tabela de produtos encontrada!")
                    print("\n4️⃣ Tabelas restantes no banco:\n")
                else:
                    # Remover tabelas
                    print("\n2️⃣ Removendo tabelas...\n")

                    for tabela, total in tabelas_removidas:
                        print(f"   🗑️  Removendo tabela '{tabela}'...")
                        cursor.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")
                        print(f"   ✅ Tabela '{tabela}' removida! ({total} registros deletados)")

                    # Remover sequences
                    print("\n3️⃣ Removendo sequences...\n")

                    sequences = [
                        'produtos_id_seq',
                        'produto_categorias_id_seq',
                        'produto_estoque_id_seq',
                        'produto_precos_id_seq'
                    ]

                    for seq in sequences:
                        try:
                            cursor.execute(f"DROP SEQUENCE IF EXISTS {seq} CASCADE")
                            print(f"   ✅ Sequence '{seq}' removida")
                        except:
                            pass

                    print("\n4️⃣ Tabelas restantes no banco:\n")

                # Verificar tabelas restantes
                cursor.execute("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """)

                tabelas = cursor.fetchall()

                if tabelas:
                    for tabela in tabelas:
                        # Contar registros
                        try:
                            cursor.execute(f"SELECT COUNT(*) as total FROM {tabela['tablename']}")
                            total = cursor.fetchone()['total']
                            print(f"   ✅ {tabela['tablename']:30s} ({total:5d} registros)")
                        except:
                            print(f"   ✅ {tabela['tablename']:30s}")
                else:
                    print("   ℹ️  Nenhuma tabela encontrada")

                # Commit
                conn.commit()

                print("\n" + "=" * 70)
                print("✅ LIMPEZA CONCLUÍDA COM SUCESSO!")
                print("=" * 70)

                if tabelas_removidas:
                    print(f"\n📊 Resumo:")
                    print(f"   • Tabelas removidas: {len(tabelas_removidas)}")
                    print(f"   • Tabelas restantes: {len(tabelas)}")

                return True

        except Exception as e:
            conn.rollback()
            print(f"\n❌ Erro ao remover tabelas: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    print("\n🚀 Iniciando limpeza de tabelas de produtos...\n")

    sucesso = remover_tabela_produtos()

    if sucesso:
        print("\n✅ Script executado com sucesso!")
        print("\n💡 Próximos passos:")
        print("   1. Execute: python run.py")
        print("   2. Acesse: http://localhost:5000")
        sys.exit(0)
    else:
        print("\n❌ Script falhou!")
        sys.exit(1)