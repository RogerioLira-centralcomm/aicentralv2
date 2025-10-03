"""
Script para testar usuários no banco de dados
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app
from aicentralv2 import db


def listar_usuarios():
    """Lista todos os usuários no banco"""
    print("=" * 70)
    print("👥 Usuários Cadastrados no Sistema")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        conn = db.get_db()

        try:
            with conn.cursor() as cursor:
                # Listar todos os usuários de autenticação
                cursor.execute('''
                    SELECT id, username, nome_completo, created_at, updated_at
                    FROM auth_users
                    ORDER BY id
                ''')

                usuarios = cursor.fetchall()

                if not usuarios:
                    print("\n❌ Nenhum usuário encontrado!")
                    print("\n💡 Crie um usuário primeiro:")
                    print(
                        "   python -c \"from aicentralv2 import create_app; from aicentralv2 import db; app = create_app(); app.app_context().push(); db.criar_auth_usuario('admin', 'admin123', 'Administrador')\"")
                    return

                print(f"\n📊 Total de usuários: {len(usuarios)}\n")

                for i, user in enumerate(usuarios, 1):
                    print(f"┌─ Usuário #{i}")
                    print(f"│  ID: {user['id']}")
                    print(f"│  Username: {user['username']}")
                    print(f"│  Nome: {user['nome_completo']}")
                    print(f"│  Criado: {user['created_at']}")
                    print(f"│  Atualizado: {user['updated_at']}")
                    print("└" + "─" * 50)

                print("\n" + "=" * 70)
                print("✅ Listagem concluída!")
                print("=" * 70)

        except Exception as e:
            print(f"\n❌ Erro ao listar usuários: {e}")
            import traceback
            traceback.print_exc()


def testar_recuperacao_senha():
    """Testa o processo de recuperação de senha"""
    print("\n" + "=" * 70)
    print("🔑 Teste de Recuperação de Senha")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        # Listar usuários disponíveis
        conn = db.get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT username FROM auth_users ORDER BY id LIMIT 5')
            usuarios = cursor.fetchall()

            if not usuarios:
                print("\n❌ Nenhum usuário encontrado!")
                return

            print("\n📋 Usuários disponíveis:")
            for i, u in enumerate(usuarios, 1):
                print(f"   {i}. {u['username']}")

        # Pedir username
        print("\n" + "─" * 70)
        username = input("Digite o username para testar (ou Enter para cancelar): ").strip()

        if not username:
            print("❌ Cancelado")
            return

        email = input("Digite um email (qualquer): ").strip()

        if not email:
            email = "teste@example.com"

        print("\n🔍 Testando criar_reset_token...")
        print(f"   Username: {username}")
        print(f"   Email: {email}")

        # Testar criação de token
        token, error = db.criar_reset_token(username, email)

        if error:
            print(f"\n❌ Erro: {error}")
        else:
            print(f"\n✅ Token criado com sucesso!")
            print(f"   Token: {token[:50]}...")

            # Testar verificação do token
            print("\n🔍 Testando verificar_reset_token...")
            token_data, error = db.verificar_reset_token(token)

            if error:
                print(f"❌ Erro ao verificar: {error}")
            else:
                print(f"✅ Token válido!")
                print(f"   Usuário: {token_data['username']}")
                print(f"   Nome: {token_data['nome_completo']}")

                # Perguntar se quer resetar senha
                reset = input("\nDeseja testar reset de senha? (s/N): ").strip().lower()

                if reset == 's':
                    nova_senha = input("Digite a nova senha de teste: ").strip()

                    if nova_senha:
                        print("\n🔐 Testando resetar_senha...")
                        success, error = db.resetar_senha(token, nova_senha)

                        if success:
                            print("✅ Senha resetada com sucesso!")
                            print(f"💡 Agora você pode fazer login com:")
                            print(f"   Username: {username}")
                            print(f"   Senha: {nova_senha}")
                        else:
                            print(f"❌ Erro ao resetar: {error}")


def criar_usuario_teste():
    """Cria um usuário de teste"""
    print("\n" + "=" * 70)
    print("➕ Criar Usuário de Teste")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        username = input("\nUsername (Enter para 'admin'): ").strip() or "admin"
        senha = input("Senha (Enter para 'admin123'): ").strip() or "admin123"
        nome = input("Nome completo (Enter para 'Administrador'): ").strip() or "Administrador"

        print(f"\n📝 Criando usuário:")
        print(f"   Username: {username}")
        print(f"   Senha: {senha}")
        print(f"   Nome: {nome}")

        try:
            user_id = db.criar_auth_usuario(username, senha, nome)
            print(f"\n✅ Usuário criado com sucesso! (ID: {user_id})")
            print(f"\n💡 Você pode fazer login com:")
            print(f"   Username: {username}")
            print(f"   Senha: {senha}")
        except Exception as e:
            print(f"\n❌ Erro ao criar usuário: {e}")


def menu():
    """Menu principal"""
    while True:
        print("\n" + "=" * 70)
        print("🤖 AIcentralv2 - Gerenciamento de Usuários")
        print("=" * 70)
        print("\n1. Listar todos os usuários")
        print("2. Criar usuário de teste")
        print("3. Testar recuperação de senha")
        print("0. Sair")

        opcao = input("\nEscolha uma opção: ").strip()

        if opcao == '1':
            listar_usuarios()
        elif opcao == '2':
            criar_usuario_teste()
        elif opcao == '3':
            testar_recuperacao_senha()
        elif opcao == '0':
            print("\n👋 Até logo!")
            break
        else:
            print("\n❌ Opção inválida!")


if __name__ == '__main__':
    menu()