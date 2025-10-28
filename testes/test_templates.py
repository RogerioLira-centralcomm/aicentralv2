"""
Testa se templates estão corretos
"""
from aicentralv2 import create_app
import os

app = create_app()

print("\n" + "="*80)
print("VERIFICAÇÃO DE TEMPLATES")
print("="*80 + "\n")

templates_dir = os.path.join(app.root_path, 'templates')

required_templates = ['login.html', 'index.html']

for template in required_templates:
    path = os.path.join(templates_dir, template)
    exists = os.path.exists(path)
    
    status = "✓" if exists else "✗"
    print(f"{status} {template}")
    
    if exists:
        size = os.path.getsize(path)
        print(f"  Tamanho: {size} bytes")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            title_line = [line for line in content.split('\n') if '<title>' in line]
            if title_line:
                print(f"  Title: {title_line[0].strip()}")

print("\n" + "="*80)

# Testar rotas
with app.test_client() as client:
    print("\nTESTE DE ROTAS")
    print("-"*80)
    
    # GET /login sem sessão
    response = client.get('/login')
    print(f"GET /login (sem sessão): {response.status_code}")
    print(f"  Template usado: {'login.html' if 'Login' in response.data.decode() else 'OUTRO'}")
    
    # GET / sem sessão (deve redirecionar)
    response = client.get('/', follow_redirects=False)
    print(f"\nGET / (sem sessão): {response.status_code}")
    print(f"  Redirect: {response.location}")

print("\n" + "="*80 + "\n")