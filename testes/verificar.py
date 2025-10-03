"""
Script para verificar a estrutura do projeto
"""
import os
from pathlib import Path

projeto = Path(__file__).parent / "aicentralv2"

print("=" * 60)
print("🔍 Verificando estrutura do projeto...")
print("=" * 60)

# Verificar arquivos principais
arquivos_necessarios = [
    "__init__.py",
    "db.py",
    "routes.py",
    "models.py",
    "templates/base.html",
    "templates/index.html",
    "templates/user.html",
    "static/css/style.css",
    "static/js/script.js"
]

print("\n📁 Arquivos:")
for arquivo in arquivos_necessarios:
    caminho = projeto / arquivo
    existe = "✅" if caminho.exists() else "❌"
    print(f"{existe} {arquivo}")

# Verificar pastas
print("\n📂 Pastas:")
pastas = ["templates", "static", "static/css", "static/js"]
for pasta in pastas:
    caminho = projeto / pasta
    existe = "✅" if caminho.exists() else "❌"
    print(f"{existe} {pasta}")

print("\n" + "=" * 60)