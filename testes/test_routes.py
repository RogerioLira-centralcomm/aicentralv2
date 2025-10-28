"""Testa rotas"""
from aicentralv2 import create_app

app = create_app()

print("\n" + "="*80)
print("ROTAS REGISTRADAS")
print("="*80 + "\n")

routes = []
for rule in app.url_map.iter_rules():
    routes.append({
        'endpoint': rule.endpoint,
        'methods': ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})),
        'path': rule.rule
    })

routes.sort(key=lambda x: x['path'])

for route in routes:
    print(f"{route['methods']:12} {route['path']:40} -> {route['endpoint']}")

print("\n" + "="*80 + "\n")