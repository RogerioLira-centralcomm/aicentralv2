"""
Aplicação Flask - AIcentralv2
"""
from flask import Flask
from dotenv import load_dotenv
import os


def create_app():
    """Factory para criar a aplicação Flask"""

    # Carregar variáveis de ambiente
    load_dotenv()

    # Criar aplicação Flask
    app = Flask(__name__)

    print("=" * 70)
    print("🤖 AIcentralv2 v2.0.0")
    print("=" * 70)

    # Configurações básicas
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = os.getenv('DEBUG', 'False') == 'True'

    # Configurações do Banco de Dados
    app.config['DB_HOST'] = os.getenv('DB_HOST', 'localhost')
    app.config['DB_PORT'] = os.getenv('DB_PORT', '5432')
    app.config['DB_NAME'] = os.getenv('DB_NAME', 'aicentralv2')
    app.config['DB_USER'] = os.getenv('DB_USER', 'postgres')
    app.config['DB_PASSWORD'] = os.getenv('DB_PASSWORD', '')

    # Configurações de Email
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

    # Informações do projeto
    app.config['PROJECT_NAME'] = os.getenv('PROJECT_NAME', 'AIcentralv2')
    app.config['VERSION'] = os.getenv('VERSION', '2.0.0')

    # Mostrar configurações carregadas
    print("🔧 Configurações carregadas:")
    print(f"📁 Base directory: {app.root_path}")
    print(f"📁 Templates folder: {app.template_folder}")
    print(f"📁 Static folder: {app.static_folder}")
    print(f"🗄️  Database: {app.config['DB_NAME']}")
    print(f"🖥️  Host: {app.config['DB_HOST']}:{app.config['DB_PORT']}")
    print(f"👤 User: {app.config['DB_USER']}")
    print("=" * 70)

    # Inicializar extensões
    from flask_mail import Mail
    mail = Mail(app)

    # Registrar funções de banco de dados
    from . import db
    app.teardown_appcontext(db.close_db)

    # Inicializar banco de dados
    with app.app_context():
        try:
            db.init_db(app)
            print("✅ Banco de dados inicializado!")
        except Exception as e:
            print(f"⚠️  Aviso ao inicializar banco: {e}")

        # Criar admin padrão
        try:
            if db.criar_usuario_admin_padrao():
                print("✅ Usuário admin padrão criado!")
                print("   📧 Email: admin@admin.com")
                print("   🔐 Senha: admin123")
        except Exception as e:
            print(f"⚠️  Aviso ao criar admin padrão: {e}")

    # Inicializar rotas
    try:
        from . import routes
        routes.init_routes(app)
        print("✅ Rotas registradas com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao registrar rotas: {e}")
        raise

    return app
