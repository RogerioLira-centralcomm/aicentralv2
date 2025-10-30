"""
AIcentralv2 - Arquivo principal para executar a aplicação
Versão: 2.0.0
"""
import sys
from pathlib import Path

# Adicionar o diretório atual ao path do Python
sys.path.insert(0, str(Path(__file__).parent))

from aicentralv2 import create_app

# Criar aplicação
app = create_app()

# Configurar ambiente de desenvolvimento
app.config['ENV'] = 'development'
app.config['DEBUG'] = True

if __name__ == '__main__':
    print("=" * 70)
    print("🤖 AIcentralv2 - Sistema de Gerenciamento")
    print("=" * 70)
    print("🚀 Iniciando servidor Flask em modo desenvolvimento...")
    print("📍 Acesse: http://localhost:5000")
    print("📁 Projeto: AIcentralv2")
    print("🔐 Login padrão: admin / admin123")
    print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)