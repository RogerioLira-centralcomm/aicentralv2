"""
=====================================================
AICENTRAL V2 - Inicialização da Aplicação
=====================================================
"""

from flask import Blueprint, Flask, request, url_for
from flask_mail import Mail
from .config import Config
import hashlib
import logging
import os

# Instância do Flask-Mail
mail = Mail()


def _workspace_asset_version(static_folder, configured_version=""):
    """Return one content fingerprint for every current Cadu interface shell."""
    digest = hashlib.sha256()
    bundle_paths = (
        "cadu_workspace/conversations/react/app.css",
        "cadu_workspace/conversations/react/app.js",
        "cadu_workspace/conversations/react/chat-layout-fixes.css",
        "cadu_auth/app.css",
        "cadu_auth/app.js",
        "css/cadu-auth-motion.css",
        "css/cadu-public-analytics.css",
        "css/cadu-public-forms.css",
        "css/cadu-public-motion.css",
        "css/cadu-workspace-public.css",
        "css/cadu-workspace-legal.css",
        "css/cadu-workspace-legal-media.css",
        "css/cadu-workspace-onboarding.css",
        "css/error-pages.css",
        "js/cadu-public-analytics.js",
        "js/cadu-public-motion.js",
        "js/cadu-workspace-public.js",
        "js/cadu-workspace-onboarding.js",
    )
    found_bundle = False
    for relative_path in bundle_paths:
        absolute_path = os.path.join(static_folder, relative_path)
        if not os.path.isfile(absolute_path):
            continue
        found_bundle = True
        with open(absolute_path, "rb") as bundle_file:
            for chunk in iter(lambda: bundle_file.read(1024 * 1024), b""):
                digest.update(chunk)

    fingerprint = digest.hexdigest()[:12] if found_bundle else "missing"
    return f"{configured_version}-{fingerprint}" if configured_version else fingerprint


def is_erp_nav_item_active(item):
    """Compara endpoint e query string declarados pelo item da navbar ERP."""
    from flask import request

    endpoint = request.endpoint or ""
    endpoint_match = (
        endpoint == item.get("endpoint")
        or endpoint in item.get("match_endpoints", [])
        or (
            item.get("match_prefix")
            and endpoint.startswith(item["match_prefix"])
        )
    )
    if not endpoint_match:
        return False
    for key, expected in item.get("match_args", {}).items():
        if request.args.get(key) != str(expected):
            return False
    for key in item.get("exclude_args", []):
        if request.args.get(key) not in (None, ""):
            return False
    return True


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

    @app.template_global()
    def studio_url(endpoint, **values):
        """Resolve telas de criação no produto Studio, sem acoplar a CentralX.

        As mesmas telas ainda podem ser abertas no backoffice durante a
        transição. Dentro do domínio Studio, porém, todo link interno deve
        apontar para o blueprint próprio e nunca para ``/parametros``.
        """
        if endpoint == "modelagem_design-system":
            from .product_domains import product_url
            return product_url("workspace", "/workspace/app/marcas")
        if request.blueprint == "studio_product":
            from .creative_modeling_routes import STUDIO_SHORT_ROUTES
            if endpoint == "modelagem_criativos":
                return url_for("studio_product.studio_home", **values)
            if endpoint in STUDIO_SHORT_ROUTES:
                page = endpoint.removeprefix("modelagem_")
                return url_for(f"studio_product.studio_{page}", **values)
        blueprint = "studio" if request.blueprint == "studio" else "parametros"
        return url_for(f"{blueprint}.{endpoint}", **values)
    # The same deployment serves multiple hosts. CentralX remains host-only;
    # Cadu products share a dedicated SSO cookie before any request opens a
    # Flask session.
    from .product_domains import ProductSessionInterface
    app.session_interface = ProductSessionInterface()

    from werkzeug.exceptions import RequestEntityTooLarge

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(e):
        from flask import jsonify, request
        max_mb = app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
        msg = (
            f'Upload excede o limite do servidor ({max_mb} MB por requisição). '
            'Reduza a quantidade de arquivos por vez ou aumente MAX_CONTENT_LENGTH_MB no .env.'
        )
        if request.path.startswith('/financeiro/api/'):
            return jsonify({'success': False, 'error': msg}), 413
        return msg, 413

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

    def resolve_existing_foto_url(foto_url):
        """Ignora caminhos /static/... ausentes no disco para evitar 404 no avatar."""
        if not foto_url:
            return None
        if foto_url.startswith(('http://', 'https://')):
            return foto_url
        if foto_url.startswith('/static/'):
            from pathlib import Path
            rel_path = foto_url[len('/static/'):]
            file_path = Path(app.root_path) / 'static' / rel_path
            return foto_url if file_path.is_file() else None
        return foto_url

    # Tornar config acessível nos templates
    @app.context_processor
    def inject_config():
        from flask import session
        from .erp_page_context import resolve_page_context, uses_legacy_daisy
        from .product_domains import product_url
        
        # Verificar se usuário é CENTRALCOMM; reutiliza o mesmo contato para o modal Meu perfil
        is_cc_user = False
        perfil_contato = None
        perfil_google = None
        cadu_nav_credit = None
        if 'user_id' in session:
            try:
                contato = db.obter_contato_por_id(session['user_id'])
                perfil_contato = contato
                # A foto definida no cadastro é a fonte principal. Quando a
                # conta ainda não tem uma, o avatar recebido no SSO Google é
                # mantido apenas na sessão e disponibilizado a todos os shells.
                if perfil_contato:
                    perfil_contato = dict(perfil_contato)
                    perfil_contato['foto_url'] = resolve_existing_foto_url(
                        perfil_contato.get('foto_url')
                    ) or resolve_existing_foto_url(session.get('user_photo_url'))
                try:
                    perfil_google = db.obter_conexao_google_usuario(session['user_id'])
                except Exception:
                    perfil_google = None
                if contato and contato.get('pk_id_tbl_cliente'):
                    cliente = db.obter_cliente_por_id(contato['pk_id_tbl_cliente'])
                    if cliente:
                        is_cc_user = cliente.get('nome_fantasia', '').upper() == 'CENTRALCOMM'
            except Exception:
                pass
            try:
                from .cadu_skills.repository import credit_position
                # Em sessões SSO antigas o vínculo da organização pode não
                # estar serializado no cookie, apesar de estar no contato que
                # já carregamos acima. A navbar deve usar a mesma organização
                # que a conta autenticada, nunca assumir saldo zero.
                # The signed-in contact is the source of truth for Workspace.
                # A carried-over SSO session can contain a previous client id.
                client_id = (perfil_contato or {}).get('pk_id_tbl_cliente') or session.get('cliente_id')
                cadu_nav_credit = credit_position(int(client_id or 0))
            except Exception:
                # O menu continua funcional se o ledger estiver indisponível.
                cadu_nav_credit = None
        
        return dict(
            APP_CONFIG=app.config,
            is_centralcomm_user=is_cc_user,
            perfil_contato=perfil_contato,
            perfil_google=perfil_google,
            cadu_nav_credit=cadu_nav_credit,
            cx_page_context=resolve_page_context(),
            cx_uses_legacy_daisy=uses_legacy_daisy(),
            is_erp_nav_item_active=is_erp_nav_item_active,
            product_url=product_url,
            public_analytics={
                'gtm_id': str(app.config.get('GOOGLE_TAG_MANAGER_ID') or ''),
                'ga4_id': str(app.config.get('GA4_MEASUREMENT_ID') or ''),
                'site_verification': str(app.config.get('GOOGLE_SITE_VERIFICATION') or ''),
            },
            # A content fingerprint changes even when deploy tooling preserves
            # mtimes, preventing browser and CDN caches from retaining an old
            # public, authentication, onboarding, error, or Workspace shell.
            cadu_workspace_asset_version=_workspace_asset_version(
                app.static_folder,
                app.config.get('CADU_WORKSPACE_ASSET_VERSION', ''),
            ),
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
        # Error screens are deliberately outside the CentralX shell. Register
        # them after legacy routes, which historically registered bare pages.
        from .error_pages import register_error_pages
        register_error_pages(app)
        
        # Registrar blueprint da Inteligência
        from .intelligence_routes.intelligence import bp as intelligence_bp
        app.register_blueprint(intelligence_bp)
        
        # Registrar blueprint do CRM
        from .crm import bp as crm_bp
        app.register_blueprint(crm_bp)

        # Registrar blueprint Financeiro / Reembolsos
        from .financeiro import bp as financeiro_bp
        app.register_blueprint(financeiro_bp)

        # Registrar blueprint WhatsApp Comercial
        from .whatsapp import bp as whatsapp_bp
        app.register_blueprint(whatsapp_bp)

        from .dv360_routes import bp as dv360_bp, pages_bp as dv360_pages_bp, parametros_bp
        from .creative_modeling_routes import (
            public_bp as creative_public_bp,
            register_creative_modeling_routes,
            register_studio_product_routes,
            register_modeling_ux_lab,
        )
        from .camadas.routes import register_camadas_routes
        from .integration_settings_routes import register_integration_settings_routes
        from .server_monitor_routes import register_server_monitor_routes
        from .training_studio.routes import register_training_studio_routes

        # Studio owns its public work surface.  Keep the old Parametros
        # registration below for internal CentralX compatibility only.
        studio_bp = Blueprint("studio", __name__, url_prefix="/studio")
        register_creative_modeling_routes(studio_bp)
        register_camadas_routes(studio_bp)
        from .creative_analyzer import register_api_routes as register_creative_analyzer_api
        register_creative_analyzer_api(studio_bp)
        app.register_blueprint(studio_bp)

        studio_product_bp = Blueprint("studio_product", __name__)
        register_studio_product_routes(studio_product_bp)
        from .creative_analyzer import register_product_routes as register_creative_analyzer_product
        register_creative_analyzer_product(studio_product_bp)
        app.register_blueprint(studio_product_bp)

        register_creative_modeling_routes(parametros_bp)
        register_camadas_routes(parametros_bp)
        register_modeling_ux_lab(app)
        register_integration_settings_routes(parametros_bp)
        register_server_monitor_routes(parametros_bp)
        register_training_studio_routes(parametros_bp)
        app.register_blueprint(dv360_bp)
        app.register_blueprint(dv360_pages_bp)
        app.register_blueprint(parametros_bp)
        app.register_blueprint(creative_public_bp)

        from .cotacoes_routes import register_cotacoes_routes
        register_cotacoes_routes(app)

        from .brevo_test_routes import bp as brevo_test_bp
        app.register_blueprint(brevo_test_bp)
        from .brevo_webhook_routes import bp as brevo_webhook_bp
        app.register_blueprint(brevo_webhook_bp)

        from .crm_v3_routes import bp as crm_v3_bp
        app.register_blueprint(crm_v3_bp)

        from .smart_planner.routes import bp as smart_planner_bp
        app.register_blueprint(smart_planner_bp)

        from .places.routes import bp as places_bp
        app.register_blueprint(places_bp)

        from .cadu_skills import bp as cadu_skills_bp
        app.register_blueprint(cadu_skills_bp)

        from .cadu_workspace import bp as cadu_workspace_bp, brand_api_bp as workspace_brand_api_bp
        from .creative_modeling_routes import register_creative_modeling_routes
        register_creative_modeling_routes(workspace_brand_api_bp)
        app.register_blueprint(cadu_workspace_bp)
        app.register_blueprint(workspace_brand_api_bp)

        # Conversations V2 owns a versioned API and an authenticated MCP
        # adapter. Both are backend-only during the parallel rollout.
        from .cadu_workspace.agent_v2.routes import bp as cadu_agent_v2_bp, lab_bp as cadu_agent_v2_lab_bp, public_bp as cadu_public_artifacts_bp
        from .cadu_workspace.mcp import bp as cadu_workspace_mcp_bp
        from .cadu_public_mcp import bp as cadu_public_mcp_bp
        app.register_blueprint(cadu_agent_v2_bp)
        app.register_blueprint(cadu_agent_v2_lab_bp)
        app.register_blueprint(cadu_public_artifacts_bp)
        app.register_blueprint(cadu_workspace_mcp_bp)
        app.register_blueprint(cadu_public_mcp_bp)

        # Compatibility for older Studio shelf bundles still requesting the
        # unprefixed endpoint while their frontend cache is being replaced.
        from .creative_media.studio import studio_library_sessions
        app.add_url_rule(
            '/api/format-lab/studio/library-sessions',
            endpoint='legacy_studio_library_sessions',
            view_func=studio_library_sessions,
            methods=['GET'],
        )

        # Apresentação institucional é uma superfície pública isolada: não
        # herda a navegação, sessão ou chrome operacional do CentralX.
        from .cadu_presentation import bp as cadu_presentation_bp
        app.register_blueprint(cadu_presentation_bp)

        from .cadu_family import register as register_cadu_family
        register_cadu_family(app)

        from .cadu_planner.marketplace import bp as planner_marketplace_bp
        app.register_blueprint(planner_marketplace_bp)

        from .cadu_connect import bp as cadu_connect_bp
        app.register_blueprint(cadu_connect_bp)

        from .cadu_identity import bp as cadu_identity_bp
        app.register_blueprint(cadu_identity_bp)

        from .agent import bp as agent_bp
        app.register_blueprint(agent_bp)

        from .pi_operacao_routes import bp as pi_operacao_bp
        app.register_blueprint(pi_operacao_bp)

        from .pi_financeiro_routes import bp as pi_financeiro_bp
        app.register_blueprint(pi_financeiro_bp)

        from .assinaturas.routes import bp as assinaturas_bp
        app.register_blueprint(assinaturas_bp)

        # Painel administrativo de migrations — permite executar
        # `migrations/*.sql` e `migrations/run_*.py` pelo navegador
        # após o deploy. Restrito a superadmin (auth.py).
        from .admin_migrations_routes import bp as admin_migrations_bp
        app.register_blueprint(admin_migrations_bp)

        from .product_domains import register_product_host_routing
        register_product_host_routing(app)

        # Redirect da rota legada /teste-crm para /crm-v3 (mantido 1-2 sprints)
        from flask import redirect as _redirect, url_for as _url_for

        @app.route('/teste-crm')
        @app.route('/teste-crm/')
        def _legacy_teste_crm_redirect():
            return _redirect(_url_for('crm_v3.crm_v3'), code=302)

        # Alias /crm-legacy → CRM antigo (documenta que /crm agora é considerado legado).
        # O menu principal aponta para /crm-v3; o CRM legado só é linkado para admins/superadmins.
        @app.route('/crm-legacy')
        @app.route('/crm-legacy/')
        def _crm_legacy_alias():
            return _redirect(_url_for('crm.index'), code=302)

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

    @app.cli.command("dv360-oauth")
    def dv360_oauth_command():
        """Gera refresh token com scopes display-video + doubleclickbidmanager (abre o browser)."""
        import subprocess
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        script = root / "scripts" / "dv360_oauth_refresh_token.py"
        r = subprocess.run([sys.executable, str(script)], cwd=str(root))
        raise SystemExit(r.returncode)

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

    @app.cli.command('process-onboarding-followups')
    @click.option('--limit', default=50, show_default=True, type=int)
    def process_onboarding_followups_command(limit):
        """Envia contatos de onboarding que venceram (agende a cada minuto)."""
        from .services.onboarding_comercial import processar_followups_onboarding
        result = processar_followups_onboarding(limit=limit)
        print(f"Onboarding: {result['enviados']} enviado(s), {result['falhas']} falha(s).")
    
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
