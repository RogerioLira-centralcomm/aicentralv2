"""
Inspeciona a sessão real após login
"""

from aicentralv2 import create_app
from flask import session

app = create_app()

with app.test_client() as client:
    with client.session_transaction() as sess:
        print("\n" + "="*80)
        print("📦 SESSÃO ANTES DO LOGIN")
        print("="*80)
        print(dict(sess))
    
    # Login
    client.post('/login', data={
        'email': 'cadu@centralcomm.media',
        'password': 'centralcomm'
    }, follow_redirects=True)
    
    with client.session_transaction() as sess:
        print("\n" + "="*80)
        print("📦 SESSÃO DEPOIS DO LOGIN")
        print("="*80)
        print(dict(sess))
        print()
        
        # Verificar campos específicos
        campos = ['user_id', 'user_name', 'user_email', 'cliente_id', 'cliente_nome', 'cliente_razao_social']
        
        print("📋 CAMPOS ESPERADOS:")
        for campo in campos:
            valor = sess.get(campo)
            status = "✅" if valor else "❌"
            print(f"  {status} {campo}: {valor}")
    
    print("\n" + "="*80 + "\n")