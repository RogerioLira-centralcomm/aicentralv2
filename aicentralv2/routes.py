# --- (ao final do arquivo, após a última rota existente) ---

# Removido endpoint direto para compatibilidade com factory
"""
Rotas da Aplicação
"""

from flask import session, redirect, url_for, flash, request, render_template, jsonify, current_app
from functools import wraps
from datetime import datetime, timedelta
import secrets
from aicentralv2 import db, audit
from aicentralv2.email_service import send_password_reset_email, send_password_changed_email
from aicentralv2.services.openrouter_image_extract import extract_fields_from_image_bytes, get_available_models

# Helper para serializar dados para JSON
def serializar_para_json(obj):
    """Converte objetos (incluindo datetime) para formato JSON serializável"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: serializar_para_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serializar_para_json(item) for item in obj]
    if isinstance(obj, (datetime, timedelta)):
        return obj.isoformat()
    if hasattr(obj, '__dict__'):
        return serializar_para_json(obj.__dict__)
    return obj

# Helper para registro de auditoria
def registrar_auditoria(acao, modulo, descricao, registro_id=None, registro_tipo=None, dados_anteriores=None, dados_novos=None):
    """Helper para registrar auditoria automaticamente"""
    try:
        user_id = session.get('user_id')
        if user_id:
            # Capturar IP real mesmo atrás de proxy/load balancer
            ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
                 request.headers.get('X-Real-IP', '').strip() or \
                 request.remote_addr or 'unknown'
            user_agent = request.headers.get('User-Agent', '')[:255]
            
            # Serializar dados para JSON
            dados_anteriores_json = serializar_para_json(dados_anteriores)
            dados_novos_json = serializar_para_json(dados_novos)
            
            db.registrar_audit_log(
                fk_id_usuario=user_id,
                acao=acao,
                modulo=modulo,
                descricao=descricao,
                registro_id=registro_id,
                registro_tipo=registro_tipo,
                ip_address=ip,
                user_agent=user_agent,
                dados_anteriores=dados_anteriores_json,
                dados_novos=dados_novos_json
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao registrar auditoria: {e}")


def login_required(f):
    """Decorator para rotas protegidas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def is_centralcomm_user():
    """Verifica se o usuário logado pertence ao cliente CENTRALCOMM"""
    if 'user_id' not in session:
        return False
    
    try:
        # Buscar informações do usuário
        contato = db.obter_contato_por_id(session['user_id'])
        if not contato:
            return False
        
        # Verificar se tem cliente associado
        if not contato.get('pk_id_tbl_cliente'):
            return False
        
        # Buscar dados do cliente
        cliente = db.obter_cliente_por_id(contato['pk_id_tbl_cliente'])
        if not cliente:
            return False
        
        # Verificar se é CENTRALCOMM
        nome_fantasia = cliente.get('nome_fantasia', '').upper()
        return nome_fantasia == 'CENTRALCOMM'
    except:
        return False


def init_routes(app):
    @app.route('/planos')
    @login_required
    def planos_lista():
        """Lista todos os planos de clientes - Admin ou usuários CENTRALCOMM"""
        from datetime import date
        try:
            # Verificar permissões
            user_type = session.get('user_type', 'client')
            is_admin = user_type in ['admin', 'superadmin']
            is_cc = is_centralcomm_user()
            
            if not is_admin and not is_cc:
                flash('Você não tem permissão para acessar esta página.', 'error')
                return redirect(url_for('index'))
            
            # Filtros
            filtros = {}
            
            if request.args.get('plan_status'):
                filtros['plan_status'] = request.args.get('plan_status')
            
            if request.args.get('plan_type'):
                filtros['plan_type'] = request.args.get('plan_type')
            
            if request.args.get('cliente_id'):
                filtros['cliente_id'] = int(request.args.get('cliente_id'))
            
            planos = db.obter_planos_clientes(filtros)
            
            return render_template('cadu_planos.html',
                                 planos=planos,
                                 filtros=filtros,
                                 today=date.today())
        except Exception as e:
            flash('Erro ao carregar lista de planos.', 'error')
            return redirect(url_for('index'))

    @app.route('/contratos/novo')
    @login_required
    def contrato_novo():
        """Formulário para criar novo contrato/plano"""
        try:
            # Verificar permissões
            user_type = session.get('user_type', 'client')
            is_admin = user_type in ['admin', 'superadmin']
            is_cc = is_centralcomm_user()
            
            if not is_admin and not is_cc:
                flash('Você não tem permissão para acessar esta página.', 'error')
                return redirect(url_for('index'))
            
            # Obter lista de clientes para o select
            clientes = db.obter_clientes_sistema({'status': True})
            if not clientes:
                clientes = []
            
            # Cliente pré-selecionado via query string
            cliente_id = request.args.get('cliente_id', '')
            
            return render_template('plano_form.html',
                                 clientes=clientes,
                                 cliente_id=cliente_id,
                                 modo='novo')
        except Exception as e:
            import logging
            import traceback
            logging.getLogger(__name__).error(f"Erro ao carregar formulário de contrato: {str(e)}")
            logging.getLogger(__name__).error(traceback.format_exc())
            flash(f'Erro ao carregar formulário de contrato: {str(e)}', 'error')
            return redirect(url_for('index'))

    @app.route('/logs')
    @login_required
    def logs_auditoria():
        """Visualizar logs de auditoria"""
        from datetime import datetime, timedelta
        try:
            # Filtros
            filtros = {}
            dias = int(request.args.get('dias', 30))
            
            if request.args.get('modulo'):
                filtros['modulo'] = request.args.get('modulo')
            
            if request.args.get('acao'):
                filtros['acao'] = request.args.get('acao')
            
            if request.args.get('usuario_id'):
                filtros['usuario_id'] = int(request.args.get('usuario_id'))
            
            # Calcular data de início baseado em dias
            data_inicio = datetime.now() - timedelta(days=dias)
            filtros['data_inicio'] = data_inicio
            
            # Paginação
            limit = 50
            offset = int(request.args.get('offset', 0))
            
            # Buscar logs
            logs = db.obter_audit_logs(filtros=filtros, limit=limit, offset=offset)
            
            # Contar total (para paginação)
            total_logs = len(db.obter_audit_logs(filtros=filtros, limit=10000, offset=0))
            
            # Estatísticas
            stats = db.obter_estatisticas_audit_log(dias=dias)
            
            # Lista de usuários para filtro
            usuarios_filtro = db.obter_usuarios_sistema({'status': True})
            
            return render_template('audit_logs.html',
                                 logs=logs,
                                 stats=stats,
                                 filtros={'modulo': request.args.get('modulo', ''),
                                         'acao': request.args.get('acao', ''),
                                         'usuario_id': request.args.get('usuario_id', ''),
                                         'dias': str(dias)},
                                 usuarios_filtro=usuarios_filtro,
                                 limit=limit,
                                 offset=offset,
                                 total_logs=total_logs)
        except Exception as e:
            import traceback
            app.logger.error(f"Erro ao carregar logs: {str(e)}")
            app.logger.error(traceback.format_exc())
            flash(f'Erro ao carregar logs: {str(e)}', 'error')
            return redirect(url_for('index'))

    @app.route('/cadu_categorias')
    @login_required
    def cadu_categorias():
        categorias = db.obter_cadu_categorias()
        return render_template('cadu_categorias.html', categorias=categorias)
    @app.route('/cadu_categorias/novo', methods=['GET', 'POST'])
    @login_required
    def cadu_categorias_novo():
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            slug = request.form.get('slug', '').strip()
            descricao = request.form.get('descricao', '').strip()
            icone = request.form.get('icone', '').strip()
            cor_hex = request.form.get('cor_hex', '').strip()
            ordem_exibicao = request.form.get('ordem_exibicao', 0)
            is_active = request.form.get('is_active') == 'on'
            is_featured = request.form.get('is_featured') == 'on'
            meta_titulo = request.form.get('meta_titulo', '').strip()
            meta_descricao = request.form.get('meta_descricao', '').strip()
            
            if not nome or not slug:
                flash('Preencha o nome e o slug.', 'error')
                return render_template('cadu_categorias_form.html')
            
            novo_id = db.criar_cadu_categoria({
                'nome': nome,
                'slug': slug,
                'descricao': descricao,
                'icone': icone,
                'cor_hex': cor_hex,
                'ordem_exibicao': ordem_exibicao,
                'is_active': is_active,
                'is_featured': is_featured,
                'meta_titulo': meta_titulo,
                'meta_descricao': meta_descricao
            })
            
            # Registro de auditoria
            registrar_auditoria(
                acao='criar',
                modulo='categorias',
                descricao=f'Categoria criada: {nome}',
                registro_id=novo_id,
                registro_tipo='categoria',
                dados_novos={'nome': nome, 'slug': slug}
            )
            
            flash('Categoria criada com sucesso!', 'success')
            return redirect(url_for('cadu_categorias_detalhes', id_categoria=novo_id))
        return render_template('cadu_categorias_form.html')
    
    @app.route('/cadu_categorias/detalhes/<int:id_categoria>')
    @login_required
    def cadu_categorias_detalhes(id_categoria):
        categoria = db.obter_cadu_categoria_por_id(id_categoria)
        if not categoria:
            flash('Categoria não encontrada.', 'error')
            return redirect(url_for('cadu_categorias'))
        return render_template('cadu_categorias_detalhes.html', categoria=categoria)
    
    @app.route('/cadu_categorias/editar/<int:id_categoria>', methods=['GET', 'POST'])
    @login_required
    def cadu_categorias_editar(id_categoria):
        categoria = db.obter_cadu_categoria_por_id(id_categoria)
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            slug = request.form.get('slug', '').strip()
            descricao = request.form.get('descricao', '').strip()
            icone = request.form.get('icone', '').strip()
            cor_hex = request.form.get('cor_hex', '').strip()
            ordem_exibicao = request.form.get('ordem_exibicao', 0)
            is_active = request.form.get('is_active') == 'on'
            is_featured = request.form.get('is_featured') == 'on'
            meta_titulo = request.form.get('meta_titulo', '').strip()
            meta_descricao = request.form.get('meta_descricao', '').strip()
            
            if not nome or not slug:
                flash('Preencha o nome e o slug.', 'error')
                return render_template('cadu_categorias_form.html', categoria=categoria)
            
            db.atualizar_cadu_categoria(id_categoria, {
                'nome': nome,
                'slug': slug,
                'descricao': descricao,
                'icone': icone,
                'cor_hex': cor_hex,
                'ordem_exibicao': ordem_exibicao,
                'is_active': is_active,
                'is_featured': is_featured,
                'meta_titulo': meta_titulo,
                'meta_descricao': meta_descricao
            })
            
            # Registro de auditoria
            registrar_auditoria(
                acao='editar',
                modulo='categorias',
                descricao=f'Categoria editada: {nome}',
                registro_id=id_categoria,
                registro_tipo='categoria',
                dados_anteriores=dict(categoria) if categoria else None,
                dados_novos={'nome': nome, 'slug': slug}
            )
            
            flash('Categoria atualizada com sucesso!', 'success')
            return redirect(url_for('cadu_categorias'))
        return render_template('cadu_categorias_form.html', categoria=categoria)

    # ==================== CADU SUBCATEGORIAS ====================
    
    @app.route('/cadu_subcategorias')
    @login_required
    def cadu_subcategorias():
        categoria_id = request.args.get('categoria_id', type=int)
        subcategorias = db.obter_cadu_subcategorias(categoria_id)
        categorias = db.obter_cadu_categorias()  # Para filtro
        return render_template('cadu_subcategorias.html', 
                             subcategorias=subcategorias, 
                             categorias=categorias,
                             categoria_id_filtro=categoria_id)
    
    @app.route('/cadu_subcategorias/novo', methods=['GET', 'POST'])
    @login_required
    def cadu_subcategorias_novo():
        if request.method == 'POST':
            categoria_id = request.form.get('categoria_id', type=int)
            nome = request.form.get('nome', '').strip()
            slug = request.form.get('slug', '').strip()
            descricao = request.form.get('descricao', '').strip()
            icone = request.form.get('icone', '').strip()
            ordem_exibicao = request.form.get('ordem_exibicao', 0)
            is_active = request.form.get('is_active') == 'on'
            meta_titulo = request.form.get('meta_titulo', '').strip()
            meta_descricao = request.form.get('meta_descricao', '').strip()
            
            if not categoria_id or not nome or not slug:
                flash('Preencha a categoria, nome e slug.', 'error')
                categorias = db.obter_cadu_categorias()
                return render_template('cadu_subcategorias_form.html', categorias=categorias)
            
            novo_id = db.criar_cadu_subcategoria({
                'categoria_id': categoria_id,
                'nome': nome,
                'slug': slug,
                'descricao': descricao,
                'icone': icone,
                'ordem_exibicao': ordem_exibicao,
                'is_active': is_active,
                'meta_titulo': meta_titulo,
                'meta_descricao': meta_descricao
            })
            
            # Registro de auditoria
            registrar_auditoria(
                acao='criar',
                modulo='subcategorias',
                descricao=f'Subcategoria criada: {nome}',
                registro_id=novo_id,
                registro_tipo='subcategoria',
                dados_novos={'nome': nome, 'slug': slug, 'categoria_id': categoria_id}
            )
            
            flash('Subcategoria criada com sucesso!', 'success')
            return redirect(url_for('cadu_subcategorias_detalhes', id_subcategoria=novo_id))
        categorias = db.obter_cadu_categorias()
        return render_template('cadu_subcategorias_form.html', categorias=categorias)
    
    @app.route('/cadu_subcategorias/detalhes/<int:id_subcategoria>')
    @login_required
    def cadu_subcategorias_detalhes(id_subcategoria):
        subcategoria = db.obter_cadu_subcategoria_por_id(id_subcategoria)
        if not subcategoria:
            flash('Subcategoria não encontrada.', 'error')
            return redirect(url_for('cadu_subcategorias'))
        return render_template('cadu_subcategorias_detalhes.html', subcategoria=subcategoria)
    
    @app.route('/cadu_subcategorias/editar/<int:id_subcategoria>', methods=['GET', 'POST'])
    @login_required
    def cadu_subcategorias_editar(id_subcategoria):
        subcategoria = db.obter_cadu_subcategoria_por_id(id_subcategoria)
        if request.method == 'POST':
            categoria_id = request.form.get('categoria_id', type=int)
            nome = request.form.get('nome', '').strip()
            slug = request.form.get('slug', '').strip()
            descricao = request.form.get('descricao', '').strip()
            icone = request.form.get('icone', '').strip()
            ordem_exibicao = request.form.get('ordem_exibicao', 0)
            is_active = request.form.get('is_active') == 'on'
            meta_titulo = request.form.get('meta_titulo', '').strip()
            meta_descricao = request.form.get('meta_descricao', '').strip()
            
            if not categoria_id or not nome or not slug:
                flash('Preencha a categoria, nome e slug.', 'error')
                categorias = db.obter_cadu_categorias()
                return render_template('cadu_subcategorias_form.html', subcategoria=subcategoria, categorias=categorias)
            
            db.atualizar_cadu_subcategoria(id_subcategoria, {
                'categoria_id': categoria_id,
                'nome': nome,
                'slug': slug,
                'descricao': descricao,
                'icone': icone,
                'ordem_exibicao': ordem_exibicao,
                'is_active': is_active,
                'meta_titulo': meta_titulo,
                'meta_descricao': meta_descricao
            })
            
            # Registro de auditoria
            registrar_auditoria(
                acao='editar',
                modulo='subcategorias',
                descricao=f'Subcategoria editada: {nome}',
                registro_id=id_subcategoria,
                registro_tipo='subcategoria',
                dados_anteriores=dict(subcategoria) if subcategoria else None,
                dados_novos={'nome': nome, 'slug': slug, 'categoria_id': categoria_id}
            )
            
            flash('Subcategoria atualizada com sucesso!', 'success')
            return redirect(url_for('cadu_subcategorias'))
        categorias = db.obter_cadu_categorias()
        return render_template('cadu_subcategorias_form.html', subcategoria=subcategoria, categorias=categorias)

    # --- API: Verifica se CNPJ/CPF já existe na base ---
    @app.route('/api/verifica_documento')
    def verifica_documento():
        doc = request.args.get('doc', '').replace('.', '').replace('-', '').replace('/', '')
        tipo = request.args.get('tipo', 'J')
        if not doc or tipo not in ['J', 'F']:
            return jsonify({'existe': False})
        from aicentralv2.db import get_db
        db = get_db()
        # Buscar ignorando máscara (removendo pontos, traços, barras do campo cnpj no banco)
        row = db.execute("""
            SELECT id_cliente, nome_fantasia, razao_social, inscricao_estadual, inscricao_municipal
            FROM tbl_cliente
            WHERE REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '-', ''), '/', '') = %s
        """, (doc,)).fetchone()
        if row:
            return jsonify({
                'existe': True,
                'cliente': {
                    'id_cliente': row['id_cliente'],
                    'nome_fantasia': row['nome_fantasia'],
                    'razao_social': row['razao_social'],
                    'inscricao_estadual': row['inscricao_estadual'],
                    'inscricao_municipal': row['inscricao_municipal']
                }
            })
        else:
            return jsonify({'existe': False})
    """Inicializa todas as rotas"""
    
    # ==================== FAVICON ====================
    
    @app.route('/favicon.ico')
    def favicon():
        return '', 204
    
    # ==================== COMPONENTES ====================
    
    @app.route('/components')
    @login_required
    def components():
        """Página de componentes Tailwind"""
        return render_template('components/tailwind_components.html')
        
    @app.route('/design-system')
    @login_required
    def design_system():
        """Página do Design System"""
        return render_template('design_system.html')

    # ==================== ARQUIVOS ESTÁTICOS ====================
    @app.after_request
    def add_header(response):
        """Adiciona headers para cache e CORS"""
        if 'static' in request.path:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    # ==================== LOGIN ====================
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Página de login"""
        # Se já estiver logado, vai para index
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        # POST - processar login
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            if not email or not password:
                flash('Preencha todos os campos.', 'error')
                return render_template('login_tailwind.html')
            
            user = db.verificar_credenciais(email, password)
            
            if user:
                # Verificar se é um usuário inativo
                if isinstance(user, dict) and user.get('inactive_user'):
                    flash('Usuário inativo. Entre em contato com o administrador.', 'error')
                    return render_template('login_tailwind.html')
                
                session.clear()
                session['user_id'] = user['id_contato_cliente']
                session['user_name'] = user['nome_completo']
                session['user_email'] = user['email']
                session['cliente_id'] = user['pk_id_tbl_cliente']
                session['user_type'] = user.get('user_type', 'client')
                
                app.logger.info(f"Login: {user['nome_completo']} ({email}) - Type: {session['user_type']}")
                flash(f'Bem-vindo, {user["nome_completo"]}!', 'success')
                
                return redirect(url_for('index'))
            else:
                flash('Email ou senha incorretos.', 'error')
        
        # GET - mostrar página de login
        return render_template('login_tailwind.html')
    
    # ==================== LOGOUT ====================
    
    @app.route('/logout')
    def logout():
        """Logout"""
        session.clear()
        flash('Logout realizado!', 'success')
        return redirect(url_for('login'))
    
    # ==================== INDEX ====================
    
    @app.route('/')
    @login_required
    def index():
        """Página inicial - Dashboard"""
        from datetime import date, timedelta
        
        # Valores padrão seguros
        stats = {'total_clientes_ativos': 0, 'total_usuarios': 0, 
                'tokens_mes_atual': 0, 'tokens_mes_anterior': 0,
                'imagens_mes_atual': 0,
                'planos_proximo_limite': 0, 'planos_vencendo': 0,
                'mes_atual': 'N/A', 'mes_anterior': 'N/A'}
        logs_recentes = []
        planos_alerta = []
        planos_vencendo = []
        show_plan_alerts = False
        ALERTA_CONSUMO_TOKEN = 80
        aviso_plan = 20
        
        try:
            # Estatísticas principais
            stats = db.obter_dashboard_stats()
        except Exception as e:
            app.logger.error(f"Erro stats: {str(e)}")
        
        try:
            # Logs recentes
            user_id = session.get('user_id')
            logs_recentes = audit.obter_logs_recentes(limite=10, user_id=user_id)
        except Exception as e:
            app.logger.error(f"Erro logs: {str(e)}")
        
        try:
            # Alertas de planos
            user_type = session.get('user_type', 'client')
            is_admin = user_type in ['admin', 'superadmin']
            is_cc = is_centralcomm_user()
            show_plan_alerts = is_admin or is_cc
            
            if show_plan_alerts:
                todos_planos = db.obter_planos_clientes({'plan_status': 'active'}) or []
                
                # Filtrar planos em alerta
                planos_alerta = [p for p in todos_planos 
                                if p.get('valid_until') and p['valid_until'] >= date.today()
                                and (p.get('tokens_usage_percentage', 0) >= ALERTA_CONSUMO_TOKEN 
                                     or p.get('images_usage_percentage', 0) >= ALERTA_CONSUMO_TOKEN)]
                
                # Filtrar planos vencendo
                data_limite = date.today() + timedelta(days=aviso_plan)
                planos_vencendo = [p for p in todos_planos
                                  if p.get('valid_until') and date.today() <= p['valid_until'] <= data_limite]
        except Exception as e:
            app.logger.error(f"Erro planos: {str(e)}")
        
        return render_template('index_tailwind.html',
                             stats=stats,
                             logs_recentes=logs_recentes,
                             planos_alerta=planos_alerta,
                             planos_vencendo=planos_vencendo,
                             show_plan_alerts=show_plan_alerts,
                             aviso_plan=aviso_plan,
                             today=date.today())
    
    # ==================== FORGOT PASSWORD ====================
    
    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        """Recuperação de senha"""
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()

            if not email:
                flash('Email obrigatório!', 'error')
                return render_template('forgot_password_tailwind.html')

            contato = db.obter_contato_por_email(email)

            if contato:
                # Verificar se o usuário está ativo
                if not contato['status']:
                    app.logger.warning(f"Tentativa de recuperação de senha - Usuário inativo: {email}")
                    flash('Conta inativa. Entre em contato com o administrador.', 'error')
                    return render_template('forgot_password_tailwind.html')
                    
                try:
                    reset_token = secrets.token_urlsafe(32)
                    expires = datetime.utcnow() + timedelta(hours=1)
                    db.atualizar_reset_token(email, reset_token, expires)
                    reset_link = url_for('reset_password', token=reset_token, _external=True)
                    
                    send_password_reset_email(
                        user_email=contato['email'],
                        user_name=contato['nome_completo'],
                        reset_link=reset_link,
                        expires_hours=1
                    )
                    flash('Email enviado!', 'success')
                except Exception as e:
                    app.logger.error(f"Erro: {e}")
                    flash('Erro ao processar.', 'error')
            else:
                flash('Se o email existir, receberá instruções.', 'info')

            return render_template('forgot_password_tailwind.html')

        return render_template('forgot_password_tailwind.html')
    
    @app.route('/clientes/<int:cliente_id>/editar', methods=['GET', 'POST'])
    @login_required
    def cliente_editar(cliente_id):
        """Editar cliente - Redireciona para lista de clientes onde o modal é usado"""
        # GET: redireciona para a página de clientes
        if request.method == 'GET':
            return redirect(url_for('clientes'))
        
        # POST: processa o formulário do modal
        planos = []  # Lista vazia - planos antigos foram removidos
        agencias = db.obter_aux_agencia()
        tipos_cliente = db.obter_tipos_cliente()
        estados = db.obter_estados()
        vendedores_cc = db.obter_vendedores_centralcomm()
        apresentacoes = db.obter_apresentacoes_executivo()
        fluxos = db.obter_fluxos_boas_vindas()
        cliente = db.obter_cliente_por_id(cliente_id)

        # Garante que o vendedor atualmente vinculado apareça na lista, mesmo que esteja inativo ou fora do filtro
        try:
            sel_id = cliente.get('vendas_central_comm') if cliente else None
            if sel_id:
                presente = any(v.get('id_contato_cliente') == sel_id for v in (vendedores_cc or []))
                if not presente:
                    vend_atual = db.obter_contato_por_id(sel_id)
                    if vend_atual:
                        if vendedores_cc is None:
                            vendedores_cc = []
                        vendedores_cc = list(vendedores_cc) + [{
                            'id_contato_cliente': vend_atual.get('id_contato_cliente'),
                            'nome_completo': vend_atual.get('nome_completo') + ' (atual)'
                        }]
        except Exception as _e:
            app.logger.warning(f"Falha ao incluir vendedor atual na lista: {_e}")

        print("\n=== DEBUG EDITAR CLIENTE ===")
        print("Agências:", [{"id": a["id_agencia"], "display": a["display"]} for a in agencias] if agencias else [])
        print("Cliente pk_id_tbl_agencia:", cliente.get("pk_id_tbl_agencia") if cliente else None)
        print("===========================\n")
        
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('clientes'))
        
        if request.method == 'POST':
            try:
                razao_social = request.form.get('razao_social', '').strip()
                nome_fantasia = request.form.get('nome_fantasia', '').strip()
                pessoa = request.form.get('pessoa', 'J').strip()
                cnpj = request.form.get('cnpj', '').strip()
                inscricao_estadual = request.form.get('inscricao_estadual', '').strip() or None
                inscricao_municipal = request.form.get('inscricao_municipal', '').strip() or None
                pk_id_tbl_plano = request.form.get('pk_id_tbl_plano', type=int)
                id_tipo_cliente = request.form.get('id_tipo_cliente', type=int)
                
                # Campos de endereço
                cep = request.form.get('cep', '').strip() or None
                pk_id_aux_estado = request.form.get('pk_id_aux_estado', type=int) or None
                cidade = request.form.get('cidade', '').strip() or None
                bairro = request.form.get('bairro', '').strip() or None
                logradouro = request.form.get('logradouro', '').strip() or None
                numero = request.form.get('numero', '').strip() or None
                complemento = request.form.get('complemento', '').strip() or None
                
                # Obrigatoriedades por tipo de pessoa (edição)
                if pessoa == 'J':
                    if not razao_social or not nome_fantasia:
                        flash('Razão Social e Nome Fantasia obrigatórios!', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                else:
                    if not nome_fantasia:
                        flash('Nome Completo é obrigatório!', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                if not cnpj:
                    flash('CNPJ/CPF é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                if not id_tipo_cliente:
                    flash('Tipo de Cliente é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, apresentacoes=apresentacoes, fluxos=fluxos)
                
                # Validação de CPF quando Pessoa Física
                if pessoa == 'F':
                    if not db.validar_cpf(cnpj):
                        flash('CPF inválido!', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                    # Ajustes padrão para PF
                    if not razao_social:
                        razao_social = 'NÃO REQUERIDO'
                    inscricao_estadual = 'ISENTO'
                    inscricao_municipal = 'ISENTO'

                # Validações de unicidade na edição (exclui o próprio cliente)
                try:
                    if db.cliente_existe_por_cnpj(cnpj, excluir_id=cliente_id):
                        flash('CNPJ já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                    if pessoa == 'J' and db.cliente_existe_por_razao_social(razao_social, excluir_id=cliente_id):
                        flash('Razão Social já cadastrada em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                    if db.cliente_existe_por_nome_fantasia(nome_fantasia, excluir_id=cliente_id):
                        flash('Nome Fantasia já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, percentuais=percentuais)
                except Exception as ve:
                    app.logger.error(f"Erro ao validar duplicidades: {ve}")
                    flash('Erro ao validar unicidade. Tente novamente.', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                pk_id_tbl_agencia = request.form.get('pk_id_tbl_agencia', type=int)
                vendas_central_comm = request.form.get('vendas_central_comm', type=int) or None
                id_fluxo_boas_vindas = request.form.get('id_fluxo_boas_vindas', type=int) or None
                percentual = request.form.get('percentual', '').strip()
                id_centralx = request.form.get('id_centralx', '').strip() or None
                
                if not vendas_central_comm:
                    flash('Vendas CentralComm é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                if not id_fluxo_boas_vindas:
                    flash('Fluxo de Boas-Vindas é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                # Se for pessoa física, força agência 2
                if pessoa == 'F':
                    pk_id_tbl_agencia = 2
                elif not pk_id_tbl_agencia:
                    flash('Agência é obrigatória para Pessoa Jurídica!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)

                # Converter percentual para float se fornecido
                percentual_valor = None
                if percentual:
                    try:
                        # Substituir vírgula por ponto para conversão
                        percentual_normalizado = percentual.replace(',', '.')
                        percentual_valor = float(percentual_normalizado)
                    except ValueError:
                        percentual_valor = None

                if not db.atualizar_cliente(
                    id_cliente=cliente_id,
                    razao_social=razao_social,
                    nome_fantasia=nome_fantasia,
                    id_tipo_cliente=id_tipo_cliente,
                    pessoa=pessoa,
                    cnpj=cnpj,
                    inscricao_estadual=inscricao_estadual,
                    inscricao_municipal=inscricao_municipal,
                    pk_id_aux_agencia=pk_id_tbl_agencia,
                    pk_id_aux_estado=pk_id_aux_estado,
                    vendas_central_comm=vendas_central_comm,
                    id_apresentacao_executivo=request.form.get('id_apresentacao_executivo', type=int) or None,
                    id_fluxo_boas_vindas=id_fluxo_boas_vindas,
                    percentual=percentual_valor,
                    id_centralx=id_centralx,
                    cep=cep,
                    bairro=bairro,
                    cidade=cidade,
                    rua=logradouro,
                    numero=numero,
                    complemento=complemento
                ):
                    flash('Cliente não encontrado!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                # Registro de auditoria
                registrar_auditoria(
                    acao='editar',
                    modulo='clientes',
                    descricao=f'Cliente editado: {nome_fantasia}',
                    registro_id=cliente_id,
                    registro_tipo='cliente',
                    dados_anteriores=dict(cliente),
                    dados_novos={'nome_fantasia': nome_fantasia, 'cnpj': cnpj, 'pessoa': pessoa}
                )
                
                flash(f'Cliente "{nome_fantasia}" atualizado!', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                app.logger.error(f"Erro ao atualizar cliente: {e}")
                flash('Erro ao atualizar.', 'error')
                return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
        
        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)

    # ==================== CLIENTES ====================

    @app.route('/api/cliente/<int:cliente_id>')
    @login_required
    def api_cliente(cliente_id):
        """API para retornar dados do cliente em JSON"""
        try:
            cliente = db.obter_cliente_por_id(cliente_id)
            if not cliente:
                return jsonify({'error': 'Cliente não encontrado'}), 404
            return jsonify(cliente)
        except Exception as e:
            app.logger.error(f"Erro ao buscar cliente {cliente_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cliente/<int:cliente_id>/contatos')
    @login_required
    def api_cliente_contatos(cliente_id):
        """API para retornar contatos do cliente em JSON"""
        try:
            contatos = db.obter_contatos_por_cliente(cliente_id)
            return jsonify(contatos or [])
        except Exception as e:
            app.logger.error(f"Erro ao buscar contatos do cliente {cliente_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/contato/<int:contato_id>')
    @login_required
    def api_contato_detalhes(contato_id):
        """API para retornar detalhes de um contato"""
        try:
            contato = db.obter_contato_por_id(contato_id)
            if not contato:
                return jsonify({'error': 'Contato não encontrado'}), 404
            return jsonify(dict(contato))
        except Exception as e:
            app.logger.error(f"Erro ao buscar contato {contato_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cliente/<int:cliente_id>/criar-contato', methods=['POST'])
    @login_required
    def api_criar_contato_cliente(cliente_id):
        """API para criar contato do cliente"""
        try:
            data = request.get_json()
            
            nome_completo = data.get('nome_completo', '').strip()
            email = data.get('email', '').strip().lower()
            senha = data.get('senha', '').strip()
            telefone = data.get('telefone', '').strip() or None
            pk_id_aux_setor = data.get('pk_id_aux_setor', type=int)
            pk_id_tbl_cargo = data.get('pk_id_tbl_cargo', type=int)
            cohorts = data.get('cohorts', 1)
            user_type = data.get('user_type', 'client')
            
            # Validação de campos obrigatórios
            if not all([nome_completo, email, senha, pk_id_aux_setor, pk_id_tbl_cargo]):
                return jsonify({'success': False, 'message': 'Preencha todos os campos obrigatórios!'}), 400
            
            # Validar se cargo pertence ao setor
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1 FROM tbl_cargo_contato WHERE id_cargo_contato = %s AND pk_id_aux_setor = %s', 
                             (pk_id_tbl_cargo, pk_id_aux_setor))
                if cursor.fetchone() is None:
                    return jsonify({'success': False, 'message': 'Cargo não pertence ao setor selecionado!'}), 400
            
            # Criar contato
            contato_id = db.criar_contato(
                nome_completo=nome_completo,
                email=email,
                senha=senha,
                pk_id_tbl_cliente=cliente_id,
                pk_id_tbl_cargo=pk_id_tbl_cargo,
                pk_id_tbl_setor=pk_id_aux_setor,
                telefone=telefone,
                cohorts=cohorts,
                user_type=user_type
            )
            
            # Registro de auditoria
            registrar_auditoria(
                acao='CREATE',
                modulo='CONTATOS',
                descricao=f'Criado contato {nome_completo} para cliente ID {cliente_id}',
                registro_id=contato_id,
                registro_tipo='contato',
                dados_novos={
                    'nome_completo': nome_completo,
                    'email': email,
                    'cliente_id': cliente_id
                }
            )
            
            return jsonify({'success': True, 'message': f'Contato "{nome_completo}" criado com sucesso!', 'contato_id': contato_id})
            
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
        except Exception as e:
            app.logger.error(f"Erro ao criar contato para cliente {cliente_id}: {e}")
            return jsonify({'success': False, 'message': f'Erro ao criar contato: {str(e)}'}), 500

    @app.route('/api/contato/<int:contato_id>/editar', methods=['PUT'])
    @login_required
    def api_editar_contato(contato_id):
        """API para editar contato"""
        try:
            data = request.get_json()
            
            nome_completo = data.get('nome_completo', '').strip()
            email = data.get('email', '').strip().lower()
            telefone = data.get('telefone', '').strip() or None
            pk_id_aux_setor = data.get('pk_id_aux_setor')
            pk_id_tbl_cargo = data.get('pk_id_tbl_cargo')
            nova_senha = data.get('nova_senha', '').strip()
            cohorts = data.get('cohorts', 1)
            user_type = data.get('user_type', 'client')
            
            # Validação de campos obrigatórios
            if not all([nome_completo, email, pk_id_aux_setor, pk_id_tbl_cargo]):
                return jsonify({'success': False, 'message': 'Preencha todos os campos obrigatórios!'}), 400
            
            # Validar se cargo pertence ao setor
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1 FROM tbl_cargo_contato WHERE id_cargo_contato = %s AND pk_id_aux_setor = %s', 
                             (pk_id_tbl_cargo, pk_id_aux_setor))
                if cursor.fetchone() is None:
                    return jsonify({'success': False, 'message': 'Cargo não pertence ao setor selecionado!'}), 400
                
                # Verificar duplicação de email
                cursor.execute('''
                    SELECT id_contato_cliente 
                    FROM tbl_contato_cliente 
                    WHERE LOWER(email) = %s AND id_contato_cliente != %s
                ''', (email, contato_id))
                
                if cursor.fetchone():
                    return jsonify({'success': False, 'message': 'Email já cadastrado!'}), 400
                
                # Buscar dados anteriores para auditoria
                contato_anterior = db.obter_contato_por_id(contato_id)
                
                # Atualizar contato
                cursor.execute('''
                    UPDATE tbl_contato_cliente
                    SET nome_completo = %s, email = %s, telefone = %s, cohorts = %s,
                        pk_id_tbl_cargo = %s, pk_id_tbl_setor = %s,
                        user_type = %s,
                        data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_contato_cliente = %s
                ''', (nome_completo, email, telefone, cohorts,
                      pk_id_tbl_cargo, pk_id_aux_setor, user_type,
                      contato_id))
            
            # Atualizar senha se fornecida
            if nova_senha:
                db.atualizar_senha_contato(contato_id, nova_senha)
            
            conn.commit()
            
            # Registro de auditoria
            registrar_auditoria(
                acao='UPDATE',
                modulo='CONTATOS',
                descricao=f'Editado contato {nome_completo}',
                registro_id=contato_id,
                registro_tipo='contato',
                dados_anteriores=dict(contato_anterior) if contato_anterior else None,
                dados_novos={
                    'nome_completo': nome_completo,
                    'email': email,
                    'user_type': user_type
                }
            )
            
            return jsonify({'success': True, 'message': f'Contato "{nome_completo}" atualizado com sucesso!'})
            
        except Exception as e:
            if conn:
                conn.rollback()
            app.logger.error(f"Erro ao editar contato {contato_id}: {e}")
            return jsonify({'success': False, 'message': f'Erro ao editar contato: {str(e)}'}), 500

    @app.route('/api/contato/<int:contato_id>/toggle-status', methods=['POST'])
    @login_required
    def api_toggle_status_contato(contato_id):
        """API para ativar/desativar contato"""
        try:
            # Verificar se não está tentando desativar a si mesmo
            if contato_id == session.get('user_id'):
                return jsonify({'success': False, 'message': 'Você não pode desativar seu próprio usuário!'}), 400
            
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('SELECT status, nome_completo FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (contato_id,))
                result = cursor.fetchone()
                
                if not result:
                    return jsonify({'success': False, 'message': 'Contato não encontrado!'}), 404
                
                novo_status = not result['status']
                cursor.execute('''
                    UPDATE tbl_contato_cliente
                    SET status = %s, data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_contato_cliente = %s
                ''', (novo_status, contato_id))
                conn.commit()
                
                # Registro de auditoria
                registrar_auditoria(
                    acao='UPDATE',
                    modulo='CONTATOS',
                    descricao=f'Status alterado para {"ativo" if novo_status else "inativo"}',
                    registro_id=contato_id,
                    registro_tipo='contato',
                    dados_anteriores={'status': result['status']},
                    dados_novos={'status': novo_status}
                )
                
                return jsonify({
                    'success': True, 
                    'message': f'Contato {"ativado" if novo_status else "desativado"} com sucesso!',
                    'novo_status': novo_status
                })
                
        except Exception as e:
            app.logger.error(f"Erro ao alterar status do contato {contato_id}: {e}")
            return jsonify({'success': False, 'message': f'Erro ao alterar status: {str(e)}'}), 500

    @app.route('/api/contato/<int:contato_id>/deletar', methods=['DELETE'])
    @login_required
    def api_deletar_contato(contato_id):
        """API para deletar contato"""
        try:
            # Verificar se não está tentando deletar a si mesmo
            if contato_id == session.get('user_id'):
                return jsonify({'success': False, 'message': 'Você não pode deletar sua própria conta!'}), 400
            
            contato = db.obter_contato_por_id(contato_id)
            
            if not contato:
                return jsonify({'success': False, 'message': 'Contato não encontrado!'}), 404
            
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (contato_id,))
            conn.commit()
            
            # Registro de auditoria
            registrar_auditoria(
                acao='DELETE',
                modulo='CONTATOS',
                descricao=f'Usuário deletado: {contato["nome_completo"]}',
                registro_id=contato_id,
                registro_tipo='contato',
                dados_anteriores=dict(contato)
            )
            
            return jsonify({'success': True, 'message': f'Contato "{contato["nome_completo"]}" deletado com sucesso!'})
            
        except Exception as e:
            app.logger.error(f"Erro ao deletar contato {contato_id}: {e}")
            return jsonify({'success': False, 'message': f'Erro ao deletar contato: {str(e)}'}), 500

    @app.route('/api/setor/<int:setor_id>/cargos')
    @login_required
    def api_cargos_por_setor(setor_id):
        """API para retornar cargos de um setor"""
        try:
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id_cargo_contato, descricao 
                    FROM tbl_cargo_contato 
                    WHERE pk_id_aux_setor = %s 
                    ORDER BY descricao
                ''', (setor_id,))
                cargos = cursor.fetchall()
            return jsonify(cargos or [])
        except Exception as e:
            app.logger.error(f"Erro ao buscar cargos do setor {setor_id}: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cliente/<int:cliente_id>/criar-plano', methods=['POST'])
    @login_required
    def api_criar_plano_cliente(cliente_id):
        """API para criar um plano para o cliente"""
        try:
            user_id = session.get('user_id')
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
            
            # Extrair dados do plano
            plan_type = data.get('plan_type')
            tokens_monthly = data.get('tokens_monthly_limit')
            image_credits = data.get('image_credits_monthly')
            max_users = data.get('max_users')
            valid_months = data.get('valid_months', 3)
            
            if not all([plan_type, tokens_monthly, image_credits, max_users]):
                return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
            
            # Verificar se já existe plano ativo com o mesmo tipo para este cliente
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id FROM cadu_client_plans 
                    WHERE id_cliente = %s 
                    AND plan_type = %s 
                    AND plan_status = 'active'
                ''', (cliente_id, plan_type))
                plano_existente = cursor.fetchone()
                
                if plano_existente:
                    return jsonify({
                        'success': False, 
                        'error': f'Já existe um plano {plan_type} ativo para este cliente'
                    }), 400
            
            # Calcular data de validade
            valid_from = datetime.now()
            valid_until = datetime.now() + timedelta(days=30 * valid_months)
            
            # Preparar dados do plano
            plan_data = {
                'id_cliente': cliente_id,
                'plan_type': plan_type,
                'tokens_monthly_limit': tokens_monthly,
                'image_credits_monthly': image_credits,
                'max_users': max_users,
                'features': '{"all_modes": true, "unlimited_docs": true, "unlimited_conversations": true}',
                'plan_status': 'active',
                'valid_from': valid_from,
                'valid_until': valid_until,
                'plan_start_date': valid_from,
                'plan_end_date': valid_until
            }
            
            # Criar plano usando função do db
            plano_id = db.criar_client_plan(plan_data)
            
            if plano_id:
                # Registrar auditoria
                registrar_auditoria(
                    acao='CREATE',
                    modulo='PLANOS',
                    descricao=f'Criado plano {plan_type} para cliente {cliente_id}',
                    registro_id=plano_id,
                    registro_tipo='client_plan',
                    dados_novos={
                        'cliente_id': cliente_id,
                        'plan_type': plan_type,
                        'tokens_monthly_limit': tokens_monthly,
                        'image_credits_monthly': image_credits,
                        'max_users': max_users,
                        'valid_until': valid_until.isoformat()
                    }
                )
                
                return jsonify({'success': True, 'plano_id': plano_id})
            else:
                return jsonify({'success': False, 'error': 'Erro ao criar plano'}), 500
                
        except Exception as e:
            app.logger.error(f"Erro ao criar plano para cliente {cliente_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/cliente/<int:cliente_id>/planos', methods=['GET'])
    @login_required
    def api_obter_planos_cliente(cliente_id):
        """API para obter os planos de um cliente específico"""
        try:
            # Buscar planos do cliente
            planos = db.obter_planos_clientes({'cliente_id': cliente_id})
            
            # Formatar resposta
            planos_formatados = []
            for plano in planos:
                planos_formatados.append({
                    'id': plano.get('id'),
                    'plan_type': plano.get('plan_type'),
                    'plan_status': plano.get('plan_status'),
                    'tokens_monthly_limit': plano.get('tokens_monthly_limit'),
                    'tokens_used_current_month': plano.get('tokens_used_current_month') or 0,
                    'tokens_usage_percentage': plano.get('tokens_usage_percentage') or 0,
                    'image_credits_monthly': plano.get('image_credits_monthly'),
                    'image_credits_used_current_month': plano.get('image_credits_used_current_month') or 0,
                    'images_usage_percentage': plano.get('images_usage_percentage') or 0,
                    'max_users': plano.get('max_users'),
                    'valid_until': plano.get('valid_until').isoformat() if plano.get('valid_until') else None,
                    'valid_from': plano.get('valid_from').isoformat() if plano.get('valid_from') else None
                })
            
            return jsonify({'success': True, 'planos': planos_formatados})
            
        except Exception as e:
            app.logger.error(f"Erro ao obter planos do cliente {cliente_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/plano/<int:plano_id>/toggle-status', methods=['POST'])
    @login_required
    def api_toggle_plano_status(plano_id):
        """API para alternar o status de um plano entre active e cancelled"""
        try:
            conn = db.get_db()
            cursor = conn.cursor()
            
            # Buscar status atual do plano
            cursor.execute("SELECT plan_status FROM cadu_client_plans WHERE id = %s", (plano_id,))
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'success': False, 'error': 'Plano não encontrado'}), 404
            
            status_atual = result['plan_status']
            
            # Alternar status: active <-> cancelled
            novo_status = 'cancelled' if status_atual == 'active' else 'active'
            
            # Atualizar no banco
            cursor.execute(
                "UPDATE cadu_client_plans SET plan_status = %s WHERE id = %s",
                (novo_status, plano_id)
            )
            conn.commit()
            
            return jsonify({'success': True, 'novo_status': novo_status})
            
        except Exception as e:
            app.logger.error(f"Erro ao alterar status do plano {plano_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==================== ROTAS DE INVITES ====================
    
    @app.route('/api/cliente/<int:cliente_id>/invites', methods=['GET'])
    @login_required
    def api_obter_invites_cliente(cliente_id):
        """API para obter convites de um cliente"""
        try:
            invites = db.obter_invites_cliente(cliente_id)
            return jsonify(invites or [])
        except Exception as e:
            app.logger.error(f"Erro ao obter invites do cliente {cliente_id}: {e}")
            return jsonify([]), 200

    @app.route('/api/cliente/<int:cliente_id>/invites', methods=['POST'])
    @login_required
    def api_criar_invite(cliente_id):
        """API para criar novo convite"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            role = data.get('role', 'member')
            
            if not email:
                return jsonify({'success': False, 'message': 'Email é obrigatório!'}), 400
            
            # Validar se email já está cadastrado
            if db.email_existe(email):
                return jsonify({'success': False, 'message': 'Este email já está cadastrado no sistema!'}), 400
            
            # Pegar ID do usuário logado (garantido pelo @login_required)
            invited_by = session.get('user_id')
            
            # Criar convite
            invite_id = db.criar_invite(cliente_id, invited_by, email, role)
            
            if invite_id:
                # Registro de auditoria
                registrar_auditoria(
                    acao='criar',
                    modulo='invites',
                    descricao=f'Convite enviado para {email} (role: {role})',
                    registro_id=invite_id,
                    registro_tipo='invite',
                    dados_novos={'email': email, 'role': role, 'cliente_id': cliente_id}
                )
                
                # TODO: Enviar email com link de convite
                return jsonify({
                    'success': True, 
                    'message': f'Convite enviado para {email}!',
                    'invite_id': invite_id
                })
            else:
                return jsonify({'success': False, 'message': 'Erro ao criar convite!'}), 500
                
        except Exception as e:
            app.logger.error(f"Erro ao criar invite: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/invites/<int:invite_id>/resend', methods=['POST'])
    @login_required
    def api_reenviar_invite(invite_id):
        """API para reenviar convite"""
        try:
            if db.reenviar_invite(invite_id):
                # Registro de auditoria
                registrar_auditoria(
                    acao='reenviar',
                    modulo='invites',
                    descricao=f'Convite reenviado (ID: {invite_id})',
                    registro_id=invite_id,
                    registro_tipo='invite'
                )
                
                # TODO: Reenviar email
                return jsonify({'success': True, 'message': 'Convite reenviado com sucesso!'})
            else:
                return jsonify({'success': False, 'message': 'Convite não encontrado ou já foi aceito!'}), 404
        except Exception as e:
            app.logger.error(f"Erro ao reenviar invite {invite_id}: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/invites/<int:invite_id>', methods=['DELETE'])
    @login_required
    def api_cancelar_invite(invite_id):
        """API para cancelar convite"""
        try:
            if db.cancelar_invite(invite_id):
                # Registro de auditoria
                registrar_auditoria(
                    acao='cancelar',
                    modulo='invites',
                    descricao=f'Convite cancelado (ID: {invite_id})',
                    registro_id=invite_id,
                    registro_tipo='invite'
                )
                
                return jsonify({'success': True, 'message': 'Convite cancelado com sucesso!'})
            else:
                return jsonify({'success': False, 'message': 'Convite não encontrado!'}), 404
        except Exception as e:
            app.logger.error(f"Erro ao cancelar invite {invite_id}: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # ==================== FIM ROTAS DE INVITES ====================

    # ROTA ANTIGA - DESABILITADA - usar cotacoes_list() abaixo
    # @app.route('/cotacoes')
    # @login_required
    # def cotacoes():
    #     """Lista de cotações com filtros"""
    #     try:
    #         # Obter filtros
    #         vendedor_id = request.args.get('vendedor', type=int)
    #         cliente_id = request.args.get('cliente', type=int)
    #         status_id = request.args.get('status', type=int)
    #         nome_campanha = request.args.get('campanha', '').strip()
    #         
    #         # Buscar cotações com filtros
    #         cotacoes_list = db.obter_cotacoes_filtradas(
    #             vendedor_id=vendedor_id,
    #             cliente_id=cliente_id,
    #             status_id=status_id,
    #             nome_campanha=nome_campanha or None
    #         )
    #         
    #         # Buscar dados para os dropdowns
    #         vendedores = db.obter_vendedores_centralcomm()
    #         clientes_list = db.obter_clientes_sistema(
    #             filtros={'status': True},
    #             vendedor_id=vendedor_id
    #         )
    #         status_list = db.obter_status_cotacoes()
    #         
    #         return render_template('cadu_cotacoes.html',
    #             cotacoes=cotacoes_list,
    #             vendedores=vendedores,
    #             clientes=clientes_list,
    #             status_list=status_list,
    #             filtro_vendedor=vendedor_id,
    #             filtro_cliente=cliente_id,
    #             filtro_status=status_id,
    #             filtro_campanha=nome_campanha
    #         )
    #     except Exception as e:
    #         app.logger.error(f"Erro ao listar cotações: {e}")
    #         flash('Erro ao carregar cotações!', 'error')
    #         return render_template('cadu_cotacoes.html', cotacoes=[], vendedores=[], clientes=[], status_list=[])

    @app.route('/clientes')
    @login_required
    def clientes():
        """Lista de clientes com estatísticas e filtro opcional por executivo."""
        try:
            conn = db.get_db()
            if not conn:
                raise Exception("Falha na conexão com o banco de dados")

            with conn.cursor() as cursor:
                # Estatísticas por tipo de pessoa
                cursor.execute(
                    """
                    SELECT 
                        pessoa,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = TRUE THEN 1 ELSE 0 END) as ativos
                    FROM tbl_cliente 
                    GROUP BY pessoa
                    """
                )
                pessoas = cursor.fetchall() or []

                pessoas_stats = {
                    'fisica': {'total': 0, 'ativos': 0},
                    'juridica': {'total': 0, 'ativos': 0}
                }
                for p in pessoas:
                    if p.get('pessoa') == 'F':
                        pessoas_stats['fisica'] = {'total': p.get('total', 0), 'ativos': p.get('ativos', 0)}
                    elif p.get('pessoa') == 'J':
                        pessoas_stats['juridica'] = {'total': p.get('total', 0), 'ativos': p.get('ativos', 0)}

                # Filtro opcional por executivo (vendas_central_comm)
                filtro_vendedor = request.args.get('vendas_central_comm', type=int)

                query = (
                    """
                    SELECT 
                        c.id_cliente,
                        c.razao_social,
                        c.nome_fantasia,
                        c.cnpj,
                        c.status,
                        c.pessoa,
                        c.pk_id_tbl_agencia as pk_id_aux_agencia,
                        ag.display as agencia_display,
                        ag.key as agencia_key,
                        (
                            SELECT COUNT(*) 
                            FROM tbl_contato_cliente ct 
                            WHERE ct.pk_id_tbl_cliente = c.id_cliente
                        ) as total_contatos,
                        (
                            SELECT COUNT(*) 
                            FROM cadu_client_plans cp 
                            WHERE cp.id_cliente = c.id_cliente 
                            AND cp.plan_status = 'active'
                            AND (cp.valid_until IS NULL OR cp.valid_until >= CURRENT_DATE)
                        ) as planos_ativos,
                        vend.id_contato_cliente as executivo_id,
                        vend.nome_completo as executivo_nome
                    FROM tbl_cliente c
                    LEFT JOIN tbl_agencia ag ON c.pk_id_tbl_agencia = ag.id_agencia
                    LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = c.vendas_central_comm
                    """
                )
                params = []
                if filtro_vendedor:
                    query += " WHERE c.vendas_central_comm = %s"
                    params.append(filtro_vendedor)
                query += " ORDER BY c.id_cliente DESC"

                cursor.execute(query, tuple(params) if params else None)
                resultados = cursor.fetchall() or []

                lista = []
                for row in resultados:
                    lista.append({
                        'id_cliente': row.get('id_cliente'),
                        'razao_social': row.get('razao_social') or '',
                        'nome_fantasia': row.get('nome_fantasia') or '',
                        'cnpj': row.get('cnpj') or '',
                        'status': bool(row.get('status')) if row.get('status') is not None else False,
                        'total_contatos': row.get('total_contatos') or 0,
                        'planos_ativos': row.get('planos_ativos') or 0,
                        'pk_id_aux_agencia': row.get('pk_id_aux_agencia'),
                        'agencia_display': row.get('agencia_display'),
                        'agencia_key': row.get('agencia_key'),
                        'executivo_id': row.get('executivo_id'),
                        'executivo_nome': row.get('executivo_nome'),
                        'tipo_pessoa': 'Física' if row.get('pessoa') == 'F' else 'Jurídica' if row.get('pessoa') == 'J' else '-',
                    })

            try:
                vendedores_cc = db.obter_vendedores_centralcomm()
            except Exception as _e:
                app.logger.warning(f"Falha ao obter vendedores CentralComm: {_e}")
                vendedores_cc = []

            # Dados para o modal de criação
            agencias = db.obter_aux_agencia()
            tipos_cliente = db.obter_tipos_cliente()
            estados = db.obter_estados()
            fluxos = db.obter_fluxos_boas_vindas()
            apresentacoes = db.obter_apresentacoes_executivo()
            setores = db.obter_setores()

            return render_template(
                'clientes.html',
                clientes=lista,
                pessoas_stats=pessoas_stats,
                vendedores_cc=vendedores_cc,
                filtro_vendas_central_comm=filtro_vendedor,
                agencias=agencias,
                tipos_cliente=tipos_cliente,
                estados=estados,
                fluxos=fluxos,
                apresentacoes=apresentacoes,
                setores=setores
            )
        except Exception as e:
            import traceback
            app.logger.error("Erro ao listar clientes:")
            app.logger.error(str(e))
            app.logger.error(traceback.format_exc())
            flash(f'Erro ao buscar clientes: {str(e)}', 'error')
            return render_template(
                'clientes.html',
                clientes=[],
                pessoas_stats={'fisica': {'total': 0, 'ativos': 0}, 'juridica': {'total': 0, 'ativos': 0}}
            )

    # ==================== INTERESSE PRODUTO ====================
    
    @app.route('/interesse-produto')
    @login_required
    def interesse_produto_listar():
        """Lista de interesses em produtos com filtros."""
        try:
            # Obter filtros da query string
            filtro_tipo = request.args.get('tipo_produto', '').strip()
            filtro_notificado = request.args.get('notificado', '').strip()
            filtro_cliente_id = request.args.get('cliente_id', '').strip()
            
            # Converter filtro_notificado para boolean ou None
            notificado_param = None
            if filtro_notificado == 'true':
                notificado_param = True
            elif filtro_notificado == 'false':
                notificado_param = False
            
            # Converter cliente_id para int ou None
            cliente_id_param = None
            if filtro_cliente_id:
                try:
                    cliente_id_param = int(filtro_cliente_id)
                except ValueError:
                    pass
            
            # Buscar interesses com filtro de cliente direto na query
            interesses = db.obter_interesses_produto(
                tipo_produto=filtro_tipo if filtro_tipo else None,
                notificado=notificado_param,
                cliente_id=cliente_id_param
            )
            
            # Buscar lista de clientes ativos (usado para pré-preencher o nome selecionado na busca)
            clientes_ativos = db.obter_clientes_sistema({'status': True})

            cliente_nome_prefill = ''
            if cliente_id_param and clientes_ativos:
                cliente_encontrado = next((c for c in clientes_ativos if c.get('id_cliente') == cliente_id_param), None)
                if cliente_encontrado:
                    cliente_nome_prefill = cliente_encontrado.get('nome_fantasia') or cliente_encontrado.get('razao_social') or ''
            
            return render_template(
                'interesse_produto.html',
                interesses=interesses,
                filtro_tipo=filtro_tipo,
                filtro_notificado=filtro_notificado,
                filtro_cliente_id=filtro_cliente_id,
                clientes_ativos=clientes_ativos or [],
                cliente_nome_prefill=cliente_nome_prefill
            )
        except Exception as e:
            import traceback
            app.logger.error("Erro ao listar interesses em produtos:")
            app.logger.error(str(e))
            app.logger.error(traceback.format_exc())
            flash(f'Erro ao buscar interesses: {str(e)}', 'error')
            return render_template(
                'interesse_produto.html',
                interesses=[],
                filtro_tipo='',
                filtro_notificado='',
                filtro_cliente_id='',
                clientes_ativos=[]
            )

    # ==================== AUX SETOR ====================
    
    @app.route('/tbl_setor')
    @login_required
    def tbl_setor():
        """Página de gerenciamento de setores."""
        try:
            setores = db.obter_setores(apenas_ativos=False)
            return render_template('tbl_setor.html', setores=setores)
        except Exception as e:
            app.logger.error(f"Erro ao carregar setores: {str(e)}")
            flash('Erro ao carregar setores.', 'error')
            return redirect(url_for('index'))

    # Compatibilidade com o antigo caminho
    @app.route('/aux_setor')
    @login_required
    def aux_setor_legacy():
        return redirect(url_for('tbl_setor'))

    # Alias para suportar o caminho esperado pelo JS (/setor/<id>/toggle_status)
    @app.route('/setor/<int:setor_id>/toggle_status', methods=['PUT'])
    @login_required
    def toggle_status_setor(setor_id):
        try:
            new_status = db.toggle_status_setor(setor_id)
            if new_status is not None:
                return jsonify({'message': f'Status alterado para {"ativo" if new_status else "inativo"}', 'status': new_status}), 200
            return jsonify({'message': 'Setor não encontrado'}), 404
        except Exception as e:
            app.logger.error(f"Erro ao alterar status do setor: {str(e)}")
            return jsonify({'message': 'Erro ao alterar status'}), 500

    # ==================== UP AUDIÊNCIA ====================

    @app.route('/up_audiencia', methods=['GET', 'POST'])
    @login_required
    def up_audiencia():
        """Upload e extração de campos de imagem."""
        result = None
        prompt_text = None
        models = []
        try:
            models = get_available_models() or []
        except Exception:
            models = []
        # modelo selecionado persiste em sessão
        from flask import session as _session
        default_model_id = 'google/gemini-1.5-flash-8b'
        selected_model_id = _session.get('selected_model_id', default_model_id)
        if request.method == 'POST':
            try:
                prompt_text = (request.form.get('prompt') or '').strip()
                # Lê modelo escolhido no formulário (se enviado)
                sel_from_form = (request.form.get('model') or '').strip()
                if sel_from_form:
                    selected_model_id = sel_from_form
                    _session['selected_model_id'] = selected_model_id
                if not prompt_text:
                    flash('Informe o prompt.', 'error')
                file = request.files.get('upimagem')
                if not file or not file.filename:
                    flash('Selecione um arquivo de imagem.', 'error')
                elif prompt_text:
                    image_bytes = file.read()
                    data = extract_fields_from_image_bytes(image_bytes, filename=file.filename, model=selected_model_id, prompt=prompt_text)
                    
                    # FALLBACK: Se data não tem campos estruturados mas tem 'content' como string, tenta parsear
                    if isinstance(data, dict) and 'content' in data and isinstance(data['content'], str):
                        # Verifica se não tem outros campos além de _raw e content
                        other_keys = [k for k in data.keys() if k not in ('_raw', 'content', '_parse_error')]
                        if not other_keys:
                            import json as _json
                            content_str = data['content'].strip()
                            # Remove markdown code fences se existir
                            if content_str.startswith('```'):
                                content_str = content_str.lstrip('`')
                                if '\n' in content_str:
                                    lines = content_str.split('\n')
                                    if lines[0].strip().lower() in ['json', 'JSON', '']:
                                        content_str = '\n'.join(lines[1:])
                                    else:
                                        content_str = '\n'.join(lines)
                                content_str = content_str.rstrip('`').strip()
                            # Tenta encontrar e parsear JSON
                            try:
                                start = content_str.find('{')
                                end = content_str.rfind('}')
                                if start != -1 and end != -1 and end > start:
                                    json_str = content_str[start:end+1]
                                    parsed = _json.loads(json_str)
                                    if isinstance(parsed, dict):
                                        # Substitui data com o JSON parseado, mantendo _raw
                                        raw_backup = data.get('_raw')
                                        data = parsed
                                        data['_raw'] = raw_backup
                            except Exception as e:
                                # Se falhar, mantém data original mas adiciona informação de erro
                                data['_content_parse_attempt_error'] = str(e)
                    
                    # data esperado: dict com campos extraídos conforme o prompt (genérico)
                    # Monta texto chave:valor para exibição à esquerda somente com chaves não vazias
                    def _serialize_value(val):
                        import json as _json
                        if isinstance(val, (str, int, float, bool)) or val is None:
                            return '' if val is None else str(val)
                        try:
                            return _json.dumps(val, ensure_ascii=False)
                        except Exception:
                            return str(val)

                    kv_lines = []
                    seen_keys = set()
                    def _is_empty_text(val):
                        return (val is None) or (isinstance(val, str) and val.strip() == '')

                    # 1) Acrescenta quaisquer chaves de nível superior (exceto _raw e content bruto)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if k in seen_keys or k == '_raw' or (k == 'content' and isinstance(v, str)):
                                continue
                            if _is_empty_text(v):
                                continue
                            kv_lines.append(f"{k}: {_serialize_value(v)}")
                            seen_keys.add(k)

                        # 2) Tenta extrair JSON do campo 'content' para incluir pares adicionais
                        content = data.get('content')
                        parsed_extra = None
                        if isinstance(content, str):
                            txt = content.strip()
                            try:
                                start = txt.find('{')
                                end = txt.rfind('}')
                                if start != -1 and end != -1 and end > start:
                                    txt_obj = txt[start:end+1]
                                    import json as _json
                                    parsed_extra = _json.loads(txt_obj)
                            except Exception:
                                parsed_extra = None
                        elif isinstance(content, dict):
                            parsed_extra = content

                        if isinstance(parsed_extra, dict):
                            for k, v in parsed_extra.items():
                                if k in seen_keys:
                                    continue
                                if _is_empty_text(v):
                                    continue
                                kv_lines.append(f"{k}: {_serialize_value(v)}")
                                seen_keys.add(k)

                    kv_text = "\n".join(kv_lines)

                    # Extrai uso de tokens do raw (se disponível) e estima custo em USD com base em variáveis de ambiente
                    raw_obj = (data or {}).get('_raw') or {}
                    usage = (raw_obj or {}).get('usage') or {}
                    pt = usage.get('prompt_tokens') or 0
                    ct = usage.get('completion_tokens') or 0
                    tt = usage.get('total_tokens') or (pt + ct)

                    # Estimar tokens e preços caso não venham no retorno
                    import os as _os, math as _math, json as _json
                    usage_estimated = False
                    pricing_defaults_used = False

                    if pt == 0 and ct == 0:
                        # Equivalência de imagem em tokens (configurável)
                        try:
                            img_eq = int((_os.getenv('OPENROUTER_IMAGE_TOKENS_EQUIV') or '300').strip() or 300)
                        except Exception:
                            img_eq = 300

                        def _est_tokens(text: str) -> int:
                            if not text:
                                return 0
                            return int(_math.ceil(len(text) / 4.0))

                        pt = img_eq + _est_tokens(prompt_text or '')
                        # completion: usa 'content' bruto quando disponível, senão JSON dos campos extraídos
                        try:
                            structured_fields = {}
                            if isinstance(data, dict):
                                structured_fields = {k: v for k, v in data.items() if k not in ('_raw', 'content')}
                        except Exception:
                            structured_fields = {}
                        comp_src = (data or {}).get('content') if isinstance((data or {}).get('content'), str) else _json.dumps(structured_fields, ensure_ascii=False)
                        ct = _est_tokens(comp_src or '')
                        tt = pt + ct
                        usage_estimated = True

                    # Tentar obter custo diretamente da OpenRouter (headers ou corpo)
                    cost_usd = None
                    headers_map = (raw_obj or {}).get('__headers__') or {}
                    # Candidatos comuns de header para custo
                    for hk in ['x-openrouter-total-cost', 'x-request-cost', 'x-openrouter-cost', 'x-openrouter-processed-total-cost']:
                        if hk in headers_map:
                            try:
                                cost_usd = float(str(headers_map.get(hk)).strip().replace('$',''))
                                break
                            except Exception:
                                pass
                    # Candidatos no corpo
                    if cost_usd is None and isinstance(usage, dict):
                        for k, v in usage.items():
                            if isinstance(k, str) and 'cost' in k.lower():
                                try:
                                    cost_usd = float(v)
                                    break
                                except Exception:
                                    continue

                    # Se ainda não houver custo, calcular estimativa via preços
                    if cost_usd is None:
                        # Preços por milhão de tokens (entrada/saída)
                        try:
                            in_price = float((_os.getenv('OPENROUTER_PRICE_IN_PER_MTOKENS') or '0').strip() or 0)
                            out_price = float((_os.getenv('OPENROUTER_PRICE_OUT_PER_MTOKENS') or '0').strip() or 0)
                        except Exception:
                            in_price = 0.0
                            out_price = 0.0
                        if in_price == 0:
                            try:
                                in_price = float((_os.getenv('OPENROUTER_DEFAULT_IN_PRICE') or '3.0').strip() or 3.0)
                            except Exception:
                                in_price = 3.0
                        if out_price == 0:
                            try:
                                out_price = float((_os.getenv('OPENROUTER_DEFAULT_OUT_PRICE') or '15.0').strip() or 15.0)
                            except Exception:
                                out_price = 15.0

                        cost_usd = (pt / 1_000_000.0) * in_price + (ct / 1_000_000.0) * out_price
                    model_used = (raw_obj or {}).get('model')
                    # Resolve label do modelo selecionado para exibição
                    def _label_for(mid: str) -> str:
                        try:
                            for m in (models or []):
                                if m.get('id') == mid:
                                    return m.get('label') or mid
                        except Exception:
                            pass
                        return mid
                    model_selected_label = _label_for(selected_model_id)

                    # Conversão para BRL com base no dólar do dia
                    usd_brl_rate = None
                    usd_brl_source = None
                    cost_brl = None
                    try:
                        # 1) Override por variável de ambiente (maior prioridade)
                        rate_env = _os.getenv('USD_BRL_RATE')
                        if rate_env:
                            usd_brl_rate = float(str(rate_env).strip())
                            usd_brl_source = 'env:USD_BRL_RATE'
                        # 2) Buscar em serviço público se não definido
                        if usd_brl_rate is None:
                            try:
                                import requests as _req
                                r = _req.get('https://api.exchangerate.host/latest?base=USD&symbols=BRL', timeout=5)
                                if r.status_code == 200:
                                    data_fx = r.json() or {}
                                    rates = data_fx.get('rates') or {}
                                    brl = rates.get('BRL')
                                    if brl:
                                        usd_brl_rate = float(brl)
                                        usd_brl_source = 'exchangerate.host'
                            except Exception:
                                pass
                        # 3) Se ainda não houver taxa, tenta um segundo provedor (opcional)
                        if usd_brl_rate is None:
                            try:
                                import requests as _req
                                r2 = _req.get('https://economia.awesomeapi.com.br/json/last/USD-BRL', timeout=5)
                                if r2.status_code == 200:
                                    j = r2.json() or {}
                                    usdb = j.get('USDBRL') or {}
                                    bid = usdb.get('bid')
                                    if bid:
                                        usd_brl_rate = float(bid)
                                        usd_brl_source = 'awesomeapi.com.br'
                            except Exception:
                                pass
                    except Exception:
                        usd_brl_rate = None
                        usd_brl_source = None

                    if cost_usd is not None and usd_brl_rate is not None:
                        cost_brl = round(cost_usd * usd_brl_rate, 6)

                    # Prepara texto JSON seguro para a direita: tenta serializar 'data'; se falhar, usa KV->JSON básico
                    import json as _json
                    json_text = ''
                    try:
                        json_text = _json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False, indent=2)
                    except Exception:
                        # Fallback: monta dict a partir do kv_lines
                        kv_dict = {}
                        for line in kv_lines:
                            try:
                                if ':' not in line:
                                    continue
                                k, v = line.split(':', 1)
                                k = (k or '').strip()
                                v = (v or '').strip()
                                if not k:
                                    continue
                                # tentativa simples de coerção numérica/boolean/json
                                _v = v
                                if _v.lower() in ['true','false']:
                                    _v = True if _v.lower() == 'true' else False
                                else:
                                    try:
                                        if (_v.startswith('{') and _v.endswith('}')) or (_v.startswith('[') and _v.endswith(']')):
                                            _v = _json.loads(_v)
                                        else:
                                            # número com vírgula/ponto
                                            if _v.replace('.', '', 1).replace(',', '', 1).isdigit():
                                                _v = float(_v.replace(',', '.'))
                                    except Exception:
                                        _v = v
                                kv_dict[k] = _v
                            except Exception:
                                continue
                        try:
                            json_text = _json.dumps(kv_dict, ensure_ascii=False, indent=2)
                        except Exception:
                            json_text = '{}'

                    result = {
                        'fields': {k: v for k, v in ((data or {}).items()) if k not in ('_raw', 'content')} if isinstance(data, dict) else {},
                        'raw': data,
                        'json_text': json_text,
                        'kv_text': kv_text,
                        'usage': { 'prompt_tokens': pt, 'completion_tokens': ct, 'total_tokens': tt },
                        'cost_usd': round(cost_usd, 3),
                        'model_used': model_used,
                        'model_selected_id': selected_model_id,
                        'model_selected_label': model_selected_label,
                        'usage_estimated': usage_estimated,
                        'pricing_defaults_used': pricing_defaults_used,
                        'cost_brl': cost_brl,
                        'usd_brl_rate': usd_brl_rate,
                        'usd_brl_source': usd_brl_source,
                    }
                    flash('Arquivo processado com sucesso!', 'success')
            except Exception as e:
                try:
                    import os as _os
                    detail = str(e)
                    # Exibir detalhes completos quando habilitado
                    if _os.getenv('SHOW_ERRORS', '1') == '1':
                        flash(f'Erro ao processar a imagem: {detail}', 'error')
                    else:
                        flash('Erro ao processar a imagem.', 'error')
                    app.logger.error(f"Erro no processamento da imagem: {detail}")
                except Exception:
                    app.logger.error(f"Erro no processamento da imagem: {e}")
                    flash('Erro ao processar a imagem.', 'error')
        
        # Buscar categorias para o dropdown
        categorias = []
        try:
            categorias = db.obter_cadu_categorias() or []
        except Exception as e:
            app.logger.error(f"Erro ao buscar categorias: {e}")
        
        return render_template('up_audiencia.html', 
                             result=result, 
                             prompt=prompt_text, 
                             models=models, 
                             selected_model_id=selected_model_id,
                             categorias=categorias)

    @app.route('/api/webhook-proxy', methods=['POST'])
    @login_required
    def webhook_proxy():
        """Proxy para enviar dados ao webhook n8n de forma assíncrona (contorna CORS)"""
        try:
            import requests
            import threading
            
            # URL do webhook n8n (PRODUÇÃO)
            webhook_url = 'https://n8n.centralcomm.media/webhook/f8702380-85c1-4a1d-8b6b-1996a9c6d822'
            
            # Obter dados do request
            payload = request.get_json()
            
            if not payload:
                return jsonify({'success': False, 'error': 'Payload vazio'}), 400
            
            # Função para enviar webhook em background
            def send_webhook_async():
                try:
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=60
                    )
                    app.logger.info(f'Webhook enviado com sucesso: {response.status_code}')
                except Exception as e:
                    app.logger.error(f'Erro ao enviar webhook: {str(e)}')
            
            # Iniciar thread para envio assíncrono
            thread = threading.Thread(target=send_webhook_async)
            thread.daemon = True
            thread.start()
            
            # Retornar resposta imediata
            return jsonify({
                'success': True,
                'message': 'Webhook enviado para processamento assíncrono'
            }), 202
            
        except Exception as e:
            return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

    @app.route('/clientes/novo', methods=['GET', 'POST'])
    @login_required
    def cliente_novo():
        """Criar cliente - Redireciona para lista de clientes onde o modal é usado"""
        # GET: redireciona para a página de clientes
        if request.method == 'GET':
            return redirect(url_for('clientes'))
        
        # POST: processa o formulário do modal
        planos = []  # Lista vazia - planos antigos foram removidos
        agencias = db.obter_aux_agencia()
        tipos_cliente = db.obter_tipos_cliente()
        estados = db.obter_estados()
        vendedores_cc = db.obter_vendedores_centralcomm()
        fluxos = db.obter_fluxos_boas_vindas()
        apresentacoes = db.obter_apresentacoes_executivo()
        
        if request.method == 'POST':
            try:
                razao_social = request.form.get('razao_social', '').strip()
                nome_fantasia = request.form.get('nome_fantasia', '').strip()
                pessoa = request.form.get('pessoa', 'J').strip()
                cnpj = request.form.get('cnpj', '').strip()
                inscricao_estadual = request.form.get('inscricao_estadual', '').strip() or None
                pk_id_tbl_plano = request.form.get('pk_id_tbl_plano', type=int)
                inscricao_municipal = request.form.get('inscricao_municipal', '').strip() or None
                id_tipo_cliente = request.form.get('id_tipo_cliente', type=int)
                
                # Campos de endereço
                cep = request.form.get('cep', '').strip() or None
                pk_id_aux_estado = request.form.get('pk_id_aux_estado', type=int) or None
                cidade = request.form.get('cidade', '').strip() or None
                bairro = request.form.get('bairro', '').strip() or None
                logradouro = request.form.get('logradouro', '').strip() or None
                numero = request.form.get('numero', '').strip() or None
                complemento = request.form.get('complemento', '').strip() or None
                
                # Obrigatoriedades por tipo de pessoa
                if pessoa == 'J':
                    if not razao_social or not nome_fantasia:
                        flash('Razão Social e Nome Fantasia obrigatórios!', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                else:
                    # Pessoa Física: Razão Social não é obrigatória, mas Nome Completo sim (usa campo nome_fantasia)
                    if not nome_fantasia:
                        flash('Nome Completo é obrigatório!', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                if not cnpj:
                    flash('CNPJ/CPF é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                if not id_tipo_cliente:
                    flash('Tipo de Cliente é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                # Validação de CPF quando Pessoa Física
                if pessoa == 'F':
                    if not db.validar_cpf(cnpj):
                        flash('CPF inválido!', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                    # Ajustes padrão para PF
                    if not razao_social:
                        razao_social = 'NÃO REQUERIDO'
                    inscricao_estadual = 'ISENTO'
                    inscricao_municipal = 'ISENTO'

                # Validações de unicidade (CNPJ, Razão Social, Nome Fantasia)
                try:
                    if db.cliente_existe_por_cnpj(cnpj):
                        flash('CNPJ já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                    # PF com Razão Social padrão não deve bloquear por duplicidade
                    if pessoa == 'J' and db.cliente_existe_por_razao_social(razao_social):
                        flash('Razão Social já cadastrada em outro cliente.', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                    if db.cliente_existe_por_nome_fantasia(nome_fantasia):
                        flash('Nome Fantasia já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                except Exception as ve:
                    app.logger.error(f"Erro ao validar duplicidades: {ve}")
                    flash('Erro ao validar unicidade. Tente novamente.', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                if pessoa not in ['F', 'J']:
                    flash('Tipo de pessoa inválido!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                pk_id_tbl_agencia = request.form.get('pk_id_tbl_agencia', type=int)
                # Campo do form: vendas_central_comm (ID do contato executivo de vendas)
                vendas_central_comm = request.form.get('vendas_central_comm', type=int) or None
                id_apresentacao_executivo = request.form.get('id_apresentacao_executivo', type=int) or None
                id_fluxo_boas_vindas = request.form.get('id_fluxo_boas_vindas', type=int) or None
                percentual = request.form.get('percentual', '').strip()
                id_centralx = request.form.get('id_centralx', '').strip() or None
                
                if not vendas_central_comm:
                    flash('Vendas CentralComm é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)

                # Fluxo de boas-vindas (não opcional)
                if not id_fluxo_boas_vindas:
                    flash('Fluxo de Boas-Vindas é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos)
                
                # Se for pessoa física, força agência 2
                if pessoa == 'F':
                    pk_id_tbl_agencia = 2
                elif not pk_id_tbl_agencia:
                    flash('Agência é obrigatória para Pessoa Jurídica!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)

                # Percentual obrigatório quando Agência = Sim (Pessoa Jurídica)
                if pessoa == 'J' and pk_id_tbl_agencia:
                    ag = db.obter_aux_agencia_por_id(pk_id_tbl_agencia)
                    ag_key = (str(ag.get('key')).lower() if isinstance(ag, dict) and 'key' in ag else '')
                    if (ag.get('key') is True) or (ag_key in ['sim','true','1','s','yes','y']):
                        if not percentual:
                            flash('Percentual é obrigatório quando Agência = Sim.', 'error')
                            return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)

                id_cliente = db.criar_cliente(
                    razao_social=razao_social,
                    nome_fantasia=nome_fantasia,
                    id_tipo_cliente=id_tipo_cliente,
                    pessoa=pessoa,
                    cnpj=cnpj,
                    inscricao_estadual=inscricao_estadual,
                    inscricao_municipal=inscricao_municipal,
                    pk_id_tbl_plano=pk_id_tbl_plano,
                    pk_id_aux_agencia=pk_id_tbl_agencia,
                    pk_id_aux_estado=pk_id_aux_estado,
                    vendas_central_comm=vendas_central_comm,
                    id_centralx=id_centralx,
                    cep=cep,
                    bairro=bairro,
                    cidade=cidade,
                    rua=logradouro,
                    numero=numero,
                    complemento=complemento,
                    id_apresentacao_executivo=id_apresentacao_executivo,
                    id_fluxo_boas_vindas=id_fluxo_boas_vindas,
                    id_percentual=int(percentual) if percentual else None
                )
                
                # Registro de auditoria
                registrar_auditoria(
                    acao='criar',
                    modulo='clientes',
                    descricao=f'Cliente criado: {nome_fantasia}',
                    registro_id=id_cliente,
                    registro_tipo='cliente',
                    dados_novos={'nome_fantasia': nome_fantasia, 'cnpj': cnpj, 'pessoa': pessoa}
                )
                
                # Criar plano Beta Tester automaticamente
                try:
                    valid_from = datetime.now()
                    valid_until = datetime.now() + timedelta(days=90)  # 3 meses
                    
                    plan_data = {
                        'id_cliente': id_cliente,
                        'plan_type': 'Plano Beta Tester',
                        'tokens_monthly_limit': 100000,
                        'image_credits_monthly': 50,
                        'max_users': 10,
                        'features': '{"all_modes": true, "unlimited_docs": true, "unlimited_conversations": true}',
                        'plan_status': 'active',
                        'valid_from': valid_from,
                        'valid_until': valid_until,
                        'plan_start_date': valid_from,
                        'plan_end_date': valid_until
                    }
                    
                    plano_id = db.criar_client_plan(plan_data)
                    
                    if plano_id:
                        # Registrar auditoria do plano
                        registrar_auditoria(
                            acao='CREATE',
                            modulo='PLANOS',
                            descricao=f'Criado plano Beta Tester automaticamente para cliente {nome_fantasia}',
                            registro_id=plano_id,
                            registro_tipo='client_plan',
                            dados_novos={
                                'cliente_id': id_cliente,
                                'plan_type': 'Plano Beta Tester',
                                'tokens_monthly_limit': 100000,
                                'image_credits_monthly': 50,
                                'max_users': 10,
                                'valid_until': valid_until.isoformat()
                            }
                        )
                except Exception as e:
                    app.logger.warning(f"Erro ao criar plano Beta Tester para cliente {id_cliente}: {e}")
                    # Não falha a criação do cliente se o plano falhar
                
                flash(f'Cliente "{nome_fantasia}" criado com plano Beta Tester!', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                app.logger.error(f"Erro: {e}")
                flash('Erro ao criar.', 'error')
                return render_template('cliente_form.html', cliente=None, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)

        return render_template('cliente_form.html', cliente=None, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
    
    
    
    @app.route('/clientes/<int:cliente_id>/toggle-status', methods=['POST'])
    @login_required
    def cliente_toggle_status(cliente_id):
        """Ativar/desativar"""
        try:
            conn = db.get_db()
            with conn.cursor() as cursor:
                # Primeiro, verifica se é o cliente CENTRALCOMM
                cursor.execute('SELECT status, nome_fantasia FROM tbl_cliente WHERE id_cliente = %s', (cliente_id,))
                cliente = cursor.fetchone()
                
                if not cliente:
                    flash('Cliente não encontrado!', 'error')
                    return redirect(url_for('clientes'))
                
                # Verifica se é o cliente CENTRALCOMM (usando nome_fantasia)
                if cliente['nome_fantasia'].upper() == 'CENTRALCOMM':
                    flash('O cliente CENTRALCOMM não pode ser inativado!', 'error')
                    return redirect(url_for('clientes'))
                
                novo_status = not cliente['status']
                cursor.execute('''
                    UPDATE tbl_cliente
                    SET status = %s, data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_cliente = %s
                ''', (novo_status, cliente_id))
                conn.commit()
                
                # Registro de auditoria
                registrar_auditoria(
                    acao='editar',
                    modulo='clientes',
                    descricao=f'Status do cliente {cliente["nome_fantasia"]} alterado para {"ativo" if novo_status else "inativo"}',
                    registro_id=cliente_id,
                    registro_tipo='cliente',
                    dados_anteriores={'status': cliente['status']},
                    dados_novos={'status': novo_status}
                )
                
                flash('Status atualizado!', 'success')
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            flash('Erro ao alterar status.', 'error')
        
        return redirect(url_for('clientes'))
    
    # ==================== API: Consulta CNPJ ====================
    @app.route('/api/cnpj/<cnpj>', methods=['GET'])
    @login_required
    def api_cnpj(cnpj):
        """Consulta dados públicos de Pessoa Jurídica por CNPJ e retorna campos mapeados.

        Fonte: publica.cnpj.ws
        """
        import re
        try:
            import requests
        except Exception:
            return jsonify({'ok': False, 'error': 'Dependência ausente: requests'}), 500

        try:
            digits = re.sub(r'\D', '', cnpj or '')
            if len(digits) != 14:
                return jsonify({'ok': False, 'error': 'CNPJ inválido'}), 400

            url = f'https://publica.cnpj.ws/cnpj/{digits}'
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return jsonify({'ok': False, 'error': 'Não encontrado'}), r.status_code

            data = r.json() or {}
            razao_social = data.get('razao_social')
            nome_fantasia = data.get('nome_fantasia') or (data.get('estabelecimento') or {}).get('nome_fantasia')

            estab = data.get('estabelecimento') or {}
            inscricoes = estab.get('inscricoes_estaduais') or []
            inscricao_estadual = None
            for ie in inscricoes:
                if isinstance(ie, dict) and ie.get('inscricao_estadual'):
                    if ie.get('ativo') is True:
                        inscricao_estadual = ie.get('inscricao_estadual')
                        break
                    if not inscricao_estadual:
                        inscricao_estadual = ie.get('inscricao_estadual')

            inscricao_municipal = None

            return jsonify({
                'ok': True,
                'razao_social': razao_social,
                'nome_fantasia': nome_fantasia,
                'inscricao_estadual': inscricao_estadual,
                'inscricao_municipal': inscricao_municipal,
            })
        except requests.Timeout:
            return jsonify({'ok': False, 'error': 'Timeout na consulta do CNPJ'}), 504
        except Exception as e:
            app.logger.error(f"Erro API CNPJ: {e}")
            return jsonify({'ok': False, 'error': 'Erro interno na consulta do CNPJ'}), 500

    # ==================== API: Validação Unicidade Cliente ====================
    @app.route('/api/clientes/validate', methods=['POST'])
    @login_required
    def api_validate_cliente():
        """Valida duplicidade de CNPJ, Razão Social e Nome Fantasia (AJAX)."""
        try:
            payload = request.get_json(silent=True) or {}
            cnpj = (payload.get('cnpj') or '').strip()
            razao_social = (payload.get('razao_social') or '').strip()
            nome_fantasia = (payload.get('nome_fantasia') or '').strip()
            cliente_id = payload.get('cliente_id', None)
            try:
                cliente_id = int(cliente_id) if cliente_id is not None else None
            except Exception:
                cliente_id = None

            dup_cnpj = db.cliente_existe_por_cnpj(cnpj, excluir_id=cliente_id) if cnpj else False
            dup_razao = db.cliente_existe_por_razao_social(razao_social, excluir_id=cliente_id) if razao_social else False
            dup_nome = db.cliente_existe_por_nome_fantasia(nome_fantasia, excluir_id=cliente_id) if nome_fantasia else False

            return jsonify({
                'ok': True,
                'duplicates': {
                    'cnpj': bool(dup_cnpj),
                    'razao_social': bool(dup_razao),
                    'nome_fantasia': bool(dup_nome),
                }
            })
        except Exception as e:
            app.logger.error(f"Erro API validação cliente: {e}")
            return jsonify({'ok': False, 'error': 'Erro ao validar dados'}), 500
    
    
    # Note: Removed duplicate aux_setor route definition that was causing conflicts
    # The route /aux_setor is already defined above

    @app.route('/setor/create', methods=['POST'])
    @login_required
    def criar_setor():
        """Cria um novo setor"""
        try:
            data = request.get_json()
            display = data.get('display', '').strip()
            status = data.get('status', True)
            
            if not display:
                return jsonify({'message': 'Display é obrigatório'}), 400
            
            id_setor = db.criar_setor(display, status)
            return jsonify({'message': 'Setor criado com sucesso', 'id': id_setor}), 201
        
        except Exception as e:
            app.logger.error(f"Erro ao criar setor: {str(e)}")
            return jsonify({'message': 'Erro ao criar setor'}), 500

    @app.route('/setor/<int:id_setor>', methods=['PUT'])
    @login_required
    def atualizar_setor(id_setor):
        """Atualiza um setor existente"""
        try:
            data = request.get_json()
            display = data.get('display', '').strip()
            status = data.get('status', True)
            
            if not display:
                return jsonify({'message': 'Display é obrigatório'}), 400
            
            if db.atualizar_setor(id_setor, display, status):
                return jsonify({'message': 'Setor atualizado com sucesso'}), 200
            return jsonify({'message': 'Setor não encontrado'}), 404
        
        except Exception as e:
            app.logger.error(f"Erro ao atualizar setor: {str(e)}")
            return jsonify({'message': 'Erro ao atualizar setor'}), 500

    # Note: Removed duplicate toggle_status_setor route definition that was causing conflicts
    # The route /aux_setor/<int:setor_id>/toggle_status is already defined acima

    # ==================== TBL CARGO CONTATO ====================
    
    @app.route('/cargo')
    @login_required
    def tbl_cargo_contato():
        """Página de cargo"""
        cargos = db.obter_cargos()
        setores = db.obter_setores()
        return render_template('tbl_cargo_contato.html', cargos=cargos, setores=setores)
    
    @app.route('/cargo/<int:id_cargo>')
    @login_required
    def get_cargo(id_cargo):
        """Retorna os dados de um cargo"""
        cargo = db.get_cargo(id_cargo)
        if cargo:
            return jsonify(cargo)
        return jsonify({'message': 'Cargo não encontrado'}), 404
    
    @app.route('/cargo/create', methods=['POST'])
    @login_required
    def create_cargo():
        """Cria um novo cargo"""
        try:
            data = request.get_json()
            descricao = data.get('descricao', '').strip()
            pk_id_aux_setor = data.get('pk_id_aux_setor')
            id_centralx = data.get('id_centralx')
            indice = data.get('indice')
            
            if not descricao:
                return jsonify({'message': 'Descrição é obrigatória'}), 400
            
            if db.criar_cargo(descricao, pk_id_aux_setor, id_centralx, indice):
                return jsonify({'message': 'Cargo criado com sucesso'}), 201
            return jsonify({'message': 'Erro ao criar cargo'}), 500
        
        except Exception as e:
            app.logger.error(f"Erro ao criar cargo: {str(e)}")
            return jsonify({'message': 'Erro ao criar cargo'}), 500
    
    @app.route('/cargo/<int:id_cargo>', methods=['PUT'])
    @login_required
    def update_cargo(id_cargo):
        """Atualiza um cargo"""
        try:
            data = request.get_json()
            descricao = data.get('descricao', '').strip()
            pk_id_aux_setor = data.get('pk_id_aux_setor')
            id_centralx = data.get('id_centralx')
            indice = data.get('indice')
            status = data.get('status', True)
            
            if not descricao:
                return jsonify({'message': 'Descrição é obrigatória'}), 400
            
            if db.atualizar_cargo(id_cargo, descricao, pk_id_aux_setor, id_centralx, indice, status):
                return jsonify({'message': 'Cargo atualizado com sucesso'}), 200
            return jsonify({'message': 'Cargo não encontrado'}), 404
        
        except Exception as e:
            app.logger.error(f"Erro ao atualizar cargo: {str(e)}")
            return jsonify({'message': 'Erro ao atualizar cargo'}), 500

    @app.route('/cargo/<int:id_cargo>/toggle_status', methods=['PUT'])
    @login_required
    def toggle_status_cargo(id_cargo):
        """Alterna o status de um cargo"""
        try:
            new_status = db.toggle_status_cargo(id_cargo)
            if new_status is not None:
                return jsonify({
                    'message': f'Status alterado para {"ativo" if new_status else "inativo"}',
                    'status': new_status
                }), 200
            return jsonify({'message': 'Cargo não encontrado'}), 404
        
        except Exception as e:
            app.logger.error(f"Erro ao alterar status do cargo: {str(e)}")
            return jsonify({'message': 'Erro ao alterar status'}), 500
    
    # ==================== TIPO CLIENTE ====================
    
    @app.route('/tipo-cliente')
    @login_required
    def tipos_cliente():
        """Lista todos os tipos de cliente"""
        try:
            tipos = db.obter_tipos_cliente()
            return render_template('tipo_cliente.html', tipos=tipos)
        except Exception as e:
            app.logger.error(f"Erro ao listar tipos de cliente: {str(e)}")
            flash('Erro ao carregar tipos de cliente.', 'error')
            return redirect(url_for('index'))
    
    @app.route('/tipo-cliente/novo', methods=['GET', 'POST'])
    @login_required
    def tipo_cliente_novo():
        """Criar novo tipo de cliente"""
        if request.method == 'POST':
            try:
                display = request.form.get('display', '').strip()
                
                if not display:
                    flash('O nome do tipo de cliente é obrigatório!', 'error')
                    return render_template('tipo_cliente_form.html')
                
                id_tipo = db.criar_tipo_cliente(display)
                
                if id_tipo:
                    flash(f'Tipo de cliente "{display}" criado com sucesso!', 'success')
                    return redirect(url_for('tipos_cliente'))
                else:
                    flash('Erro ao criar tipo de cliente.', 'error')
                    
            except Exception as e:
                app.logger.error(f"Erro ao criar tipo de cliente: {str(e)}")
                flash('Erro ao criar tipo de cliente.', 'error')
        
        return render_template('tipo_cliente_form.html')
    
    @app.route('/tipo-cliente/<int:id_tipo>/editar', methods=['GET', 'POST'])
    @login_required
    def tipo_cliente_editar(id_tipo):
        """Editar tipo de cliente"""
        tipo = db.obter_tipo_cliente_por_id(id_tipo)
        
        if not tipo:
            flash('Tipo de cliente não encontrado!', 'error')
            return redirect(url_for('tipos_cliente'))
        
        if request.method == 'POST':
            try:
                display = request.form.get('display', '').strip()
                
                if not display:
                    flash('O nome do tipo de cliente é obrigatório!', 'error')
                    return render_template('tipo_cliente_form.html', tipo=tipo)
                
                if db.atualizar_tipo_cliente(id_tipo, display):
                    flash(f'Tipo de cliente "{display}" atualizado com sucesso!', 'success')
                    return redirect(url_for('tipos_cliente'))
                else:
                    flash('Erro ao atualizar tipo de cliente.', 'error')
                    
            except Exception as e:
                app.logger.error(f"Erro ao atualizar tipo de cliente: {str(e)}")
                flash('Erro ao atualizar tipo de cliente.', 'error')
        
        return render_template('tipo_cliente_form.html', tipo=tipo)
    
    @app.route('/tipo-cliente/<int:id_tipo>/excluir', methods=['POST'])
    @login_required
    def tipo_cliente_excluir(id_tipo):
        """Excluir tipo de cliente"""
        try:
            tipo = db.obter_tipo_cliente_por_id(id_tipo)
            
            if not tipo:
                flash('Tipo de cliente não encontrado!', 'error')
                return redirect(url_for('tipos_cliente'))
            
            if db.excluir_tipo_cliente(id_tipo):
                # Registro de auditoria
                registrar_auditoria(
                    acao='deletar',
                    modulo='tipos_cliente',
                    descricao=f'Tipo de cliente deletado: {tipo["display"]}',
                    registro_id=id_tipo,
                    registro_tipo='tipo_cliente',
                    dados_anteriores=dict(tipo)
                )
                flash(f'Tipo de cliente "{tipo["display"]}" excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir tipo de cliente.', 'error')
                
        except Exception as e:
            app.logger.error(f"Erro ao excluir tipo de cliente: {str(e)}")
            flash('Não é possível excluir este tipo de cliente pois está em uso.', 'error')
        
        return redirect(url_for('tipos_cliente'))
    
    # ==================== CADU AUDIÊNCIAS - ROTAS ====================
    
    @app.route('/cadu-audiencias')
    @login_required
    def cadu_audiencias():
        """Lista todas as audiências do catálogo"""
        try:
            audiencias = db.obter_cadu_audiencias()
            categorias = db.obter_cadu_categorias()
            
            # Calcular estatísticas
            total = len(audiencias)
            ativos = sum(1 for a in audiencias if a.get('is_active'))
            inativos = total - ativos
            
            stats = {
                'total': total,
                'ativos': ativos,
                'inativos': inativos
            }
            
            return render_template('cadu_audiencias.html', 
                                 audiencias=audiencias,
                                 categorias=categorias,
                                 stats=stats)
        except Exception as e:
            app.logger.error(f"Erro ao listar audiências: {str(e)}")
            flash('Erro ao carregar audiências.', 'error')
            return render_template('cadu_audiencias.html', 
                                 audiencias=[],
                                 categorias=[],
                                 stats={'total': 0, 'ativos': 0, 'inativos': 0})
    
    @app.route('/cadu-audiencias/nova', methods=['GET', 'POST'])
    @login_required
    def cadu_audiencia_nova():
        """Cria nova audiência"""
        if request.method == 'POST':
            try:
                dados = {
                    'id_audiencia_plataforma': request.form.get('id_audiencia_plataforma', '').strip(),
                    'fonte': request.form.get('fonte', '').strip(),
                    'nome': request.form.get('nome', '').strip(),
                    'slug': request.form.get('slug', '').strip(),
                    'perfil_socioeconomico': request.form.get('perfil_socioeconomico', '').strip(),
                    'titulo_chamativo': request.form.get('titulo_chamativo', '').strip(),
                    'descricao': request.form.get('descricao', '').strip(),
                    'descricao_curta': request.form.get('descricao_curta', '').strip(),
                    'descricao_comercial': request.form.get('descricao_comercial', '').strip(),
                    'cpm_custo': float(request.form.get('cpm_custo')) if request.form.get('cpm_custo') else None,
                    'cpm_venda': float(request.form.get('cpm_venda')) if request.form.get('cpm_venda') else None,
                    'cpm_minimo': float(request.form.get('cpm_minimo')) if request.form.get('cpm_minimo') else None,
                    'cpm_maximo': float(request.form.get('cpm_maximo')) if request.form.get('cpm_maximo') else None,
                    'categoria_id': int(request.form.get('categoria_id')),
                    'subcategoria_id': int(request.form.get('subcategoria_id')) if request.form.get('subcategoria_id') else None,
                    'is_active': True  # Sempre ativa por padrão ao criar
                }
                
                # Validações
                if not dados['id_audiencia_plataforma']:
                    flash('ID da Plataforma é obrigatório!', 'error')
                    raise ValueError('ID Plataforma obrigatório')
                
                if not dados['nome']:
                    flash('Nome da audiência é obrigatório!', 'error')
                    raise ValueError('Nome obrigatório')
                
                if not dados['slug']:
                    flash('Slug é obrigatório!', 'error')
                    raise ValueError('Slug obrigatório')
                
                novo_id = db.criar_cadu_audiencia(dados)
                
                if novo_id:
                    flash(f'Audiência "{dados["nome"]}" cadastrada com sucesso!', 'success')
                    return redirect(url_for('cadu_audiencias'))
                else:
                    flash('Erro ao cadastrar audiência.', 'error')
                    
            except Exception as e:
                app.logger.error(f"Erro ao criar audiência: {str(e)}")
                flash(f'Erro ao cadastrar audiência: {str(e)}', 'error')
        
        # GET - Carregar formulário
        try:
            categorias = db.obter_cadu_categorias()
            subcategorias = db.obter_cadu_subcategorias()
            return render_template('cadu_audiencias_form.html',
                                 categorias=categorias,
                                 subcategorias=subcategorias,
                                 audiencia=None)
        except Exception as e:
            app.logger.error(f"Erro ao carregar formulário: {str(e)}")
            flash('Erro ao carregar formulário.', 'error')
            return redirect(url_for('cadu_audiencias'))
    
    @app.route('/cadu-audiencias/editar/<int:audiencia_id>', methods=['GET', 'POST'])
    @login_required
    def cadu_audiencia_editar(audiencia_id):
        """Edita audiência existente"""
        
        # GET: redireciona para a lista com o modal aberto
        if request.method == 'GET':
            return redirect(url_for('cadu_audiencias', editar=audiencia_id))
        
        # POST: processa o formulário
        try:
            dados = {
                'id_audiencia_plataforma': request.form.get('id_audiencia_plataforma', '').strip(),
                'fonte': request.form.get('fonte', '').strip(),
                'nome': request.form.get('nome', '').strip(),
                'slug': request.form.get('slug', '').strip(),
                'perfil_socioeconomico': request.form.get('perfil_socioeconomico', '').strip(),
                'titulo_chamativo': request.form.get('titulo_chamativo', '').strip(),
                'descricao': request.form.get('descricao', '').strip(),
                'descricao_curta': request.form.get('descricao_curta', '').strip(),
                'descricao_comercial': request.form.get('descricao_comercial', '').strip(),
                'cpm_custo': float(request.form.get('cpm_custo')) if request.form.get('cpm_custo') else None,
                'cpm_venda': float(request.form.get('cpm_venda')) if request.form.get('cpm_venda') else None,
                'cpm_minimo': float(request.form.get('cpm_minimo')) if request.form.get('cpm_minimo') else None,
                'cpm_maximo': float(request.form.get('cpm_maximo')) if request.form.get('cpm_maximo') else None,
                'categoria_id': int(request.form.get('categoria_id')),
                'subcategoria_id': int(request.form.get('subcategoria_id')) if request.form.get('subcategoria_id') else None,
                # Campos demográficos
                'publico_estimado': request.form.get('publico_estimado', '').strip(),
                'publico_numero': int(request.form.get('publico_numero')) if request.form.get('publico_numero') else None,
                'tamanho': request.form.get('tamanho', '').strip(),
                'propensao_compra': request.form.get('propensao_compra', '').strip() or None,
                'demografia_homens': float(request.form.get('demografia_homens')) if request.form.get('demografia_homens') else None,
                'demografia_mulheres': float(request.form.get('demografia_mulheres')) if request.form.get('demografia_mulheres') else None,
                'idade_18_24': float(request.form.get('idade_18_24')) if request.form.get('idade_18_24') else None,
                'idade_25_34': float(request.form.get('idade_25_34')) if request.form.get('idade_25_34') else None,
                'idade_35_44': float(request.form.get('idade_35_44')) if request.form.get('idade_35_44') else None,
                'idade_45_mais': float(request.form.get('idade_45_mais')) if request.form.get('idade_45_mais') else None,
                'dispositivo_mobile': float(request.form.get('dispositivo_mobile')) if request.form.get('dispositivo_mobile') else None,
                'dispositivo_desktop': float(request.form.get('dispositivo_desktop')) if request.form.get('dispositivo_desktop') else None,
                'dispositivo_tablet': float(request.form.get('dispositivo_tablet')) if request.form.get('dispositivo_tablet') else None
            }
            
            if db.atualizar_cadu_audiencia(audiencia_id, dados):
                flash(f'Audiência "{dados["nome"]}" atualizada com sucesso!', 'success')
            else:
                flash('Erro ao atualizar audiência.', 'error')
                
        except Exception as e:
            app.logger.error(f"Erro ao atualizar audiência: {str(e)}")
            flash(f'Erro ao atualizar audiência: {str(e)}', 'error')
        
        return redirect(url_for('cadu_audiencias'))
    
    @app.route('/cadu-audiencias/deletar/<int:audiencia_id>', methods=['POST'])
    @login_required
    def cadu_audiencia_deletar(audiencia_id):
        """Deleta audiência"""
        try:
            audiencia = db.obter_cadu_audiencia_por_id(audiencia_id)
            
            if not audiencia:
                return jsonify({'success': False, 'message': 'Audiência não encontrada'})
            
            if db.excluir_cadu_audiencia(audiencia_id):
                # Registro de auditoria
                registrar_auditoria(
                    acao='deletar',
                    modulo='audiencias',
                    descricao=f'Audiência deletada: {audiencia["nome"]}',
                    registro_id=audiencia_id,
                    registro_tipo='audiencia',
                    dados_anteriores=dict(audiencia)
                )
                return jsonify({'success': True, 'message': f'Audiência "{audiencia["nome"]}" excluída com sucesso'})
            else:
                return jsonify({'success': False, 'message': 'Erro ao excluir audiência'})
                
        except Exception as e:
            app.logger.error(f"Erro ao deletar audiência: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/cadu-audiencias/<int:audiencia_id>')
    @login_required
    def cadu_audiencia_detalhes(audiencia_id):
        """Exibe detalhes de uma audiência específica"""
        try:
            audiencia = db.obter_cadu_audiencia_por_id(audiencia_id)
            
            if not audiencia:
                flash('Audiência não encontrada!', 'error')
                return redirect(url_for('cadu_audiencias'))
            
            return render_template('cadu_audiencias_detalhes.html', audiencia=audiencia)
        except Exception as e:
            app.logger.error(f"Erro ao carregar detalhes da audiência: {str(e)}")
            flash('Erro ao carregar detalhes da audiência.', 'error')
            return redirect(url_for('cadu_audiencias'))
    
    @app.route('/cadu-audiencias/toggle-status/<int:audiencia_id>', methods=['POST'])
    @login_required
    def cadu_audiencia_toggle_status(audiencia_id):
        """Alterna o status (ativo/inativo) de uma audiência"""
        try:
            audiencia = db.obter_cadu_audiencia_por_id(audiencia_id)
            
            if not audiencia:
                flash('Audiência não encontrada!', 'error')
                return redirect(url_for('cadu_audiencias'))
            
            novo_status = db.toggle_status_cadu_audiencia(audiencia_id)
            
            if novo_status is not None:
                status_texto = 'ativada' if novo_status else 'desativada'
                flash(f'Audiência "{audiencia["nome"]}" {status_texto} com sucesso!', 'success')
            else:
                flash('Erro ao alterar status da audiência.', 'error')
                
        except Exception as e:
            app.logger.error(f"Erro ao alterar status da audiência: {str(e)}")
            flash(f'Erro ao alterar status: {str(e)}', 'error')
        
        # Redirecionar de volta para a página de origem
        referer = request.referrer
        if referer and 'cadu-audiencias' in referer:
            return redirect(referer)
        return redirect(url_for('cadu_audiencias'))

    
    @app.route('/api/cadu-audiencias/toggle-status/<int:audiencia_id>', methods=['POST'])
    @login_required
    def api_cadu_audiencia_toggle_status(audiencia_id):
        """Alterna status ativo/inativo da audiência (API)"""
        try:
            novo_status = db.toggle_status_cadu_audiencia(audiencia_id)
            
            if novo_status is not None:
                return jsonify({
                    'success': True, 
                    'is_active': novo_status,
                    'message': f'Status alterado para {"Ativa" if novo_status else "Inativa"}'
                })
            else:
                return jsonify({'success': False, 'message': 'Audiência não encontrada'})
                
        except Exception as e:
            app.logger.error(f"Erro ao alterar status: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/cadu-subcategorias')
    @login_required
    def api_cadu_subcategorias():
        """API para carregar subcategorias por categoria"""
        try:
            categoria_id = request.args.get('categoria_id', type=int)
            
            if categoria_id:
                subcategorias = db.obter_cadu_subcategorias(categoria_id=categoria_id)
            else:
                subcategorias = db.obter_cadu_subcategorias()
            
            return jsonify({
                'success': True,
                'subcategorias': [
                    {
                        'id': sub['id'],
                        'nome': sub['nome'],
                        'categoria_id': sub['categoria_id']
                    }
                    for sub in subcategorias
                ]
            })
        except Exception as e:
            app.logger.error(f"Erro ao carregar subcategorias: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/cadu-audiencia/<int:audiencia_id>')
    @login_required
    def api_cadu_audiencia(audiencia_id):
        """API para buscar dados de uma audiência"""
        try:
            audiencia = db.obter_cadu_audiencia_por_id(audiencia_id)
            if audiencia:
                return jsonify(audiencia)
            else:
                return jsonify({'error': 'Audiência não encontrada'}), 404
        except Exception as e:
            app.logger.error(f"Erro ao buscar audiência: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # ==================== GERAÇÃO DE IMAGENS PARA AUDIÊNCIAS ====================

    @app.route('/api/preparar-prompt-imagem', methods=['POST'])
    @login_required
    def api_preparar_prompt_imagem():
        """Prepara prompt otimizado para geração de imagem usando Gemini 2.5 Flash"""
        try:
            from aicentralv2.services import image_generation_service
            
            data = request.get_json()
            nome_audiencia = data.get('nome_audiencia', '')
            categoria = data.get('categoria', '')
            descricao = data.get('descricao', '')
            
            if not nome_audiencia:
                return jsonify({'success': False, 'error': 'Nome da audiência é obrigatório'})
            
            resultado = image_generation_service.preparar_prompt_imagem(nome_audiencia, categoria, descricao)
            return jsonify(resultado)
            
        except Exception as e:
            app.logger.error(f"Erro ao preparar prompt de imagem: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/gerar-imagem-audiencia', methods=['POST'])
    @login_required
    def api_gerar_imagem_audiencia():
        """Gera imagem usando modelo escolhido via OpenRouter"""
        try:
            from aicentralv2.services import image_generation_service
            
            data = request.get_json()
            prompt = data.get('prompt', '').strip()
            modelo = data.get('modelo', 'google/gemini-2.5-flash-image')
            audiencia_id = data.get('audiencia_id')
            
            if not prompt or len(prompt) < 50:
                return jsonify({'success': False, 'error': 'Prompt muito curto. Mínimo 50 caracteres.'})
            
            # Gerar imagem com modelo selecionado
            resultado = image_generation_service.gerar_imagem_audiencia(prompt, modelo)
            
            return jsonify(resultado)
            
        except Exception as e:
            app.logger.error(f"Erro ao gerar imagem: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/salvar-imagem-audiencia', methods=['POST'])
    @login_required
    def api_salvar_imagem_audiencia():
        """Salva URL da imagem gerada no banco de dados e deleta a imagem antiga"""
        try:
            import os
            from pathlib import Path
            
            data = request.get_json()
            audiencia_id = data.get('audiencia_id')
            imagem_url = data.get('imagem_url', '').strip()
            
            if not audiencia_id or not imagem_url:
                return jsonify({'success': False, 'error': 'ID da audiência e URL da imagem são obrigatórios'})
            
            # Buscar imagem antiga antes de atualizar
            audiencia = db.obter_cadu_audiencia_por_id(audiencia_id)
            imagem_antiga = audiencia.get('imagem_url') if audiencia else None
            
            # Atualizar no banco
            if db.atualizar_imagem_audiencia(audiencia_id, imagem_url):
                app.logger.info(f"Imagem salva para audiência {audiencia_id}: {imagem_url}")
                
                # Incrementar contador de imagens no plano do cliente
                if audiencia and audiencia.get('id_cliente'):
                    try:
                        # Buscar plano ativo do cliente
                        conn = db.get_db()
                        with conn.cursor() as cursor:
                            cursor.execute('''
                                SELECT id_plan 
                                FROM cadu_client_plans 
                                WHERE id_cliente = %s AND plan_status = 'active'
                                LIMIT 1
                            ''', (audiencia['id_cliente'],))
                            plano = cursor.fetchone()
                            
                            if plano:
                                # Incrementar contador de imagens (apenas se for imagem nova, não atualização)
                                if not imagem_antiga:
                                    db.atualizar_consumo_tokens(plano['id_plan'], 0, 1)
                                    app.logger.info(f"✅ Contador de imagens incrementado para plano {plano['id_plan']}")
                    except Exception as e:
                        app.logger.error(f"⚠️ Erro ao incrementar contador de imagens: {e}")
                        # Não falhar a operação por causa disso
                
                # Deletar imagem antiga se existir e for diferente da nova
                if imagem_antiga and imagem_antiga != imagem_url:
                    try:
                        # Extrair nome do arquivo da URL (tanto relativa quanto completa)
                        # Ex: /static/uploads/audiencias/gemini_123.png -> gemini_123.png
                        # Ex: http://localhost:5000/static/uploads/audiencias/gemini_123.png -> gemini_123.png
                        if '/static/uploads/audiencias/' in imagem_antiga:
                            filename = imagem_antiga.split('/static/uploads/audiencias/')[-1]
                            caminho_completo = Path('aicentralv2/static/uploads/audiencias') / filename
                            
                            if caminho_completo.exists():
                                caminho_completo.unlink()
                                app.logger.info(f"✅ Imagem antiga deletada: {filename}")
                            else:
                                app.logger.warning(f"⚠️ Imagem antiga não encontrada: {caminho_completo}")
                    except Exception as e:
                        app.logger.error(f"❌ Erro ao deletar imagem antiga: {e}")
                        # Não falhar a operação por causa disso
                
                return jsonify({'success': True, 'message': 'Imagem salva com sucesso'})
            else:
                return jsonify({'success': False, 'error': 'Falha ao salvar imagem no banco'})
            
        except Exception as e:
            app.logger.error(f"Erro ao salvar imagem: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})

    # ==================== ERRO HANDLERS ====================

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Erro interno do servidor: {error}")
        return render_template('errors/500.html'), 500
    
    app.logger.info("Rotas registradas com sucesso")

    # ==================== CATEGORIAS AUDIÊNCIA - CRUD ====================
    from flask import abort

    @app.route('/api/cadu_categorias', methods=['GET'])
    @login_required
    def api_listar_cadu_categorias():
        categorias = db.obter_cadu_categorias()
        return jsonify(categorias)

    @app.route('/api/cadu_categorias/<int:id_categoria>', methods=['GET'])
    @login_required
    def api_obter_cadu_categoria(id_categoria):
        categoria = db.obter_cadu_categoria_por_id(id_categoria)
        if not categoria:
            abort(404)
        return jsonify(categoria)

    @app.route('/api/cadu_categorias', methods=['POST'])
    @login_required
    def api_criar_cadu_categoria():
        data = request.json
        novo_id = db.criar_cadu_categoria(data)
        return jsonify({'id': novo_id}), 201

    @app.route('/api/cadu_categorias/<int:id_categoria>', methods=['PUT'])
    @login_required
    def api_atualizar_cadu_categoria(id_categoria):
        data = request.json
        ok = db.atualizar_cadu_categoria(id_categoria, data)
        if not ok:
            abort(404)
        return jsonify({'success': True})

    @app.route('/api/cadu_categorias/<int:id_categoria>', methods=['DELETE'])
    @login_required
    def api_excluir_cadu_categoria(id_categoria):
        # Busca categoria antes de deletar para auditoria
        categoria = db.obter_cadu_categoria_por_id(id_categoria)
        ok = db.excluir_cadu_categoria(id_categoria)
        if not ok:
            abort(404)
        
        # Registro de auditoria
        if categoria:
            registrar_auditoria(
                acao='deletar',
                modulo='categorias',
                descricao=f'Categoria deletada: {categoria.get("nome", "")}',
                registro_id=id_categoria,
                registro_tipo='categoria',
                dados_anteriores=dict(categoria)
            )
        
        return jsonify({'success': True})

    # ==================== API CADU SUBCATEGORIAS ====================

    @app.route('/api/cadu_subcategorias', methods=['GET'])
    @login_required
    def api_listar_cadu_subcategorias():
        categoria_id = request.args.get('categoria_id', type=int)
        subcategorias = db.obter_cadu_subcategorias(categoria_id)
        return jsonify([dict(s) for s in subcategorias])

    @app.route('/api/cadu_subcategorias/<int:id_subcategoria>', methods=['GET'])
    @login_required
    def api_obter_cadu_subcategoria(id_subcategoria):
        subcategoria = db.obter_cadu_subcategoria_por_id(id_subcategoria)
        if not subcategoria:
            abort(404)
        return jsonify(dict(subcategoria))

    @app.route('/api/cadu_subcategorias', methods=['POST'])
    @login_required
    def api_criar_cadu_subcategoria():
        dados = request.get_json()
        novo_id = db.criar_cadu_subcategoria(dados)
        return jsonify({'id': novo_id, 'success': True}), 201

    @app.route('/api/cadu_subcategorias/<int:id_subcategoria>', methods=['PUT'])
    @login_required
    def api_atualizar_cadu_subcategoria(id_subcategoria):
        dados = request.get_json()
        ok = db.atualizar_cadu_subcategoria(id_subcategoria, dados)
        if not ok:
            abort(404)
        return jsonify({'success': True})

    @app.route('/api/cadu_subcategorias/<int:id_subcategoria>', methods=['DELETE'])
    @login_required
    def api_excluir_cadu_subcategoria(id_subcategoria):
        ok = db.excluir_cadu_subcategoria(id_subcategoria)
        if not ok:
            abort(404)
        return jsonify({'success': True})

    # ==================== ROTAS ADMIN ====================
    
    @app.route('/api/cliente/<int:cliente_id>/criar-plano-beta', methods=['POST'])
    @login_required
    def criar_plano_beta_cliente(cliente_id):
        """Cria um plano Beta Tester para um cliente"""
        try:
            # Verificar permissão (admin ou usuário CENTRALCOMM)
            user_type = session.get('user_type', 'client')
            is_admin = user_type in ['admin', 'superadmin']
            
            # Verificar se é usuário CENTRALCOMM
            is_centralcomm = False
            if not is_admin:
                contato = db.obter_contato_por_id(session.get('user_id'))
                if contato and contato.get('pk_id_tbl_cliente'):
                    cliente_user = db.obter_cliente_por_id(contato['pk_id_tbl_cliente'])
                    if cliente_user:
                        is_centralcomm = cliente_user.get('nome_fantasia', '').upper() == 'CENTRALCOMM'
            
            if not is_admin and not is_centralcomm:
                return jsonify({'success': False, 'error': 'Permissão negada'}), 403
            
            # Verificar se cliente existe
            cliente = db.obter_cliente_por_id(cliente_id)
            if not cliente:
                return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404
            
            # Verificar se já existe plano ativo
            planos_ativos = db.obter_planos_clientes({'cliente_id': cliente_id, 'plan_status': 'active'})
            if planos_ativos:
                return jsonify({'success': False, 'error': 'Cliente já possui um plano ativo'}), 400
            
            # Criar plano Beta Tester
            plan_id = db.criar_plano_beta_tester(
                cliente_id=cliente_id,
                created_by=session.get('user_id')
            )
            
            # Registrar auditoria
            registrar_auditoria(
                acao='criar',
                modulo='planos',
                descricao=f'Criou plano Beta Tester para cliente {cliente.get("nome_fantasia", cliente_id)}',
                registro_id=plan_id,
                registro_tipo='cadu_client_plans'
            )
            
            app.logger.info(f"Plano Beta Tester criado para cliente {cliente_id} por usuário {session.get('user_id')}")
            return jsonify({'success': True, 'plan_id': plan_id}), 200
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            app.logger.error(f"Erro ao criar plano beta para cliente {cliente_id}:")
            app.logger.error(error_detail)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==================== GESTÃO DE BRIEFINGS ====================

    @app.route('/briefings')
    @login_required
    def briefing_list():
        """Lista todos os briefings"""
        try:
            # Obter filtros
            status = request.args.get('status', '').strip()
            cliente_id = request.args.get('cliente_id', '').strip()
            busca = request.args.get('busca', '').strip()
            
            filtros = {}
            if status:
                filtros['status'] = status
            if cliente_id:
                filtros['cliente_id'] = int(cliente_id)
            if busca:
                filtros['busca'] = busca
            
            # Buscar briefings - com tratamento de erro
            try:
                briefings = db.obter_todos_briefings(filtros) or []
            except Exception as db_error:
                app.logger.error(f"Erro ao buscar briefings: {str(db_error)}")
                briefings = []
            
            # Buscar clientes para filtro
            try:
                clientes = db.obter_clientes_simples() or []
            except Exception as cli_error:
                app.logger.error(f"Erro ao buscar clientes: {str(cli_error)}")
                clientes = []
            
            # Buscar cliente selecionado se houver filtro
            cliente_selecionado = None
            if cliente_id:
                try:
                    conn = db.get_db()
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT id_cliente, nome_fantasia FROM tbl_cliente WHERE id_cliente = %s', (int(cliente_id),))
                        cliente_selecionado = cursor.fetchone()
                except Exception as e:
                    app.logger.error(f"Erro ao buscar cliente selecionado: {str(e)}")
            
            # Estatísticas
            stats = {
                'total': len(briefings),
                'rascunho': sum(1 for b in briefings if b.get('status') == 'rascunho'),
                'pendente': sum(1 for b in briefings if b.get('status') == 'pendente'),
                'em_andamento': sum(1 for b in briefings if b.get('status') == 'em_andamento'),
                'em_revisao': sum(1 for b in briefings if b.get('status') == 'em_revisao'),
                'completo': sum(1 for b in briefings if b.get('status') == 'completo'),
                'arquivado': sum(1 for b in briefings if b.get('status') == 'arquivado')
            }
            
            return render_template('briefing_list.html', 
                                 briefings=briefings, 
                                 clientes=clientes,
                                 cliente_selecionado=cliente_selecionado,
                                 stats=stats,
                                 filtros={'status': status, 'cliente_id': cliente_id, 'busca': busca})
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            app.logger.error(f"Erro geral ao listar briefings: {str(e)}")
            app.logger.error(error_detail)
            
            # Se a tabela não existe ainda, mostrar mensagem específica
            if 'relation "cadu_briefings" does not exist' in str(e):
                flash('A tabela de briefings ainda não foi criada. Execute a migração: python migrations/create_cadu_briefings.py', 'warning')
            else:
                flash(f'Erro ao carregar lista de briefings: {str(e)}', 'error')
            return redirect(url_for('index'))

    @app.route('/briefings/novo', methods=['GET', 'POST'])
    @login_required
    def briefing_create():
        """Cria novo briefing"""
        if request.method == 'GET':
            clientes = db.obter_clientes_simples()
            return render_template('briefing_form.html', 
                                 briefing=None, 
                                 clientes=clientes,
                                 acao='Novo')
        
        try:
            # Obter dados do formulário
            dados = {
                'cliente_id': int(request.form.get('cliente_id')),
                'titulo': request.form.get('titulo', '').strip(),
                'objetivo': request.form.get('objetivo', '').strip(),
                'publico_alvo': request.form.get('publico_alvo', '').strip(),
                'mensagem_chave': request.form.get('mensagem_chave', '').strip(),
                'canais': request.form.get('canais', '').strip(),
                'budget': float(request.form.get('budget')) if request.form.get('budget') else None,
                'prazo': request.form.get('prazo') if request.form.get('prazo') else None,
                'observacoes': request.form.get('observacoes', '').strip(),
                'status': request.form.get('status', 'rascunho')
            }
            
            # Validações
            if not dados['titulo'] or not dados['cliente_id']:
                flash('Preencha todos os campos obrigatórios.', 'error')
                clientes = db.obter_clientes_simples()
                return render_template('briefing_form.html', 
                                     briefing=dados, 
                                     clientes=clientes,
                                     acao='Novo')
            
            # Criar briefing
            briefing_id = db.criar_briefing(dados)
            
            # Registrar auditoria
            registrar_auditoria(
                acao='criar',
                modulo='briefings',
                descricao=f'Criou briefing "{dados["titulo"]}"',
                registro_id=briefing_id,
                registro_tipo='cadu_briefings',
                dados_novos=dados
            )
            
            flash(f'Briefing "{dados["titulo"]}" criado com sucesso!', 'success')
            return redirect(url_for('briefing_list'))
            
        except Exception as e:
            app.logger.error(f"Erro ao criar briefing: {str(e)}")
            flash(f'Erro ao criar briefing: {str(e)}', 'error')
            clientes = db.obter_clientes_simples()
            return render_template('briefing_form.html', 
                                 briefing=dados if 'dados' in locals() else None, 
                                 clientes=clientes,
                                 acao='Novo')

    @app.route('/briefings/<int:briefing_id>/editar', methods=['GET', 'POST'])
    @login_required
    def briefing_edit(briefing_id):
        """Edita briefing existente"""
        if request.method == 'GET':
            briefing = db.obter_briefing_por_id(briefing_id)
            if not briefing:
                flash('Briefing não encontrado.', 'error')
                return redirect(url_for('briefing_list'))
            
            clientes = db.obter_clientes_simples()
            return render_template('briefing_form.html', 
                                 briefing=briefing, 
                                 clientes=clientes,
                                 acao='Editar')
        
        try:
            # Buscar briefing anterior
            briefing_anterior = db.obter_briefing_por_id(briefing_id)
            if not briefing_anterior:
                flash('Briefing não encontrado.', 'error')
                return redirect(url_for('briefing_list'))
            
            # Obter dados do formulário
            dados = {
                'cliente_id': int(request.form.get('cliente_id')),
                'titulo': request.form.get('titulo', '').strip(),
                'objetivo': request.form.get('objetivo', '').strip(),
                'publico_alvo': request.form.get('publico_alvo', '').strip(),
                'mensagem_chave': request.form.get('mensagem_chave', '').strip(),
                'canais': request.form.get('canais', '').strip(),
                'budget': float(request.form.get('budget')) if request.form.get('budget') else None,
                'prazo': request.form.get('prazo') if request.form.get('prazo') else None,
                'observacoes': request.form.get('observacoes', '').strip(),
                'status': request.form.get('status', 'rascunho')
            }
            
            # Validações
            if not dados['titulo'] or not dados['cliente_id']:
                flash('Preencha todos os campos obrigatórios.', 'error')
                clientes = db.obter_clientes_simples()
                return render_template('briefing_form.html', 
                                     briefing={**dados, 'id': briefing_id}, 
                                     clientes=clientes,
                                     acao='Editar')
            
            # Atualizar briefing
            db.atualizar_briefing(briefing_id, dados)
            
            # Registrar auditoria
            registrar_auditoria(
                acao='atualizar',
                modulo='briefings',
                descricao=f'Atualizou briefing "{dados["titulo"]}"',
                registro_id=briefing_id,
                registro_tipo='cadu_briefings',
                dados_anteriores=dict(briefing_anterior),
                dados_novos=dados
            )
            
            flash(f'Briefing "{dados["titulo"]}" atualizado com sucesso!', 'success')
            return redirect(url_for('briefing_list'))
            
        except Exception as e:
            app.logger.error(f"Erro ao atualizar briefing: {str(e)}")
            flash(f'Erro ao atualizar briefing: {str(e)}', 'error')
            return redirect(url_for('briefing_list'))

    @app.route('/briefings/<int:briefing_id>/excluir', methods=['POST'])
    @login_required
    def briefing_delete(briefing_id):
        """Exclui briefing"""
        try:
            briefing = db.obter_briefing_por_id(briefing_id)
            if not briefing:
                flash('Briefing não encontrado.', 'error')
                return redirect(url_for('briefing_list'))
            
            titulo = briefing['titulo']
            db.excluir_briefing(briefing_id)
            
            # Registrar auditoria
            registrar_auditoria(
                acao='excluir',
                modulo='briefings',
                descricao=f'Excluiu briefing "{titulo}"',
                registro_id=briefing_id,
                registro_tipo='cadu_briefings',
                dados_anteriores=dict(briefing)
            )
            
            flash(f'Briefing "{titulo}" excluído com sucesso!', 'success')
            return redirect(url_for('briefing_list'))
            
        except Exception as e:
            app.logger.error(f"Erro ao excluir briefing: {str(e)}")
            flash('Erro ao excluir briefing.', 'error')
            return redirect(url_for('briefing_list'))

    @app.route('/briefings/<int:briefing_id>/status', methods=['POST'])
    @login_required
    def briefing_update_status(briefing_id):
        """Atualiza status do briefing"""
        try:
            novo_status = request.form.get('status')
            if not novo_status:
                flash('Status não informado.', 'error')
                return redirect(url_for('briefing_list'))
            
            briefing = db.obter_briefing_por_id(briefing_id)
            if not briefing:
                flash('Briefing não encontrado.', 'error')
                return redirect(url_for('briefing_list'))
            
            status_anterior = briefing['status']
            db.atualizar_status_briefing(briefing_id, novo_status)
            
            # Registrar auditoria
            registrar_auditoria(
                acao='alterar_status',
                modulo='briefings',
                descricao=f'Alterou status do briefing "{briefing["titulo"]}" de {status_anterior} para {novo_status}',
                registro_id=briefing_id,
                registro_tipo='cadu_briefings',
                dados_anteriores={'status': status_anterior},
                dados_novos={'status': novo_status}
            )
            
            flash('Status atualizado com sucesso!', 'success')
            return redirect(url_for('briefing_list'))
            
        except Exception as e:
            app.logger.error(f"Erro ao atualizar status: {str(e)}")
            flash('Erro ao atualizar status.', 'error')
            return redirect(url_for('briefing_list'))

    # ==================== COTAÇÕES ====================

    @app.route('/cotacoes')
    @login_required
    def cotacoes_list():
        """Lista cotações, opcionalmente filtradas por cliente ou vendedor"""
        try:
            db.criar_tabela_cotacoes()
            
            # Verificar se há filtro de cliente ou vendedor responsável
            cliente_id = request.args.get('cliente_id', type=int)
            responsavel_id = request.args.get('responsavel_comercial', type=int)
            cliente_info = None
            
            app.logger.info(f"DEBUG cotacoes_list: cliente_id={cliente_id}, responsavel_id={responsavel_id}")
            
            # Se há cliente_id, buscar informações do cliente
            if cliente_id:
                conn = db.get_db()
                with conn.cursor() as cursor:
                    cursor.execute('SELECT id_cliente, nome_fantasia, razao_social FROM tbl_cliente WHERE id_cliente = %s', (cliente_id,))
                    cliente_info = cursor.fetchone()
                    app.logger.info(f"DEBUG cotacoes_list: cliente_info={cliente_info}")
            
            # Obter cotações com filtro apropriado
            if responsavel_id:
                # Filtrar por vendedor/responsável
                cotacoes = db.obter_cotacoes_por_vendedor(responsavel_id)
            else:
                # Filtrar por cliente se fornecido
                cotacoes = db.obter_cotacoes(cliente_id=cliente_id)
            
            app.logger.info(f"DEBUG: Cotações obtidas: {len(cotacoes) if cotacoes else 0} registros")
            
            vendedores = db.obter_vendedores()
            return render_template('cadu_cotacoes.html', cotacoes=cotacoes or [], cliente_filtro=cliente_info, vendedores=vendedores)
        except Exception as e:
            app.logger.error(f"Erro ao listar cotações: {str(e)}", exc_info=True)
            flash('Erro ao carregar cotações.', 'error')
            vendedores = db.obter_vendedores()
            return render_template('cadu_cotacoes.html', cotacoes=[], cliente_filtro=None, vendedores=vendedores)

    @app.route('/cotacoes/nova', methods=['GET', 'POST'])
    @login_required
    def cotacao_nova():
        """Criar nova cotação"""
        if request.method == 'POST':
            try:
                # Campos obrigatórios
                client_id = request.form.get('client_id', type=int)
                nome_campanha = request.form.get('nome_campanha', '').strip()
                periodo_inicio = request.form.get('periodo_inicio', '').strip()
                valor_total_str = request.form.get('valor_total_proposta') or request.form.get('valor_total_proposta_display', '0')
                
                # Validação de campos obrigatórios
                if not client_id or not nome_campanha or not periodo_inicio or not valor_total_str:
                    flash('Cliente, nome da campanha, data de início e valor total são obrigatórios.', 'error')
                    clientes = db.obter_clientes_simples()
                    vendedores = db.obter_vendedores()
                    return render_template('cadu_cotacoes_form.html', clientes=clientes, vendedores=vendedores, modo='novo')

                # Converter valor para float
                valor_total = float(valor_total_str) if valor_total_str else 0.0

                # Coletar todos os campos opcionais
                kwargs = {
                    'objetivo_campanha': request.form.get('objetivo_campanha', '').strip(),
                    'periodo_fim': request.form.get('periodo_fim', '').strip() or None,
                    'responsavel_comercial': request.form.get('responsavel_comercial', type=int),
                    'briefing_id': request.form.get('briefing_id', type=int) if request.form.get('briefing_id') else None,
                    'budget_estimado': float(request.form.get('budget_estimado', '0') or 0) if request.form.get('budget_estimado') else None,
                    'observacoes': request.form.get('observacoes', '').strip(),
                    'origem': request.form.get('origem', '').strip(),
                    'expires_at': request.form.get('expires_at', '').strip() or None,
                    'link_publico_ativo': 'link_publico_ativo' in request.form,
                    'link_publico_token': request.form.get('link_publico_token', '').strip(),
                    'link_publico_expires_at': request.form.get('link_publico_expires_at', '').strip() or None,
                }

                # Remover None values para evitar conflitos
                kwargs = {k: v for k, v in kwargs.items() if v is not None and v != ''}

                resultado = db.criar_cotacao(
                    client_id=client_id,
                    nome_campanha=nome_campanha,
                    periodo_inicio=periodo_inicio,
                    valor_total_proposta=valor_total,
                    **kwargs
                )

                registrar_auditoria(
                    acao='INSERT',
                    modulo='cotacoes',
                    descricao=f'Cotação criada: {resultado["numero_cotacao"]}',
                    registro_id=resultado['id'],
                    registro_tipo='cadu_cotacoes',
                    dados_novos={'nome_campanha': nome_campanha, 'valor_total_proposta': valor_total}
                )

                flash(f'Cotação {resultado["numero_cotacao"]} criada com sucesso!', 'success')
                return redirect(url_for('cotacoes_list'))

            except Exception as e:
                app.logger.error(f"Erro ao criar cotação: {str(e)}", exc_info=True)
                flash(f'Erro ao criar cotação: {str(e)}', 'error')
                clientes = db.obter_clientes_simples()
                vendedores = db.obter_vendedores()
                return render_template('cadu_cotacoes_form.html', clientes=clientes, vendedores=vendedores, modo='novo')

        clientes = db.obter_clientes_simples()
        vendedores = db.obter_vendedores()
        cliente_selecionado = None
        briefings = []
        
        # Se vier cliente_id da URL (vindo do modal de busca)
        cliente_id_url = request.args.get('cliente_id', type=int)
        if cliente_id_url:
            cliente_selecionado = cliente_id_url
            briefings = db.obter_briefings_por_cliente(cliente_id_url)
            app.logger.info(f"DEBUG cotacao_nova GET: cliente_id pre-selecionado={cliente_id_url}")
        
        return render_template('cadu_cotacoes_form.html', clientes=clientes, vendedores=vendedores, briefings=briefings, modo='novo', cliente_selecionado=cliente_selecionado)

    @app.route('/cotacoes/<int:cotacao_id>/editar', methods=['GET', 'POST'])
    @login_required
    def cotacao_editar(cotacao_id):
        """Editar cotação"""
        try:
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                flash('Cotação não encontrada.', 'error')
                return redirect(url_for('cotacoes_list'))

            if request.method == 'POST':
                # Campos obrigatórios
                nome_campanha = request.form.get('nome_campanha', '').strip()
                periodo_inicio = request.form.get('periodo_inicio', '').strip()
                valor_total_str = request.form.get('valor_total_proposta') or request.form.get('valor_total_proposta_display', '0')
                
                if not nome_campanha or not periodo_inicio or not valor_total_str:
                    flash('Nome da campanha, data de início e valor total são obrigatórios.', 'error')
                    clientes = db.obter_clientes_simples()
                    vendedores = db.obter_vendedores()
                    return render_template('cadu_cotacoes_form.html', 
                                         cotacao=cotacao, clientes=clientes, vendedores=vendedores, modo='editar')

                # Converter valor para float
                valor_total = float(valor_total_str) if valor_total_str else 0.0

                # Coletar todos os campos opcionais
                update_kwargs = {
                    'nome_campanha': nome_campanha,
                    'periodo_inicio': periodo_inicio,
                    'valor_total_proposta': valor_total,
                    'objetivo_campanha': request.form.get('objetivo_campanha', '').strip(),
                    'periodo_fim': request.form.get('periodo_fim', '').strip() or None,
                    'responsavel_comercial': request.form.get('responsavel_comercial', type=int),
                    'briefing_id': request.form.get('briefing_id', type=int) if request.form.get('briefing_id') else None,
                    'budget_estimado': float(request.form.get('budget_estimado', '0') or 0) if request.form.get('budget_estimado') else None,
                    'observacoes': request.form.get('observacoes', '').strip(),
                    'observacoes_internas': request.form.get('observacoes_internas', '').strip(),
                    'origem': request.form.get('origem', '').strip(),
                    'status': request.form.get('status', '').strip(),
                    'expires_at': request.form.get('expires_at', '').strip() or None,
                    'link_publico_ativo': 'link_publico_ativo' in request.form,
                    'link_publico_token': request.form.get('link_publico_token', '').strip(),
                    'link_publico_expires_at': request.form.get('link_publico_expires_at', '').strip() or None,
                }

                # Remover None values para evitar conflitos
                update_kwargs = {k: v for k, v in update_kwargs.items() if v is not None and v != ''}

                db.atualizar_cotacao(cotacao_id=cotacao_id, **update_kwargs)

                registrar_auditoria(
                    acao='UPDATE',
                    modulo='cotacoes',
                    descricao=f'Cotação atualizada: {cotacao["numero_cotacao"]}',
                    registro_id=cotacao_id,
                    registro_tipo='cadu_cotacoes',
                    dados_anteriores={'nome_campanha': cotacao.get('nome_campanha'), 'valor_total_proposta': cotacao.get('valor_total_proposta')},
                    dados_novos={'nome_campanha': nome_campanha, 'valor_total_proposta': valor_total}
                )

                flash('Cotação atualizada com sucesso!', 'success')
                return redirect(url_for('cotacoes_list'))

            clientes = db.obter_clientes_simples()
            vendedores = db.obter_vendedores()
            briefings = []
            if cotacao.get('client_id'):
                briefings = db.obter_briefings_por_cliente(cotacao['client_id'])
            return render_template('cadu_cotacoes_form.html', 
                                  cotacao=cotacao, clientes=clientes, vendedores=vendedores, briefings=briefings, modo='editar')

        except Exception as e:
            app.logger.error(f"Erro ao editar cotação: {str(e)}", exc_info=True)
            flash(f'Erro ao editar cotação: {str(e)}', 'error')
            return redirect(url_for('cotacoes_list'))

    @app.route('/cotacoes/<int:cotacao_id>/detalhes', methods=['GET', 'POST'])
    @login_required
    def cotacao_detalhes(cotacao_id):
        """Página de detalhes da cotação"""
        try:
            if request.method == 'POST':
                # Atualizar cotação
                try:
                    resp_comercial = request.form.get('responsavel_comercial')
                    app.logger.info(f"DEBUG: Responsável comercial recebido: '{resp_comercial}' (tipo: {type(resp_comercial)})")
                    
                    dados = {
                        'client_id': request.form.get('client_id'),
                        'nome_campanha': request.form.get('nome_campanha'),
                        'responsavel_comercial': resp_comercial if resp_comercial and resp_comercial.strip() else None,
                        'client_user_id': request.form.get('client_user_id'),
                        'briefing_id': request.form.get('briefing_id') if request.form.get('briefing_id') else None,
                        'objetivo_campanha': request.form.get('objetivo_campanha'),
                        'periodo_inicio': request.form.get('periodo_inicio'),
                        'periodo_fim': request.form.get('periodo_fim'),
                        'expires_at': request.form.get('expires_at'),
                        'budget_estimado': request.form.get('budget_estimado'),
                        'valor_total_proposta': request.form.get('valor_total_proposta'),
                        'status': request.form.get('status'),
                        'link_publico_ativo': bool(request.form.get('link_publico_ativo')),
                        'link_publico_token': request.form.get('link_publico_token'),
                        'link_publico_expires_at': request.form.get('link_publico_expires_at'),
                        'observacoes': request.form.get('observacoes'),
                        'observacoes_internas': request.form.get('observacoes_internas')
                    }
                    
                    db.atualizar_cotacao(cotacao_id, **dados)
                    flash('Cotação atualizada com sucesso!', 'success')
                    return redirect(url_for('cotacao_detalhes', cotacao_id=cotacao_id))
                    
                except Exception as e:
                    app.logger.error(f"Erro ao atualizar cotação: {str(e)}", exc_info=True)
                    flash('Erro ao atualizar cotação.', 'error')
            
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                flash('Cotação não encontrada.', 'error')
                return redirect(url_for('cotacoes_list'))

            clientes = db.obter_clientes_simples()
            vendedores = db.obter_vendedores()
            
            # Buscar contatos ativos do cliente da cotação
            contatos_cliente = []
            briefings = []
            briefing_atual = None
            if cotacao.get('client_id'):
                app.logger.info(f"DEBUG: Buscando briefings para client_id={cotacao['client_id']}")
                contatos_cliente = db.obter_contatos_ativos_por_cliente(cotacao['client_id'])
                briefings = db.obter_briefings_por_cliente(cotacao['client_id'])
                app.logger.info(f"DEBUG: Encontrados {len(briefings)} briefings")
            
            # Buscar briefing selecionado
            if cotacao.get('briefing_id'):
                briefing_atual = db.obter_briefing_por_id(cotacao['briefing_id'])
            
            # Buscar linhas da cotação
            linhas = db.obter_linhas_cotacao(cotacao_id)
            
            # Buscar audiências da cotação
            audiencias = db.obter_audiencias_cotacao(cotacao_id)
            
            # Buscar comentários da cotação
            comentarios = db.obter_comentarios_cotacao(cotacao_id)
            
            return render_template('cadu_cotacoes_detalhes.html', 
                                  modo='editar',
                                  cotacao=cotacao, 
                                  clientes=clientes, 
                                  vendedores=vendedores,
                                  contatos_cliente=contatos_cliente,
                                  briefings=briefings,
                                  briefing_atual=briefing_atual,
                                  linhas=linhas,
                                  audiencias=audiencias,
                                  comentarios=comentarios)

        except Exception as e:
            app.logger.error(f"Erro ao carregar detalhes da cotação: {str(e)}", exc_info=True)
            flash('Erro ao carregar cotação.', 'error')
            return redirect(url_for('cotacoes_list'))

    @app.route('/teste-rota')
    def teste_rota():
        """Rota de teste"""
        return "Rota de teste funcionando!"

    @app.route('/cotacao/publico/<string:token>')
    def cotacao_publica(token):
        """Visualização pública da cotação via token compartilhável"""
        try:
            from datetime import datetime
            
            app.logger.info(f"Acessando cotação pública com token: {token[:10]}...")
            
            # Buscar cotação pelo token
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT * FROM cadu_cotacoes 
                    WHERE link_publico_token = %s 
                    AND link_publico_ativo = TRUE
                    AND deleted_at IS NULL
                ''', (token,))
                cotacao = cursor.fetchone()
            
            app.logger.info(f"Cotação encontrada: {cotacao is not None}")
            
            if not cotacao:
                return render_template('erro_publico.html', 
                    mensagem='Link inválido ou expirado'), 404
            
            # Verificar se o link expirou
            if cotacao.get('link_publico_expires_at'):
                expires_at = cotacao['link_publico_expires_at']
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                if expires_at < datetime.now():
                    return render_template('erro_publico.html', 
                        mensagem='Este link expirou'), 410
            
            cotacao_id = cotacao['id']
            
            # Buscar informações do responsável comercial
            responsavel_info = None
            if cotacao.get('responsavel_comercial'):
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT nome_completo, email 
                        FROM tbl_contato_cliente 
                        WHERE id_contato_cliente = %s AND status = TRUE
                    ''', (cotacao['responsavel_comercial'],))
                    responsavel_info = cursor.fetchone()
            
            # Buscar informações adicionais
            cliente_info = None
            if cotacao.get('client_id'):
                cliente_info = db.obter_cliente_por_id(cotacao['client_id'])
            
            briefing_atual = None
            if cotacao.get('briefing_id'):
                briefing_atual = db.obter_briefing_por_id(cotacao['briefing_id'])
            
            # Buscar linhas da cotação
            linhas = db.obter_linhas_cotacao(cotacao_id)
            
            # Buscar audiências da cotação
            audiencias = db.obter_audiencias_cotacao(cotacao_id)
            
            # Buscar anexos da cotação
            anexos = db.obter_anexos_cotacao(cotacao_id)
            
            # Renderizar template público (sem edição)
            return render_template('cadu_cotacao_publica.html', 
                                  cotacao=cotacao,
                                  cliente=cliente_info,
                                  responsavel=responsavel_info,
                                  briefing=briefing_atual,
                                  linhas=linhas,
                                  audiencias=audiencias,
                                  anexos=anexos)

        except Exception as e:
            app.logger.error(f"Erro ao carregar cotação pública: {str(e)}", exc_info=True)
            return render_template('erro_publico.html', 
                mensagem='Erro ao carregar cotação'), 500

    @app.route('/download/anexo/<int:anexo_id>')
    def download_anexo(anexo_id):
        """Download de anexo - acessível publicamente"""
        try:
            from flask import send_file
            import os
            
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT nome_arquivo, nome_original, url_arquivo
                    FROM cadu_cotacao_anexos 
                    WHERE id = %s
                ''', (anexo_id,))
                anexo = cursor.fetchone()
            
            if not anexo:
                return "Anexo não encontrado", 404
            
            # Tentar diferentes caminhos possíveis
            upload_base = os.path.join(app.root_path, 'static', 'uploads')
            
            # Possibilidade 1: nome_arquivo direto
            file_path = os.path.join(upload_base, anexo['nome_arquivo'])
            
            # Possibilidade 2: com subdiretório cotacoes/
            if not os.path.exists(file_path):
                file_path = os.path.join(upload_base, 'cotacoes', anexo['nome_arquivo'])
            
            # Possibilidade 3: usar url_arquivo
            if not os.path.exists(file_path) and anexo.get('url_arquivo'):
                url_path = anexo['url_arquivo']
                # Remover prefixos comuns
                for prefix in ['uploads/', 'static/uploads/', '/uploads/', '/static/uploads/']:
                    if url_path.startswith(prefix):
                        url_path = url_path[len(prefix):]
                        break
                file_path = os.path.join(upload_base, url_path)
            
            if not os.path.exists(file_path):
                return "Arquivo não encontrado no servidor", 404
            
            return send_file(
                file_path,
                as_attachment=True,
                download_name=anexo['nome_original'],
                mimetype='application/octet-stream'
            )
            
        except Exception as e:
            return f"Erro ao baixar arquivo: {str(e)}", 500
            return "Erro ao baixar arquivo", 500

    @app.route('/api/cotacoes/<int:cotacao_id>/atualizar', methods=['PATCH'])
    @login_required
    def api_atualizar_cotacao(cotacao_id):
        """API para atualizar campos específicos da cotação via AJAX"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'message': 'Nenhum dado fornecido'}), 400

            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404

            # Armazenar dados anteriores para auditoria
            dados_anteriores = {}
            dados_novos = {}

            # Campos permitidos para atualização
            campos_permitidos = [
                'nome_campanha', 'objetivo_campanha', 'responsavel_comercial',
                'periodo_inicio', 'periodo_fim', 'expires_at',
                'budget_estimado', 'valor_total_proposta',
                'briefing_id',
                'client_user_id',
                'observacoes', 'observacoes_internas', 'origem',
                'status', 'link_publico_ativo', 'link_publico_token', 'link_publico_expires_at', 'aprovada_em'
            ]

            # Coletar dados para atualização
            update_data = {}
            for campo in campos_permitidos:
                if campo in data:
                    valor_novo = data[campo]
                    valor_anterior = cotacao.get(campo)
                    
                    if valor_anterior != valor_novo:
                        update_data[campo] = valor_novo
                        dados_anteriores[campo] = valor_anterior
                        dados_novos[campo] = valor_novo

            if not update_data:
                return jsonify({'success': True, 'message': 'Nenhuma alteração necessária'})

            # Atualizar no banco
            db.atualizar_cotacao(cotacao_id=cotacao_id, **update_data)

            # Registrar auditoria
            registrar_auditoria(
                acao='UPDATE',
                modulo='cotacoes',
                descricao=f'Cotação atualizada: {cotacao["numero_cotacao"]}',
                registro_id=cotacao_id,
                registro_tipo='cadu_cotacoes',
                dados_anteriores=dados_anteriores,
                dados_novos=dados_novos
            )

            return jsonify({'success': True, 'message': 'Cotação atualizada com sucesso'})

        except Exception as e:
            app.logger.error(f"Erro ao atualizar cotação via API: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/cotacoes/<int:cotacao_id>/enviar-email', methods=['POST'])
    @login_required
    def enviar_email_cotacao(cotacao_id):
        """API para enviar email relacionado à cotação"""
        try:
            data = request.get_json()
            
            tipo = data.get('tipo')
            destinatario = data.get('destinatario')
            cc = data.get('cc', '')
            assunto = data.get('assunto')
            mensagem = data.get('mensagem')
            
            if not all([tipo, destinatario, assunto, mensagem]):
                return jsonify({'success': False, 'message': 'Campos obrigatórios faltando'}), 400
            
            # Buscar cotação
            cotacao = db.obter_cotacao(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            # Preparar lista de destinatários CC
            cc_list = [email.strip() for email in cc.split(',') if email.strip()] if cc else []
            
            # Enviar email usando o serviço de email
            try:
                from aicentralv2.email_service import enviar_email
                
                # Criar corpo HTML do email
                corpo_html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="white-space: pre-wrap;">{mensagem}</div>
                        
                        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                        
                        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
                            <p style="margin: 0 0 10px 0; font-weight: bold;">Informações da Cotação:</p>
                            <p style="margin: 5px 0;"><strong>Número:</strong> {cotacao['numero_cotacao']}</p>
                            <p style="margin: 5px 0;"><strong>Cliente:</strong> {cotacao.get('cliente_nome', 'Não especificado')}</p>
                            <p style="margin: 5px 0;"><strong>Campanha:</strong> {cotacao.get('nome_campanha', '-')}</p>
                            <p style="margin: 5px 0;"><strong>Status:</strong> {cotacao.get('status', 'pendente')}</p>
                        </div>
                        
                        <p style="margin-top: 30px; font-size: 12px; color: #666;">
                            Este email foi enviado através do sistema CentralComm AI
                        </p>
                    </div>
                </body>
                </html>
                """
                
                # Enviar email
                resultado = enviar_email(
                    destinatario=destinatario,
                    assunto=assunto,
                    corpo_html=corpo_html,
                    cc=cc_list
                )
                
                if resultado:
                    # Registrar auditoria
                    registrar_auditoria(
                        acao='EMAIL_SENT',
                        modulo='cotacoes',
                        descricao=f'Email {tipo} enviado para {destinatario} - Cotação {cotacao["numero_cotacao"]}',
                        registro_id=cotacao_id,
                        registro_tipo='cadu_cotacoes',
                        dados_novos={
                            'tipo': tipo,
                            'destinatario': destinatario,
                            'cc': cc_list,
                            'assunto': assunto
                        }
                    )
                    
                    return jsonify({'success': True, 'message': 'Email enviado com sucesso'})
                else:
                    return jsonify({'success': False, 'message': 'Falha ao enviar email'}), 500
                    
            except ImportError:
                # Se email_service não estiver disponível, simular sucesso
                app.logger.warning('email_service não disponível, simulando envio de email')
                return jsonify({'success': True, 'message': 'Email registrado (modo simulação)'})
            
        except Exception as e:
            app.logger.error(f"Erro ao enviar email: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/briefings/cliente/<int:cliente_id>')
    @login_required
    def api_briefings_por_cliente(cliente_id):
        """API para obter briefings de um cliente"""
        try:
            briefings = db.obter_briefings_por_cliente(cliente_id)
            return jsonify(briefings)
        except Exception as e:
            app.logger.error(f"Erro ao buscar briefings do cliente: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/clientes/<int:cliente_id>/contatos')
    @login_required
    def api_contatos_por_cliente(cliente_id):
        """API para obter contatos ativos de um cliente"""
        try:
            contatos = db.obter_contatos_ativos_por_cliente(cliente_id)
            return jsonify(contatos)
        except Exception as e:
            app.logger.error(f"Erro ao buscar contatos do cliente: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cotacoes/linhas', methods=['POST'])
    @login_required
    def criar_linha_cotacao_api():
        """API para criar nova linha de cotação"""
        try:
            data = request.get_json()
            cotacao_id = data.get('cotacao_id')
            
            if not cotacao_id:
                return jsonify({'error': 'cotacao_id é obrigatório'}), 400
            
            # Criar linha
            linha_id = db.criar_linha_cotacao(
                cotacao_id=cotacao_id,
                pedido_sugestao=data.get('pedido_sugestao'),
                target=data.get('target'),
                veiculo=data.get('veiculo'),
                plataforma=data.get('plataforma'),
                produto=data.get('produto'),
                detalhamento=data.get('detalhamento'),
                formato=data.get('formato'),
                formato_compra=data.get('formato_compra'),
                periodo=data.get('periodo'),
                viewability_minimo=data.get('viewability_minimo'),
                volume_contratado=data.get('volume_contratado'),
                valor_unitario=data.get('valor_unitario'),
                valor_total=data.get('valor_total'),
                is_header=data.get('is_header', False),
                is_subtotal=data.get('is_subtotal', False),
                subtotal_label=data.get('subtotal_label'),
                meio=data.get('meio'),
                tipo_peca=data.get('tipo_peca'),
                # Novos campos
                segmentacao=data.get('segmentacao'),
                formatos=data.get('formatos'),
                canal=data.get('canal'),
                objetivo_kpi=data.get('objetivo_kpi'),
                data_inicio=data.get('data_inicio'),
                data_fim=data.get('data_fim'),
                investimento_bruto=data.get('investimento_bruto'),
                especificacoes=data.get('especificacoes')
            )
            
            return jsonify({'success': True, 'linha_id': linha_id}), 201
        except Exception as e:
            app.logger.error(f"Erro ao criar linha de cotação: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500


    @app.route('/api/cotacoes/linhas/<int:linha_id>', methods=['GET'])
    @login_required
    def obter_linha_cotacao_api(linha_id):
        """Obtém dados de uma linha específica"""
        try:
            linha = db.obter_linha_cotacao(linha_id)
            if not linha:
                return jsonify({'success': False, 'message': 'Linha não encontrada'}), 404
            return jsonify({'success': True, 'linha': linha})
        except Exception as e:
            app.logger.error(f"Erro ao obter linha: {str(e)}")
            return jsonify({'error': str(e)}), 500


    @app.route('/api/cotacoes/linhas/<int:linha_id>', methods=['PUT'])
    @login_required
    def atualizar_linha_cotacao_api(linha_id):
        """Atualiza uma linha de cotação"""
        try:
            data = request.get_json()
            
            db.atualizar_linha_cotacao(
                linha_id=linha_id,
                pedido_sugestao=data.get('pedido_sugestao'),
                target=data.get('target'),
                veiculo=data.get('veiculo'),
                plataforma=data.get('plataforma'),
                produto=data.get('produto'),
                detalhamento=data.get('detalhamento'),
                formato=data.get('formato'),
                formato_compra=data.get('formato_compra'),
                periodo=data.get('periodo'),
                viewability_minimo=data.get('viewability_minimo'),
                volume_contratado=data.get('volume_contratado'),
                valor_unitario=data.get('valor_unitario'),
                valor_total=data.get('valor_total'),
                meio=data.get('meio'),
                tipo_peca=data.get('tipo_peca'),
                is_subtotal=data.get('is_subtotal'),
                subtotal_label=data.get('subtotal_label'),
                # Novos campos
                segmentacao=data.get('segmentacao'),
                formatos=data.get('formatos'),
                canal=data.get('canal'),
                objetivo_kpi=data.get('objetivo_kpi'),
                data_inicio=data.get('data_inicio'),
                data_fim=data.get('data_fim'),
                investimento_bruto=data.get('investimento_bruto'),
                especificacoes=data.get('especificacoes')
            )
            
            return jsonify({'success': True, 'message': 'Linha atualizada com sucesso'})
        except Exception as e:
            app.logger.error(f"Erro ao atualizar linha: {str(e)}")
            return jsonify({'error': str(e)}), 500


    @app.route('/api/cotacoes/linhas/<int:linha_id>', methods=['DELETE'])
    @login_required
    def remover_linha_cotacao_api(linha_id):
        """Remove uma linha de cotação"""
        try:
            db.deletar_linha_cotacao(linha_id)
            return jsonify({'success': True, 'message': 'Linha removida com sucesso'})
        except Exception as e:
            app.logger.error(f"Erro ao remover linha: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/audiencias/buscar')
    @login_required
    def buscar_audiencias_api():
        """API para buscar audiências por termo"""
        try:
            termo = request.args.get('q', '')
            if not termo or len(termo) < 2:
                return jsonify([])
            
            audiencias = db.buscar_audiencias(termo)
            return jsonify(audiencias)
        except Exception as e:
            app.logger.error(f"Erro ao buscar audiências: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/audiencias/<int:audiencia_id>')
    @login_required
    def obter_audiencia_completa_api(audiencia_id):
        """API para obter dados completos de uma audiência"""
        try:
            audiencia = db.obter_cadu_audiencia_por_id(audiencia_id)
            if not audiencia:
                return jsonify({'error': 'Audiência não encontrada'}), 404
            return jsonify(audiencia)
        except Exception as e:
            app.logger.error(f"Erro ao buscar audiência: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cotacoes/audiencias', methods=['POST'])
    @login_required
    def criar_audiencia_cotacao_api():
        """API para adicionar audiência à cotação"""
        try:
            data = request.get_json()
            cotacao_id = data.get('cotacao_id')
            audiencia_nome = data.get('audiencia_nome')
            
            if not cotacao_id or not audiencia_nome:
                return jsonify({'error': 'cotacao_id e audiencia_nome são obrigatórios'}), 400
            
            # Adicionar audiência
            audiencia_id = db.adicionar_audiencia_cotacao(
                cotacao_id=cotacao_id,
                audiencia_id=data.get('audiencia_id'),
                audiencia_nome=audiencia_nome,
                audiencia_publico=data.get('audiencia_publico'),
                audiencia_categoria=data.get('audiencia_categoria'),
                audiencia_subcategoria=data.get('audiencia_subcategoria'),
                cpm_estimado=data.get('cpm_estimado'),
                investimento_sugerido=data.get('investimento_sugerido'),
                impressoes_estimadas=data.get('impressoes_estimadas'),
                incluido_proposta=data.get('incluido_proposta', True)
            )
            
            return jsonify({'success': True, 'audiencia_id': audiencia_id}), 201
        except Exception as e:
            app.logger.error(f"Erro ao adicionar audiência: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cotacoes/audiencias/<int:audiencia_id>', methods=['PUT'])
    @login_required
    def atualizar_audiencia_cotacao_api(audiencia_id):
        """API para atualizar audiência da cotação"""
        try:
            data = request.get_json()
            
            # Atualizar audiência
            db.atualizar_audiencia_cotacao(
                audiencia_cotacao_id=audiencia_id,
                cpm_estimado=data.get('cpm_estimado'),
                investimento_sugerido=data.get('investimento_sugerido'),
                impressoes_estimadas=data.get('impressoes_estimadas'),
                incluido_proposta=data.get('incluido_proposta')
            )
            
            return jsonify({'success': True}), 200
        except Exception as e:
            app.logger.error(f"Erro ao atualizar audiência: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cotacoes/audiencias/<int:audiencia_id>', methods=['DELETE'])
    @login_required
    def remover_audiencia_cotacao_api(audiencia_id):
        """API para remover audiência da cotação"""
        try:
            db.remover_audiencia_cotacao(audiencia_id)
            return jsonify({'success': True}), 200
        except Exception as e:
            app.logger.error(f"Erro ao remover audiência: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cotacoes/<int:cotacao_id>/deletar', methods=['DELETE'])

    @login_required
    def deletar_cotacao(cotacao_id):
        """API para deletar cotação"""
        try:
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404

            db.deletar_cotacao(cotacao_id)

            registrar_auditoria(
                acao='DELETE',
                modulo='cotacoes',
                descricao=f'Cotação deletada: {cotacao["numero_cotacao"]}',
                registro_id=cotacao_id,
                registro_tipo='cadu_cotacoes',
                dados_anteriores={'titulo': cotacao['titulo'], 'numero_cotacao': cotacao['numero_cotacao']}
            )

            flash('Cotação deletada com sucesso!', 'success')
            return jsonify({'success': True})

        except Exception as e:
            app.logger.error(f"Erro ao deletar cotação: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500


    # ==================== COMENTÁRIOS DE COTAÇÃO ====================
    
    @app.route('/api/cotacoes/<int:cotacao_id>/comentarios', methods=['GET'])
    @login_required
    def obter_comentarios_cotacao(cotacao_id):
        """Obtém todos os comentários de uma cotação"""
        try:
            comentarios = db.obter_comentarios_cotacao(cotacao_id)
            return jsonify({'success': True, 'comentarios': comentarios})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter comentários: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/cotacoes/<int:cotacao_id>/comentarios', methods=['POST'])
    @login_required
    def adicionar_comentario_cotacao(cotacao_id):
        """Adiciona um comentário à cotação"""
        try:
            data = request.get_json()
            comentario = data.get('comentario', '').strip()
            
            if not comentario:
                return jsonify({'success': False, 'message': 'Comentário não pode estar vazio'}), 400
            
            # Determinar user_id e user_type
            user_id = session.get('user_id')
            user_type = 'admin' if session.get('is_admin') else 'client'
            
            result = db.adicionar_comentario_cotacao(cotacao_id, user_id, user_type, comentario)
            
            registrar_auditoria(
                acao='INSERT',
                modulo='cotacoes',
                descricao=f'Comentário adicionado à cotação ID {cotacao_id}',
                registro_id=result['id'],
                registro_tipo='cadu_cotacao_comentarios'
            )
            
            return jsonify({
                'success': True, 
                'message': 'Comentário adicionado com sucesso',
                'comentario_id': result['id'],
                'created_at': result['created_at'].isoformat() if result['created_at'] else None
            })
            
        except Exception as e:
            current_app.logger.error(f"Erro ao adicionar comentário: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/cotacoes/comentarios/<int:comentario_id>', methods=['DELETE'])
    @login_required
    def remover_comentario_cotacao(comentario_id):
        """Remove um comentário"""
        try:
            user_id = session.get('user_id')
            user_type = 'admin' if session.get('is_admin') else 'client'
            
            sucesso = db.remover_comentario_cotacao(comentario_id, user_id, user_type)
            
            if sucesso:
                registrar_auditoria(
                    acao='DELETE',
                    modulo='cotacoes',
                    descricao=f'Comentário removido ID {comentario_id}',
                    registro_id=comentario_id,
                    registro_tipo='cadu_cotacao_comentarios'
                )
                return jsonify({'success': True, 'message': 'Comentário removido com sucesso'})
            else:
                return jsonify({'success': False, 'message': 'Comentário não encontrado ou sem permissão'}), 404
                
        except Exception as e:
            current_app.logger.error(f"Erro ao remover comentário: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    
    @app.route('/api/cotacoes/audiencias/<int:audiencia_id>/dados', methods=['GET'])
    @login_required
    def obter_dados_audiencia_cotacao(audiencia_id):
        """Obtém dados de uma audiência específica da cotação para edição"""
        try:
            audiencia = db.obter_audiencia_cotacao_por_id(audiencia_id)
            
            if not audiencia:
                return jsonify({'success': False, 'message': 'Audiência não encontrada'}), 404
            
            return jsonify({'success': True, 'audiencia': audiencia})
            
        except Exception as e:
            current_app.logger.error(f"Erro ao obter dados da audiência: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    
    @app.route('/api/cotacoes/<int:cotacao_id>/link-publico/gerar', methods=['POST'])
    @login_required
    def gerar_link_publico(cotacao_id):
        """Gera um novo link público para a cotação"""
        try:
            data = request.get_json() or {}
            dias_validade = data.get('dias_validade', 30)
            
            # Obter UUID da cotação
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            cotacao_uuid = cotacao.get('cotacao_uuid')
            if not cotacao_uuid:
                return jsonify({'success': False, 'message': 'UUID da cotação não encontrado'}), 400
            
            # Gerar token
            token = db.gerar_link_publico_cotacao(cotacao_uuid, dias_validade)
            
            if token:
                # Construir URL completa
                base_url = request.host_url.rstrip('/')
                link_publico = f"{base_url}/cotacao/publico/{token}"
                
                registrar_auditoria(
                    acao='UPDATE',
                    modulo='cotacoes',
                    descricao=f'Link público gerado para cotação {cotacao_id}',
                    registro_id=cotacao_id,
                    registro_tipo='cadu_cotacoes'
                )
                
                return jsonify({'success': True, 'link': link_publico, 'token': token})
            else:
                return jsonify({'success': False, 'message': 'Erro ao gerar link público'}), 500
                
        except Exception as e:
            app.logger.error(f"Erro ao gerar link público: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/cotacoes/<int:cotacao_id>/link-publico', methods=['PUT'])
    @login_required
    def atualizar_link_publico(cotacao_id):
        """Atualiza as configurações do link público da cotação"""
        try:
            data = request.get_json() or {}
            
            # Obter cotação
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            # Atualizar campos
            updates = {}
            
            # Link público ativo
            if 'link_publico_ativo' in data:
                updates['link_publico_ativo'] = data['link_publico_ativo']
            
            # Token personalizado
            if 'link_publico_token' in data:
                token = data['link_publico_token']
                if token:
                    updates['link_publico_token'] = token
                else:
                    # Se não forneceu token, gerar um novo
                    import secrets
                    updates['link_publico_token'] = secrets.token_urlsafe(16)
            elif updates.get('link_publico_ativo') and not cotacao.get('link_publico_token'):
                # Se ativou o link mas não tem token, gerar um
                import secrets
                updates['link_publico_token'] = secrets.token_urlsafe(16)
            
            # Data de expiração
            if 'link_publico_expires_at' in data:
                updates['link_publico_expires_at'] = data['link_publico_expires_at']
            
            # Atualizar cotação
            if updates:
                success = db.atualizar_cotacao(cotacao_id, **updates)
                
                if success:
                    registrar_auditoria(
                        acao='UPDATE',
                        modulo='cotacoes',
                        descricao=f'Configurações do link público atualizadas para cotação {cotacao_id}',
                        registro_id=cotacao_id,
                        registro_tipo='cadu_cotacoes'
                    )
                    
                    return jsonify({'success': True, 'message': 'Link público atualizado com sucesso'})
                else:
                    return jsonify({'success': False, 'message': 'Erro ao atualizar link público'}), 500
            else:
                return jsonify({'success': True, 'message': 'Nenhuma alteração realizada'})
                
        except Exception as e:
            app.logger.error(f"Erro ao atualizar link público: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/cotacoes/<int:cotacao_id>/pdf', methods=['GET'])
    @login_required
    def exportar_cotacao_pdf(cotacao_id):
        """Exporta cotação para PDF"""
        try:
            from flask import make_response
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            # Obter dados da cotação
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                flash('Cotação não encontrada', 'error')
                return redirect(url_for('cotacoes_list'))
            
            # Obter dados relacionados
            cliente = db.obter_cliente_por_id(cotacao['client_id']) if cotacao.get('client_id') else None
            linhas = db.obter_linhas_cotacao(cotacao_id)
            audiencias = db.obter_audiencias_cotacao(cotacao_id)
            
            # Criar PDF em memória
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
            
            # Estilos
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1e3a8a'), spaceAfter=12, alignment=TA_CENTER)
            heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#1e3a8a'), spaceAfter=8, spaceBefore=12)
            normal_style = styles['Normal']
            
            # Conteúdo do PDF
            story = []
            
            # Título
            story.append(Paragraph("PROPOSTA COMERCIAL", title_style))
            story.append(Spacer(1, 10*mm))
            
            # Informações da Cotação
            info_data = [
                ['Número:', cotacao.get('numero_cotacao', 'N/A')],
                ['Cliente:', cliente.get('nome_fantasia', 'N/A') if cliente else 'N/A'],
                ['Campanha:', cotacao.get('nome_campanha', 'N/A')],
                ['Data Criação:', cotacao.get('created_at').strftime('%d/%m/%Y') if cotacao.get('created_at') else 'N/A'],
                ['Status:', cotacao.get('status', 'N/A')],
                ['Responsável:', cotacao.get('responsavel_comercial', 'N/A')],
            ]
            
            info_table = Table(info_data, colWidths=[40*mm, 130*mm])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1e3a8a')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 8*mm))
            
            # Linhas de Cotação
            if linhas:
                story.append(Paragraph("Itens da Proposta", heading_style))
                
                linhas_data = [['Item', 'Descrição', 'Plataforma', 'Período', 'Volume', 'Valor Unit.', 'Total']]
                
                for idx, linha in enumerate(linhas, 1):
                    # Montar descrição
                    descricao_parts = []
                    if linha.get('segmentacao'):
                        descricao_parts.append(linha['segmentacao'])
                    if linha.get('especificacoes'):
                        descricao_parts.append(linha['especificacoes'])
                    descricao = ' - '.join(descricao_parts) if descricao_parts else 'N/A'
                    
                    periodo = ''
                    if linha.get('data_inicio') and linha.get('data_fim'):
                        periodo = f"{linha['data_inicio'].strftime('%d/%m') if hasattr(linha['data_inicio'], 'strftime') else linha['data_inicio']} a {linha['data_fim'].strftime('%d/%m') if hasattr(linha['data_fim'], 'strftime') else linha['data_fim']}"
                    
                    linhas_data.append([
                        str(idx),
                        Paragraph(descricao[:80], normal_style) if len(descricao) > 80 else descricao,
                        linha.get('plataforma', 'N/A'),
                        periodo,
                        f"{linha.get('volume_contratado', 0):,.0f}".replace(',', '.') if linha.get('volume_contratado') else '-',
                        f"R$ {linha.get('valor_unitario', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if linha.get('valor_unitario') else '-',
                        f"R$ {linha.get('investimento_bruto', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if linha.get('investimento_bruto') else '-'
                    ])
                
                linhas_table = Table(linhas_data, colWidths=[12*mm, 48*mm, 25*mm, 22*mm, 20*mm, 22*mm, 22*mm])
                linhas_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(linhas_table)
                story.append(Spacer(1, 6*mm))
            
            # Valores Totais
            story.append(Paragraph("Resumo Financeiro", heading_style))
            valores_data = []
            
            if cotacao.get('budget_estimado'):
                valores_data.append(['Budget Estimado:', f"R$ {cotacao['budget_estimado']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')])
            
            if cotacao.get('valor_total_proposta'):
                valores_data.append(['Valor Total da Proposta:', f"R$ {cotacao['valor_total_proposta']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')])
            
            if valores_data:
                valores_table = Table(valores_data, colWidths=[60*mm, 110*mm])
                valores_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(valores_table)
            
            # Gerar PDF
            doc.build(story)
            buffer.seek(0)
            
            # Criar resposta
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=cotacao_{cotacao.get("numero_cotacao", cotacao_id)}.pdf'
            
            registrar_auditoria(
                acao='EXPORT',
                modulo='cotacoes',
                descricao=f'Cotação {cotacao_id} exportada para PDF',
                registro_id=cotacao_id,
                registro_tipo='cadu_cotacoes'
            )
            
            return response
            
        except ImportError as e:
            app.logger.error(f"Erro ao importar reportlab: {str(e)}")
            flash('Biblioteca reportlab não instalada. Execute: pip install reportlab', 'error')
            return redirect(url_for('cotacao_detalhes', cotacao_id=cotacao_id))
        except Exception as e:
            app.logger.error(f"Erro ao exportar PDF: {str(e)}", exc_info=True)
            flash(f'Erro ao exportar PDF: {str(e)}', 'error')
            return redirect(url_for('cotacao_detalhes', cotacao_id=cotacao_id))

    @app.route('/api/cotacoes/<int:cotacao_id>/duplicar', methods=['POST'])
    @login_required
    def duplicar_cotacao(cotacao_id):
        """Duplica uma cotação existente"""
        try:
            # Obter cotação original
            cotacao_original = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao_original:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            # Copiar dados da cotação (sem ID, timestamps, etc)
            dados_nova_cotacao = {
                'client_id': cotacao_original.get('client_id'),
                'nome_campanha': f"{cotacao_original.get('nome_campanha', '')} (CÓPIA)",
                'objetivo_campanha': cotacao_original.get('objetivo_campanha'),
                'periodo_inicio': cotacao_original.get('periodo_inicio'),
                'periodo_fim': cotacao_original.get('periodo_fim'),
                'responsavel_comercial': cotacao_original.get('responsavel_comercial'),
                'client_user_id': cotacao_original.get('client_user_id'),
                'briefing_id': cotacao_original.get('briefing_id'),
                'budget_estimado': cotacao_original.get('budget_estimado'),
                'status': 'Rascunho',
                'observacoes': cotacao_original.get('observacoes'),
                'origem': cotacao_original.get('origem', 'Admin')
            }
            
            # Criar nova cotação
            resultado_nova_cotacao = db.criar_cotacao(**dados_nova_cotacao)
            nova_cotacao_id = resultado_nova_cotacao['id'] if isinstance(resultado_nova_cotacao, dict) else resultado_nova_cotacao
            
            if nova_cotacao_id:
                # Copiar linhas de cotação
                import json
                linhas_originais = db.obter_linhas_cotacao(cotacao_id)
                for linha in linhas_originais:
                    # Converter campos dict/array para JSON string
                    def converter_json(valor):
                        if valor is None:
                            return None
                        if isinstance(valor, (dict, list)):
                            return json.dumps(valor)
                        if isinstance(valor, str):
                            return valor
                        return None
                    
                    db.criar_linha_cotacao(
                        cotacao_id=nova_cotacao_id,
                        pedido_sugestao=linha.get('pedido_sugestao'),
                        target=linha.get('target'),
                        veiculo=linha.get('veiculo'),
                        plataforma=linha.get('plataforma'),
                        detalhamento=linha.get('detalhamento'),
                        formato=linha.get('formato'),
                        formato_compra=linha.get('formato_compra'),
                        periodo=linha.get('periodo'),
                        viewability_minimo=linha.get('viewability_minimo'),
                        volume_contratado=linha.get('volume_contratado'),
                        valor_unitario=linha.get('valor_unitario'),
                        valor_total=linha.get('valor_total'),
                        ordem=linha.get('ordem', 0),
                        is_subtotal=linha.get('is_subtotal', False),
                        subtotal_label=linha.get('subtotal_label'),
                        is_header=linha.get('is_header', False),
                        meio=linha.get('meio'),
                        tipo_peca=linha.get('tipo_peca'),
                        segmentacao=linha.get('segmentacao'),
                        formatos=converter_json(linha.get('formatos')),
                        canal=converter_json(linha.get('canal')),
                        objetivo_kpi=linha.get('objetivo_kpi'),
                        data_inicio=linha.get('data_inicio'),
                        data_fim=linha.get('data_fim'),
                        investimento_bruto=linha.get('investimento_bruto'),
                        produto=converter_json(linha.get('produto')),
                        especificacoes=linha.get('especificacoes'),
                        dados_extras=converter_json(linha.get('dados_extras'))
                    )
                
                # Copiar audiências
                audiencias_originais = db.obter_audiencias_cotacao(cotacao_id)
                for audiencia in audiencias_originais:
                    db.adicionar_audiencia_cotacao(
                        cotacao_id=nova_cotacao_id,
                        audiencia_nome=audiencia.get('audiencia_nome'),
                        audiencia_id=audiencia.get('audiencia_id'),
                        audiencia_publico=audiencia.get('audiencia_publico'),
                        audiencia_categoria=audiencia.get('audiencia_categoria'),
                        audiencia_subcategoria=audiencia.get('audiencia_subcategoria'),
                        cpm_estimado=audiencia.get('cpm_estimado'),
                        investimento_sugerido=audiencia.get('investimento_sugerido'),
                        impressoes_estimadas=audiencia.get('impressoes_estimadas'),
                        incluido_proposta=audiencia.get('incluido_proposta', True)
                    )
                
                # Copiar anexos
                anexos_originais = db.obter_anexos_cotacao(cotacao_id)
                for anexo in anexos_originais:
                    db.criar_anexo_cotacao(
                        cotacao_id=nova_cotacao_id,
                        nome_original=anexo.get('nome_original'),
                        nome_arquivo=anexo.get('nome_arquivo'),
                        url_arquivo=anexo.get('url_arquivo'),
                        mime_type=anexo.get('mime_type'),
                        tamanho_bytes=anexo.get('tamanho_bytes'),
                        descricao=anexo.get('descricao'),
                        uploaded_by=anexo.get('uploaded_by')
                    )
                
                registrar_auditoria(
                    acao='CREATE',
                    modulo='cotacoes',
                    descricao=f'Cotação {nova_cotacao_id} criada como cópia da cotação {cotacao_id}',
                    registro_id=nova_cotacao_id,
                    registro_tipo='cadu_cotacoes'
                )
                
                return jsonify({'success': True, 'nova_cotacao_id': nova_cotacao_id})
            else:
                return jsonify({'success': False, 'message': 'Erro ao criar cotação duplicada'}), 500
                
        except Exception as e:
            app.logger.error(f"Erro ao duplicar cotação: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

    # ==================== FIM DAS ROTAS ====================
            current_app.logger.error(f"Erro ao gerar link público: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    
    @app.route('/api/cotacoes/<int:cotacao_id>/link-publico/renovar', methods=['POST'])
    @login_required
    def renovar_link_publico(cotacao_id):
        """Renova a validade de um link público existente"""
        try:
            data = request.get_json() or {}
            dias_validade = data.get('dias_validade', 30)
            
            # Obter UUID da cotação
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            cotacao_uuid = cotacao.get('cotacao_uuid')
            if not cotacao_uuid:
                return jsonify({'success': False, 'message': 'UUID da cotação não encontrado'}), 400
            
            # Renovar link
            nova_expiracao = db.renovar_link_publico_cotacao(cotacao_uuid, dias_validade)
            
            if nova_expiracao:
                registrar_auditoria(
                    acao='UPDATE',
                    modulo='cotacoes',
                    descricao=f'Link público renovado para cotação {cotacao_id}',
                    registro_id=cotacao_id,
                    registro_tipo='cadu_cotacoes'
                )
                
                return jsonify({
                    'success': True, 
                    'nova_expiracao': nova_expiracao.isoformat(),
                    'message': 'Link público renovado com sucesso'
                })
            else:
                return jsonify({'success': False, 'message': 'Erro ao renovar link público'}), 500
                
        except Exception as e:
            current_app.logger.error(f"Erro ao renovar link público: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    
    @app.route('/api/cotacoes/<int:cotacao_id>/calcular-total', methods=['POST'])
    @login_required
    def calcular_total_cotacao(cotacao_id):
        """Calcula e atualiza o valor total da cotação"""
        try:
            total = db.calcular_valor_total_cotacao(cotacao_id)
            
            registrar_auditoria(
                acao='UPDATE',
                modulo='cotacoes',
                descricao=f'Valor total calculado para cotação {cotacao_id}: R$ {total:,.2f}',
                registro_id=cotacao_id,
                registro_tipo='cadu_cotacoes'
            )
            
            return jsonify({
                'success': True, 
                'valor_total': total,
                'message': 'Valor total calculado com sucesso'
            })
                
        except Exception as e:
            current_app.logger.error(f"Erro ao calcular total da cotação: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500


    # ==================== API ANEXOS DE COTAÇÕES ====================
    
    @app.route('/api/cotacoes/<int:cotacao_id>/anexos', methods=['GET'])
    @login_required
    def listar_anexos_cotacao(cotacao_id):
        """Listar todos os anexos de uma cotação"""
        try:
            anexos = db.obter_anexos_cotacao(cotacao_id)
            return jsonify({'success': True, 'anexos': anexos})
        except Exception as e:
            current_app.logger.error(f"Erro ao listar anexos: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/cotacoes/<int:cotacao_id>/anexos', methods=['POST'])
    @login_required
    def adicionar_anexo_cotacao(cotacao_id):
        """Adicionar novo anexo à cotação"""
        try:
            # Verificar se arquivo foi enviado
            if 'arquivo' not in request.files:
                return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400
            
            arquivo = request.files['arquivo']
            if arquivo.filename == '':
                return jsonify({'success': False, 'message': 'Arquivo sem nome'}), 400
            
            # Obter dados do formulário
            descricao = request.form.get('descricao', '')
            
            # Gerar nome único para o arquivo
            import os
            import uuid
            from werkzeug.utils import secure_filename
            
            nome_original = secure_filename(arquivo.filename)
            extensao = os.path.splitext(nome_original)[1]
            nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
            
            # Criar diretório se não existir
            upload_dir = os.path.join(current_app.static_folder, 'uploads', 'cotacoes')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Salvar arquivo
            arquivo_path = os.path.join(upload_dir, nome_arquivo)
            arquivo.save(arquivo_path)
            
            # URL relativa para acesso
            url_arquivo = f"/static/uploads/cotacoes/{nome_arquivo}"
            
            # Obter tamanho do arquivo
            tamanho_bytes = os.path.getsize(arquivo_path)
            
            # Salvar no banco
            anexo_id = db.criar_anexo_cotacao(
                cotacao_id=cotacao_id,
                nome_original=nome_original,
                nome_arquivo=nome_arquivo,
                url_arquivo=url_arquivo,
                mime_type=arquivo.content_type,
                tamanho_bytes=tamanho_bytes,
                descricao=descricao,
                uploaded_by=session.get('user_id')
            )
            
            registrar_auditoria(
                acao='CREATE',
                modulo='cotacoes_anexos',
                descricao=f'Anexo adicionado à cotação {cotacao_id}: {nome_original}',
                registro_id=anexo_id,
                registro_tipo='cadu_cotacao_anexos'
            )
            
            return jsonify({
                'success': True,
                'anexo_id': anexo_id,
                'message': 'Anexo adicionado com sucesso'
            })
            
        except Exception as e:
            current_app.logger.error(f"Erro ao adicionar anexo: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Erro ao adicionar anexo: {str(e)}'}), 500
    
    
    @app.route('/api/cotacoes/<int:cotacao_id>/anexos/<int:anexo_id>', methods=['GET'])
    @login_required
    def obter_anexo_cotacao(cotacao_id, anexo_id):
        """Obter dados de um anexo específico"""
        try:
            anexo = db.obter_anexo_por_id(anexo_id)
            if not anexo:
                return jsonify({'success': False, 'message': 'Anexo não encontrado'}), 404
            return jsonify({'success': True, 'anexo': anexo})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter anexo: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/cotacoes/<int:cotacao_id>/anexos/<int:anexo_id>', methods=['PUT'])
    @login_required
    def editar_anexo_cotacao(cotacao_id, anexo_id):
        """Editar informações de um anexo"""
        try:
            data = request.json
            sucesso = db.atualizar_anexo_cotacao(
                anexo_id,
                nome_original=data.get('nome_original'),
                descricao=data.get('descricao')
            )
            
            if sucesso:
                registrar_auditoria(
                    acao='UPDATE',
                    modulo='cotacoes_anexos',
                    descricao=f'Anexo {anexo_id} da cotação {cotacao_id} editado',
                    registro_id=anexo_id,
                    registro_tipo='cadu_cotacao_anexos'
                )
                return jsonify({'success': True, 'message': 'Anexo atualizado com sucesso'})
            else:
                return jsonify({'success': False, 'message': 'Nenhuma alteração realizada'}), 400
                
        except Exception as e:
            current_app.logger.error(f"Erro ao editar anexo: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/cotacoes/<int:cotacao_id>/anexos/<int:anexo_id>', methods=['DELETE'])
    @login_required
    def deletar_anexo_cotacao(cotacao_id, anexo_id):
        """Deletar um anexo (soft delete)"""
        try:
            sucesso = db.deletar_anexo_cotacao(anexo_id, hard_delete=False)
            
            if sucesso:
                registrar_auditoria(
                    acao='DELETE',
                    modulo='cotacoes_anexos',
                    descricao=f'Anexo {anexo_id} da cotação {cotacao_id} removido',
                    registro_id=anexo_id,
                    registro_tipo='cadu_cotacao_anexos'
                )
                return jsonify({'success': True, 'message': 'Anexo removido com sucesso'})
            else:
                return jsonify({'success': False, 'message': 'Anexo não encontrado'}), 404
                
        except Exception as e:
            current_app.logger.error(f"Erro ao deletar anexo: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # ==================== API BUSCA DE CLIENTES ====================
    
    @app.route('/api/clientes/buscar', methods=['POST'])
    @login_required
    def api_buscar_clientes():
        """API para buscar clientes com filtros"""
        try:
            data = request.get_json()
            app.logger.info(f"=== API BUSCAR CLIENTES ===")
            app.logger.info(f"Data recebida: {data}")
            
            nome = data.get('nome') or ''
            razao = data.get('razao') or ''
            
            # Limpar espaços
            nome = nome.strip() if nome else ''
            razao = razao.strip() if razao else ''
            
            app.logger.info(f"Filtros processados: nome='{nome}', razao='{razao}'")
            
            # Construir query com filtros - SÓ adicionar filtros que têm valor
            query = 'SELECT id_cliente, nome_fantasia, razao_social, cnpj, pessoa FROM tbl_cliente WHERE status = true'
            params = []
            
            # Apenas adicionar filtro NOME se nome não for vazio
            if nome and len(nome) > 0:
                query += ' AND nome_fantasia ILIKE %s'
                params.append(f'%{nome}%')
                app.logger.info(f"Adicionado filtro nome: %{nome}%")
            
            # Apenas adicionar filtro RAZAO se razao não for vazio
            if razao and len(razao) > 0:
                query += ' AND razao_social ILIKE %s'
                params.append(f'%{razao}%')
                app.logger.info(f"Adicionado filtro razao: %{razao}%")
            
            if not nome and not razao:
                return jsonify({
                    'success': False,
                    'message': 'Preencha pelo menos um filtro'
                })
            
            query += ' ORDER BY nome_fantasia ASC LIMIT 50'
            
            app.logger.info(f"Query final: {query}")
            app.logger.info(f"Params: {params}")
            
            # Executar query
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                clientes = cursor.fetchall()
            
            app.logger.info(f"Resultados encontrados: {len(clientes) if clientes else 0}")
            if clientes:
                app.logger.info(f"Primeiro cliente: {dict(clientes[0]) if clientes else None}")
            
            # Converter para lista de dicts
            resultado = []
            if clientes:
                for cliente in clientes:
                    app.logger.info(f"Processando cliente: {cliente['nome_fantasia']}, id: {cliente['id_cliente']}")
                    resultado.append({
                        'pk_id_tbl_cliente': cliente['id_cliente'],
                        'nome_fantasia': cliente['nome_fantasia'],
                        'razao_social': cliente['razao_social'],
                        'cnpj': cliente['cnpj'],
                        'tipo_pessoa': cliente['pessoa']
                    })
            
            app.logger.info(f"Resultado final: {resultado}")
            return jsonify({
                'success': True,
                'clientes': resultado,
                'total': len(resultado)
            })
            
        except Exception as e:
            app.logger.error(f"Erro ao buscar clientes: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    # ==================== UP AUDIÊNCIA ====================