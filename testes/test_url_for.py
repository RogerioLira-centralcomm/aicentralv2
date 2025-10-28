"""
Testa se url_for está gerando URLs corretas
"""

from aicentralv2 import create_app

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔗 TESTE DE url_for")
    print("="*80 + "\n")
    
    from flask import url_for
    
    urls = [
        'index',
        'login',
        'logout',
        'admin_clientes',
        'admin_contatos',
        'admin_cliente_novo',
        'admin_contato_novo',
    ]
    
    for endpoint in urls:
        try:
            url = url_for(endpoint)
            print(f"✅ {endpoint:25} → {url}")
        except Exception as e:
            print(f"❌ {endpoint:25} → ERRO: {e}")
    
    print("\n" + "="*80 + "\n")