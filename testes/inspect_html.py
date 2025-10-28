"""
Verifica o HTML real renderizado no index
"""

import sys
import io

# Redirecionar stderr para evitar erros de encoding
sys.stderr = io.StringIO()

from aicentralv2 import create_app

app = create_app()

# Restaurar stderr
sys.stderr = sys.__stderr__

with app.test_client() as client:
    # Login
    response = client.post('/login', data={
        'email': 'cadu@centralcomm.media',
        'password': 'centralcomm'
    }, follow_redirects=False)
    
    print("\n" + "="*80)
    print("LOGIN")
    print("="*80)
    print(f"Status: {response.status_code}")
    print(f"Redirect para: {response.location}")
    
    # Acessar index
    response = client.get('/', follow_redirects=False)
    
    print("\n" + "="*80)
    print("INDEX")
    print("="*80)
    print(f"Status: {response.status_code}")
    
    html = response.data.decode('utf-8')
    
    # Salvar HTML completo
    with open('rendered_index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\nHTML salvo em: rendered_index.html ({len(html)} bytes)")
    
    # Procurar links admin
    import re
    
    print("\n" + "="*80)
    print("ANALISE DO HTML")
    print("="*80)
    
    # Procurar todos os href
    hrefs = re.findall(r'href="([^"]*)"', html)
    print(f"\nTotal de links encontrados: {len(hrefs)}")
    
    admin_links = [h for h in hrefs if 'admin' in h.lower()]
    print(f"\nLinks admin encontrados: {len(admin_links)}")
    for link in admin_links:
        print(f"  - {link}")
    
    # Procurar especificamente os botões
    print("\n" + "-"*80)
    print("PROCURANDO BOTOES ADMIN")
    print("-"*80)
    
    if 'admin-btn' in html:
        print("OK: Classe 'admin-btn' encontrada")
        
        # Extrair seção dos botões
        start = html.find('admin-buttons')
        if start > 0:
            end = html.find('</div>', start + 1000)
            botoes_html = html[start:end]
            
            print("\nHTML dos botoes:")
            print("-"*80)
            print(botoes_html)
            print("-"*80)
    else:
        print("ERRO: Classe 'admin-btn' NAO encontrada")
    
    # Verificar url_for
    print("\n" + "-"*80)
    print("VERIFICANDO TEMPLATE")
    print("-"*80)
    
    if "{{ url_for(" in html or "{{url_for(" in html:
        print("ERRO: url_for NAO foi processado!")
        print("Template nao esta sendo renderizado")
        
        # Mostrar trecho
        pos = html.find("{{ url_for(")
        if pos < 0:
            pos = html.find("{{url_for(")
        if pos >= 0:
            print("\nTrecho problematico:")
            print(html[max(0, pos-50):pos+100])
    else:
        print("OK: Template renderizado corretamente")
    
    # Procurar texto dos botões
    print("\n" + "-"*80)
    print("TEXTOS DOS BOTOES")
    print("-"*80)
    
    textos = ['Gerenciar Clientes', 'Gerenciar Contatos', 'admin_clientes', 'admin_contatos']
    for texto in textos:
        if texto in html:
            print(f"OK: '{texto}' encontrado")
        else:
            print(f"ERRO: '{texto}' NAO encontrado")
    
    # Verificar se há erros no HTML
    print("\n" + "-"*80)
    print("VERIFICACOES ADICIONAIS")
    print("-"*80)
    
    if '<a href=' in html:
        links_count = html.count('<a href=')
        print(f"OK: {links_count} tags <a> encontradas")
    else:
        print("ERRO: Nenhuma tag <a> encontrada!")
    
    if 'dashboard-container' in html:
        print("OK: Container principal encontrado")
    else:
        print("ERRO: Container principal NAO encontrado")
    
    if len(html) < 500:
        print(f"\nAVISO: HTML muito pequeno ({len(html)} bytes)")
        print("HTML completo:")
        print(html)
    
    print("\n" + "="*80)
    print("CONCLUSAO")
    print("="*80)
    print(f"1. Abra o arquivo: rendered_index.html")
    print(f"2. Procure por 'admin-btn' no arquivo")
    print(f"3. Copie a secao dos botoes aqui")
    print("="*80 + "\n")