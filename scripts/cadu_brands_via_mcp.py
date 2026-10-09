"""Cria as marcas de produto do Cadu e seus projetos pelas ferramentas do MCP interno (mesmo registro do transporte MCP).

Fluxo por produto: brands.create → brands.prepare_logo_upload + envio do logo → brands.update_identity (cores e diretrizes)
→ workspace.create_project (com a marca).
Idempotente: o request_id de cada passo é fixo por produto, então rodar de novo devolve o que já existe.

Uso: .venv/bin/python scripts/cadu_brands_via_mcp.py --account 174 --user 2
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SITE = 'https://workspace.centralcomm.media'  # o site público é um só, com todas as ferramentas
DARK = '#0A0D12'
PRODUCTS = [
    ('workspace', 'Cadu Workspace', '#00A691', 'workspace-192.png', 'conversas, projetos, documentos e marcas da equipe, com o assistente Cadu'),
    ('planner', 'Cadu Planner', '#16BC7B', 'planner-192.png', 'planejamento de mídia, canais, formatos, audiências e o Radar de tendências'),
    ('reports', 'Cadu Reports', '#076EF0', 'connect-192.png', 'conexões com as plataformas de mídia, relatórios e páginas de resultado das campanhas'),
    ('studio', 'Cadu Studio', '#6848EB', 'studio-192.png', 'criação e edição de peças, ilustrações, mockups de sites e vídeo com a identidade de cada marca'),
]
NAMESPACE = uuid.UUID('6f1c7f0e-5b7a-4f43-9b7e-0c4d1a2e3f10')
rid = (lambda *parts: str(uuid.uuid5(NAMESPACE, ':'.join(parts))))


def identity(name, color, does):
    return {
        'primary_color': color, 'secondary_color': DARK,
        'brand_summary': f'{name}: {does}. Faz parte do Cadu, a plataforma de IA da Centralcomm para marketing.',
        'tone_of_voice': 'Direto, confiante e próximo; português do Brasil, frases curtas, sem jargão.',
        'target_audience': 'Times de marketing, agências e veículos que planejam, criam e medem campanhas.',
        'creative_guidelines': ('Interface limpa e técnica: traço único e uniforme, geometria simples, cantos levemente arredondados, '
                                f'muito respiro. A cor {color} entra só como acento sobre neutros (quase preto {DARK}, branco e cinza).'),
        'visual_motifs': ['chevron duplo (dois "<" sobrepostos): o da frente na cor do produto, o de trás quase preto',
                          'formas geométricas simples', 'fundo liso'],
        'mandatory_elements': ['chevron duplo na cor do produto quando a marca aparecer'],
        'forbidden_elements': ['redesenhar ou distorcer o chevron', 'gradientes chamativos', 'sombras pesadas',
                               'estilo infantil ou cartoon', 'cor de outro produto Cadu'],
        'products_services': [name.replace('Cadu ', '')],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--account', type=int, required=True)
    parser.add_argument('--user', type=int, required=True)
    args = parser.parse_args()
    from run import app
    from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
    from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools
    registry = load_builtin_tools()
    with app.test_request_context():
        base = RequestContext(client_id=args.account, user_id=args.user, conversation_id=None, surface='workspace', capabilities=('workspace',))
        for key, name, color, logo, does in PRODUCTS:
            brand = registry.execute('brands.create', {'request_id': rid(key, 'brand'), 'confirmed': True, 'name': name, 'website_url': SITE,
                                                       'sector': 'Tecnologia para marketing', 'official_logo_url': f'{SITE}/static/images/cadu/brand-icons/{logo}'}, base)
            upload = registry.execute('brands.prepare_logo_upload', {'request_id': rid(key, 'logo'), 'brand_id': brand['brand_id']}, base)
            if upload.get('purpose') == 'set_primary_logo':  # o mesmo envio que o endpoint /workspace/mcp/brand-uploads faz
                from werkzeug.datastructures import FileStorage
                from aicentralv2.cadu_workspace import brand_mcp_service
                path = ROOT / 'aicentralv2' / 'static' / 'images' / 'cadu' / 'brand-icons' / logo
                with path.open('rb') as handle:
                    brand_mcp_service.save_logo_upload(base, upload['upload_token'], FileStorage(stream=handle, filename=logo, content_type='image/png'))
            registry.execute('brands.update_identity', {'request_id': rid(key, 'identity'), 'confirmed': True, 'brand_id': brand['brand_id'],
                                                        'changes': identity(name, color, does)}, base)
            project = registry.execute('workspace.create_project', {'request_id': rid(key, 'project'), 'confirmed': True, 'name': f'Interface do {name}',
                                                                     'description': f'Ícones, ilustrações e telas da interface do {name}.', 'color': color,
                                                                     'brand_ref': brand['brand_ref'], 'brand_name': name, 'visibility': 'team'}, base)
            print(json.dumps({'produto': name, 'brand_id': brand['brand_id'], 'criada': brand.get('created'),
                              'logo': (brand.get('site_inspection') or {}).get('explicit_logo') or brand.get('logo_status'),
                              'projeto': project.get('project_ref') or project.get('id')}, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
