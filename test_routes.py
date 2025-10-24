from aicentralv2 import create_app

app = create_app()

print("\n" + "="*60)
print("📋 ROTAS REGISTRADAS:")
print("="*60)

for rule in app.url_map.iter_rules():
    if 'setor' in rule.rule or 'contato' in rule.rule:
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        print(f"✅ {rule.endpoint:40s} {methods:20s} {rule.rule}")

print("="*60 + "\n")