# --- (ao final do arquivo, após a última rota existente) ---

# Removido endpoint direto para compatibilidade com factory
"""
Rotas da Aplicação
"""

from flask import session, redirect, url_for, flash, request, render_template, jsonify
from functools import wraps
from datetime import datetime, timedelta
import secrets
from aicentralv2 import db
from aicentralv2.email_service import send_password_reset_email, send_password_changed_email
from aicentralv2.services.openrouter_image_extract import extract_fields_from_image_bytes, get_available_models


def login_required(f):
    """Decorator para rotas protegidas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def init_routes(app):
    @app.route('/cadu_audiencias')
    @login_required
    def cadu_audiencias():
        # Placeholder: renderiza um template simples ou lista vazia
        return render_template('cadu_audiencias.html')
    @app.route('/categorias_audiencia/novo', methods=['GET', 'POST'])
    @login_required
    def categorias_audiencia_novo():
        if request.method == 'POST':
            nome_exibicao = request.form.get('nome_exibicao', '').strip()
            categoria_nome = request.form.get('categoria', '').strip()
            subcategoria = request.form.get('subcategoria', '').strip()
            is_active = request.form.get('is_active') == 'on'
            if not nome_exibicao:
                flash('Preencha o nome de exibição.', 'error')
                return render_template('categorias_audiencia_form.html')
            novo_id = db.criar_categoria_audiencia({
                'nome_exibicao': nome_exibicao,
                'categoria': categoria_nome,
                'subcategoria': subcategoria,
                'is_active': is_active
            })
            flash('Categoria criada com sucesso!', 'success')
            return redirect(url_for('categorias_audiencia_detalhes', id_categoria=novo_id))
        return render_template('categorias_audiencia_form.html')
    @app.route('/categorias_audiencia/detalhes/<int:id_categoria>')
    @login_required
    def categorias_audiencia_detalhes(id_categoria):
        categoria = db.obter_categoria_audiencia_por_id(id_categoria)
        if not categoria:
            flash('Categoria não encontrada.', 'error')
            return redirect(url_for('categorias_audiencia'))
        return render_template('categorias_audiencia_detalhes.html', categoria=categoria)
    @app.route('/categorias_audiencia/editar/<int:id_categoria>', methods=['GET', 'POST'])
    @login_required
    def categorias_audiencia_editar(id_categoria):
        categoria = db.obter_categoria_audiencia_por_id(id_categoria)
        if request.method == 'POST':
            nome_exibicao = request.form.get('nome_exibicao', '').strip()
            categoria_nome = request.form.get('categoria', '').strip()
            subcategoria = request.form.get('subcategoria', '').strip()
            is_active = request.form.get('is_active') == 'on'
            if not nome_exibicao:
                flash('Preencha o nome de exibição.', 'error')
                return render_template('categorias_audiencia_form.html', categoria=categoria)
            db.atualizar_categoria_audiencia(id_categoria, {
                'nome_exibicao': nome_exibicao,
                'categoria': categoria_nome,
                'subcategoria': subcategoria,
                'is_active': is_active
            })
            flash('Categoria atualizada com sucesso!', 'success')
            return redirect(url_for('categorias_audiencia'))
        return render_template('categorias_audiencia_form.html', categoria=categoria)
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
                
                app.logger.info(f"Login: {user['nome_completo']} ({email})")
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
        try:
            # Obtém conexão usando o padrão do projeto
            conn = db.get_db()
            with conn.cursor() as cursor:
                # Total de clientes
                cursor.execute("SELECT COUNT(*) FROM tbl_cliente")
                total_clientes = cursor.fetchone()['count']
                
                # Clientes ativos (status = TRUE significa ativo)
                cursor.execute("SELECT COUNT(*) FROM tbl_cliente WHERE status = TRUE")
                clientes_ativos = cursor.fetchone()['count']
                
                # Clientes inativos (status = FALSE significa inativo)
                cursor.execute("SELECT COUNT(*) FROM tbl_cliente WHERE status = FALSE")
                clientes_inativos = cursor.fetchone()['count']
                
                # Total de contatos
                cursor.execute("SELECT COUNT(*) FROM tbl_contato_cliente")
                total_contatos = cursor.fetchone()['count']
                
                # Segmentação por tipo de pessoa
                cursor.execute("""
                    SELECT 
                        pessoa,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = TRUE THEN 1 ELSE 0 END) as ativos
                    FROM tbl_cliente 
                    GROUP BY pessoa
                """)
                pessoas = cursor.fetchall()
                
                # Processar dados de pessoas
                pessoas_stats = {
                    'fisica': {'total': 0, 'ativos': 0},
                    'juridica': {'total': 0, 'ativos': 0}
                }
                
                for p in pessoas:
                    if p['pessoa'] == 'F':
                        pessoas_stats['fisica'] = {
                            'total': p['total'],
                            'ativos': p['ativos']
                        }
                    elif p['pessoa'] == 'J':
                        pessoas_stats['juridica'] = {
                            'total': p['total'],
                            'ativos': p['ativos']
                        }
                
                dados = {
                    'total_clientes': total_clientes,
                    'clientes_ativos': clientes_ativos,
                    'clientes_inativos': clientes_inativos,
                    'total_contatos': total_contatos,
                    'pessoas_stats': pessoas_stats,
                    'atividades': []  # TODO: Implementar atividades recentes
                }
                
                return render_template('index_tailwind.html', **dados)
        except Exception as e:
            app.logger.error(f"Erro ao carregar dashboard: {str(e)}")
            flash('Erro ao carregar dados do dashboard.', 'error')
            return render_template('index_tailwind.html', 
                                total_clientes=0,
                                clientes_ativos=0,
                                clientes_inativos=0,
                                total_contatos=0,
                                atividades=[])
    
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
        """Editar cliente"""
        planos = db.obter_planos()
        agencias = db.obter_aux_agencia()
        tipos_cliente = db.obter_tipos_cliente()
        estados = db.obter_estados()
        vendedores_cc = db.obter_vendedores_centralcomm()
        apresentacoes = db.obter_apresentacoes_executivo()
        fluxos = db.obter_fluxos_boas_vindas()
        percentuais = db.obter_percentuais_ativos()
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
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                else:
                    if not nome_fantasia:
                        flash('Nome Completo é obrigatório!', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                if not cnpj:
                    flash('CNPJ/CPF é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                if not id_tipo_cliente:
                    flash('Tipo de Cliente é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                # Validação de CPF quando Pessoa Física
                if pessoa == 'F':
                    if not db.validar_cpf(cnpj):
                        flash('CPF inválido!', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                    # Ajustes padrão para PF
                    if not razao_social:
                        razao_social = 'NÃO REQUERIDO'
                    inscricao_estadual = 'ISENTO'
                    inscricao_municipal = 'ISENTO'

                # Validações de unicidade na edição (exclui o próprio cliente)
                try:
                    if db.cliente_existe_por_cnpj(cnpj, excluir_id=cliente_id):
                        flash('CNPJ já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                    if pessoa == 'J' and db.cliente_existe_por_razao_social(razao_social, excluir_id=cliente_id):
                        flash('Razão Social já cadastrada em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, percentuais=percentuais)
                    if db.cliente_existe_por_nome_fantasia(nome_fantasia, excluir_id=cliente_id):
                        flash('Nome Fantasia já cadastrado em outro cliente.', 'error')
                        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, percentuais=percentuais)
                except Exception as ve:
                    app.logger.error(f"Erro ao validar duplicidades: {ve}")
                    flash('Erro ao validar unicidade. Tente novamente.', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                pk_id_tbl_agencia = request.form.get('pk_id_tbl_agencia', type=int)
                vendas_central_comm = request.form.get('vendas_central_comm', type=int) or None
                id_fluxo_boas_vindas = request.form.get('id_fluxo_boas_vindas', type=int) or None
                id_percentual = request.form.get('id_percentual', type=int) or None
                if not vendas_central_comm:
                    flash('Vendas CentralComm é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                if not id_fluxo_boas_vindas:
                    flash('Fluxo de Boas-Vindas é obrigatório!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                
                # Se for pessoa física, força agência 2
                if pessoa == 'F':
                    pk_id_tbl_agencia = 2
                elif not pk_id_tbl_agencia:
                    flash('Agência é obrigatória para Pessoa Jurídica!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, percentuais=percentuais)

                # Percentual obrigatório quando Agência = Sim (Pessoa Jurídica)
                try:
                    if pessoa == 'J' and pk_id_tbl_agencia:
                        ag = db.obter_aux_agencia_por_id(pk_id_tbl_agencia)
                        ag_key = (str(ag.get('key')).lower() if isinstance(ag, dict) and 'key' in ag else '')
                        if (ag.get('key') is True) or (ag_key in ['sim','true','1','s','yes','y']):
                            if not id_percentual:
                                flash('Percentual é obrigatório quando Agência = Sim.', 'error')
                                return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                except Exception as _e:
                    app.logger.warning(f"Falha ao validar obrigatoriedade de Percentual: {_e}")

                if not db.atualizar_cliente(
                    id_cliente=cliente_id,
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
                    id_apresentacao_executivo=request.form.get('id_apresentacao_executivo', type=int) or None,
                    id_fluxo_boas_vindas=id_fluxo_boas_vindas,
                    id_percentual=id_percentual,
                    cep=cep,
                    bairro=bairro,
                    cidade=cidade,
                    rua=logradouro,
                    numero=numero,
                    complemento=complemento
                ):
                    flash('Cliente não encontrado!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, percentuais=percentuais)
                
                flash(f'Cliente "{nome_fantasia}" atualizado!', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                app.logger.error(f"Erro ao atualizar cliente: {e}")
                flash('Erro ao atualizar.', 'error')
                return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
        
        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)

    # ==================== CLIENTES ====================

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

            return render_template(
                'clientes.html',
                clientes=lista,
                pessoas_stats=pessoas_stats,
                vendedores_cc=vendedores_cc,
                filtro_vendas_central_comm=filtro_vendedor
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

    # ==================== PLANOS ====================

    @app.route('/planos')
    @login_required
    def planos():
        """Lista os planos cadastrados."""
        try:
            lista = db.obter_planos() or []
            return render_template('planos.html', planos=lista)
        except Exception as e:
            app.logger.error(f"Erro ao listar planos: {e}")
            flash('Erro ao carregar planos.', 'error')
            return render_template('planos.html', planos=[])

    @app.route('/planos/form', methods=['GET', 'POST'])
    @login_required
    def plano_form():
        """Criação e edição de plano (identificado por query param id_plano)."""
        id_plano = request.args.get('id_plano', type=int)
        if request.method == 'POST':
            try:
                descricao = (request.form.get('descricao') or '').strip()
                tokens = request.form.get('tokens', type=int)
                if not descricao or not tokens:
                    flash('Descrição e Tokens são obrigatórios.', 'error')
                    plano = db.obter_plano(id_plano) if id_plano else None
                    return render_template('plano_form.html', plano=plano)
                if id_plano:
                    db.atualizar_plano(id_plano, descricao, tokens)
                    flash('Plano atualizado com sucesso!', 'success')
                else:
                    novo_id = db.criar_plano(descricao, tokens)
                    flash(f'Plano criado com sucesso (ID {novo_id})!', 'success')
                return redirect(url_for('planos'))
            except Exception as e:
                app.logger.error(f"Erro ao salvar plano: {e}")
                flash('Erro ao salvar plano.', 'error')
        plano = db.obter_plano(id_plano) if id_plano else None
        return render_template('plano_form.html', plano=plano)

    @app.route('/planos/<int:id_plano>/toggle_status', methods=['POST'])
    @login_required
    def toggle_status_plano(id_plano):
        try:
            ok = db.toggle_status_plano(id_plano)
            if ok:
                return jsonify({'message': 'Status alterado com sucesso'}), 200
            return jsonify({'message': 'Plano não encontrado'}), 404
        except Exception as e:
            app.logger.error(f"Erro ao alterar status do plano: {e}")
            return jsonify({'message': 'Erro ao alterar status do plano'}), 500

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
        return render_template('up_audiencia.html', result=result, prompt=prompt_text, models=models, selected_model_id=selected_model_id)

    # ==================== PERCENTUAL (Fluxo de Boas-Vindas) ====================

    @app.route('/percentual')
    @login_required
    def percentual_list():
        """Lista de Percentuais (fluxos de boas-vindas), ordenada pelo índice (ID)."""
        try:
            percentuais = db.obter_percentuais() or []
            return render_template('percentual.html', percentuais=percentuais)
        except Exception as e:
            app.logger.error(f"Erro ao listar Percentuais: {e}")
            flash('Erro ao carregar Percentuais.', 'error')
            return render_template('percentual.html', fluxos=[])

    @app.route('/percentual/form', methods=['GET', 'POST'])
    @login_required
    def percentual_form():
        """Criação/Edição de Percentual (fluxo de boas-vindas).

        - Para edição, usar query param ?id=ID
        - No modo edição, o ID fica somente leitura.
        """
        perc_id = request.args.get('id', type=int)
        percentual = db.obter_percentual_por_id(perc_id) if perc_id else None
        if request.method == 'POST':
            try:
                id_input = request.form.get('id_percentual', type=int)
                display = (request.form.get('display') or '').strip()
                status = True if (request.form.get('status') == 'on') else False
                if not id_input or not display:
                    flash('Preencha ID e Descrição.', 'error')
                    return render_template('percentual_form.html', percentual=percentual)

                if perc_id:  # edição
                    # Garante que o ID do form corresponde ao que está sendo editado
                    if id_input != perc_id:
                        flash('O ID não pode ser alterado na edição.', 'error')
                        return render_template('percentual_form.html', percentual=percentual)
                    db.atualizar_percentual(perc_id, display, status)
                    flash('Percentual atualizado com sucesso!', 'success')
                else:  # criação
                    db.criar_percentual(id_input, display, status)
                    flash('Percentual criado com sucesso!', 'success')
                return redirect(url_for('percentual_list'))
            except Exception as e:
                app.logger.error(f"Erro ao salvar Percentual: {e}")
                flash('Erro ao salvar Percentual.', 'error')
        # GET
        return render_template('percentual_form.html', percentual=percentual)

    @app.route('/percentual/<int:fluxo_id>/delete', methods=['POST'])
    @login_required
    def percentual_delete(fluxo_id):
        """Exclui Percentual se não estiver em uso por clientes."""
        try:
            try:
                ok = db.deletar_percentual(fluxo_id)
                if ok:
                    flash('Percentual excluído com sucesso.', 'success')
                else:
                    flash('Percentual não encontrado.', 'warning')
            except Exception as e:
                # Provável violação de FK
                app.logger.warning(f"Falha ao excluir Percentual {fluxo_id}: {e}")
                flash('Não é possível excluir: Percentual em uso por algum cliente.', 'error')
        except Exception as e:
            app.logger.error(f"Erro ao excluir Percentual: {e}")
            flash('Erro ao excluir Percentual.', 'error')
        return redirect(url_for('percentual_list'))
    @app.route('/clientes/novo', methods=['GET', 'POST'])
    @login_required
    def cliente_novo():
        """Criar cliente"""
        planos = db.obter_planos()
        agencias = db.obter_aux_agencia()
        tipos_cliente = db.obter_tipos_cliente()
        estados = db.obter_estados()
        vendedores_cc = db.obter_vendedores_centralcomm()
        fluxos = db.obter_fluxos_boas_vindas()
        apresentacoes = db.obter_apresentacoes_executivo()
        percentuais = db.obter_percentuais_ativos()
        
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
                id_percentual = request.form.get('id_percentual', type=int) or None
                if not vendas_central_comm:
                    flash('Vendas CentralComm é obrigatório!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)

                # Nova opção: apresentação do executivo (opcional)
                id_apresentacao_executivo = request.form.get('id_apresentacao_executivo', type=int) or None
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
                try:
                    if pessoa == 'J' and pk_id_tbl_agencia:
                        ag = db.obter_aux_agencia_por_id(pk_id_tbl_agencia)
                        ag_key = (str(ag.get('key')).lower() if isinstance(ag, dict) and 'key' in ag else '')
                        if (ag.get('key') is True) or (ag_key in ['sim','true','1','s','yes','y']):
                            if not id_percentual:
                                flash('Percentual é obrigatório quando Agência = Sim.', 'error')
                                return render_template('cliente_form.html', planos=planos, agencias=agencias, tipos_cliente=tipos_cliente, estados=estados, vendedores_cc=vendedores_cc, apresentacoes=apresentacoes, fluxos=fluxos, percentuais=percentuais)
                except Exception as _e:
                    app.logger.warning(f"Falha ao validar obrigatoriedade de Percentual: {_e}")

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
                    cep=cep,
                    bairro=bairro,
                    cidade=cidade,
                    rua=logradouro,
                    numero=numero,
                    complemento=complemento,
                    id_apresentacao_executivo=id_apresentacao_executivo,
                    id_fluxo_boas_vindas=id_fluxo_boas_vindas,
                    id_percentual=id_percentual
                )

                # Inicializa os tokens do cliente: total do plano e gasto = 0
                try:
                    if pk_id_tbl_plano:
                        plano = db.obter_plano(pk_id_tbl_plano)
                        if plano and 'tokens' in plano:
                            db.atualizar_tokens_cliente(id_cliente, total_token_plano=plano['tokens'], total_token_gasto=0)
                        else:
                            # Se não conseguir obter o plano, ao menos zera o gasto
                            db.atualizar_tokens_cliente(id_cliente, total_token_gasto=0)
                    else:
                        db.atualizar_tokens_cliente(id_cliente, total_token_gasto=0)
                except Exception as e:
                    app.logger.warning(f"Falha ao inicializar tokens do cliente {id_cliente}: {e}")
                
                flash(f'Cliente "{nome_fantasia}" criado!', 'success')
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
                flash('Status atualizado!', 'success')
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            flash('Erro ao alterar status.', 'error')
        
        return redirect(url_for('clientes'))

    @app.route('/clientes/<int:cliente_id>/detalhes')
    @login_required
    def cliente_detalhes(cliente_id):
        """Visualizar detalhes do cliente"""
        conn = None
        try:
            conn = db.get_db()
            if not conn:
                raise Exception("Não foi possível conectar ao banco de dados")

            cliente = None
            contatos = []
            
            # Busca dados do cliente
            with conn.cursor() as cursor:
                app.logger.info(f"Buscando detalhes do cliente {cliente_id}")
                cursor.execute('''
                    SELECT 
                        c.id_cliente,
                        c.razao_social,
                        c.nome_fantasia,
                        c.cnpj,
                        c.id_percentual,
                        c.pessoa,
                        c.inscricao_estadual,
                        c.inscricao_municipal,
                        c.status,
                        COALESCE(TO_CHAR(c.data_cadastro, 'DD/MM/YYYY HH24:MI:SS'), 'N/A') as data_criacao,
                        COALESCE(c.inscricao_estadual, '') as inscricao_estadual,
                        COALESCE(c.inscricao_municipal, '') as inscricao_municipal,
                        COALESCE(c.cnpj, '') as cnpj,
                        c.pk_id_tbl_agencia AS pk_id_aux_agencia,
                        c.pk_id_aux_estado,
                        ag.key as agencia_key,
                        es.sigla as estado_sigla,
                        es.descricao as estado_descricao,
                        tc.display as tipo_cliente_display,
                        p.id_plano,
                        p.descricao as plano_descricao,
                        p.tokens as plano_tokens,
                        p.status as plano_status,
                        COALESCE(c.total_token_gasto, 0) as total_tokens_gasto,
                        c.vendas_central_comm,
                        vend.nome_completo AS vendedor_nome,
                        vendcar.descricao AS vendedor_cargo,
                        ae.display AS apresentacao_executivo_display,
                        fb.display AS fluxo_boas_vindas_display,
                        pr.display AS percentual_display
                    FROM tbl_cliente c
                    LEFT JOIN tbl_agencia ag ON c.pk_id_tbl_agencia = ag.id_agencia
                    LEFT JOIN tbl_estado es ON es.id_estado = c.pk_id_aux_estado
                    LEFT JOIN tbl_tipo_cliente tc ON c.id_tipo_cliente = tc.id_tipo_cliente
                    LEFT JOIN tbl_plano p ON p.id_plano = c.pk_id_tbl_plano
                    LEFT JOIN tbl_apresentacao_executivo ae ON ae.id_tbl_apresentacao_executivo = c.id_apresentacao_executivo
                    LEFT JOIN tbl_fluxo_boas_vindas fb ON fb.id_fluxo_boas_vindas = c.id_fluxo_boas_vindas
                    LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = c.vendas_central_comm
                    LEFT JOIN tbl_cargo_contato vendcar ON vend.pk_id_tbl_cargo = vendcar.id_cargo_contato
                    LEFT JOIN tbl_percentual pr ON pr.id_percentual = c.id_percentual
                    WHERE c.id_cliente = %s
                ''', (cliente_id,))
                cliente = cursor.fetchone()
            
            if not cliente:
                flash('Cliente não encontrado!', 'error')
                return redirect(url_for('clientes'))

            # Busca contatos do cliente
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        c.id_contato_cliente,
                        c.nome_completo,
                        COALESCE(c.email, '') as email,
                        COALESCE(c.telefone, '') as telefone,
                        c.status,
                        COALESCE(TO_CHAR(c.data_cadastro, 'DD/MM/YYYY'), 'N/A') as data_criacao,
                        car.descricao AS cargo_descricao,
                        s.display AS setor_descricao
                    FROM tbl_contato_cliente c
                    LEFT JOIN tbl_cargo_contato car ON c.pk_id_tbl_cargo = car.id_cargo_contato
                    LEFT JOIN tbl_setor s ON s.id_setor = car.pk_id_aux_setor
                    WHERE c.pk_id_tbl_cliente = %s 
                    ORDER BY c.nome_completo
                ''', (cliente_id,))
                contatos = cursor.fetchall()

                # Conta o total de contatos
                cursor.execute('''
                    SELECT COUNT(*) as total_contatos 
                    FROM tbl_contato_cliente 
                    WHERE pk_id_tbl_cliente = %s
                ''', (cliente_id,))
                total = cursor.fetchone()
                
            # Garante que cliente seja um dicionário com todos os campos necessários
            cliente = dict(cliente or {})
            cliente['total_contatos'] = total['total_contatos'] if total else 0
            
            # Garante que contatos seja uma lista de dicionários
            contatos = [dict(contato) for contato in (contatos or [])]

            return render_template(
                'cliente_detalhes.html',
                cliente=cliente,
                contatos=contatos
            )

        except Exception as e:
            import traceback
            app.logger.error("Erro ao buscar detalhes do cliente:")
            app.logger.error(f"Erro: {str(e)}")
            app.logger.error("Traceback:")
            app.logger.error(traceback.format_exc())
            
            if conn:
                conn.close()
            
            flash(f'Erro ao carregar detalhes do cliente: {str(e)}', 'error')
            return redirect(url_for('clientes'))
    
    # ==================== CONTATOS ====================
    
    @app.route('/contatos')
    @login_required
    def contatos():
        """Lista contatos"""
        try:
            contatos = db.obter_contatos()
            return render_template('contatos.html', contatos=contatos)
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            flash('Erro ao carregar.', 'error')
            return redirect(url_for('index'))

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
    
    
    @app.route('/contatos/novo', methods=['GET', 'POST'])
    @login_required
    def contato_novo():
        """Criar contato"""
        conn = db.get_db()
        
        if request.method == 'POST':
            try:
                nome_completo = request.form.get('nome_completo', '').strip()
                email = request.form.get('email', '').strip().lower()
                senha = request.form.get('senha', '').strip()
                telefone = request.form.get('telefone', '').strip() or None
                pk_id_tbl_cliente = request.form.get('pk_id_tbl_cliente', type=int)
                pk_id_aux_setor = request.form.get('pk_id_aux_setor', type=int)
                pk_id_tbl_cargo = request.form.get('pk_id_tbl_cargo', type=int)
                cohorts = request.form.get('cohorts', type=int) or 1
                
                # Agora setor e cargo são obrigatórios
                if not all([nome_completo, email, senha, pk_id_tbl_cliente, pk_id_aux_setor, pk_id_tbl_cargo]):
                    flash('Preencha todos os campos obrigatórios (incluindo Setor e Cargo)!', 'error')
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT id_cliente, razao_social, nome_fantasia FROM tbl_cliente WHERE status = TRUE ORDER BY razao_social')
                        clientes = cursor.fetchall()
                        setores = db.obter_setores()
                        cargos = db.obter_cargos()
                    return render_template('contato_form.html', contato=None, clientes=clientes, setores=setores, cargos=cargos)

                # Validação: cargo deve pertencer ao setor informado
                with conn.cursor() as cursor:
                    cursor.execute('SELECT 1 FROM tbl_cargo_contato WHERE id_cargo_contato = %s AND pk_id_aux_setor = %s', (pk_id_tbl_cargo, pk_id_aux_setor))
                    if cursor.fetchone() is None:
                        flash('Cargo selecionado não pertence ao Setor escolhido.', 'error')
                        with conn.cursor() as c2:
                            c2.execute('SELECT id_cliente, razao_social, nome_fantasia FROM tbl_cliente WHERE status = TRUE ORDER BY razao_social')
                            clientes = c2.fetchall()
                        setores = db.obter_setores()
                        cargos = db.obter_cargos()
                        return render_template('contato_form.html', contato=None, clientes=clientes, setores=setores, cargos=cargos)
                
                db.criar_contato(
                    nome_completo=nome_completo,
                    email=email,
                    senha=senha,
                    pk_id_tbl_cliente=pk_id_tbl_cliente,
                    pk_id_tbl_cargo=pk_id_tbl_cargo,
                    pk_id_tbl_setor=pk_id_aux_setor,
                    telefone=telefone,
                    cohorts=cohorts
                )
                
                flash(f'Contato "{nome_completo}" criado!', 'success')
                return redirect(url_for('contatos'))
            except ValueError as e:
                flash(str(e), 'error')
            except Exception as e:
                app.logger.error(f"Erro: {e}")
                flash('Erro ao criar.', 'error')
        
        with conn.cursor() as cursor:
            cursor.execute('SELECT id_cliente, razao_social, nome_fantasia FROM tbl_cliente WHERE status = TRUE ORDER BY razao_social')
            clientes = cursor.fetchall()
            
            # Busca setores e cargos
            setores = db.obter_setores()
            cargos = db.obter_cargos()
        
        return render_template('contato_form.html', contato=None, clientes=clientes, setores=setores, cargos=cargos)
    
    @app.route('/contatos/<int:contato_id>/editar', methods=['GET', 'POST'])
    @login_required
    def contato_editar(contato_id):
        """Editar contato"""
        conn = db.get_db()
        
        if request.method == 'POST':
            try:
                nome_completo = request.form.get('nome_completo', '').strip()
                email = request.form.get('email', '').strip().lower()
                telefone = request.form.get('telefone', '').strip() or None
                pk_id_tbl_cliente = request.form.get('pk_id_tbl_cliente', type=int)
                pk_id_aux_setor = request.form.get('pk_id_aux_setor', type=int)
                pk_id_tbl_cargo = request.form.get('pk_id_tbl_cargo', type=int)
                nova_senha = request.form.get('nova_senha', '').strip()
                cohorts = request.form.get('cohorts', type=int) or 1
                
                # Agora setor e cargo são obrigatórios na edição também
                if not all([nome_completo, email, pk_id_tbl_cliente, pk_id_aux_setor, pk_id_tbl_cargo]):
                    flash('Campos obrigatórios (incluindo Setor e Cargo)!', 'error')
                    return redirect(url_for('contato_editar', contato_id=contato_id))

                # Validação: cargo deve pertencer ao setor informado
                with conn.cursor() as cursor:
                    cursor.execute('SELECT 1 FROM tbl_cargo_contato WHERE id_cargo_contato = %s AND pk_id_aux_setor = %s', (pk_id_tbl_cargo, pk_id_aux_setor))
                    if cursor.fetchone() is None:
                        flash('Cargo selecionado não pertence ao Setor escolhido.', 'error')
                        return redirect(url_for('contato_editar', contato_id=contato_id))
                
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT id_contato_cliente 
                        FROM tbl_contato_cliente 
                        WHERE LOWER(email) = %s AND id_contato_cliente != %s
                    ''', (email, contato_id))
                    
                    if cursor.fetchone():
                        flash('Email já cadastrado!', 'error')
                        return redirect(url_for('contato_editar', contato_id=contato_id))
                    
                    cursor.execute('''
                        UPDATE tbl_contato_cliente
                        SET nome_completo = %s, email = %s, telefone = %s, cohorts = %s,
                            pk_id_tbl_cliente = %s, pk_id_tbl_cargo = %s, pk_id_tbl_setor = %s,
                            data_modificacao = CURRENT_TIMESTAMP
                        WHERE id_contato_cliente = %s
              ''', (nome_completo, email, telefone, cohorts, pk_id_tbl_cliente,
                  pk_id_tbl_cargo, pk_id_aux_setor,
                          contato_id))
                
                if nova_senha:
                    db.atualizar_senha_contato(contato_id, nova_senha)
                
                conn.commit()
                flash(f'Contato "{nome_completo}" atualizado!', 'success')
                return redirect(url_for('contatos'))
            except Exception as e:
                conn.rollback()
                app.logger.error(f"Erro: {e}")
                flash('Erro ao atualizar.', 'error')
        
        contato = db.obter_contato_por_id(contato_id)
        
        if not contato:
            flash('Contato não encontrado!', 'error')
            return redirect(url_for('contatos'))
        
        with conn.cursor() as cursor:
            cursor.execute('SELECT id_cliente, razao_social, nome_fantasia FROM tbl_cliente WHERE status = TRUE ORDER BY razao_social')
            clientes = cursor.fetchall()
            
            # Busca setores e TODOS os cargos (necessário para filtrar no front ao trocar setor)
            setores = db.obter_setores()
            cargos = db.obter_cargos()
        
        return render_template('contato_form.html', contato=contato, clientes=clientes, setores=setores, cargos=cargos)
    
    @app.route('/contatos/<int:contato_id>/toggle-status', methods=['POST'])
    @login_required
    def contato_toggle_status(contato_id):
        """Ativar/desativar"""
        # Verifica se o usuário está tentando desativar seu próprio perfil
        if contato_id == session.get('user_id'):
            flash('Você não pode desativar seu próprio usuário!', 'error')
            return redirect(url_for('contatos'))
            
        try:
            conn = db.get_db()
            with conn.cursor() as cursor:
                # Verifica o contato e seu cliente
                cursor.execute('''
                    SELECT c.status, cli.nome_fantasia
                    FROM tbl_contato_cliente c
                    JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
                    WHERE c.id_contato_cliente = %s
                ''', (contato_id,))
                result = cursor.fetchone()
                
                if not result:
                    flash('Contato não encontrado!', 'error')
                    return redirect(url_for('contatos'))
                    
                # Se chegou aqui, pode alterar o status
                novo_status = not result['status']
                cursor.execute('''
                    UPDATE tbl_contato_cliente
                    SET status = %s, data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_contato_cliente = %s
                ''', (novo_status, contato_id))
                conn.commit()
                flash(f'Contato {"desativado" if not novo_status else "ativado"} com sucesso!', 'success')
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            flash('Erro.', 'error')
        
        return redirect(url_for('contatos'))
    
    @app.route('/contatos/<int:contato_id>/deletar', methods=['POST'])
    @login_required
    def contato_deletar(contato_id):
        """Deletar contato"""
        try:
            if contato_id == session.get('user_id'):
                flash('Não pode deletar sua própria conta!', 'error')
                return redirect(url_for('contatos'))
            
            contato = db.obter_contato_por_id(contato_id)
            
            if contato:
                conn = db.get_db()
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (contato_id,))
                conn.commit()
                flash(f'Contato "{contato["nome_completo"]}" deletado!', 'warning')
            else:
                flash('Contato não encontrado!', 'error')
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            flash('Erro ao deletar.', 'error')
        
        return redirect(url_for('contatos'))

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
                flash(f'Tipo de cliente "{tipo["display"]}" excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir tipo de cliente.', 'error')
                
        except Exception as e:
            app.logger.error(f"Erro ao excluir tipo de cliente: {str(e)}")
            flash('Não é possível excluir este tipo de cliente pois está em uso.', 'error')
        
        return redirect(url_for('tipos_cliente'))

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

    @app.route('/api/categorias_audiencia', methods=['GET'])
    @login_required
    def api_listar_categorias_audiencia():
        categorias = db.obter_categorias_audiencia()
        return jsonify(categorias)

    @app.route('/api/categorias_audiencia/<int:id_categoria>', methods=['GET'])
    @login_required
    def api_obter_categoria_audiencia(id_categoria):
        categoria = db.obter_categoria_audiencia_por_id(id_categoria)
        if not categoria:
            abort(404)
        return jsonify(categoria)

    @app.route('/api/categorias_audiencia', methods=['POST'])
    @login_required
    def api_criar_categoria_audiencia():
        data = request.json
        novo_id = db.criar_categoria_audiencia(data)
        return jsonify({'id': novo_id}), 201

    @app.route('/api/categorias_audiencia/<int:id_categoria>', methods=['PUT'])
    @login_required
    def api_atualizar_categoria_audiencia(id_categoria):
        data = request.json
        ok = db.atualizar_categoria_audiencia(id_categoria, data)
        if not ok:
            abort(404)
        return jsonify({'success': True})

    @app.route('/api/categorias_audiencia/<int:id_categoria>', methods=['DELETE'])
    @login_required
    def api_excluir_categoria_audiencia(id_categoria):
        ok = db.excluir_categoria_audiencia(id_categoria)
        if not ok:
            abort(404)
        return jsonify({'success': True})

    @app.route('/categorias_audiencia')
    @login_required
    def categorias_audiencia():
        categorias = db.obter_categorias_audiencia()
        return render_template('categorias_audiencia.html', categorias=categorias)