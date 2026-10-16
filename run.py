"""
AIcentralv2 - Arquivo principal para executar a aplicação
Versão: 2.0.0
"""
import sys
import os
from pathlib import Path

# Adicionar o diretório atual ao path do Python
sys.path.insert(0, str(Path(__file__).parent))

_venv_python = Path(__file__).parent / "venv" / "Scripts" / "python.exe"
if sys.prefix == sys.base_prefix and _venv_python.is_file():
    print("Use o venv do projeto (o Python global não tem as dependências):")
    print(f"  {_venv_python} {Path(__file__).name}")
    print("  ou: .\\venv\\Scripts\\Activate.ps1  &&  python run.py")
    sys.exit(1)

from aicentralv2 import create_app
from aicentralv2.config import DevelopmentConfig, ProductionConfig

# Selecionar configuração por ambiente
env = os.getenv('AICENTRAL_ENV') or os.getenv('FLASK_ENV') or 'development'
config_class = ProductionConfig if env.lower() == 'production' else DevelopmentConfig

# Criar aplicação
app = create_app(config_class)

if __name__ == '__main__':
    print("=" * 70)
    print("AIcentralv2 - Sistema de Gerenciamento")
    print("=" * 70)
    print("Iniciando servidor Flask em modo desenvolvimento...")
    print("Acesse: http://localhost:5000")
    print("Projeto: AIcentralv2")
    print("Login padrao: admin / admin123")
    print("=" * 70)
    
    app.run(debug=app.config.get('DEBUG', False), host='0.0.0.0', port=5000, use_reloader=True, extra_files=['.env'])