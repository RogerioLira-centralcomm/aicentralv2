"""
Faz backup completo do banco de dados antes da migração
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app
import json
from datetime import datetime


def fazer_backup():
    """Cria backup completo em JSON"""
    print("=" * 70)
    print("💾 BACKUP DO BANCO DE DADOS")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        from aicentralv2 import db
        conn = db.get_db()

        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'auth_users': [],
            'users': [],
            'products': []
        }

        try:
            with conn.cursor() as cursor:
                # Backup auth_users
                print("\n📋 Backup de auth_users...")
                cursor.execute("SELECT * FROM auth_users ORDER BY id")
                auth_users = cursor.fetchall()

                for user in auth_users:
                    backup_data['auth_users'].append({
                        'id': user['id'],
                        'username': user['username'],
                        'password_hash': user['password_hash'],
                        'nome_completo': user['nome_completo'],
                        'created_at': str(user['created_at']),
                        'updated_at': str(user['updated_at'])
                    })
                print(f"   ✓ {len(auth_users)} registros de auth_users")

                # Backup users
                print("\n📋 Backup de users...")
                cursor.execute("SELECT * FROM users ORDER BY id")
                users = cursor.fetchall()

                for user in users:
                    backup_data['users'].append({
                        'id': user['id'],
                        'nome': user['nome'],
                        'email': user['email'],
                        'idade': user['idade'],
                        'created_at': str(user['created_at'])
                    })
                print(f"   ✓ {len(users)} registros de users")

                # Backup products (se existir)
                try:
                    print("\n📋 Backup de products...")
                    cursor.execute("SELECT * FROM products ORDER BY id")
                    products = cursor.fetchall()

                    for product in products:
                        backup_data['products'].append({
                            'id': product['id'],
                            'nome': product['nome'],
                            'preco': float(product['preco']) if product['preco'] else None,
                            'quantidade': product['quantidade'],
                            'created_at': str(product['created_at'])
                        })
                    print(f"   ✓ {len(products)} registros de products")
                except Exception as e:
                    print(f"   ⚠️  Tabela products: {e}")

            # Salvar backup em arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'backup_{timestamp}.json'

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            print("\n" + "=" * 70)
            print(f"✅ Backup salvo em: {filename}")
            print("=" * 70)
            print("\n📊 Resumo:")
            print(f"   • auth_users: {len(backup_data['auth_users'])} registros")
            print(f"   • users: {len(backup_data['users'])} registros")
            print(f"   • products: {len(backup_data['products'])} registros")
            print("\n💡 Guarde este arquivo em local seguro!")

            return filename

        except Exception as e:
            print(f"\n❌ Erro ao fazer backup: {e}")
            import traceback
            traceback.print_exc()
            return None


if __name__ == '__main__':
    fazer_backup()