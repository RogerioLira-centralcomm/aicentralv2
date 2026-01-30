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
from aicentralv2.email_service import send_password_reset_email, send_password_changed_email, send_invite_email
from aicentralv2.services.openrouter_image_extract import extract_fields_from_image_bytes, get_available_models

# Helper para serializar dados para JSON
def serializar_para_json(obj):
    """Converte objetos (incluindo datetime) para formato JSON serializável"""
    from datetime import date
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: serializar_para_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serializar_para_json(item) for item in obj]
    if isinstance(obj, (datetime, date, timedelta)):
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
    """Decorator para rotas protegidas - SOMENTE CENTRALCOMM"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        
        # REGRA INQUEBRÁVEL: Verificar se usuário pertence à CENTRALCOMM
        try:
            contato = db.obter_contato_por_id(session['user_id'])
            if not contato or not contato.get('pk_id_tbl_cliente'):
                session.clear()
                flash('Acesso não autorizado.', 'error')
                return redirect(url_for('login'))
            
            cliente = db.obter_cliente_por_id(contato['pk_id_tbl_cliente'])
            if not cliente or cliente.get('nome_fantasia', '').upper() != 'CENTRALCOMM':
                session.clear()
                flash('Acesso restrito apenas para usuários CENTRALCOMM.', 'error')
                return redirect(url_for('login'))
        except Exception:
            session.clear()
            flash('Erro de autenticação.', 'error')
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

    # --- API: Buscar dados do CNPJ na ReceitaWS ---
    @app.route('/api/buscar_cnpj/<cnpj>')
    @login_required
    def buscar_cnpj(cnpj):
        """Proxy para buscar dados do CNPJ na ReceitaWS"""
        import requests
        
        # Pegar cliente_id se estiver editando (para ignorar ele mesmo na verificação)
        cliente_id_editando = request.args.get('cliente_id', None)
        
        # Remover caracteres não numéricos
        cnpj = ''.join(filter(str.isdigit, cnpj))
        
        if len(cnpj) != 14:
            return jsonify({'success': False, 'message': 'CNPJ inválido - deve ter 14 dígitos'})
        
        # Validar dígitos verificadores do CNPJ
        def validar_cnpj(cnpj):
            if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
                return False
            
            # Cálculo do primeiro dígito verificador
            multiplicadores1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            soma = sum(int(cnpj[i]) * multiplicadores1[i] for i in range(12))
            resto = soma % 11
            digito1 = 0 if resto < 2 else 11 - resto
            
            if int(cnpj[12]) != digito1:
                return False
            
            # Cálculo do segundo dígito verificador
            multiplicadores2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            soma = sum(int(cnpj[i]) * multiplicadores2[i] for i in range(13))
            resto = soma % 11
            digito2 = 0 if resto < 2 else 11 - resto
            
            return int(cnpj[13]) == digito2
        
        if not validar_cnpj(cnpj):
            return jsonify({'success': False, 'message': 'CNPJ inválido - dígitos verificadores incorretos'})
        
        # Verificar se CNPJ já existe na base de dados
        try:
            conn = db.get_db()
            with conn.cursor() as cursor:
                if cliente_id_editando:
                    # Se está editando, ignorar o próprio cliente
                    cursor.execute("""
                        SELECT id_cliente, nome_fantasia, razao_social 
                        FROM tbl_cliente 
                        WHERE REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '-', ''), '/', '') = %s
                        AND id_cliente != %s
                    """, (cnpj, cliente_id_editando))
                else:
                    cursor.execute("""
                        SELECT id_cliente, nome_fantasia, razao_social 
                        FROM tbl_cliente 
                        WHERE REPLACE(REPLACE(REPLACE(cnpj, '.', ''), '-', ''), '/', '') = %s
                    """, (cnpj,))
                
                cliente_existente = cursor.fetchone()
                
                if cliente_existente:
                    nome_cliente = cliente_existente['nome_fantasia'] or cliente_existente['razao_social'] or 'Cliente'
                    return jsonify({
                        'success': False, 
                        'message': f'CNPJ já cadastrado para: {nome_cliente}',
                        'ja_cadastrado': True,
                        'cliente_id': cliente_existente['id_cliente']
                    })
        except Exception as e:
            app.logger.error(f'Erro ao verificar CNPJ na base: {e}')
        
        try:
            # Buscar na ReceitaWS
            resp = requests.get(f'https://www.receitaws.com.br/v1/cnpj/{cnpj}', timeout=30)
            data = resp.json()
            
            if data.get('status') == 'OK':
                return jsonify({
                    'success': True,
                    'data': {
                        'razao_social': data.get('nome', ''),
                        'nome_fantasia': data.get('fantasia', ''),
                        'inscricao_estadual': data.get('inscricao_estadual', ''),
                        'inscricao_municipal': data.get('inscricao_municipal', ''),
                        'logradouro': data.get('logradouro', ''),
                        'numero': data.get('numero', ''),
                        'complemento': data.get('complemento', ''),
                        'bairro': data.get('bairro', ''),
                        'municipio': data.get('municipio', ''),
                        'uf': data.get('uf', ''),
                        'cep': data.get('cep', '').replace('.', '').replace('-', ''),
                        'telefone': data.get('telefone', ''),
                        'email': data.get('email', ''),
                        'situacao': data.get('situacao', ''),
                        'atividade_principal': data.get('atividade_principal', [{}])[0].get('text', '') if data.get('atividade_principal') else ''
                    }
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': data.get('message', 'CNPJ não encontrado na Receita Federal')
                })
                
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'message': 'Timeout ao consultar ReceitaWS'})
        except Exception as e:
            app.logger.error(f'Erro ao buscar CNPJ: {e}')
            return jsonify({'success': False, 'message': f'Erro ao consultar CNPJ: {str(e)}'})

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
                
                # VERIFICAR SE É USUÁRIO DO CLIENTE CENTRALCOMM
                cliente_id = user.get('pk_id_tbl_cliente')
                if cliente_id:
                    cliente = db.obter_cliente_por_id(cliente_id)
                    if not cliente or cliente.get('nome_fantasia', '').upper() != 'CENTRALCOMM':
                        flash('Acesso restrito. Cliente não autorizado.', 'error')
                        return render_template('login_tailwind.html')
                else:
                    flash('Acesso restrito. Cliente não autorizado.', 'error')
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
    
    @app.route('/reset-password/<string:token>', methods=['GET', 'POST'])
    def reset_password(token):
        """Redefinição de senha via token"""
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        # Verificar se o token é válido
        contato = db.buscar_contato_por_token(token)
        
        if not contato:
            flash('Link inválido ou expirado. Solicite um novo.', 'error')
            return redirect(url_for('forgot_password'))
        
        if request.method == 'POST':
            nova_senha = request.form.get('password', '').strip()
            confirmar_senha = request.form.get('confirm_password', '').strip()
            
            # Validações
            if not nova_senha or not confirmar_senha:
                flash('Preencha todos os campos!', 'error')
                return render_template('reset_password_tailwind.html', token=token, user=contato)
            
            if nova_senha != confirmar_senha:
                flash('As senhas não coincidem!', 'error')
                return render_template('reset_password_tailwind.html', token=token, user=contato)
            
            if len(nova_senha) < 6:
                flash('A senha deve ter no mínimo 6 caracteres!', 'error')
                return render_template('reset_password_tailwind.html', token=token, user=contato)
            
            try:
                # Atualizar senha usando bcrypt (mesmo padrão do sistema)
                nova_senha_hash = db.gerar_senha_hash(nova_senha)
                
                conn = db.get_db()
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE tbl_contato_cliente
                        SET senha = %s,
                            reset_token = NULL,
                            reset_token_expires = NULL,
                            data_modificacao = CURRENT_TIMESTAMP
                        WHERE id_contato_cliente = %s
                    ''', (nova_senha_hash, contato['id_contato_cliente']))
                conn.commit()
                
                # Enviar email de confirmação
                try:
                    send_password_changed_email(
                        user_email=contato['email'],
                        user_name=contato['nome_completo']
                    )
                except Exception as e:
                    app.logger.warning(f"Erro ao enviar email de confirmação: {e}")
                
                app.logger.info(f"Senha redefinida com sucesso para: {contato['email']}")
                flash('Senha redefinida com sucesso! Faça login com sua nova senha.', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                app.logger.error(f"Erro ao redefinir senha: {str(e)}", exc_info=True)
                flash('Erro ao redefinir senha. Tente novamente.', 'error')
                return render_template('reset_password_tailwind.html', token=token, user=contato)
        
        return render_template('reset_password_tailwind.html', token=token, user=contato)
    
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
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                else:
                    if not nome_fantasia:
                        flash('Nome Completo é obrigatório!', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                
                if not cnpj:
                    flash('CNPJ/CPF é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                
                if not id_tipo_cliente:
                    flash('Tipo de Cliente é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados)
                
                # Validação de CPF quando Pessoa Física
                if pessoa == 'F':
                    if not db.validar_cpf(cnpj):
                        flash('CPF inválido!', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                    # Ajustes padrão para PF
                    if not razao_social:
                        razao_social = 'NÃO REQUERIDO'
                    inscricao_estadual = 'ISENTO'
                    inscricao_municipal = 'ISENTO'

                # Validações de unicidade na edição (exclui o próprio cliente)
                try:
                    if db.cliente_existe_por_cnpj(cnpj, excluir_id=cliente_id):
                        flash('CNPJ já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                    if pessoa == 'J' and db.cliente_existe_por_razao_social(razao_social, excluir_id=cliente_id):
                        flash('Razão Social já cadastrada em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                    if db.cliente_existe_por_nome_fantasia(nome_fantasia, excluir_id=cliente_id):
                        flash('Nome Fantasia já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
                except Exception as ve:
                    app.logger.error(f"Erro ao validar duplicidades: {ve}")
                    flash('Erro ao validar unicidade. Tente novamente.', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                
                pk_id_tbl_agencia = request.form.get('pk_id_tbl_agencia', type=int)
                vendas_central_comm = request.form.get('vendas_central_comm', type=int) or None
                percentual = request.form.get('percentual', '').strip()
                id_centralx = request.form.get('id_centralx', '').strip() or None
                
                if not vendas_central_comm:
                    flash('Vendas CentralComm é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                
                # Se for pessoa física, força agência 2
                if pessoa == 'F':
                    pk_id_tbl_agencia = 2
                elif not pk_id_tbl_agencia:
                    flash('Agência é obrigatória para Pessoa Jurídica!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)

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
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                
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
                return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
        
        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)

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
            # Converter Row objects para dict para garantir todos os campos
            resultado = [dict(c) for c in contatos] if contatos else []
            return jsonify(resultado)
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
        """API para criar contato do cliente com integração Brevo"""
        try:
            data = request.get_json()
            
            nome_completo = data.get('nome_completo', '').strip()
            email = data.get('email', '').strip().lower()
            senha = data.get('senha', '').strip()
            telefone = data.get('telefone', '').strip() or None
            pk_id_aux_setor = data.get('pk_id_aux_setor')
            pk_id_tbl_cargo = data.get('pk_id_tbl_cargo')
            cohorts = data.get('cohorts', 1)
            user_type = data.get('user_type', 'client')
            
            # Converter para int se necessário
            if pk_id_aux_setor:
                pk_id_aux_setor = int(pk_id_aux_setor)
            if pk_id_tbl_cargo:
                pk_id_tbl_cargo = int(pk_id_tbl_cargo)
            
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
            
            # ==================== INTEGRAÇÃO BREVO ====================
            # Sincronizar contato no Brevo após criação
            brevo_result = None
            try:
                from aicentralv2.services.brevo_service import get_brevo_service, LISTA_USUARIOS_ATIVOS
                
                # Obter dados do cliente para contexto
                cliente = db.obter_cliente_por_id(cliente_id)
                cliente_nome = cliente.get('nome_fantasia', '') if cliente else ''
                
                brevo_service = get_brevo_service()
                brevo_result = brevo_service.adicionar_contato(
                    email=email,
                    nome=nome_completo,
                    atributos={
                        'NOME': nome_completo,
                        'EMPRESA': cliente_nome,
                        'TELEFONE': telefone or '',
                        'TIPO_USUARIO': user_type,
                        'DATA_CADASTRO': datetime.now().strftime('%Y-%m-%d')
                    },
                    lista_ids=[LISTA_USUARIOS_ATIVOS]
                )
                
                if brevo_result.get('success'):
                    app.logger.info(f"Brevo: Contato {email} sincronizado com sucesso")
                else:
                    app.logger.warning(f"Brevo: Falha ao sincronizar contato {email}: {brevo_result.get('error')}")
                    
            except Exception as brevo_error:
                app.logger.error(f"Brevo: Erro ao sincronizar contato {email}: {brevo_error}")
                brevo_result = {'success': False, 'error': str(brevo_error)}
            
            # Registro de auditoria (inclui resultado Brevo)
            registrar_auditoria(
                acao='CREATE',
                modulo='CONTATOS',
                descricao=f'Criado contato {nome_completo} para cliente ID {cliente_id}',
                registro_id=contato_id,
                registro_tipo='contato',
                dados_novos={
                    'nome_completo': nome_completo,
                    'email': email,
                    'cliente_id': cliente_id,
                    'brevo_sync': brevo_result.get('success') if brevo_result else False
                }
            )
            
            return jsonify({
                'success': True, 
                'message': f'Contato "{nome_completo}" criado com sucesso!', 
                'contato_id': contato_id,
                'brevo_synced': brevo_result.get('success') if brevo_result else False
            })
            
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
    
    @app.route('/api/verificar-email', methods=['POST'])
    @login_required
    def api_verificar_email():
        """API para verificar se email já está cadastrado"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            
            if not email:
                return jsonify({'existe': False})
            
            existe = db.email_existe(email)
            return jsonify({'existe': existe})
        except Exception as e:
            app.logger.error(f"Erro ao verificar email: {e}")
            return jsonify({'existe': False})
    
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
            
            app.logger.info(f"DEBUG criar_invite: cliente_id={cliente_id}, email={email}, role={role}")
            
            if not email:
                return jsonify({'success': False, 'message': 'Email é obrigatório!'}), 400
            
            # Validar se email já está cadastrado
            if db.email_existe(email):
                return jsonify({'success': False, 'message': 'Este email já está cadastrado no sistema!'}), 400
            
            # Pegar ID do usuário logado (garantido pelo @login_required)
            invited_by = session.get('user_id')
            app.logger.info(f"DEBUG criar_invite: invited_by={invited_by}")
            
            if not invited_by:
                return jsonify({'success': False, 'message': 'Usuário não identificado. Faça login novamente.'}), 401
            
            # Criar convite
            invite_id = db.criar_invite(cliente_id, invited_by, email, role)
            app.logger.info(f"DEBUG criar_invite: invite_id={invite_id}")
            
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
                
                # Enviar email com link de convite
                try:
                    # Buscar dados para o email
                    cliente = db.obter_cliente_por_id(cliente_id)
                    convidante = db.obter_contato_por_id(invited_by)
                    invite = db.obter_invite_por_id(invite_id)
                    
                    cliente_nome = cliente.get('nome_fantasia') or cliente.get('razao_social') if cliente else 'Cliente'
                    convidante_nome = convidante.get('nome_completo') if convidante else 'Equipe'
                    invite_token = invite.get('invite_token') if invite else None
                    expires_at = invite.get('expires_at') if invite else None
                    
                    if invite_token:
                        send_invite_email(
                            to_email=email,
                            invite_token=invite_token,
                            cliente_nome=cliente_nome,
                            invited_by_name=convidante_nome,
                            expires_at=expires_at
                        )
                        app.logger.info(f"Email de convite enviado para {email}")
                except Exception as email_error:
                    app.logger.error(f"Erro ao enviar email de convite: {email_error}")
                    # Não falha se o email não for enviado
                
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
                
                # Enviar email
                try:
                    invite = db.obter_invite_por_id(invite_id)
                    if invite:
                        cliente = db.obter_cliente_por_id(invite['id_cliente'])
                        convidante_nome = session.get('user_name', 'Administrador')
                        cliente_nome = cliente.get('nome_fantasia') or cliente.get('razao_social') if cliente else 'Cliente'
                        
                        send_invite_email(
                            to_email=invite['email'],
                            invite_token=invite['invite_token'],
                            cliente_nome=cliente_nome,
                            invited_by_name=convidante_nome,
                            expires_at=invite.get('expires_at')
                        )
                        app.logger.info(f"Email de convite reenviado para {invite['email']}")
                except Exception as email_error:
                    app.logger.error(f"Erro ao enviar email de convite: {email_error}")
                    # Não falha a operação se o email não for enviado
                
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

    @app.route('/aceitar-convite/<token>')
    def aceitar_convite_page(token):
        """Página para aceitar convite"""
        from datetime import datetime
        
        invite = db.obter_invite_por_token(token)
        
        if not invite:
            return render_template('aceitar_convite.html', 
                                   error='Convite não encontrado ou inválido.')
        
        # Verificar se já foi aceito
        if invite['status'] == 'accepted':
            return render_template('aceitar_convite.html', 
                                   error='Este convite já foi utilizado.')
        
        # Verificar se expirou
        if invite['expires_at'] and invite['expires_at'] < datetime.now():
            return render_template('aceitar_convite.html', 
                                   error='Este convite expirou. Solicite um novo convite.')
        
        # Convite válido
        cliente_nome = invite.get('cliente_nome') or invite.get('cliente_razao') or 'Cliente'
        
        # REGRA INQUEBRÁVEL: Verificar se o convite é para CENTRALCOMM
        cliente = db.obter_cliente_por_id(invite['id_cliente'])
        if not cliente or cliente.get('nome_fantasia', '').upper() != 'CENTRALCOMM':
            return render_template('aceitar_convite.html', 
                                   error='Acesso restrito. Apenas usuários CENTRALCOMM podem criar conta neste sistema.')
        
        return render_template('aceitar_convite.html', 
                               invite=invite, 
                               cliente_nome=cliente_nome,
                               token=token)

    @app.route('/aceitar-convite/<token>', methods=['POST'])
    def aceitar_convite_submit(token):
        """Processa o formulário de aceitar convite"""
        from datetime import datetime
        import hashlib
        
        invite = db.obter_invite_por_token(token)
        
        if not invite:
            return render_template('aceitar_convite.html', 
                                   error='Convite não encontrado ou inválido.')
        
        # REGRA INQUEBRÁVEL: Verificar se o convite é para CENTRALCOMM
        cliente = db.obter_cliente_por_id(invite['id_cliente'])
        if not cliente or cliente.get('nome_fantasia', '').upper() != 'CENTRALCOMM':
            return render_template('aceitar_convite.html', 
                                   error='Acesso restrito. Apenas usuários CENTRALCOMM podem criar conta neste sistema.')
        
        if invite['status'] == 'accepted':
            return render_template('aceitar_convite.html', 
                                   error='Este convite já foi utilizado.')
        
        if invite['expires_at'] and invite['expires_at'] < datetime.now():
            return render_template('aceitar_convite.html', 
                                   error='Este convite expirou.')
        
        # Obter dados do formulário
        nome = request.form.get('nome', '').strip()
        senha = request.form.get('senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')
        
        # Validações
        errors = []
        if not nome or len(nome) < 3:
            errors.append('Nome deve ter pelo menos 3 caracteres.')
        if not senha or len(senha) < 6:
            errors.append('Senha deve ter pelo menos 6 caracteres.')
        if senha != confirmar_senha:
            errors.append('As senhas não conferem.')
        
        if errors:
            cliente_nome = invite.get('cliente_nome') or invite.get('cliente_razao') or 'Cliente'
            return render_template('aceitar_convite.html', 
                                   invite=invite, 
                                   cliente_nome=cliente_nome,
                                   token=token,
                                   errors=errors,
                                   nome=nome)
        
        try:
            # Criar o contato/usuário
            senha_hash = hashlib.sha256(senha.encode()).hexdigest()
            
            # Mapear role do invite para user_type válido (client, admin, superadmin, readonly)
            role_mapping = {
                'member': 'client',
                'admin': 'admin',
                'superadmin': 'superadmin',
                'readonly': 'readonly',
                'client': 'client'
            }
            user_type = role_mapping.get(invite['role'], 'client')
            
            contato_id = db.criar_contato(
                nome_completo=nome,
                email=invite['email'],
                senha=senha_hash,
                pk_id_tbl_cliente=invite['id_cliente'],
                user_type=user_type
            )
            
            if contato_id:
                # Marcar convite como aceito
                db.aceitar_invite(invite['id'], contato_id)
                
                # Fazer login automático
                session['user_id'] = contato_id
                session['user_name'] = nome
                session['user_email'] = invite['email']
                session['cliente_id'] = invite['id_cliente']
                
                flash('Conta criada com sucesso! Bem-vindo!', 'success')
                return redirect(url_for('index'))
            else:
                return render_template('aceitar_convite.html', 
                                       invite=invite,
                                       cliente_nome=invite.get('cliente_nome') or 'Cliente',
                                       token=token,
                                       errors=['Erro ao criar conta. Tente novamente.'],
                                       nome=nome)
        except Exception as e:
            app.logger.error(f"Erro ao aceitar convite: {e}")
            return render_template('aceitar_convite.html', 
                                   invite=invite,
                                   cliente_nome=invite.get('cliente_nome') or 'Cliente',
                                   token=token,
                                   errors=[f'Erro ao criar conta: {str(e)}'],
                                   nome=nome)

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
        """Lista de clientes com paginação server-side, métricas mensais e filtros."""
        try:
            # Parâmetros de paginação
            page = request.args.get('page', 1, type=int)
            per_page = current_app.config.get('CLIENTES_PER_PAGE', 25)
            
            # Filtros
            filtros = {}
            
            # Filtro por executivo (obrigatório - default para usuário logado se for vendedor)
            executivo_id = request.args.get('executivo_id', type=int)
            if executivo_id:
                filtros['executivo_id'] = executivo_id
            
            # Filtro por status - Default: ativo
            status_filter = request.args.get('status', 'ativo')
            if status_filter == 'ativo':
                filtros['status'] = True
            elif status_filter == 'inativo':
                filtros['status'] = False
            # Se 'todos', não aplica filtro de status
            
            # Filtro por busca
            search = request.args.get('search', '').strip()
            if search:
                filtros['search'] = search
            
            # Filtro por categoria ABC
            categoria = request.args.get('categoria', '').upper()
            if categoria in ['A', 'B', 'C']:
                filtros['categoria_abc'] = categoria
            
            # Filtro por agência: 'nao' = clientes (default), 'sim' = agências, '' = todos
            agencia = request.args.get('agencia', 'nao').strip().lower()
            if agencia in ['sim', 'nao']:
                filtros['agencia'] = agencia
            # Se vazio ou outro valor, não aplica filtro (mostra todos)
            
            # Obter dados paginados com métricas
            resultado = db.obter_clientes_paginado(
                page=page,
                per_page=per_page,
                filtros=filtros
            )
            
            # Obter executivos para o filtro
            try:
                vendedores_cc = db.obter_vendedores_centralcomm()
            except Exception as _e:
                app.logger.warning(f"Falha ao obter vendedores CentralComm: {_e}")
                vendedores_cc = []

            # Dados para o modal de criação
            agencias = db.obter_aux_agencia()
            tipos_cliente = db.obter_tipos_cliente()
            estados = db.obter_estados()
            setores = db.obter_setores()

            return render_template(
                'clientes.html',
                clientes=resultado['clientes'],
                total=resultado['total'],
                pages=resultado['pages'],
                page=resultado['page'],
                per_page=resultado['per_page'],
                vendedores_cc=vendedores_cc,
                filtros=filtros,
                agencias=agencias,
                tipos_cliente=tipos_cliente,
                estados=estados,
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
                total=0,
                pages=0,
                page=1,
                per_page=25,
                filtros={},
                vendedores_cc=[]
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
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
                else:
                    # Pessoa Física: Razão Social não é obrigatória, mas Nome Completo sim (usa campo nome_fantasia)
                    if not nome_fantasia:
                        flash('Nome Completo é obrigatório!', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
                
                if not cnpj:
                    flash('CNPJ/CPF é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
                
                if not id_tipo_cliente:
                    flash('Tipo de Cliente é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                
                # Validação de CPF quando Pessoa Física
                if pessoa == 'F':
                    if not db.validar_cpf(cnpj):
                        flash('CPF inválido!', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
                    # Ajustes padrão para PF
                    if not razao_social:
                        razao_social = 'NÃO REQUERIDO'
                    inscricao_estadual = 'ISENTO'
                    inscricao_municipal = 'ISENTO'

                # Validações de unicidade (CNPJ, Razão Social, Nome Fantasia)
                try:
                    if db.cliente_existe_por_cnpj(cnpj):
                        flash('CNPJ já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
                    # PF com Razão Social padrão não deve bloquear por duplicidade
                    if pessoa == 'J' and db.cliente_existe_por_razao_social(razao_social):
                        flash('Razão Social já cadastrada em outro cliente.', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                    if db.cliente_existe_por_nome_fantasia(nome_fantasia):
                        flash('Nome Fantasia já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                except Exception as ve:
                    app.logger.error(f"Erro ao validar duplicidades: {ve}")
                    flash('Erro ao validar unicidade. Tente novamente.', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc)
                
                if pessoa not in ['F', 'J']:
                    flash('Tipo de pessoa inválido!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, percentuais=percentuais)
                
                pk_id_tbl_agencia = request.form.get('pk_id_tbl_agencia', type=int)
                # Campo do form: vendas_central_comm (ID do contato executivo de vendas)
                vendas_central_comm = request.form.get('vendas_central_comm', type=int) or None
                percentual = request.form.get('percentual', '').strip()
                id_centralx = request.form.get('id_centralx', '').strip() or None
                
                if not vendas_central_comm:
                    flash('Vendas CentralComm é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
                
                # Se for pessoa física, força agência 2
                if pessoa == 'F':
                    pk_id_tbl_agencia = 2
                elif not pk_id_tbl_agencia:
                    flash('Agência é obrigatória para Pessoa Jurídica!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)

                # Percentual obrigatório quando Agência = Sim (Pessoa Jurídica)
                if pessoa == 'J' and pk_id_tbl_agencia:
                    ag = db.obter_aux_agencia_por_id(pk_id_tbl_agencia)
                    ag_key = (str(ag.get('key')).lower() if isinstance(ag, dict) and 'key' in ag else '')
                    if (ag.get('key') is True) or (ag_key in ['sim','true','1','s','yes','y']):
                        if not percentual:
                            flash('Percentual é obrigatório quando Agência = Sim.', 'error')
                            return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)

                # Converter percentual para float se fornecido
                percentual_valor = None
                if percentual:
                    try:
                        # Substituir vírgula por ponto para conversão
                        percentual_normalizado = percentual.replace(',', '.')
                        percentual_valor = float(percentual_normalizado)
                    except ValueError:
                        percentual_valor = None

                id_cliente = db.criar_cliente(
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
                    id_centralx=id_centralx,
                    cep=cep,
                    bairro=bairro,
                    cidade=cidade,
                    rua=logradouro,
                    numero=numero,
                    complemento=complemento,
                    percentual=percentual_valor
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
                return render_template('cliente_form.html', cliente=None, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)

        return render_template('cliente_form.html', cliente=None, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, percentuais=percentuais)
    
    
    
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
        
        # GET: renderiza página de edição
        if request.method == 'GET':
            try:
                audiencia = db.obter_cadu_audiencia_por_id(audiencia_id)
                if not audiencia:
                    flash('Audiência não encontrada!', 'error')
                    return redirect(url_for('cadu_audiencias'))
                
                categorias = db.obter_cadu_categorias()
                subcategorias = db.obter_cadu_subcategorias(audiencia.get('categoria_id')) if audiencia.get('categoria_id') else []
                
                return render_template('cadu_audiencias_editar.html', 
                                       audiencia=audiencia, 
                                       categorias=categorias,
                                       subcategorias=subcategorias)
            except Exception as e:
                app.logger.error(f"Erro ao carregar audiência para edição: {str(e)}")
                flash('Erro ao carregar audiência.', 'error')
                return redirect(url_for('cadu_audiencias'))
        
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
        
        return redirect(url_for('cadu_audiencias', destaque=audiencia_id) + f'#audiencia-{audiencia_id}')
    
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
                    'new_status': 'ativa' if novo_status else 'inativa',
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
            projeto_id = request.args.get('projeto_id', '').strip()
            busca = request.args.get('busca', '').strip()
            responsavel_id = request.args.get('responsavel_id', '').strip()
            
            filtros = {}
            if status:
                filtros['status'] = status
            if cliente_id:
                filtros['cliente_id'] = int(cliente_id)
            if projeto_id:
                filtros['projeto_id'] = int(projeto_id)
            if busca:
                filtros['busca'] = busca
            if responsavel_id:
                if responsavel_id == 'sem_responsavel':
                    filtros['sem_responsavel'] = True
                else:
                    filtros['responsavel_id'] = int(responsavel_id)
            
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
            
            # Buscar responsáveis (vendedores CentralComm) para filtro
            try:
                responsaveis = db.obter_vendedores_centralcomm() or []
            except Exception as resp_error:
                app.logger.error(f"Erro ao buscar responsáveis: {str(resp_error)}")
                responsaveis = []
            
            # Buscar projetos para filtro (se cliente selecionado)
            projetos = []
            if cliente_id:
                try:
                    projetos = db.listar_projetos({'id_cliente': int(cliente_id)}) or []
                except Exception as proj_error:
                    app.logger.error(f"Erro ao buscar projetos: {str(proj_error)}")
            
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
            
            # Buscar projeto selecionado se houver filtro
            projeto_selecionado = None
            if projeto_id:
                try:
                    conn = db.get_db()
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT id, nome FROM cadu_projetos WHERE id = %s', (int(projeto_id),))
                        projeto_selecionado = cursor.fetchone()
                except Exception as e:
                    app.logger.error(f"Erro ao buscar projeto selecionado: {str(e)}")
            
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
                                 responsaveis=responsaveis,
                                 projetos=projetos,
                                 cliente_selecionado=cliente_selecionado,
                                 projeto_selecionado=projeto_selecionado,
                                 stats=stats,
                                 filtros={'status': status, 'cliente_id': cliente_id, 'projeto_id': projeto_id, 'busca': busca, 'responsavel_id': responsavel_id})
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
            responsaveis = db.obter_vendedores_centralcomm() or []
            projetos = db.listar_projetos() or []
            contatos_cliente = db.obter_contatos_comercial_operacoes() or []
            return render_template('briefing_form.html', 
                                 briefing=None, 
                                 clientes=clientes,
                                 responsaveis=responsaveis,
                                 projetos=projetos,
                                 contatos_cliente=contatos_cliente,
                                 acao='Novo')
        
        try:
            # Obter dados do formulário
            dados = {
                'cliente_id': int(request.form.get('cliente_id')),
                'titulo': request.form.get('titulo', '').strip(),
                'objetivo': request.form.get('objetivo', '').strip(),
                'publico_alvo': request.form.get('publico_alvo', '').strip(),
                'mensagem_chave': request.form.get('mensagem_chave', '').strip(),
                'plataforma': request.form.get('plataforma', '').strip(),
                'budget': float(request.form.get('budget')) if request.form.get('budget') else None,
                'prazo': request.form.get('prazo') if request.form.get('prazo') else None,
                'observacoes': request.form.get('observacoes', '').strip(),
                'status': request.form.get('status', 'rascunho'),
                'responsavel_centralcomm': request.form.get('responsavel_centralcomm', '').strip() or None,
                'id_projeto': int(request.form.get('id_projeto')) if request.form.get('id_projeto') else None
            }
            
            # Validações
            if not dados['titulo'] or not dados['cliente_id']:
                flash('Preencha todos os campos obrigatórios.', 'error')
                clientes = db.obter_clientes_simples()
                responsaveis = db.obter_vendedores_centralcomm() or []
                projetos = db.listar_projetos() or []
                contatos_cliente = db.obter_contatos_comercial_operacoes() or []
                return render_template('briefing_form.html', 
                                     briefing=dados, 
                                     clientes=clientes,
                                     responsaveis=responsaveis,
                                     projetos=projetos,
                                     contatos_cliente=contatos_cliente,
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
            responsaveis = db.obter_vendedores_centralcomm() or []
            projetos = db.listar_projetos() or []
            contatos_cliente = db.obter_contatos_comercial_operacoes() or []
            return render_template('briefing_form.html', 
                                 briefing=dados if 'dados' in locals() else None, 
                                 clientes=clientes,
                                 responsaveis=responsaveis,
                                 projetos=projetos,
                                 contatos_cliente=contatos_cliente,
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
            responsaveis = db.obter_vendedores_centralcomm() or []
            projetos = db.listar_projetos() or []
            contatos_cliente = db.obter_contatos_comercial_operacoes() or []
            return render_template('briefing_form.html', 
                                 briefing=briefing, 
                                 clientes=clientes,
                                 responsaveis=responsaveis,
                                 projetos=projetos,
                                 contatos_cliente=contatos_cliente,
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
                'id_contato_cliente': int(request.form.get('id_contato_cliente')) if request.form.get('id_contato_cliente') else None,
                'titulo': request.form.get('titulo', '').strip(),
                'objetivo': request.form.get('objetivo', '').strip(),
                'briefing_original': request.form.get('briefing_original', '').strip(),
                'briefing_melhorado': request.form.get('briefing_melhorado', '').strip(),
                'plataforma': request.form.get('plataforma', '').strip(),
                'budget': float(request.form.get('budget')) if request.form.get('budget') else None,
                'prazo': request.form.get('prazo') if request.form.get('prazo') else None,
                'status': request.form.get('status', 'rascunho'),
                'responsavel_centralcomm': request.form.get('responsavel_centralcomm', '').strip() or None,
                'id_projeto': int(request.form.get('id_projeto')) if request.form.get('id_projeto') else None
            }
            
            # Validações
            if not dados['titulo'] or not dados['cliente_id']:
                flash('Preencha todos os campos obrigatórios.', 'error')
                clientes = db.obter_clientes_simples()
                responsaveis = db.obter_vendedores_centralcomm() or []
                projetos = db.listar_projetos() or []
                contatos_cliente = db.obter_contatos_comercial_operacoes() or []
                return render_template('briefing_form.html', 
                                     briefing={**dados, 'id': briefing_id}, 
                                     clientes=clientes,
                                     responsaveis=responsaveis,
                                     projetos=projetos,
                                     contatos_cliente=contatos_cliente,
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

    @app.route('/api/briefing/<int:briefing_id>')
    @login_required
    def api_obter_briefing(briefing_id):
        """API para obter dados de um briefing"""
        try:
            briefing = db.obter_briefing_por_id(briefing_id)
            if not briefing:
                return jsonify({'error': 'Briefing não encontrado'}), 404
            
            # Converter para dict serializável
            briefing_dict = dict(briefing)
            
            # Converter datas para string ISO
            for campo in ['prazo', 'created_at', 'updated_at', 'data_envio_centralcomm']:
                if briefing_dict.get(campo):
                    briefing_dict[campo] = briefing_dict[campo].isoformat() if hasattr(briefing_dict[campo], 'isoformat') else str(briefing_dict[campo])
            
            return jsonify(briefing_dict)
            
        except Exception as e:
            app.logger.error(f"Erro ao obter briefing: {str(e)}")
            return jsonify({'error': 'Erro ao obter briefing'}), 500

    @app.route('/api/briefing/<int:briefing_id>/iniciar-cotacao', methods=['POST'])
    @login_required
    def api_briefing_iniciar_cotacao(briefing_id):
        """API para aceitar briefing e criar uma cotação a partir dele"""
        try:
            briefing = db.obter_briefing_por_id(briefing_id)
            if not briefing:
                return jsonify({'success': False, 'error': 'Briefing não encontrado'}), 404
            
            # Verificar se briefing já tem cotação vinculada
            if briefing.get('id_cotacao'):
                return jsonify({'success': False, 'error': 'Este briefing já possui uma cotação vinculada'}), 400
            
            # Dados para criar a cotação
            from datetime import datetime, timedelta
            
            dados_cotacao = {
                'client_id': briefing.get('id_cliente'),
                'nome_campanha': briefing.get('titulo') or 'Campanha do Briefing',
                'periodo_inicio': briefing.get('prazo') or datetime.now().date(),
                'objetivo_campanha': briefing.get('objetivo') or briefing.get('briefing_original', '')[:500],
                'briefing_id': briefing_id,
                'budget_estimado': briefing.get('budget'),
                'meio': briefing.get('plataforma'),
                'status': 'Rascunho',
                'responsavel_comercial': briefing.get('responsavel_centralcomm'),
                'origem': 'briefing'
            }
            
            # Criar cotação
            resultado = db.criar_cotacao(
                client_id=dados_cotacao['client_id'],
                nome_campanha=dados_cotacao['nome_campanha'],
                periodo_inicio=dados_cotacao['periodo_inicio'],
                **{k: v for k, v in dados_cotacao.items() if k not in ['client_id', 'nome_campanha', 'periodo_inicio'] and v is not None}
            )
            
            if resultado:
                cotacao_id = resultado['id']
                numero_cotacao = resultado['numero_cotacao']
                
                # Atualizar briefing com a cotação vinculada e status
                db.atualizar_briefing(briefing_id, {
                    'id_cotacao': cotacao_id,
                    'status': 'em_andamento'
                })
                
                # Registrar auditoria
                registrar_auditoria(
                    acao='criar_cotacao_de_briefing',
                    modulo='briefings',
                    descricao=f'Criou cotação {numero_cotacao} a partir do briefing "{briefing.get("titulo")}"',
                    registro_id=briefing_id,
                    registro_tipo='cadu_briefings',
                    dados_novos={'cotacao_id': cotacao_id, 'numero_cotacao': numero_cotacao}
                )
                
                return jsonify({
                    'success': True, 
                    'cotacao_id': cotacao_id,
                    'numero_cotacao': numero_cotacao,
                    'message': 'Cotação criada com sucesso'
                })
            else:
                return jsonify({'success': False, 'error': 'Erro ao criar cotação'}), 500
                
        except Exception as e:
            import traceback
            app.logger.error(f"Erro ao criar cotação de briefing: {str(e)}")
            app.logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/briefing/<int:briefing_id>/devolver', methods=['POST'])
    @login_required
    def api_briefing_devolver(briefing_id):
        """API para devolver briefing ao cliente com motivo"""
        try:
            briefing = db.obter_briefing_por_id(briefing_id)
            if not briefing:
                return jsonify({'success': False, 'error': 'Briefing não encontrado'}), 404
            
            data = request.get_json() or {}
            motivo = data.get('motivo', '').strip()
            
            if not motivo:
                return jsonify({'success': False, 'error': 'Motivo da devolução é obrigatório'}), 400
            
            # Atualizar briefing para status arquivado/devolvido
            db.atualizar_briefing(briefing_id, {
                'status': 'arquivado',
                'observacoes': f"[DEVOLVIDO] {motivo}"
            })
            
            # Registrar auditoria
            registrar_auditoria(
                acao='devolver_briefing',
                modulo='briefings',
                descricao=f'Devolveu briefing "{briefing.get("titulo")}" ao cliente. Motivo: {motivo}',
                registro_id=briefing_id,
                registro_tipo='cadu_briefings',
                dados_anteriores={'status': briefing.get('status')},
                dados_novos={'status': 'arquivado', 'motivo': motivo}
            )
            
            return jsonify({
                'success': True,
                'message': 'Briefing devolvido ao cliente'
            })
            
        except Exception as e:
            app.logger.error(f"Erro ao devolver briefing: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==================== COTAÇÕES ====================

    @app.route('/cotacoes')
    @login_required
    def cotacoes_list():
        """Lista cotações com filtros avançados"""
        try:
            db.criar_tabela_cotacoes()
            
            # Coletar todos os filtros
            cliente_id = request.args.get('cliente_id', type=int)
            responsavel_id = request.args.get('responsavel_comercial', type=int)
            mes = request.args.get('mes')
            busca = request.args.get('busca', '').strip()
            status = request.args.get('status')
            
            cliente_info = None
            
            app.logger.info(f"DEBUG cotacoes_list: cliente_id={cliente_id}, responsavel_id={responsavel_id}, mes={mes}, busca={busca}, status={status}")
            
            # Se há cliente_id, buscar informações do cliente
            if cliente_id:
                conn = db.get_db()
                with conn.cursor() as cursor:
                    cursor.execute('SELECT id_cliente, nome_fantasia, razao_social FROM tbl_cliente WHERE id_cliente = %s', (cliente_id,))
                    cliente_info = cursor.fetchone()
            
            # Obter cotações com filtros
            cotacoes = db.obter_cotacoes_filtradas(
                cliente_id=cliente_id,
                responsavel_id=responsavel_id,
                mes=mes,
                busca=busca,
                status=status
            )
            
            app.logger.info(f"DEBUG: Cotações obtidas: {len(cotacoes) if cotacoes else 0} registros")
            
            vendedores = db.obter_vendedores()
            return render_template('cadu_cotacoes.html', 
                                 cotacoes=cotacoes or [], 
                                 cliente_filtro=cliente_info, 
                                 vendedores=vendedores,
                                 now=datetime.now)
        except Exception as e:
            app.logger.error(f"Erro ao listar cotações: {str(e)}", exc_info=True)
            flash('Erro ao carregar cotações.', 'error')
            vendedores = db.obter_vendedores()
            return render_template('cadu_cotacoes.html', cotacoes=[], cliente_filtro=None, vendedores=vendedores, now=datetime.now)

    # ==================== CRM PIPELINE ====================

    @app.route('/crm/pipeline')
    @login_required
    def crm_pipeline():
        """Pipeline Kanban de cotações para acompanhamento comercial"""
        try:
            # Coletar filtros da query string
            filtros = {
                'executivo_id': request.args.get('executivo_id', type=int),
                'cliente_id': request.args.get('cliente_id', type=int),
                'periodo_inicio': request.args.get('periodo_inicio'),
                'periodo_fim': request.args.get('periodo_fim'),
                'valor_min': request.args.get('valor_min', type=float),
                'valor_max': request.args.get('valor_max', type=float),
                'mes': request.args.get('mes'),
                'status': request.args.get('status')
            }
            
            # Remover filtros vazios
            filtros = {k: v for k, v in filtros.items() if v is not None and v != ''}
            
            # Obter cotações agrupadas por status
            colunas = db.obter_cotacoes_pipeline(filtros)
            
            # Obter listas para filtros
            vendedores = db.obter_vendedores()
            clientes = db.obter_clientes_para_filtro()
            
            # Calcular totais por coluna
            totais = {
                status: {
                    'count': len(cotacoes),
                    'valor': sum(c.get('valor_total_proposta') or 0 for c in cotacoes)
                }
                for status, cotacoes in colunas.items()
            }
            
            return render_template('crm_pipeline.html',
                                 colunas=colunas,
                                 totais=totais,
                                 vendedores=vendedores,
                                 clientes=clientes,
                                 filtros=filtros,
                                 now=datetime.now)
        except Exception as e:
            app.logger.error(f"Erro ao carregar pipeline: {str(e)}", exc_info=True)
            flash('Erro ao carregar pipeline.', 'error')
            return redirect(url_for('cotacoes_list'))

    @app.route('/api/crm/pipeline/cotacao/<int:cotacao_id>')
    @login_required
    def api_pipeline_cotacao_detalhes(cotacao_id):
        """API para obter detalhes de uma cotação no modal do pipeline"""
        try:
            cotacao = db.obter_cotacao_detalhes_pipeline(cotacao_id)
            
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            # Serializar datas para JSON
            def serialize_date(d):
                if d:
                    return d.isoformat() if hasattr(d, 'isoformat') else str(d)
                return None
            
            # Preparar dados para resposta
            dados = {
                'id': cotacao['id'],
                'numero_cotacao': cotacao['numero_cotacao'],
                'nome_campanha': cotacao['nome_campanha'],
                'status': cotacao['status'],
                'valor_total_proposta': float(cotacao.get('valor_total_proposta') or 0),
                'valor_bruto': float(cotacao.get('valor_bruto') or cotacao.get('valor_total_proposta') or 0),
                'valor_desconto': float(cotacao.get('valor_desconto') or 0),
                'valor_impostos': float(cotacao.get('valor_impostos') or 0),
                'moeda': cotacao.get('moeda') or 'BRL',
                'condicoes_comerciais': cotacao.get('condicoes_comerciais'),
                'cliente_nome': cotacao.get('cliente_nome'),
                'executivo_nome': cotacao.get('executivo_nome'),
                'contato_nome': cotacao.get('contato_nome'),
                'contato_email': cotacao.get('contato_email'),
                'objetivo_campanha': cotacao.get('objetivo_campanha'),
                'observacoes': cotacao.get('observacoes'),
                'observacoes_internas': cotacao.get('observacoes_internas'),
                'periodo_inicio': serialize_date(cotacao.get('periodo_inicio')),
                'periodo_fim': serialize_date(cotacao.get('periodo_fim')),
                'validade_proposta': serialize_date(cotacao.get('validade_proposta')),
                'created_at': serialize_date(cotacao.get('created_at')),
                'updated_at': serialize_date(cotacao.get('updated_at')),
                'proposta_enviada_em': serialize_date(cotacao.get('proposta_enviada_em')),
                'aprovada_em': serialize_date(cotacao.get('aprovada_em')),
                'itens': cotacao.get('itens', []),
                'briefing': cotacao.get('briefing'),
                'anexos': cotacao.get('anexos', []),
                'audiencias': cotacao.get('audiencias', [])
            }
            
            return jsonify({'success': True, 'cotacao': dados})
        except Exception as e:
            app.logger.error(f"Erro ao obter detalhes cotação: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

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
                    'status': request.form.get('status', 'Rascunho').strip(),
                    'responsavel_comercial': request.form.get('responsavel_comercial', type=int),
                    'briefing_id': request.form.get('briefing_id', type=int) if request.form.get('briefing_id') else None,
                    'budget_estimado': float(request.form.get('budget_estimado', '0') or 0) if request.form.get('budget_estimado') else None,
                    'observacoes': request.form.get('observacoes', '').strip(),
                    'origem': request.form.get('origem', '').strip(),
                    'link_publico_ativo': 'link_publico_ativo' in request.form,
                    'link_publico_token': request.form.get('link_publico_token', '').strip(),
                    'link_publico_expires_at': request.form.get('link_publico_expires_at', '').strip() or None,
                    'agencia_id': request.form.get('agencia_id', type=int) if request.form.get('agencia_id') else None,
                    'agencia_user_id': request.form.get('agencia_user_id', type=int) if request.form.get('agencia_user_id') else None,
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
                    'client_user_id': request.form.get('client_user_id', type=int) if request.form.get('client_user_id') else None,
                    'briefing_id': request.form.get('briefing_id', type=int) if request.form.get('briefing_id') else None,
                    'agencia_id': request.form.get('agencia_id', type=int) if request.form.get('agencia_id') else None,
                    'agencia_user_id': request.form.get('agencia_user_id', type=int) if request.form.get('agencia_user_id') else None,
                    'budget_estimado': float(request.form.get('budget_estimado', '0') or 0) if request.form.get('budget_estimado') else None,
                    'observacoes': request.form.get('observacoes', '').strip(),
                    'observacoes_internas': request.form.get('observacoes_internas', '').strip(),
                    'origem': request.form.get('origem', '').strip(),
                    'status': request.form.get('status', '').strip(),
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
            contatos_cliente = []
            contatos_agencia = []
            if cotacao.get('client_id'):
                briefings = db.obter_briefings_por_cliente(cotacao['client_id'])
                contatos_cliente = db.obter_contatos_comerciais_por_cliente(cotacao['client_id'])
            if cotacao.get('agencia_id'):
                contatos_agencia = db.obter_contatos_por_cliente(cotacao['agencia_id'])
            return render_template('cadu_cotacoes_form.html', 
                                  cotacao=cotacao, clientes=clientes, vendedores=vendedores, briefings=briefings, contatos_cliente=contatos_cliente, contatos_agencia=contatos_agencia, modo='editar')

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
                    
                    # Tratar client_user_id
                    client_user_id_raw = request.form.get('client_user_id')
                    client_user_id = int(client_user_id_raw) if client_user_id_raw and client_user_id_raw.strip() else None
                    
                    # Tratar campos datetime (string vazia = None)
                    periodo_fim = request.form.get('periodo_fim')
                    periodo_fim = periodo_fim if periodo_fim and periodo_fim.strip() else None
                    
                    expires_at = request.form.get('expires_at')
                    expires_at = expires_at if expires_at and expires_at.strip() else None
                    
                    dados = {
                        'client_id': request.form.get('client_id'),
                        'nome_campanha': request.form.get('nome_campanha'),
                        'responsavel_comercial': resp_comercial if resp_comercial and resp_comercial.strip() else None,
                        'client_user_id': client_user_id,
                        'briefing_id': request.form.get('briefing_id') if request.form.get('briefing_id') else None,
                        'objetivo_campanha': request.form.get('objetivo_campanha'),
                        'periodo_inicio': request.form.get('periodo_inicio'),
                        'periodo_fim': periodo_fim,
                        'expires_at': expires_at,
                        'budget_estimado': request.form.get('budget_estimado'),
                        'valor_total_proposta': request.form.get('valor_total_proposta'),
                        'status': request.form.get('status'),
                        'observacoes': request.form.get('observacoes'),
                        'observacoes_internas': request.form.get('observacoes_internas'),
                        'desconto_total': request.form.get('desconto_total'),
                        'condicoes_comerciais': request.form.get('condicoes_comerciais')
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
            
            # Buscar dados do cliente atual (para percentual líquido)
            cliente = None
            if cotacao.get('client_id'):
                cliente = db.obter_cliente_por_id(cotacao['client_id'])
            
            # Buscar contatos ativos do cliente da cotação
            contatos_cliente = []
            contatos_agencia = []
            briefings = []
            briefing_atual = None
            if cotacao.get('client_id'):
                app.logger.info(f"DEBUG: Buscando briefings para client_id={cotacao['client_id']}")
                contatos_cliente = db.obter_contatos_comerciais_por_cliente(cotacao['client_id'])
                briefings = db.obter_briefings_por_cliente(cotacao['client_id'])
                app.logger.info(f"DEBUG: Encontrados {len(briefings)} briefings")
            
            # Buscar contatos da agência
            if cotacao.get('agencia_id'):
                contatos_agencia = db.obter_contatos_por_cliente(cotacao['agencia_id'])
            
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
                                  cliente=cliente,
                                  clientes=clientes, 
                                  vendedores=vendedores,
                                  contatos_cliente=contatos_cliente,
                                  contatos_agencia=contatos_agencia,
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
            
            # Buscar informações da agência
            agencia_info = None
            if cotacao.get('agencia_id'):
                agencia_info = db.obter_cliente_por_id(cotacao['agencia_id'])
            
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
                                  agencia=agencia_info,
                                  responsavel=responsavel_info,
                                  briefing=briefing_atual,
                                  linhas=linhas,
                                  audiencias=audiencias,
                                  anexos=anexos,
                                  token=token)

        except Exception as e:
            app.logger.error(f"Erro ao carregar cotação pública: {str(e)}", exc_info=True)
            return render_template('erro_publico.html', 
                mensagem='Erro ao carregar cotação'), 500

    @app.route('/cotacao/publico/<string:token>/pdf')
    def cotacao_publica_pdf(token):
        """Exporta cotação pública para PDF via token"""
        try:
            from flask import make_response
            from datetime import datetime
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            import os
            
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
            
            if not cotacao:
                return "Link inválido ou expirado", 404
            
            # Verificar se o link expirou
            if cotacao.get('link_publico_expires_at'):
                expires_at = cotacao['link_publico_expires_at']
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                if expires_at < datetime.now():
                    return "Este link expirou", 410
            
            cotacao_id = cotacao['id']
            
            # Obter dados relacionados
            cliente = db.obter_cliente_por_id(cotacao['client_id']) if cotacao.get('client_id') else None
            linhas = db.obter_linhas_cotacao(cotacao_id)
            audiencias = db.obter_audiencias_cotacao(cotacao_id)
            responsavel = db.obter_contato_cliente(cotacao['responsavel_id']) if cotacao.get('responsavel_id') else None
            
            # Criar PDF em memória
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
            
            # Estilos
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.white, spaceAfter=4, alignment=TA_LEFT)
            subtitle_style = ParagraphStyle('CustomSubtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#72cd80'), spaceAfter=0)
            heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1a1a2e'), spaceAfter=6, spaceBefore=10)
            normal_style = styles['Normal']
            small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)
            white_text = ParagraphStyle('WhiteText', parent=styles['Normal'], fontSize=9, textColor=colors.white)
            green_text = ParagraphStyle('GreenText', parent=styles['Normal'], fontSize=14, textColor=colors.HexColor('#72cd80'), fontName='Helvetica-Bold')
            
            # Conteúdo do PDF
            story = []
            
            # Header com fundo escuro (simula o gradient-header do site)
            logo_path = os.path.join(app.root_path, 'static', 'images', 'cc_logo.png')
            
            # Preparar dados do header
            nome_campanha = cotacao.get('nome_campanha', 'Proposta Comercial')
            numero_cotacao = cotacao.get('numero_cotacao', '')
            nome_cliente = cliente.get('nome_fantasia', cliente.get('razao_social', '')) if cliente else ''
            valor_total = cotacao.get('valor_total_proposta', 0) or 0
            valor_formatado = f"R$ {valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            # Criar header com logo e informações
            header_content = []
            
            # Linha com logo e valor total
            if os.path.exists(logo_path):
                try:
                    # Manter proporção do logo (não espremer)
                    logo = Image(logo_path, width=22*mm, height=22*mm, kind='proportional')
                    header_row1 = [[logo, '', Paragraph(f"<b>{valor_formatado}</b>", green_text)]]
                except:
                    header_row1 = [['', '', Paragraph(f"<b>{valor_formatado}</b>", green_text)]]
            else:
                header_row1 = [['CentralComm', '', Paragraph(f"<b>{valor_formatado}</b>", green_text)]]
            
            header_table1 = Table(header_row1, colWidths=[35*mm, 80*mm, 55*mm])
            header_table1.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1a1a2e')),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(header_table1)
            
            # Linha com nome da campanha e cliente
            header_row2 = [[
                Paragraph(f"<b>{nome_campanha}</b><br/><font size='8' color='#aaaaaa'>{nome_cliente}</font>", title_style),
                Paragraph(f"<font size='10' color='#ffffff'><b>Nº {numero_cotacao}</b></font>", white_text)
            ]]
            header_table2 = Table(header_row2, colWidths=[120*mm, 50*mm])
            header_table2.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1a1a2e')),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))
            story.append(header_table2)
            story.append(Spacer(1, 8*mm))
            
            # Informações da Campanha
            story.append(Paragraph("Informações da Campanha", heading_style))
            
            info_items = []
            if cotacao.get('periodo_inicio') and cotacao.get('periodo_fim'):
                periodo_inicio = cotacao['periodo_inicio'].strftime('%d/%m/%Y') if hasattr(cotacao['periodo_inicio'], 'strftime') else str(cotacao['periodo_inicio'])
                periodo_fim = cotacao['periodo_fim'].strftime('%d/%m/%Y') if hasattr(cotacao['periodo_fim'], 'strftime') else str(cotacao['periodo_fim'])
                info_items.append(['Período:', f"{periodo_inicio} a {periodo_fim}"])
            
            if responsavel:
                info_items.append(['Executivo:', responsavel.get('nome_completo', 'N/A')])
                if responsavel.get('email'):
                    info_items.append(['E-mail:', responsavel.get('email')])
            
            info_items.append(['Status:', cotacao.get('status', 'N/A')])
            info_items.append(['Data:', cotacao.get('created_at').strftime('%d/%m/%Y') if cotacao.get('created_at') else 'N/A'])
            
            if info_items:
                info_table = Table(info_items, colWidths=[35*mm, 135*mm])
                info_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
                    ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(info_table)
            story.append(Spacer(1, 6*mm))
            
            # Objetivo da Campanha
            if cotacao.get('objetivo_campanha'):
                story.append(Paragraph("Objetivo da Campanha", heading_style))
                story.append(Paragraph(cotacao['objetivo_campanha'], normal_style))
                story.append(Spacer(1, 6*mm))
            
            # Linhas de Cotação
            if linhas:
                story.append(Paragraph("Itens da Proposta", heading_style))
                
                linhas_data = [['#', 'Segmentação/Praça', 'Plataforma', 'Formato', 'KPI', 'Período', 'Volume', 'Invest. Bruto']]
                
                for idx, linha in enumerate(linhas, 1):
                    # Segmentação e Praça
                    descricao_parts = []
                    if linha.get('segmentacao'):
                        descricao_parts.append(linha['segmentacao'][:50] + '...' if len(linha['segmentacao']) > 50 else linha['segmentacao'])
                    if linha.get('praca'):
                        descricao_parts.append(f"({linha['praca']})")
                    descricao = ' '.join(descricao_parts) if descricao_parts else 'N/A'
                    
                    # Formato
                    formato = linha.get('formatos') or linha.get('formato_compra') or '-'
                    
                    # KPI
                    kpi = linha.get('objetivo_kpi') or '-'
                    
                    # Período
                    periodo = ''
                    if linha.get('data_inicio') and linha.get('data_fim'):
                        data_ini = linha['data_inicio'].strftime('%d/%m') if hasattr(linha['data_inicio'], 'strftime') else str(linha['data_inicio'])[:5]
                        data_fim = linha['data_fim'].strftime('%d/%m') if hasattr(linha['data_fim'], 'strftime') else str(linha['data_fim'])[:5]
                        periodo = f"{data_ini} a {data_fim}"
                    
                    linhas_data.append([
                        str(idx),
                        Paragraph(descricao, small_style),
                        linha.get('plataforma', '-') or '-',
                        formato[:15] if len(str(formato)) > 15 else formato,
                        kpi,
                        periodo,
                        f"{linha.get('volume_contratado', 0):,.0f}".replace(',', '.') if linha.get('volume_contratado') else '-',
                        f"R$ {linha.get('investimento_bruto', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if linha.get('investimento_bruto') else '-'
                    ])
                
                linhas_table = Table(linhas_data, colWidths=[8*mm, 42*mm, 22*mm, 20*mm, 14*mm, 22*mm, 18*mm, 24*mm])
                linhas_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (6, 1), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(linhas_table)
                story.append(Spacer(1, 6*mm))
            
            # Audiências
            if audiencias:
                story.append(Paragraph("Audiências", heading_style))
                
                for aud in audiencias:
                    if aud.get('incluido_proposta', True):
                        aud_info = f"<b>{aud.get('audiencia_nome', 'N/A')}</b>"
                        if aud.get('audiencia_publico'):
                            aud_info += f" - {aud['audiencia_publico']}"
                        if aud.get('investimento_sugerido'):
                            valor = f"R$ {aud['investimento_sugerido']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            aud_info += f" | Investimento: {valor}"
                        story.append(Paragraph(aud_info, normal_style))
                        story.append(Spacer(1, 2*mm))
            
            # Valores Totais
            story.append(Spacer(1, 6*mm))
            story.append(Paragraph("Resumo Financeiro", heading_style))
            
            total_linhas = sum(l.get('investimento_bruto', 0) or 0 for l in linhas) if linhas else 0
            total_audiencias = sum(a.get('investimento_sugerido', 0) or 0 for a in audiencias if a.get('incluido_proposta', True)) if audiencias else 0
            valor_total = cotacao.get('valor_total_proposta') or (total_linhas + total_audiencias)
            
            totais_data = [
                ['Total Linhas:', f"R$ {total_linhas:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                ['Total Audiências:', f"R$ {total_audiencias:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
                ['VALOR TOTAL:', f"R$ {valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
            ]
            
            totais_table = Table(totais_data, colWidths=[60*mm, 60*mm])
            totais_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTSIZE', (0, -1), (-1, -1), 12),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1e3a8a')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(totais_table)
            
            # Condições Comerciais
            if cotacao.get('condicoes_comerciais'):
                story.append(Spacer(1, 8*mm))
                story.append(Paragraph("Condições Comerciais", heading_style))
                # Quebrar por linhas e adicionar cada uma
                condicoes = cotacao['condicoes_comerciais'].replace('\r\n', '\n').split('\n')
                for cond in condicoes:
                    if cond.strip():
                        story.append(Paragraph(cond.strip(), small_style))
                        story.append(Spacer(1, 1*mm))
            
            # Observações
            if cotacao.get('observacoes'):
                story.append(Spacer(1, 6*mm))
                story.append(Paragraph("Observações", heading_style))
                story.append(Paragraph(cotacao['observacoes'], normal_style))
            
            # Gerar PDF
            doc.build(story)
            
            # Preparar resposta
            buffer.seek(0)
            response = make_response(buffer.read())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'inline; filename=cotacao_{cotacao.get("numero_cotacao", cotacao_id)}.pdf'
            
            return response
            
        except Exception as e:
            app.logger.error(f"Erro ao gerar PDF público: {str(e)}", exc_info=True)
            return f"Erro ao gerar PDF: {str(e)}", 500

    @app.route('/api/cotacao/publica/<string:token>/aprovar', methods=['POST'])
    def aprovar_cotacao_publica(token):
        """API para aprovar cotação via link público"""
        try:
            from datetime import datetime
            
            data = request.get_json() or {}
            observacoes = data.get('observacoes', '')
            
            # Buscar cotação pelo token
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id, status, observacoes FROM cadu_cotacoes 
                    WHERE link_publico_token = %s 
                    AND link_publico_ativo = TRUE
                    AND deleted_at IS NULL
                ''', (token,))
                cotacao = cursor.fetchone()
            
            if not cotacao:
                return jsonify({'success': False, 'error': 'Link inválido ou expirado'}), 404
            
            # Verificar se já foi aprovada/rejeitada
            if cotacao['status'] in ['Aprovada', 'Rejeitada']:
                return jsonify({'success': False, 'error': 'Esta cotação já foi processada'}), 400
            
            # Preparar observações (concatenar com existentes se houver)
            obs_existentes = cotacao.get('observacoes') or ''
            nova_obs = f"\n\n[Aprovação pelo cliente em {datetime.now().strftime('%d/%m/%Y %H:%M')}]"
            if observacoes:
                nova_obs += f"\nObservações: {observacoes}"
            obs_final = obs_existentes + nova_obs
            
            # Atualizar status para Aprovada
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE cadu_cotacoes 
                    SET status = 'Aprovada',
                        observacoes = %s,
                        updated_at = %s
                    WHERE id = %s
                ''', (obs_final.strip(), datetime.now(), cotacao['id']))
                conn.commit()
            
            app.logger.info(f"Cotação {cotacao['id']} aprovada via link público")
            
            return jsonify({'success': True, 'message': 'Cotação aprovada com sucesso!'})
            
        except Exception as e:
            app.logger.error(f"Erro ao aprovar cotação pública: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/cotacao/publica/<string:token>/rejeitar', methods=['POST'])
    def rejeitar_cotacao_publica(token):
        """API para rejeitar cotação via link público"""
        try:
            from datetime import datetime
            
            data = request.get_json() or {}
            motivo = data.get('motivo', '')
            observacoes = data.get('observacoes', '')
            
            if not motivo:
                return jsonify({'success': False, 'error': 'Motivo é obrigatório'}), 400
            
            # Buscar cotação pelo token
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id, status, observacoes FROM cadu_cotacoes 
                    WHERE link_publico_token = %s 
                    AND link_publico_ativo = TRUE
                    AND deleted_at IS NULL
                ''', (token,))
                cotacao = cursor.fetchone()
            
            if not cotacao:
                return jsonify({'success': False, 'error': 'Link inválido ou expirado'}), 404
            
            # Verificar se já foi aprovada/rejeitada
            if cotacao['status'] in ['Aprovada', 'Rejeitada']:
                return jsonify({'success': False, 'error': 'Esta cotação já foi processada'}), 400
            
            # Preparar observações (concatenar com existentes se houver)
            obs_existentes = cotacao.get('observacoes') or ''
            nova_obs = f"\n\n[Rejeição pelo cliente em {datetime.now().strftime('%d/%m/%Y %H:%M')}]"
            nova_obs += f"\nMotivo: {motivo}"
            if observacoes:
                nova_obs += f"\nObservações: {observacoes}"
            obs_final = obs_existentes + nova_obs
            
            # Atualizar status para Rejeitada
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE cadu_cotacoes 
                    SET status = 'Rejeitada',
                        observacoes = %s,
                        updated_at = %s
                    WHERE id = %s
                ''', (obs_final.strip(), datetime.now(), cotacao['id']))
                conn.commit()
            
            app.logger.info(f"Cotação {cotacao['id']} rejeitada via link público. Motivo: {motivo}")
            
            return jsonify({'success': True, 'message': 'Feedback registrado com sucesso!'})
            
        except Exception as e:
            app.logger.error(f"Erro ao rejeitar cotação pública: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

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
                'budget_estimado', 'valor_total_proposta', 'desconto_percentual', 'desconto_total',
                'briefing_id', 'client_id', 'client_user_id',
                'agencia_id', 'agencia_user_id',
                'observacoes', 'observacoes_internas', 'origem', 'condicoes_comerciais',
                'status', 'link_publico_ativo', 'link_publico_token', 'link_publico_expires_at', 'aprovada_em'
            ]

            # Coletar dados para atualização
            update_data = {}
            # Campos de data que precisam de tratamento especial
            campos_data = ['periodo_inicio', 'periodo_fim', 'expires_at', 'link_publico_expires_at', 'aprovada_em']
            
            for campo in campos_permitidos:
                if campo in data:
                    valor_novo = data[campo]
                    valor_anterior = cotacao.get(campo)
                    
                    # Para campos de data, converter para string para comparação correta
                    if campo in campos_data:
                        valor_anterior_str = str(valor_anterior) if valor_anterior else None
                        valor_novo_str = valor_novo if valor_novo else None
                        if valor_anterior_str != valor_novo_str:
                            update_data[campo] = valor_novo
                            dados_anteriores[campo] = valor_anterior_str
                            dados_novos[campo] = valor_novo_str
                    elif valor_anterior != valor_novo:
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
        """API para enviar email relacionado à cotação usando Brevo"""
        try:
            data = request.get_json() or {}
            
            tipo = data.get('tipo', 'enviar_cotacao')
            destinatario = data.get('destinatario')
            nome_destinatario = data.get('nome_destinatario')
            
            if not destinatario:
                return jsonify({'success': False, 'message': 'Email do destinatário não informado'}), 400
            
            # Buscar cotação com dados completos
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            # Importar serviço Brevo
            from aicentralv2.services.brevo_service import enviar_email_cotacao_enviada_cliente, get_brevo_service
            from datetime import datetime
            
            # Preparar dados para o template
            cliente_nome = nome_destinatario or cotacao.get('cliente_nome', 'Cliente')
            primeiro_nome = cliente_nome.split()[0] if cliente_nome else 'Cliente'
            
            # Formatar valor
            valor_total = cotacao.get('valor_total_proposta') or cotacao.get('budget_estimado') or 0
            valor_formatado = f"R$ {valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            # Formatar período
            periodo = ''
            if cotacao.get('periodo_inicio'):
                periodo_inicio = cotacao['periodo_inicio']
                if hasattr(periodo_inicio, 'strftime'):
                    periodo = periodo_inicio.strftime('%d/%m/%Y')
                else:
                    periodo = str(periodo_inicio)
                if cotacao.get('periodo_fim'):
                    periodo_fim = cotacao['periodo_fim']
                    if hasattr(periodo_fim, 'strftime'):
                        periodo += f" a {periodo_fim.strftime('%d/%m/%Y')}"
                    else:
                        periodo += f" a {str(periodo_fim)}"
            
            # Gerar link público se ativo
            link_cotacao = None
            if cotacao.get('link_publico_ativo') and cotacao.get('link_publico_token'):
                base_url = app.config.get('BASE_URL', 'http://localhost:5000')
                link_cotacao = f"{base_url}/proposta/{cotacao['link_publico_token']}"
            
            # Formatar validade do link
            validade = ''
            if cotacao.get('link_publico_expires_at'):
                validade_dt = cotacao['link_publico_expires_at']
                if hasattr(validade_dt, 'strftime'):
                    validade = validade_dt.strftime('%d/%m/%Y às %H:%M')
                else:
                    validade = str(validade_dt)
            
            # Data de envio
            data_envio = datetime.now().strftime('%d/%m/%Y às %H:%M')
            
            try:
                # Usar o serviço Brevo com template
                resultado = enviar_email_cotacao_enviada_cliente(
                    to_email=destinatario,
                    to_name=cliente_nome,
                    numero_cotacao=cotacao.get('numero_cotacao', ''),
                    nome_campanha=cotacao.get('nome_campanha', ''),
                    valor_total=valor_formatado,
                    link_proposta=link_cotacao or '',
                    validade=validade,
                    executivo_nome=cotacao.get('responsavel_nome', ''),
                    executivo_email=cotacao.get('responsavel_email', '')
                )
                
                if resultado.get('success'):
                    # Atualizar status da cotação para "Enviada"
                    db.atualizar_cotacao(cotacao_id, status='Enviada', proposta_enviada_em=datetime.now())
                    
                    # Registrar auditoria
                    registrar_auditoria(
                        acao='EMAIL_SENT',
                        modulo='cotacoes',
                        descricao=f'Email cotação enviado para {destinatario} - Cotação {cotacao["numero_cotacao"]}',
                        registro_id=cotacao_id,
                        registro_tipo='cadu_cotacoes',
                        dados_novos={
                            'tipo': tipo,
                            'destinatario': destinatario,
                            'assunto': f'Sua Proposta - {cotacao["numero_cotacao"]}'
                        }
                    )
                    
                    return jsonify({'success': True, 'message': 'Email enviado com sucesso via Brevo'})
                else:
                    return jsonify({'success': False, 'message': resultado.get('error', 'Falha ao enviar email')}), 500
                    
            except Exception as e:
                app.logger.error(f"Erro ao enviar email via Brevo: {str(e)}", exc_info=True)
                return jsonify({'success': False, 'message': f'Erro ao enviar email: {str(e)}'}), 500
            
        except Exception as e:
            app.logger.error(f"Erro ao enviar email: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/cotacoes/<int:cotacao_id>/enviar-email-tipo', methods=['POST'])
    @login_required
    def enviar_email_cotacao_por_tipo(cotacao_id):
        """
        API para enviar email de cotação por tipo (enviada, aprovada, rejeitada)
        
        Regras:
        - cotacao_enviada: só para status Rascunho ou Em Análise
        - cotacao_aprovada: só para status Aprovada (email externo + interno)
        - cotacao_rejeitada: só para status Rejeitada (email externo + interno)
        
        Se tem agência: envia para contato da agência
        Se não tem agência: envia para contato do cliente
        
        Emails internos: responsável comercial + apolo@centralcomm.media
        """
        try:
            data = request.get_json() or {}
            
            tipo = data.get('tipo')
            destinatario = data.get('destinatario')
            nome_destinatario = data.get('nome_destinatario')
            tem_agencia = data.get('tem_agencia', False)
            agencia_nome = data.get('agencia_nome', '')
            cliente_nome = data.get('cliente_nome', '')
            
            if not tipo:
                return jsonify({'success': False, 'message': 'Tipo de email não informado'}), 400
            
            if not destinatario:
                return jsonify({'success': False, 'message': 'Email do destinatário não informado'}), 400
            
            # Buscar cotação com dados completos
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404
            
            status = cotacao.get('status', '')
            
            # Validar tipo x status
            if tipo == 'cotacao_enviada' and status not in ['Rascunho', 'Em Análise', 'Enviada', 'Negociação']:
                return jsonify({'success': False, 'message': 'Email de cotação enviada só pode ser enviado para status Rascunho, Em Análise, Enviada ou Negociação'}), 400
            if tipo == 'cotacao_aprovada' and status != 'Aprovada':
                return jsonify({'success': False, 'message': 'Email de aprovação só pode ser enviado para cotações aprovadas'}), 400
            if tipo == 'cotacao_rejeitada' and status != 'Rejeitada':
                return jsonify({'success': False, 'message': 'Email de rejeição só pode ser enviado para cotações rejeitadas'}), 400
            
            # Importar funções de email
            from aicentralv2.services.brevo_service import (
                enviar_email_cotacao_enviada_cliente,
                enviar_email_cotacao_aprovada_cliente,
                enviar_email_cotacao_rejeitada_cliente,
                enviar_email_cotacao_aprovada,
                enviar_email_cotacao_rejeitada
            )
            
            # Dados comuns
            numero_cotacao = cotacao.get('numero_cotacao', '')
            nome_campanha = cotacao.get('nome_campanha', '')
            responsavel_nome = cotacao.get('responsavel_nome', '')
            responsavel_email = cotacao.get('responsavel_email', '')
            
            # Formatar valor
            valor_total = cotacao.get('valor_total_proposta') or cotacao.get('budget_estimado') or 0
            valor_formatado = f"R$ {valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            # Gerar link público se ativo
            link_cotacao = None
            if cotacao.get('link_publico_ativo') and cotacao.get('link_publico_token'):
                base_url = app.config.get('BASE_URL', 'http://localhost:5000')
                link_cotacao = f"{base_url}/proposta/{cotacao['link_publico_token']}"
            
            # Nome a usar no email (agência ou cliente)
            nome_para_email = agencia_nome if tem_agencia and agencia_nome else cliente_nome
            if not nome_para_email:
                nome_para_email = nome_destinatario
            
            resultado_externo = None
            resultado_interno = None
            
            try:
                if tipo == 'cotacao_enviada':
                    # Email externo para cliente/agência
                    resultado_externo = enviar_email_cotacao_enviada_cliente(
                        to_email=destinatario,
                        to_name=nome_destinatario,
                        numero_cotacao=numero_cotacao,
                        nome_campanha=nome_campanha,
                        valor_total=valor_formatado,
                        link_proposta=link_cotacao or '',
                        executivo_nome=responsavel_nome,
                        executivo_email=responsavel_email,
                        tem_agencia=tem_agencia,
                        agencia_nome=agencia_nome,
                        cliente_nome=cliente_nome
                    )
                    
                    # Emails internos: responsável comercial + apolo
                    destinatarios_internos = []
                    if responsavel_email:
                        destinatarios_internos.append((responsavel_email, responsavel_nome or 'Responsável'))
                    destinatarios_internos.append(('apolo@centralcomm.media', 'Equipe Apolo'))
                    
                    # Link admin para cotação
                    base_url = app.config.get('BASE_URL', 'http://localhost:5000')
                    link_admin = f"{base_url}/cadastros/cotacoes/{cotacao_id}"
                    
                    for email_interno, nome_interno in destinatarios_internos:
                        try:
                            # Usar o mesmo template de email enviado para cliente, mas para equipe interna
                            enviar_email_cotacao_enviada_cliente(
                                to_email=email_interno,
                                to_name=nome_interno,
                                numero_cotacao=numero_cotacao,
                                nome_campanha=nome_campanha,
                                valor_total=valor_formatado,
                                link_proposta=link_admin,
                                executivo_nome=responsavel_nome,
                                executivo_email=responsavel_email,
                                tem_agencia=tem_agencia,
                                agencia_nome=agencia_nome,
                                cliente_nome=cliente_nome
                            )
                        except Exception as e:
                            app.logger.warning(f"Erro ao enviar email interno para {email_interno}: {e}")
                    
                    resultado_interno = {'success': True}
                    
                    if resultado_externo.get('success'):
                        # Atualizar status para Enviada
                        db.atualizar_cotacao(cotacao_id, status='Enviada', proposta_enviada_em=datetime.now())
                
                elif tipo == 'cotacao_aprovada':
                    # Email externo para cliente/agência
                    resultado_externo = enviar_email_cotacao_aprovada_cliente(
                        to_email=destinatario,
                        to_name=nome_destinatario,
                        numero_cotacao=numero_cotacao,
                        nome_campanha=nome_campanha,
                        valor_total=valor_formatado,
                        executivo_nome=responsavel_nome,
                        executivo_email=responsavel_email,
                        tem_agencia=tem_agencia,
                        agencia_nome=agencia_nome,
                        cliente_nome=cliente_nome
                    )
                    
                    # Emails internos: responsável comercial + apolo
                    destinatarios_internos = []
                    if responsavel_email:
                        destinatarios_internos.append((responsavel_email, responsavel_nome or 'Responsável'))
                    destinatarios_internos.append(('apolo@centralcomm.media', 'Equipe Apolo'))
                    
                    # Link admin para cotação
                    base_url = app.config.get('BASE_URL', 'http://localhost:5000')
                    link_admin = f"{base_url}/cadastros/cotacoes/{cotacao_id}"
                    
                    for email_interno, nome_interno in destinatarios_internos:
                        try:
                            enviar_email_cotacao_aprovada(
                                to_email=email_interno,
                                to_name=nome_interno,
                                numero_cotacao=numero_cotacao,
                                nome_campanha=nome_campanha,
                                cliente_nome=cliente_nome,
                                cliente_email=destinatario,
                                valor_total=valor_formatado,
                                link_proposta=link_cotacao or '',
                                data_aprovacao=datetime.now().strftime('%d/%m/%Y às %H:%M'),
                                link_admin=link_admin,
                                tem_agencia=tem_agencia,
                                agencia_nome=agencia_nome,
                                agencia_email=destinatario if tem_agencia else None
                            )
                        except Exception as e:
                            app.logger.warning(f"Erro ao enviar email interno para {email_interno}: {e}")
                    
                    resultado_interno = {'success': True}
                
                elif tipo == 'cotacao_rejeitada':
                    # Email externo para cliente/agência
                    resultado_externo = enviar_email_cotacao_rejeitada_cliente(
                        to_email=destinatario,
                        to_name=nome_destinatario,
                        numero_cotacao=numero_cotacao,
                        nome_campanha=nome_campanha,
                        executivo_nome=responsavel_nome,
                        executivo_email=responsavel_email,
                        tem_agencia=tem_agencia,
                        agencia_nome=agencia_nome,
                        cliente_nome=cliente_nome
                    )
                    
                    # Emails internos: responsável comercial + apolo
                    destinatarios_internos = []
                    if responsavel_email:
                        destinatarios_internos.append((responsavel_email, responsavel_nome or 'Responsável'))
                    destinatarios_internos.append(('apolo@centralcomm.media', 'Equipe Apolo'))
                    
                    # Link admin para cotação
                    base_url = app.config.get('BASE_URL', 'http://localhost:5000')
                    link_admin = f"{base_url}/cadastros/cotacoes/{cotacao_id}"
                    
                    motivo_rejeicao = cotacao.get('comentarios_internos') or cotacao.get('motivo_rejeicao') or ''
                    
                    for email_interno, nome_interno in destinatarios_internos:
                        try:
                            enviar_email_cotacao_rejeitada(
                                to_email=email_interno,
                                to_name=nome_interno,
                                numero_cotacao=numero_cotacao,
                                nome_campanha=nome_campanha,
                                cliente_nome=cliente_nome,
                                motivo=motivo_rejeicao,
                                link_proposta=link_admin,
                                data_rejeicao=datetime.now().strftime('%d/%m/%Y às %H:%M'),
                                tem_agencia=tem_agencia,
                                agencia_nome=agencia_nome,
                                agencia_email=destinatario if tem_agencia else None
                            )
                        except Exception as e:
                            app.logger.warning(f"Erro ao enviar email interno para {email_interno}: {e}")
                    
                    resultado_interno = {'success': True}
                
                else:
                    return jsonify({'success': False, 'message': 'Tipo de email inválido'}), 400
                
                # Verificar resultado do email externo
                if resultado_externo and resultado_externo.get('success'):
                    # Registrar auditoria
                    registrar_auditoria(
                        acao='EMAIL_SENT',
                        modulo='cotacoes',
                        descricao=f'Email {tipo} enviado para {destinatario} - Cotação {numero_cotacao}',
                        registro_id=cotacao_id,
                        registro_tipo='cadu_cotacoes',
                        dados_novos={
                            'tipo': tipo,
                            'destinatario': destinatario,
                            'tem_agencia': tem_agencia,
                            'agencia_nome': agencia_nome,
                            'cliente_nome': cliente_nome
                        }
                    )
                    
                    return jsonify({'success': True, 'message': 'Email enviado com sucesso'})
                else:
                    erro = resultado_externo.get('error', 'Falha ao enviar email') if resultado_externo else 'Nenhum email enviado'
                    return jsonify({'success': False, 'message': erro}), 500
                    
            except Exception as e:
                app.logger.error(f"Erro ao enviar email por tipo: {str(e)}", exc_info=True)
                return jsonify({'success': False, 'message': f'Erro ao enviar email: {str(e)}'}), 500
            
        except Exception as e:
            app.logger.error(f"Erro no endpoint enviar-email-tipo: {str(e)}", exc_info=True)
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

    @app.route('/api/cotacoes/<int:cotacao_id>/gerar-comunicacao', methods=['POST'])
    @login_required
    def gerar_comunicacao_ia(cotacao_id):
        """API para gerar comunicação (email/WhatsApp) usando IA via OpenRouter"""
        try:
            import requests
            import os
            
            data = request.get_json() or {}
            tipo = data.get('tipo', 'email')
            cotacao_data = data.get('cotacao_data', {})
            
            # Obter nome do usuário logado para assinatura
            user_fullname = session.get('user_fullname', 'Equipe Comercial')
            
            # Construir prompt baseado no tipo
            if tipo == 'email':
                prompt = f"""Você é um assistente de vendas especializado em mídia digital. 
Gere um email profissional e cordial para o cliente sobre a cotação abaixo.

DADOS DA COTAÇÃO:
- Número: {cotacao_data.get('numero', 'N/A')}
- Cliente: {cotacao_data.get('cliente', 'N/A')}
- Campanha: {cotacao_data.get('campanha', 'N/A')}
- Objetivo: {cotacao_data.get('objetivo', 'N/A')}
- Valor Total: R$ {cotacao_data.get('valor_total', 0):,.2f}
- Período: {cotacao_data.get('periodo_inicio', '')} a {cotacao_data.get('periodo_fim', '')}
- Status: {cotacao_data.get('status', 'N/A')}
- Total de Itens: {cotacao_data.get('itens_count', 0)}
- Total de Audiências: {cotacao_data.get('audiencias_count', 0)}
- Contato: {cotacao_data.get('contato_nome', 'N/A')}

INSTRUÇÕES:
1. Use uma saudação apropriada com o nome do contato
2. Seja profissional mas amigável
3. Destaque os principais pontos da proposta
4. Inclua um call-to-action claro
5. Finalize com a assinatura: {user_fullname}
6. Mantenha o email conciso (máximo 200 palavras)
7. Use formatação adequada para email (parágrafos curtos)

Gere apenas o texto do email, sem marcações markdown."""
            else:
                prompt = f"""Você é um assistente de vendas especializado em mídia digital.
Gere uma mensagem curta e objetiva para WhatsApp sobre a cotação abaixo.

DADOS DA COTAÇÃO:
- Número: {cotacao_data.get('numero', 'N/A')}
- Cliente: {cotacao_data.get('cliente', 'N/A')}
- Campanha: {cotacao_data.get('campanha', 'N/A')}
- Valor Total: R$ {cotacao_data.get('valor_total', 0):,.2f}
- Status: {cotacao_data.get('status', 'N/A')}
- Contato: {cotacao_data.get('contato_nome', 'N/A')}

INSTRUÇÕES:
1. Inicie com saudação informal usando o primeiro nome do contato
2. Seja direto e objetivo
3. Use emojis moderadamente (1-2 no máximo)
4. Máximo de 100 palavras
5. Inclua call-to-action
6. Finalize com o nome: {user_fullname}

Gere apenas o texto da mensagem, sem marcações markdown."""
            
            # Chamar OpenRouter
            OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
            if not OPENROUTER_API_KEY:
                return jsonify({'success': False, 'message': 'API Key do OpenRouter não configurada'}), 500
            
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://centralcomm.media",
                "X-Title": "CentralComm AI"
            }
            
            payload = {
                "model": "google/gemini-pro",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            mensagem = result['choices'][0]['message']['content']
            
            return jsonify({
                'success': True,
                'mensagem': mensagem,
                'tipo': tipo
            })
            
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Erro ao chamar OpenRouter: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'Erro na comunicação com IA: {str(e)}'}), 500
        except Exception as e:
            app.logger.error(f"Erro ao gerar comunicação: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': str(e)}), 500

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

    @app.route('/api/clientes/<int:cliente_id>/contatos-briefing')
    @login_required
    def api_contatos_briefing_por_cliente(cliente_id):
        """API para obter contatos de um cliente (setores Comercial e Operações) para briefings"""
        try:
            contatos = db.obter_contatos_comerciais_por_cliente(cliente_id)
            return jsonify([dict(c) for c in contatos] if contatos else [])
        except Exception as e:
            app.logger.error(f"Erro ao buscar contatos do cliente para briefing: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/clientes/<int:cliente_id>/todos-contatos')
    @login_required
    def api_todos_contatos_por_cliente(cliente_id):
        """API para obter TODOS os contatos de um cliente (sem filtro de setor)"""
        try:
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        c.id_contato_cliente,
                        c.nome_completo,
                        c.email,
                        s.display as setor
                    FROM tbl_contato_cliente c
                    LEFT JOIN tbl_setor s ON c.pk_id_tbl_setor = s.id_setor
                    WHERE c.status = true
                    AND c.pk_id_tbl_cliente = %s
                    ORDER BY c.nome_completo ASC
                ''', (cliente_id,))
                contatos = cursor.fetchall()
            return jsonify([dict(c) for c in contatos] if contatos else [])
        except Exception as e:
            app.logger.error(f"Erro ao buscar todos contatos do cliente: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/clientes/<int:cliente_id>/projetos')
    @login_required
    def api_projetos_por_cliente(cliente_id):
        """API para obter projetos de um cliente"""
        try:
            projetos = db.listar_projetos({'id_cliente': cliente_id})
            return jsonify([dict(p) for p in projetos] if projetos else [])
        except Exception as e:
            app.logger.error(f"Erro ao buscar projetos do cliente: {str(e)}", exc_info=True)
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
                especificacoes=data.get('especificacoes'),
                # Campos adicionados para valores
                praca=data.get('praca'),
                valor_unitario_tabela=data.get('valor_unitario_tabela'),
                desconto_percentual=data.get('desconto_percentual'),
                valor_unitario_negociado=data.get('valor_unitario_negociado'),
                investimento_liquido=data.get('investimento_liquido')
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
                especificacoes=data.get('especificacoes'),
                # Campos adicionados para valores
                praca=data.get('praca'),
                valor_unitario_tabela=data.get('valor_unitario_tabela'),
                desconto_percentual=data.get('desconto_percentual'),
                valor_unitario_negociado=data.get('valor_unitario_negociado'),
                investimento_liquido=data.get('investimento_liquido')
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

    @app.route('/api/cotacoes/audiencias/<int:audiencia_id>', methods=['GET'])
    @login_required
    def obter_audiencia_cotacao_api(audiencia_id):
        """API para obter dados de uma audiência da cotação"""
        try:
            audiencia = db.obter_audiencia_cotacao_por_id(audiencia_id)
            if not audiencia:
                return jsonify({'error': 'Audiência não encontrada'}), 404
            return jsonify(audiencia), 200
        except Exception as e:
            app.logger.error(f"Erro ao obter audiência: {str(e)}", exc_info=True)
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
            # Serializar para JSON (converter datetime para string)
            comentarios_serializados = serializar_para_json(comentarios)
            return jsonify({'success': True, 'comentarios': comentarios_serializados})
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
            enviar_email = data.get('enviar_email', False)
            
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
            
            # Enviar email se solicitado
            email_enviado = False
            if enviar_email:
                try:
                    # Obter dados da cotação e cliente
                    cotacao = db.obter_cotacao_por_id(cotacao_id)
                    if cotacao and cotacao.get('contato_email'):
                        from brevo import enviar_email_brevo
                        
                        # Obter nome do usuário que comentou
                        usuario = db.obter_contato_por_id(user_id)
                        usuario_nome = usuario.get('nome_completo', 'Equipe CentralComm') if usuario else 'Equipe CentralComm'
                        
                        # Preparar conteúdo do email
                        assunto = f"Novo comentário na cotação {cotacao.get('numero_cotacao', '')}"
                        corpo_html = f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                            <h2 style="color: #333;">Novo comentário na sua cotação</h2>
                            <p><strong>Cotação:</strong> {cotacao.get('numero_cotacao', '')} - {cotacao.get('nome_campanha', '')}</p>
                            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                                <p style="margin: 0;"><strong>{usuario_nome}</strong> comentou:</p>
                                <p style="margin: 10px 0 0 0;">{comentario}</p>
                            </div>
                            <p style="color: #666; font-size: 12px;">Este é um email automático. Para responder, acesse a plataforma.</p>
                        </div>
                        """
                        
                        enviar_email_brevo(
                            destinatario_email=cotacao.get('contato_email'),
                            destinatario_nome=cotacao.get('contato_nome', ''),
                            assunto=assunto,
                            corpo_html=corpo_html
                        )
                        email_enviado = True
                        app.logger.info(f"Email de comentário enviado para {cotacao.get('contato_email')}")
                except Exception as email_error:
                    app.logger.error(f"Erro ao enviar email de comentário: {email_error}")
            
            return jsonify({
                'success': True, 
                'message': 'Comentário adicionado com sucesso' + (' e email enviado' if email_enviado else ''),
                'comentario_id': result['id'],
                'created_at': result['created_at'].isoformat() if result['created_at'] else None,
                'email_enviado': email_enviado
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

    
    @app.route('/api/cotacoes/<int:cotacao_id>/historico', methods=['GET'])
    @login_required
    def obter_historico_cotacao(cotacao_id):
        """Obtém o histórico de alterações de uma cotação via audit log"""
        try:
            historico = db.obter_historico_cotacao(cotacao_id)
            return jsonify({'success': True, 'historico': historico})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter histórico: {e}")
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

    
    @app.route('/api/cotacoes/<int:cotacao_id>/criar-briefing', methods=['POST'])
    @login_required
    def criar_briefing_cotacao(cotacao_id):
        """Cria um briefing vinculado à cotação"""
        try:
            data = request.get_json() or {}
            
            # Obter cotação
            cotacao = db.obter_cotacao_por_id(cotacao_id)
            if not cotacao:
                return jsonify({'success': False, 'error': 'Cotação não encontrada'}), 404
            
            # Verificar se já tem briefing
            if cotacao.get('briefing_id'):
                return jsonify({'success': False, 'error': 'Esta cotação já possui um briefing vinculado'}), 400
            
            # Preparar dados do briefing
            titulo = data.get('titulo', f"{cotacao.get('numero_cotacao', '')} - {cotacao.get('nome_campanha', '')}")
            cliente_id = data.get('cliente_id') or cotacao.get('client_id')
            budget = data.get('budget', cotacao.get('budget_estimado'))
            objetivo = data.get('objetivo', cotacao.get('objetivo_campanha'))
            
            user_id = session.get('user_id')
            
            dados_briefing = {
                'titulo': titulo,
                'cliente_id': cliente_id,
                'id_contato_cliente': cotacao.get('client_user_id'),
                'status': 'Em Análise',
                'progresso': 20,
                'objetivo': objetivo,
                'budget': budget,
                'prazo': cotacao.get('periodo_fim'),
                'responsavel_centralcomm': user_id,
                'responsavel': user_id,
                'id_projeto': None,
                'plataforma': None,
                'briefing_original': objetivo,
                'briefing_melhorado': None,
                'analise_ia': None,
                'link_publico_token': None,
                'link_publico_ativo': False,
                'enviado_para_centralcomm': True,
                'data_envio': None
            }
            
            # Criar briefing
            result = db.criar_briefing(dados_briefing)
            briefing_id = result.get('id') if isinstance(result, dict) else result
            
            if briefing_id:
                # Vincular briefing à cotação
                db.atualizar_cotacao(cotacao_id, briefing_id=briefing_id)
                
                registrar_auditoria(
                    acao='CREATE',
                    modulo='briefings',
                    descricao=f'Briefing criado e vinculado à cotação {cotacao.get("numero_cotacao")}',
                    registro_id=briefing_id,
                    registro_tipo='cadu_briefings'
                )
                
                return jsonify({
                    'success': True, 
                    'message': 'Briefing criado e vinculado com sucesso',
                    'briefing_id': briefing_id
                })
            else:
                return jsonify({'success': False, 'error': 'Erro ao criar briefing'}), 500
                
        except Exception as e:
            app.logger.error(f"Erro ao criar briefing para cotação: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

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

    @app.route('/api/cotacoes/<int:cotacao_id>/link-publico', methods=['PUT', 'POST', 'PATCH'])
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
                'observacoes_internas': cotacao_original.get('observacoes_internas'),
                'origem': cotacao_original.get('origem', 'Admin'),
                'meio': cotacao_original.get('meio'),
                'tipo_peca': cotacao_original.get('tipo_peca'),
                'valor_total_proposta': cotacao_original.get('valor_total_proposta'),
                'agencia_id': cotacao_original.get('agencia_id'),
                'agencia_user_id': cotacao_original.get('agencia_user_id')
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
                        produto=converter_json(linha.get('produto')),
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
                        dados_extras=converter_json(linha.get('dados_extras')),
                        meio=linha.get('meio'),
                        tipo_peca=linha.get('tipo_peca'),
                        segmentacao=linha.get('segmentacao'),
                        formatos=converter_json(linha.get('formatos')),
                        canal=converter_json(linha.get('canal')),
                        objetivo_kpi=linha.get('objetivo_kpi'),
                        data_inicio=linha.get('data_inicio'),
                        data_fim=linha.get('data_fim'),
                        investimento_bruto=linha.get('investimento_bruto'),
                        especificacoes=linha.get('especificacoes'),
                        praca=linha.get('praca'),
                        desconto_percentual=linha.get('desconto_percentual'),
                        valor_unitario_tabela=linha.get('valor_unitario_tabela'),
                        valor_unitario_negociado=linha.get('valor_unitario_negociado'),
                        investimento_liquido=linha.get('investimento_liquido')
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
            
            # Garantir que total é um número válido para formatação
            total_formatado = float(total) if total is not None else 0.0
            
            registrar_auditoria(
                acao='UPDATE',
                modulo='cotacoes',
                descricao=f'Valor total calculado para cotação {cotacao_id}: R$ {total_formatado:,.2f}',
                registro_id=cotacao_id,
                registro_tipo='cadu_cotacoes'
            )
            
            return jsonify({
                'success': True, 
                'valor_total': total_formatado,
                'message': 'Valor total calculado com sucesso'
            })
                
        except Exception as e:
            import traceback
            current_app.logger.error(f"Erro ao calcular total da cotação {cotacao_id}: {type(e).__name__} - {e}\n{traceback.format_exc()}")
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
            agencia_filter = data.get('agencia')  # True = só agências, False = só não-agências, None = todos
            
            # Limpar espaços
            nome = nome.strip() if nome else ''
            razao = razao.strip() if razao else ''
            
            app.logger.info(f"Filtros processados: nome='{nome}', razao='{razao}', agencia={agencia_filter}")
            
            # Construir query com filtros - buscar em nome_fantasia OU razao_social
            # JOIN com tbl_agencia para filtrar por tipo de agência
            query = '''
                SELECT c.id_cliente, c.nome_fantasia, c.razao_social, c.cnpj, c.pessoa, c.pk_id_tbl_agencia, a.key as is_agencia
                FROM tbl_cliente c
                LEFT JOIN tbl_agencia a ON c.pk_id_tbl_agencia = a.id_agencia
                WHERE c.status = true
            '''
            params = []
            
            # Filtro de agência - key = true significa "Sim" (é agência), key = false significa "Não" (é cliente)
            if agencia_filter is False:
                # Somente clientes (não-agências) - onde key = false ou NULL
                query += ' AND (a.key = false OR a.key IS NULL)'
                app.logger.info("Filtrando: somente clientes (key = false ou NULL)")
            elif agencia_filter is True:
                # Somente agências - onde key = true (display = "Sim")
                query += ' AND a.key = true'
                app.logger.info("Filtrando: somente agências (key = true / Sim)")
            
            # Usar OR para buscar em qualquer um dos campos
            if nome and razao:
                # Se ambos estão preenchidos (mesmo valor), buscar com OR
                query += ' AND (c.nome_fantasia ILIKE %s OR c.razao_social ILIKE %s)'
                params.append(f'%{nome}%')
                params.append(f'%{razao}%')
                app.logger.info(f"Adicionado filtro OR: nome=%{nome}% OU razao=%{razao}%")
            elif nome:
                query += ' AND c.nome_fantasia ILIKE %s'
                params.append(f'%{nome}%')
                app.logger.info(f"Adicionado filtro nome: %{nome}%")
            elif razao:
                query += ' AND c.razao_social ILIKE %s'
                params.append(f'%{razao}%')
                app.logger.info(f"Adicionado filtro razao: %{razao}%")
            
            if not nome and not razao:
                return jsonify({
                    'success': False,
                    'message': 'Preencha pelo menos um filtro'
                })
            
            query += ' ORDER BY c.nome_fantasia ASC LIMIT 50'
            
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

    # ==================== ADMIN ANALYTICS DASHBOARD ====================
    
    @app.route('/api/admin/metrics/overview', methods=['GET'])
    @login_required
    def api_admin_metrics_overview():
        """API para métricas overview do dashboard admin"""
        try:
            overview = db.get_analytics_overview()
            return jsonify({'success': True, 'data': overview})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter overview: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/sessions/daily', methods=['GET'])
    @login_required
    def api_admin_metrics_sessions_daily():
        """API para sessões diárias"""
        try:
            days = request.args.get('days', 30, type=int)
            sessions = db.get_analytics_sessions_daily(days)
            
            # Converter para formato serializable
            data = []
            for s in sessions:
                data.append({
                    'date': s['date'].isoformat() if s.get('date') else None,
                    'total_sessions': s.get('total_sessions', 0),
                    'unique_users': s.get('unique_users', 0),
                    'avg_duration': float(s.get('avg_duration', 0)) if s.get('avg_duration') else 0,
                    'total_pageviews': s.get('total_pageviews', 0),
                    'mobile_sessions': s.get('mobile_sessions', 0),
                    'desktop_sessions': s.get('desktop_sessions', 0)
                })
            
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter sessões diárias: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/audiencias/top', methods=['GET'])
    @login_required
    def api_admin_metrics_top_audiencias():
        """API para top audiências"""
        try:
            limit = request.args.get('limit', 20, type=int)
            audiencias = db.get_analytics_top_audiencias(limit)
            
            data = []
            for a in audiencias:
                data.append({
                    'audiencia_id': a.get('audiencia_id'),
                    'audiencia_nome': a.get('audiencia_nome'),
                    'categoria': a.get('categoria'),
                    'total_views': a.get('total_views', 0),
                    'unique_users': a.get('unique_users', 0),
                    'unique_clients': a.get('unique_clients', 0)
                })
            
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter top audiências: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/pages/top', methods=['GET'])
    @login_required
    def api_admin_metrics_top_pages():
        """API para top páginas"""
        try:
            limit = request.args.get('limit', 20, type=int)
            pages = db.get_analytics_top_pages(limit)
            
            data = []
            for p in pages:
                data.append({
                    'page_path': p.get('page_path'),
                    'page_type': p.get('page_type'),
                    'total_views': p.get('total_views', 0),
                    'unique_users': p.get('unique_users', 0),
                    'avg_time_on_page': float(p.get('avg_time_on_page', 0)) if p.get('avg_time_on_page') else 0
                })
            
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter top páginas: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/users/active', methods=['GET'])
    @login_required
    def api_admin_metrics_active_users():
        """API para usuários mais ativos"""
        try:
            limit = request.args.get('limit', 50, type=int)
            users = db.get_analytics_user_engagement(limit)
            
            data = []
            for u in users:
                data.append({
                    'user_id': u.get('user_id'),
                    'user_name': u.get('user_name'),
                    'user_email': u.get('user_email'),
                    'client_name': u.get('client_name'),
                    'total_sessions': u.get('total_sessions', 0),
                    'total_time_seconds': u.get('total_time_seconds', 0),
                    'avg_session_duration': float(u.get('avg_session_duration', 0)) if u.get('avg_session_duration') else 0,
                    'total_pageviews': u.get('total_pageviews', 0),
                    'active_days': u.get('active_days', 0),
                    'last_session': u.get('last_session').isoformat() if u.get('last_session') else None
                })
            
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter usuários ativos: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/briefings', methods=['GET'])
    @login_required
    def api_admin_metrics_briefings():
        """API para métricas de briefings"""
        try:
            days = request.args.get('days', 30, type=int)
            briefings = db.get_analytics_briefings_metrics(days)
            
            data = []
            for b in briefings:
                data.append({
                    'date': b['date'].isoformat() if b.get('date') else None,
                    'briefings_created': b.get('briefings_created', 0),
                    'briefings_submitted': b.get('briefings_submitted', 0),
                    'briefings_viewed': b.get('briefings_viewed', 0),
                    'conversion_rate': float(b.get('conversion_rate', 0)) if b.get('conversion_rate') else 0
                })
            
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter métricas de briefings: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/cotacoes', methods=['GET'])
    @login_required
    def api_admin_metrics_cotacoes():
        """API para métricas de cotações"""
        try:
            days = request.args.get('days', 30, type=int)
            cotacoes = db.get_analytics_cotacoes_metrics(days)
            
            data = []
            for c in cotacoes:
                data.append({
                    'date': c['date'].isoformat() if c.get('date') else None,
                    'cotacoes_created': c.get('cotacoes_created', 0),
                    'cotacoes_sent': c.get('cotacoes_sent', 0),
                    'total_value': float(c.get('total_value', 0)) if c.get('total_value') else 0,
                    'avg_value': float(c.get('avg_value', 0)) if c.get('avg_value') else 0
                })
            
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter métricas de cotações: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/briefings/platforms', methods=['GET'])
    @login_required
    def api_admin_metrics_briefing_platforms():
        """API para briefings por plataforma"""
        try:
            platforms = db.get_analytics_briefing_platforms()
            
            data = []
            for p in platforms:
                data.append({
                    'plataforma': p.get('plataforma'),
                    'total': p.get('total', 0),
                    'unique_users': p.get('unique_users', 0),
                    'unique_clients': p.get('unique_clients', 0)
                })
            
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter plataformas de briefings: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/api/admin/metrics/audiencias/funnel', methods=['GET'])
    @login_required
    def api_admin_metrics_audiencias_funnel():
        """API para funil de audiências"""
        try:
            days = request.args.get('days', 30, type=int)
            funnel = db.get_analytics_audiencias_funnel(days)
            
            return jsonify({'success': True, 'data': funnel})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter funil de audiências: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    
    @app.route('/admin/metrics/dashboard')
    @login_required
    def admin_metrics_dashboard():
        """Página do Dashboard de Métricas Admin"""
        return render_template('admin_metrics_dashboard.html')

    # ==================== MÉTRICAS SEMANAIS ====================
    
    @app.route('/metricas/semanais')
    @login_required
    def metricas_semanais():
        """Página de Métricas Semanais do Comercial"""
        # Obter executivos e clientes para os filtros
        executivos = db.obter_executivos_ativos()
        clientes = db.obter_clientes_para_filtro()
        
        return render_template('metricas_semanais.html',
            executivos=executivos,
            clientes=clientes
        )
    
    @app.route('/api/metricas/semanais/kpis', methods=['GET'])
    @login_required
    def api_metricas_semanais_kpis():
        """API para KPIs semanais"""
        try:
            from datetime import datetime, timedelta
            
            # Obter parâmetros
            semana = request.args.get('semana')  # formato: YYYY-Www (ex: 2026-W03)
            executivo_id = request.args.get('executivo_id', type=int)
            cliente_id = request.args.get('cliente_id', type=int)
            
            # Calcular datas da semana
            if semana:
                # Parse ISO week format
                year, week = semana.split('-W')
                # Encontrar a segunda-feira da semana
                jan1 = datetime(int(year), 1, 1)
                # Calcular o dia da semana de 1º de janeiro (0 = segunda)
                jan1_weekday = jan1.weekday()
                # Calcular dias até a segunda da semana 1
                days_to_week1 = (7 - jan1_weekday) % 7
                if jan1_weekday <= 3:  # Se 1º jan é seg-qui, semana 1 começa nessa semana
                    days_to_week1 = -jan1_weekday
                else:  # Se 1º jan é sex-dom, semana 1 começa na próxima segunda
                    days_to_week1 = 7 - jan1_weekday
                
                semana_inicio = jan1 + timedelta(days=days_to_week1 + (int(week) - 1) * 7)
                semana_fim = semana_inicio + timedelta(days=6)
            else:
                # Semana atual
                hoje = datetime.now()
                semana_inicio = hoje - timedelta(days=hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
            
            semana_inicio = semana_inicio.date()
            semana_fim = semana_fim.date()
            
            kpis = db.obter_kpis_semanais(semana_inicio, semana_fim, executivo_id, cliente_id)
            
            return jsonify({
                'success': True,
                'data': kpis,
                'periodo': {
                    'inicio': semana_inicio.isoformat(),
                    'fim': semana_fim.isoformat()
                }
            })
        except Exception as e:
            current_app.logger.error(f"Erro ao obter KPIs semanais: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/metricas/semanais/por-executivo', methods=['GET'])
    @login_required
    def api_metricas_semanais_por_executivo():
        """API para cotações por executivo na semana"""
        try:
            from datetime import datetime, timedelta
            
            semana = request.args.get('semana')
            executivo_id = request.args.get('executivo_id', type=int)
            cliente_id = request.args.get('cliente_id', type=int)
            
            # Calcular datas da semana (mesmo cálculo)
            if semana:
                year, week = semana.split('-W')
                jan1 = datetime(int(year), 1, 1)
                jan1_weekday = jan1.weekday()
                if jan1_weekday <= 3:
                    days_to_week1 = -jan1_weekday
                else:
                    days_to_week1 = 7 - jan1_weekday
                semana_inicio = jan1 + timedelta(days=days_to_week1 + (int(week) - 1) * 7)
                semana_fim = semana_inicio + timedelta(days=6)
            else:
                hoje = datetime.now()
                semana_inicio = hoje - timedelta(days=hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
            
            semana_inicio = semana_inicio.date()
            semana_fim = semana_fim.date()
            
            dados = db.obter_cotacoes_por_executivo_semana(semana_inicio, semana_fim, executivo_id, cliente_id)
            
            return jsonify({'success': True, 'data': [dict(d) for d in dados]})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter cotações por executivo: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/metricas/semanais/evolucao-diaria', methods=['GET'])
    @login_required
    def api_metricas_semanais_evolucao():
        """API para evolução diária na semana"""
        try:
            from datetime import datetime, timedelta
            
            semana = request.args.get('semana')
            executivo_id = request.args.get('executivo_id', type=int)
            cliente_id = request.args.get('cliente_id', type=int)
            
            if semana:
                year, week = semana.split('-W')
                jan1 = datetime(int(year), 1, 1)
                jan1_weekday = jan1.weekday()
                if jan1_weekday <= 3:
                    days_to_week1 = -jan1_weekday
                else:
                    days_to_week1 = 7 - jan1_weekday
                semana_inicio = jan1 + timedelta(days=days_to_week1 + (int(week) - 1) * 7)
                semana_fim = semana_inicio + timedelta(days=6)
            else:
                hoje = datetime.now()
                semana_inicio = hoje - timedelta(days=hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
            
            semana_inicio = semana_inicio.date()
            semana_fim = semana_fim.date()
            
            dados = db.obter_evolucao_diaria_semana(semana_inicio, semana_fim, executivo_id, cliente_id)
            
            # Formatar datas para JSON
            result = []
            for d in dados:
                item = dict(d)
                item['data'] = item['data'].isoformat() if item.get('data') else None
                result.append(item)
            
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter evolução diária: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/metricas/semanais/distribuicao-status', methods=['GET'])
    @login_required
    def api_metricas_semanais_status():
        """API para distribuição por status na semana"""
        try:
            from datetime import datetime, timedelta
            
            semana = request.args.get('semana')
            executivo_id = request.args.get('executivo_id', type=int)
            cliente_id = request.args.get('cliente_id', type=int)
            
            if semana:
                year, week = semana.split('-W')
                jan1 = datetime(int(year), 1, 1)
                jan1_weekday = jan1.weekday()
                if jan1_weekday <= 3:
                    days_to_week1 = -jan1_weekday
                else:
                    days_to_week1 = 7 - jan1_weekday
                semana_inicio = jan1 + timedelta(days=days_to_week1 + (int(week) - 1) * 7)
                semana_fim = semana_inicio + timedelta(days=6)
            else:
                hoje = datetime.now()
                semana_inicio = hoje - timedelta(days=hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
            
            semana_inicio = semana_inicio.date()
            semana_fim = semana_fim.date()
            
            dados = db.obter_distribuicao_status_semana(semana_inicio, semana_fim, executivo_id, cliente_id)
            
            return jsonify({'success': True, 'data': [dict(d) for d in dados]})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter distribuição por status: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/metricas/semanais/comparativo', methods=['GET'])
    @login_required
    def api_metricas_semanais_comparativo():
        """API para comparativo com semana anterior"""
        try:
            from datetime import datetime, timedelta
            
            semana = request.args.get('semana')
            executivo_id = request.args.get('executivo_id', type=int)
            cliente_id = request.args.get('cliente_id', type=int)
            
            if semana:
                year, week = semana.split('-W')
                jan1 = datetime(int(year), 1, 1)
                jan1_weekday = jan1.weekday()
                if jan1_weekday <= 3:
                    days_to_week1 = -jan1_weekday
                else:
                    days_to_week1 = 7 - jan1_weekday
                semana_inicio = jan1 + timedelta(days=days_to_week1 + (int(week) - 1) * 7)
                semana_fim = semana_inicio + timedelta(days=6)
            else:
                hoje = datetime.now()
                semana_inicio = hoje - timedelta(days=hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
            
            semana_inicio = semana_inicio.date()
            semana_fim = semana_fim.date()
            
            dados = db.obter_comparativo_semanal(semana_inicio, semana_fim, executivo_id, cliente_id)
            
            return jsonify({'success': True, 'data': dados})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter comparativo semanal: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/metricas/semanais/cotacoes', methods=['GET'])
    @login_required
    def api_metricas_semanais_cotacoes():
        """API para lista detalhada de cotações da semana"""
        try:
            from datetime import datetime, timedelta
            
            semana = request.args.get('semana')
            executivo_id = request.args.get('executivo_id', type=int)
            cliente_id = request.args.get('cliente_id', type=int)
            
            if semana:
                year, week = semana.split('-W')
                jan1 = datetime(int(year), 1, 1)
                jan1_weekday = jan1.weekday()
                if jan1_weekday <= 3:
                    days_to_week1 = -jan1_weekday
                else:
                    days_to_week1 = 7 - jan1_weekday
                semana_inicio = jan1 + timedelta(days=days_to_week1 + (int(week) - 1) * 7)
                semana_fim = semana_inicio + timedelta(days=6)
            else:
                hoje = datetime.now()
                semana_inicio = hoje - timedelta(days=hoje.weekday())
                semana_fim = semana_inicio + timedelta(days=6)
            
            semana_inicio = semana_inicio.date()
            semana_fim = semana_fim.date()
            
            dados = db.obter_cotacoes_detalhadas_semana(semana_inicio, semana_fim, executivo_id, cliente_id)
            
            # Formatar datas para JSON
            result = []
            for d in dados:
                item = dict(d)
                for key in ['created_at', 'updated_at', 'aprovada_em']:
                    if item.get(key):
                        item[key] = item[key].isoformat()
                result.append(item)
            
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            current_app.logger.error(f"Erro ao obter cotações detalhadas: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500


    
    @app.route('/admin/clientes/recategorizar', methods=['POST'])
    @login_required
    def admin_recategorizar_clientes():
        """
        Recategoriza todos os clientes conforme regras ABC:
        - A: aprovações >= R$200.000/mês
        - B: ativo (tem briefings/cotações), < R$200k
        - C: sem briefings/cotações no mês
        """
        try:
            # Verificar permissão (apenas admin ou CentralComm)
            user_type = session.get('user_type', 'client')
            if user_type not in ['admin', 'internal']:
                return jsonify({
                    'success': False, 
                    'message': 'Permissão negada. Apenas administradores podem recategorizar.'
                }), 403
            
            # Executar recategorização
            resumo = db.recategorizar_clientes_abc()
            
            # Registrar auditoria
            registrar_auditoria(
                acao='UPDATE',
                modulo='CLIENTES',
                descricao=f'Recategorização ABC executada: A={resumo["A"]}, B={resumo["B"]}, C={resumo["C"]}',
                dados_novos=resumo
            )
            
            return jsonify({
                'success': True,
                'message': f'Recategorização concluída! A: {resumo["A"]}, B: {resumo["B"]}, C: {resumo["C"]}',
                'data': resumo
            })
            
        except Exception as e:
            app.logger.error(f"Erro ao recategorizar clientes: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    # ==================== UP AUDIÊNCIA ====================