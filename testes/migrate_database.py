"""
Migração completa: Unifica auth_users e users em uma única tabela
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app
from werkzeug.security import generate_password_hash
from datetime import datetime


def migrar():
    """Executa a migração completa"""
    print("=" * 70)
    print("🔄 MIGRAÇÃO DO BANCO DE DADOS")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        from aicentralv2 import db
        conn = db.get_db()

        try:
            with conn.cursor() as cursor:
                # ETAPA 1: Backup
                print("\n1️⃣ Coletando dados para migração...")

                # Dados de auth_users
                cursor.execute("""
                    SELECT id, username, password_hash, nome_completo, created_at, updated_at
                    FROM auth_users
                    ORDER BY id
                """)
                auth_users = cursor.fetchall()
                print(f"   ✓ {len(auth_users)} usuários em auth_users")

                # Mostrar preview
                if auth_users:
                    print("\n   📋 Preview de auth_users:")
                    for user in auth_users[:5]:
                        print(f"      • ID: {user['id']} | User: {user['username']} | Nome: {user['nome_completo']}")
                    if len(auth_users) > 5:
                        print(f"      ... e mais {len(auth_users) - 5} usuários")

                # Dados de users
                cursor.execute("""
                    SELECT id, nome, email, idade, created_at
                    FROM users
                    ORDER BY id
                """)
                users = cursor.fetchall()
                print(f"\n   ✓ {len(users)} usuários em users")

                # Mostrar preview
                if users:
                    print("\n   📋 Preview de users:")
                    for user in users[:5]:
                        print(f"      • ID: {user['id']} | Nome: {user['nome']} | Email: {user['email']}")
                    if len(users) > 5:
                        print(f"      ... e mais {len(users) - 5} usuários")

                # ETAPA 2: Criar tabela temporária
                print("\n2️⃣ Criando nova estrutura de tabela...")
                cursor.execute("DROP TABLE IF EXISTS users_temp CASCADE")

                cursor.execute("""
                    CREATE TABLE users_temp (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(100) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        nome_completo VARCHAR(200) NOT NULL,
                        email VARCHAR(200) UNIQUE NOT NULL,
                        idade INTEGER,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_admin BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("   ✓ Tabela users_temp criada")

                # ETAPA 3: Migrar auth_users
                print("\n3️⃣ Migrando dados de auth_users...")
                migrados_auth = 0

                for user in auth_users:
                    try:
                        # Verificar se tem email válido, senão criar temporário
                        email_temp = f"{user['username']}@temporario.com"

                        cursor.execute("""
                            INSERT INTO users_temp 
                                (username, password_hash, nome_completo, email, created_at, updated_at, is_admin)
                            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                            ON CONFLICT (username) DO NOTHING
                        """, (
                            user['username'],
                            user['password_hash'],
                            user['nome_completo'],
                            email_temp,
                            user['created_at'],
                            user['updated_at']
                        ))
                        migrados_auth += 1
                        print(f"   ✓ Migrado: {user['username']} ({user['nome_completo']})")
                    except Exception as e:
                        print(f"   ⚠️  Erro ao migrar {user['username']}: {e}")

                print(f"\n   ✅ {migrados_auth}/{len(auth_users)} usuários migrados de auth_users")

                # ETAPA 4: Migrar users
                print("\n4️⃣ Migrando dados de users...")
                senha_padrao = 'senha123'
                senha_hash = generate_password_hash(senha_padrao)
                migrados_users = 0
                usuarios_com_senha_padrao = []

                for user in users:
                    nome = user['nome']
                    email = user['email']
                    idade = user['idade']
                    created = user['created_at']

                    # Gerar username a partir do nome
                    username = nome.lower().replace(' ', '_').replace('ã', 'a').replace('á', 'a') \
                        .replace('â', 'a').replace('é', 'e').replace('ê', 'e') \
                        .replace('í', 'i').replace('ó', 'o').replace('ô', 'o') \
                        .replace('õ', 'o').replace('ú', 'u').replace('ç', 'c')

                    # Remover caracteres especiais
                    import re
                    username = re.sub(r'[^a-z0-9_]', '', username)

                    # Garantir que username seja único
                    username_base = username
                    counter = 1

                    while True:
                        try:
                            cursor.execute("""
                                INSERT INTO users_temp 
                                    (username, password_hash, nome_completo, email, idade, created_at, updated_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (
                                username,
                                senha_hash,
                                nome,
                                email,
                                idade,
                                created,
                                created
                            ))

                            result = cursor.fetchone()
                            if result:
                                migrados_users += 1
                                usuarios_com_senha_padrao.append({
                                    'nome': nome,
                                    'username': username,
                                    'email': email
                                })
                                print(f"   ✓ Migrado: {nome} → username: {username} (senha: {senha_padrao})")
                                break

                        except Exception as e:
                            error_msg = str(e).lower()

                            if 'unique' in error_msg and 'username' in error_msg:
                                # Username duplicado, tentar com sufixo
                                username = f"{username_base}{counter}"
                                counter += 1
                                if counter > 100:
                                    print(f"   ⚠️  Não foi possível criar username único para {nome}")
                                    break
                            elif 'unique' in error_msg and 'email' in error_msg:
                                # Email duplicado
                                print(f"   ⚠️  Email duplicado para {nome}: {email}")
                                break
                            else:
                                # Outro erro
                                print(f"   ⚠️  Erro ao migrar {nome}: {e}")
                                break

                print(f"\n   ✅ {migrados_users}/{len(users)} usuários migrados de users")

                # ETAPA 5: Verificar migração
                print("\n5️⃣ Verificando dados migrados...")
                cursor.execute("SELECT COUNT(*) as total FROM users_temp")
                total_migrados = cursor.fetchone()['total']
                print(f"   ✓ Total de {total_migrados} usuários na nova tabela")

                # Mostrar preview
                print("\n📋 Preview dos usuários migrados:")
                cursor.execute("""
                    SELECT id, username, nome_completo, email, is_admin
                    FROM users_temp
                    ORDER BY id
                    LIMIT 10
                """)
                preview = cursor.fetchall()

                print("   ┌─────┬─────────────────┬──────────────────────────┬──────────────────────────┬───────┐")
                print("   │  ID │ USERNAME        │ NOME COMPLETO            │ EMAIL                    │ ADMIN │")
                print("   ├─────┼─────────────────┼──────────────────────────┼──────────────────────────┼───────┤")
                for u in preview:
                    admin_flag = "SIM" if u['is_admin'] else "NÃO"
                    username = str(u['username'])[:15].ljust(15)
                    nome = str(u['nome_completo'])[:24].ljust(24)
                    email = str(u['email'])[:24].ljust(24)
                    print(f"   │ {u['id']:3d} │ {username} │ {nome} │ {email} │ {admin_flag:5s} │")
                print("   └─────┴─────────────────┴──────────────────────────┴──────────────────────────┴───────┘")

                if total_migrados > 10:
                    print(f"   ... e mais {total_migrados - 10} usuários")

                # ETAPA 6: Confirmar substituição
                print("\n" + "=" * 70)
                print("⚠️  ATENÇÃO: Próximo passo irá SUBSTITUIR as tabelas antigas!")
                print("=" * 70)
                print("\nO que será feito:")
                print("   1. Deletar tabelas: auth_users, users")
                print("   2. Renomear users_temp para users")
                print("   3. Criar índices e constraints")
                print("\n📊 Estatísticas:")
                print(f"   • De auth_users → users_temp: {migrados_auth}")
                print(f"   • De users → users_temp: {migrados_users}")
                print(f"   • Total em users_temp: {total_migrados}")

                confirmar = input("\n❓ Confirma a substituição? Digite 'CONFIRMAR' para continuar: ").strip()

                if confirmar == 'CONFIRMAR':
                    print("\n6️⃣ Substituindo tabelas antigas...")

                    # Dropar tabelas antigas
                    cursor.execute("DROP TABLE IF EXISTS password_reset_tokens CASCADE")
                    print("   ✓ password_reset_tokens removida")

                    cursor.execute("DROP TABLE IF EXISTS auth_users CASCADE")
                    print("   ✓ auth_users removida")

                    cursor.execute("DROP TABLE IF EXISTS users CASCADE")
                    print("   ✓ users removida")

                    # Renomear users_temp para users
                    cursor.execute("ALTER TABLE users_temp RENAME TO users")
                    print("   ✓ users_temp renomeada para users")

                    # Criar índices
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)")
                    print("   ✓ Índices criados")

                    # Recriar tabela de tokens
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS password_reset_tokens (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            token VARCHAR(500) NOT NULL,
                            email VARCHAR(200) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            used BOOLEAN DEFAULT FALSE
                        )
                    ''')
                    print("   ✓ password_reset_tokens recriada")

                    # Commit final
                    conn.commit()

                    print("\n" + "=" * 70)
                    print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
                    print("=" * 70)

                    # Salvar lista de usuários com senha padrão
                    if usuarios_com_senha_padrao:
                        print(f"\n📝 {len(usuarios_com_senha_padrao)} usuários receberam senha padrão: {senha_padrao}")

                        with open('usuarios_senha_padrao.txt', 'w', encoding='utf-8') as f:
                            f.write("=" * 70 + "\n")
                            f.write(f"USUÁRIOS COM SENHA PADRÃO: {senha_padrao}\n")
                            f.write("=" * 70 + "\n\n")
                            f.write("⚠️ IMPORTANTE: Estes usuários devem alterar a senha!\n\n")

                            for u in usuarios_com_senha_padrao:
                                linha = f"Nome: {u['nome']:30s} | Username: {u['username']:20s} | Email: {u['email']}\n"
                                f.write(linha)

                        print(f"💾 Lista salva em: usuarios_senha_padrao.txt")

                    print("\n📊 Estatísticas Finais:")
                    print(f"   • Total de usuários: {total_migrados}")
                    print(f"   • De auth_users: {migrados_auth} (mantiveram senha)")
                    print(f"   • De users: {migrados_users} (senha padrão: {senha_padrao})")

                    print("\n🔄 Próximos passos:")
                    print("   1. ✅ Migração concluída!")
                    print("   2. 🧪 Testar login com usuários existentes")
                    print("   3. 📧 Notificar usuários para alterarem senha")
                    print("   4. 🔐 Implementar página de alteração de senha")

                else:
                    conn.rollback()
                    cursor.execute("DROP TABLE IF EXISTS users_temp")
                    print("\n❌ Migração cancelada. Nenhuma alteração foi feita.")
                    print("   A tabela users_temp foi removida.")

        except Exception as e:
            conn.rollback()
            print(f"\n❌ Erro durante migração: {e}")
            import traceback
            traceback.print_exc()

            # Tentar limpar
            try:
                with conn.cursor() as cursor:
                    cursor.execute("DROP TABLE IF EXISTS users_temp")
                conn.commit()
                print("\n🧹 Limpeza realizada. users_temp removida.")
            except:
                pass


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("⚠️  MIGRAÇÃO DO BANCO DE DADOS")
    print("=" * 70)
    print("\nEste script vai:")
    print("   • Unificar as tabelas auth_users e users")
    print("   • Criar uma única tabela 'users' com autenticação")
    print("   • Manter todos os dados existentes")
    print("   • Usuários de 'users' receberão senha padrão: senha123")
    print("\n⚠️  IMPORTANTE:")
    print("   • Faça backup antes de continuar!")
    print("   • A operação é IRREVERSÍVEL após confirmar!")

    continuar = input("\n❓ Deseja continuar? (s/N): ").strip().lower()

    if continuar == 's':
        # Fazer backup automático
        print("\n📦 Fazendo backup automático...")
        from backup_database import fazer_backup

        backup_file = fazer_backup()

        if backup_file:
            print(f"\n✅ Backup criado: {backup_file}")
            print("\n🔄 Iniciando migração...")
            input("\nPressione ENTER para continuar...")
            migrar()
        else:
            print("\n❌ Erro ao criar backup. Migração cancelada.")
    else:
        print("\n❌ Operação cancelada.")