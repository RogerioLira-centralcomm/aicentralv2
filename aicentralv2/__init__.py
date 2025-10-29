"""
=====================================================
AICENTRAL V2 - Inicialização da Aplicação
=====================================================
"""

from flask import Flask
from flask_mail import Mail
from .config import Config
import logging
import os

# Instância do Flask-Mail
mail = Mail()


def create_app(config_class=Config):
    """
    Cria e configura a aplicação Flask
    
    Args:
        config_class: Classe de configuração
    
    Returns:
        Flask: Aplicação configurada
    """
    # Criar aplicação
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configurar logging
    setup_logging(app)
    
    # Inicializar extensões
    mail.init_app(app)
    
    # Importar e registrar funções de banco
    from . import db
    
    # Registrar teardown (fechar conexão)
    app.teardown_appcontext(db.close_db)
    
    # Inicializar banco de dados
    try:
        db.init_db(app)
        app.logger.info("✅ Banco de dados inicializado")
    except Exception as e:
        app.logger.error(f"❌ Erro ao inicializar banco: {e}")
    
    # Importar e registrar rotas
    try:
        from . import routes
        routes.init_routes(app)
        app.logger.info("✅ Rotas registradas")
    except Exception as e:
        app.logger.error(f"❌ Erro ao registrar rotas: {e}")
        raise
    
    # Registrar comandos CLI
    register_commands(app)
    
    app.logger.info("✅ Aplicação criada com sucesso")
    
    return app


def setup_logging(app):
    """Configura sistema de logs"""
    import sys
    
    # Configurar formato do log
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    )
    
    # Criar diretório de logs se não existir
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    # Configurar handler para arquivo
    file_handler = logging.FileHandler('logs/aicentral.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Configurar handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Remover handlers existentes
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
    
    # Adicionar novos handlers
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    
    # Configurar codificação do console para UTF-8 no Windows
    if sys.platform.startswith('win'):
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    
    # Registrar início da aplicação
    app.logger.info('✅ AIcentral v2 startup')


def register_commands(app):
    """Registra comandos CLI personalizados"""
    
    @app.cli.command('init-db')
    def init_db_command():
        """Inicializa o banco de dados"""
        from . import db
        db.init_db(app)
        print('✅ Banco de dados inicializado!')
    
    @app.cli.command('check-db')
    def check_db_command():
        """Verifica conexão com banco de dados"""
        from . import db
        if db.check_db_connection():
            print('✅ Conexão com banco OK!')
        else:
            print('❌ Falha na conexão com banco!')
    
    @app.cli.command('create-contact')
    def create_contact_command():
        """Cria um contato de teste"""
        from . import db
        from .db import get_db
        
        # Buscar primeiro cliente
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT id_cliente FROM tbl_cliente LIMIT 1')
            cliente = cursor.fetchone()
            
            if not cliente:
                print('❌ Nenhum cliente encontrado! Crie um cliente primeiro.')
                return
            
            id_cliente = cliente['id_cliente']
        
        # Criar contato
        try:
            contato_id = db.criar_contato(
                nome_completo='Admin Teste',
                email='admin@teste.com',
                senha='admin123',
                pk_id_tbl_cliente=id_cliente,
                telefone='11999999999',
                status=True
            )
            print(f'✅ Contato criado! ID: {contato_id}')
        except Exception as e:
            print(f'❌ Erro: {e}')