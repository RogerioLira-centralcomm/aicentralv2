"""
Comparar rota /tbl-estado com /aux-agencia (que funciona)
"""

from aicentralv2 import app

print("🔍 Comparando rotas...\n")
print("=" * 80)

routes_to_check = [
    '/aux-agencia',           # Esta funciona
    '/tbl-estado',            # Esta NÃO funciona
]

with app.app_context():
    for route_path in routes_to_check:
        print(f"\n📍 Rota: {route_path}")
        print("-" * 40)
        
        # Buscar rota
        found = False
        for rule in app.url_map.iter_rules():
            if rule.rule == route_path:
                found = True
                methods = ','.join(rule.methods - {'HEAD', 'OPTIONS'})
                
                print(f"  ✅ ENCONTRADA")
                print(f"     Endpoint: {rule.endpoint}")
                print(f"     Métodos: {methods}")
                
                # Pegar função
                func = app.view_functions.get(rule.endpoint)
                if func:
                    print(f"     Função: {func.__name__}")
                    print(f"     Módulo: {func.__module__}")
                    
                    # Verificar decorators
                    if hasattr(func, '__wrapped__'):
                        print(f"     Wrapped: SIM")
                    else:
                        print(f"     Wrapped: NÃO")
                else:
                    print(f"     ❌ Função NÃO ENCONTRADA!")
                
                break
        
        if not found:
            print(f"  ❌ ROTA NÃO REGISTRADA")

print("\n" + "=" * 80)

# Testar ambas
print("\n🧪 Testando requisições...\n")

with app.test_client() as client:
    # Simular login
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'admin'
        sess['nome_completo'] = 'Admin'
        sess['email'] = 'admin@admin.com'
        sess['is_admin'] = True
    
    for route_path in routes_to_check:
        response = client.get(route_path)
        
        status_emoji = "✅" if response.status_code == 200 else "❌"
        print(f"  {status_emoji} {route_path:30s} → Status: {response.status_code}")

print("\n" + "=" * 80)