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
    app = Flask(__name__, 
                static_url_path='/static',
                static_folder='static')
    app.config.from_object(config_class)

    # Filtro Jinja2 para datas
    def format_datetime(value, fmt='%d/%m/%Y %H:%M'):
        from datetime import datetime
        if not value:
            return ''
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except Exception:
                try:
                    value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    return value
        return value.strftime(fmt)
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.jinja_env.filters['datetime_format'] = format_datetime  # Alias

    def parse_brl(value):
        """Parseia valor monetário BR para float. Aceita '1234.56' e 'R$ 1.234,56'."""
        if not value:
            return 0.0
        s = str(value).strip().replace('R$', '').strip()
        if not s:
            return 0.0
        if ',' in s:
            s = s.replace('.', '').replace(',', '.')
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    def format_brl(value):
        """Formata valor como moeda BR: R$ 1.234,56"""
        num = parse_brl(value)
        if num == 0 and not value:
            return '-'
        formatted = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"

    app.jinja_env.filters['parse_brl'] = parse_brl
    app.jinja_env.filters['format_brl'] = format_brl

    # Configurar logging
    setup_logging(app)
    
    # Inicializar extensões
    mail.init_app(app)
    
    # Importar e registrar funções de banco
    from . import db
    
    # Sinaliza se o CSS compilado existe
    try:
        has_build = os.path.exists(os.path.join(app.static_folder or 'static', 'css', 'tailwind', 'output.css'))
        app.config['HAS_TAILWIND_BUILD'] = has_build
    except Exception:
        app.config['HAS_TAILWIND_BUILD'] = False

    # Tornar config acessível nos templates
    @app.context_processor
    def inject_config():
        from flask import session
        
        # Verificar se usuário é CENTRALCOMM; reutiliza o mesmo contato para o modal Meu perfil
        is_cc_user = False
        perfil_contato = None
        if 'user_id' in session:
            try:
                contato = db.obter_contato_por_id(session['user_id'])
                perfil_contato = contato
                if contato and contato.get('pk_id_tbl_cliente'):
                    cliente = db.obter_cliente_por_id(contato['pk_id_tbl_cliente'])
                    if cliente:
                        is_cc_user = cliente.get('nome_fantasia', '').upper() == 'CENTRALCOMM'
            except Exception:
                pass
        
        return dict(
            APP_CONFIG=app.config,
            is_centralcomm_user=is_cc_user,
            perfil_contato=perfil_contato
        )

    # Registrar teardown (fechar conexão)
    app.teardown_appcontext(db.close_db)
    
    # Inicializar banco de dados
    try:
        db.init_db(app)
        app.logger.info("OK Banco de dados inicializado")
    except Exception as e:
        app.logger.error(f"FALHA Erro ao inicializar banco: {e}")
    
    # Importar e registrar rotas
    try:
        from . import routes
        routes.init_routes(app)
        
        # Registrar blueprint da Inteligência
        from .intelligence_routes.intelligence import bp as intelligence_bp
        app.register_blueprint(intelligence_bp)
        
        # Registrar blueprint do Sales War Room
        from .sales_war_room import bp as sales_war_room_bp
        app.register_blueprint(sales_war_room_bp)

        from .dv360_routes import bp as dv360_bp, pages_bp as dv360_pages_bp
        app.register_blueprint(dv360_bp)
        app.register_blueprint(dv360_pages_bp)
        
        app.logger.info("OK Rotas registradas")
    except Exception as e:
        app.logger.error(f"FALHA Erro ao registrar rotas: {e}")
        raise
    
    # Registrar comandos CLI
    register_commands(app)
    
    app.logger.info("OK Aplicacao criada com sucesso")
    
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
    app.logger.info('OK AIcentral v2 startup')


def register_commands(app):
    """Registra comandos CLI personalizados"""
    import click
    import sys

    @app.cli.command("dv360-verify")
    @click.option(
        "--oauth-only",
        is_flag=True,
        help="Só valida refresh OAuth; não chama list_advertisers.",
    )
    def dv360_verify_command(oauth_only):
        """Valida DV360: .env + OAuth (+ opcionalmente listagem de advertisers). Exit 1 se falhar."""
        from flask import current_app

        from aicentralv2.services.dv360_client import DV360API

        client = DV360API(current_app.config)
        result = client.verify_installation(list_advertisers=not oauth_only)
        for line in result["messages"]:
            print(line)
        if result.get("details"):
            print("--- detalhes (sem segredos) ---")
            import json

            print(json.dumps(result["details"], ensure_ascii=False, indent=2, default=str))
        if result["ok"]:
            print("RESULTADO: OK")
            sys.exit(0)
        print(f"RESULTADO: FALHA (passo: {result.get('step_failed')})")
        sys.exit(1)

    @app.cli.command('init-db')
    def init_db_command():
        """Inicializa o banco de dados"""
        from . import db
        db.init_db(app)
        print('OK Banco de dados inicializado!')
    
    @app.cli.command('check-db')
    def check_db_command():
        """Verifica conexao com banco de dados"""
        from . import db
        if db.check_db_connection():
            print('OK Conexao com banco OK!')
        else:
            print('FALHA Falha na conexao com banco!')
    
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
                print('FALHA Nenhum cliente encontrado! Crie um cliente primeiro.')
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
            print(f'OK Contato criado! ID: {contato_id}')
        except Exception as e:
            print(f'FALHA Erro: {e}')