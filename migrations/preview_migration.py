"""
Mostra PREVIEW da migração sem executar
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app
import re


def normalizar_username(nome):
    """Converte nome em username"""
    username = nome.lower().replace(' ', '_')
    username = username.replace('ã', 'a').replace('á', 'a').replace('â', 'a')
    username = username.replace('é', 'e').replace('ê', 'e')
    username = username.replace('í', 'i')
    username = username.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    username = username.replace('ú', 'u').replace('ü', 'u')
    username = username.replace('ç', 'c')
    username = re.sub(r'[^a-z0-9_]', '', username)
    return username


print("=" * 70)
print("PREVIEW DA MIGRAÇÃO")
print("=" * 70)

app = create_app()

with app.app_context():
    from aicentralv2 import db

    conn = db.get_db()

    with conn.cursor() as cursor:
        # Ver auth_users
        print("\n1) Tabela: auth_users")
        print("─" * 70)
        cursor.execute("SELECT * FROM auth_users ORDER BY id")
        auth_users = cursor.fetchall()

        if auth_users:
            print(f"{len(auth_users)} registros encontrados:\n")
            print("┌─────┬─────────────────┬──────────────────────────┬────────────┐")
            print("│  ID │ USERNAME        │ NOME COMPLETO            │ AÇÃO       │")
            print("├─────┼─────────────────┼──────────────────────────┼────────────┤")
            for u in auth_users:
                username = str(u['username'])[:15].ljust(15)
                nome = str(u['nome_completo'])[:24].ljust(24)
                print(f"│ {u['id']:3d} │ {username} │ {nome} │ MANTER     │")
            print("└─────┴─────────────────┴──────────────────────────┴────────────┘")
            print("\nOK Usuários mantêm senha original (já tem autenticação)")
        else:
            print("FALHA Nenhum registro encontrado")

        # Ver users
        print("\n2) Tabela: users")
        print("─" * 70)
        cursor.execute("SELECT * FROM users ORDER BY id")
        users = cursor.fetchall()

        if users:
            print(f"{len(users)} registros encontrados:\n")
            print("┌─────┬──────────────────────────┬──────────────────────────┬──────────────────────┐")
            print("│  ID │ NOME (atual)             │ USERNAME (novo)          │ SENHA (nova)         │")
            print("├─────┼──────────────────────────┼──────────────────────────┼──────────────────────┤")
            for u in users:
                nome = str(u['nome'])[:24].ljust(24)
                username = normalizar_username(u['nome'])[:24].ljust(24)
                print(f"│ {u['id']:3d} │ {nome} │ {username} │ senha123             │")
            print("└─────┴──────────────────────────┴──────────────────────────┴──────────────────────┘")
            print("\nATENÇÃO: Estes usuários receberão senha padrão: senha123")
            print("   (Eles devem alterar a senha no primeiro login)")
        else:
            print("FALHA Nenhum registro encontrado")

        # Resumo
        total = len(auth_users) + len(users)
        print("\n" + "=" * 70)
        print("RESUMO DA MIGRAÇÃO")
        print("=" * 70)
        print(f"\nOK Após a migração, teremos 1 tabela única: users")
        print(f"\nTotal de usuários:")
        print(f"   • De auth_users (mantêm senha): {len(auth_users)}")
        print(f"   • De users (senha123): {len(users)}")
        print(f"   • TOTAL: {total} usuários")

        print("\nO que vai acontecer:")
        print("   1. OK Criar tabela users_temp")
        print("   2. OK Copiar dados de auth_users → users_temp")
        print("   3. OK Copiar dados de users → users_temp (com senha123)")
        print("   4. OK Deletar tabelas antigas (auth_users e users)")
        print("   5. OK Renomear users_temp → users")
        print("   6. OK Criar índices e constraints")

        print("\nATENÇÃO:")
        print("   • Operação IRREVERSÍVEL!")
        print("   • Faça backup antes!")
        print("   • Usuários de 'users' precisam alterar senha")

        print("\n" + "=" * 70)
        print("PRÓXIMO PASSO:")
        print("=" * 70)
        print("\nSe tudo estiver correto, execute:")
        print("   python migrate_database_auto.py --confirm")
        print("\nOu se preferir fazer backup manual primeiro:")
        print("   python backup_database.py")
        print("   python migrate_database_auto.py --confirm")