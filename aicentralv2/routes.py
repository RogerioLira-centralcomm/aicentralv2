# --- (ao final do arquivo, após a última rota existente) ---

# Removido endpoint direto para compatibilidade com factory
"""
Rotas da Aplicação
"""

from flask import session, redirect, url_for, flash, request, render_template, jsonify
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

    @app.route('/cotacoes')
    @login_required
    def cotacoes():
        """Lista de cotações com filtros"""
        try:
            # Obter filtros
            vendedor_id = request.args.get('vendedor', type=int)
            cliente_id = request.args.get('cliente', type=int)
            status_id = request.args.get('status', type=int)
            nome_campanha = request.args.get('campanha', '').strip()
            
            # Buscar cotações com filtros
            cotacoes_list = db.obter_cotacoes_filtradas(
                vendedor_id=vendedor_id,
                cliente_id=cliente_id,
                status_id=status_id,
                nome_campanha=nome_campanha or None
            )
            
            # Buscar dados para os dropdowns
            vendedores = db.obter_vendedores_centralcomm()
            clientes_list = db.obter_clientes_sistema(
                filtros={'status': True},
                vendedor_id=vendedor_id
            )
            status_list = db.obter_status_cotacoes()
            
            return render_template('cotacoes.html',
                cotacoes=cotacoes_list,
                vendedores=vendedores,
                clientes=clientes_list,
                status_list=status_list,
                filtro_vendedor=vendedor_id,
                filtro_cliente=cliente_id,
                filtro_status=status_id,
                filtro_campanha=nome_campanha
            )
        except Exception as e:
            app.logger.error(f"Erro ao listar cotações: {e}")
            flash('Erro ao carregar cotações!', 'error')
            return render_template('cotacoes.html', cotacoes=[], vendedores=[], clientes=[], status_list=[])

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
            
            # Buscar lista de clientes ativos para o dropdown
            clientes_ativos = db.obter_clientes_sistema({'status': True})
            
            return render_template(
                'interesse_produto.html',
                interesses=interesses,
                filtro_tipo=filtro_tipo,
                filtro_notificado=filtro_notificado,
                filtro_cliente_id=filtro_cliente_id,
                clientes_ativos=clientes_ativos or []
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

    # ==================== UP AUDIÊNCIA ====================