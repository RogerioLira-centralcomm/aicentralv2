"""
Rotas da Aplicação
"""

from flask import session, redirect, url_for, flash, request, render_template, jsonify
from functools import wraps
from datetime import datetime, timedelta
import secrets
from aicentralv2 import db
from aicentralv2.email_service import send_password_reset_email, send_password_changed_email


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
    """Inicializa todas as rotas"""
    
    # ==================== FAVICON ====================
    
    @app.route('/favicon.ico')
    def favicon():
        return '', 204

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
    
    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        """Redefinir senha"""
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        contato = db.buscar_contato_por_token(token)

        if not contato:
            flash('Link inválido ou expirado!', 'error')
            return redirect(url_for('forgot_password'))

        if request.method == 'POST':
            nova_senha = request.form.get('password', '').strip()
            confirm = request.form.get('confirm_password', '').strip()

    # ==================== PLANOS ====================

    @app.route('/planos')
    @login_required
    def planos():
        """Lista todos os planos."""
        lista_planos = db.obter_planos()
        return render_template('planos.html', planos=lista_planos)

    @app.route('/planos/novo', methods=['GET', 'POST'])
    @login_required
    def plano_form():
        """Formulário para criar um novo plano."""
        id_plano = request.args.get('id_plano', type=int)
        plano = None
        
        if id_plano:
            plano = db.obter_plano(id_plano)
            if not plano:
                flash('Plano não encontrado.', 'error')
                return redirect(url_for('planos'))
        
        if request.method == 'POST':
            descricao = request.form.get('descricao', '').strip()
            tokens = request.form.get('tokens', type=int)
            
            if not descricao or not tokens:
                flash('Todos os campos são obrigatórios.', 'error')
                return render_template('plano_form.html')
            
            try:
                db.criar_plano(descricao, tokens)
                flash('Plano criado com sucesso!', 'success')
                return redirect(url_for('planos'))
            except Exception as e:
                flash(f'Erro ao criar plano: {str(e)}', 'error')
        
        return render_template('plano_form.html', plano=plano)

    @app.route('/planos/<int:id_plano>/editar', methods=['GET', 'POST'])
    @login_required
    def plano_editar(id_plano):
        """Formulário para editar um plano existente."""
        plano = db.obter_plano(id_plano)
        if not plano:
            flash('Plano não encontrado.', 'error')
            return redirect(url_for('planos'))
        
        if request.method == 'POST':
            descricao = request.form.get('descricao', '').strip()
            tokens = request.form.get('tokens', type=int)
            
            if not descricao or not tokens:
                flash('Todos os campos são obrigatórios.', 'error')
                return render_template('plano_form.html', plano=plano)
            
            try:
                if db.atualizar_plano(id_plano, descricao, tokens):
                    flash('Plano atualizado com sucesso!', 'success')
                    return redirect(url_for('planos'))
                else:
                    flash('Plano não encontrado.', 'error')
            except Exception as e:
                flash(f'Erro ao atualizar plano: {str(e)}', 'error')
        
        return render_template('plano_form.html', plano=plano)

    @app.route('/planos/<int:id_plano>/toggle_status', methods=['POST'])
    @login_required
    def plano_toggle_status(id_plano):
        """Alterna o status de um plano."""
        try:
            if db.toggle_status_plano(id_plano):
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'Plano não encontrado'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==================== AUX SETOR ====================
    
    @app.route('/aux_setor')
    @login_required
    def aux_setor():
        """Página de gerenciamento de setores"""
        try:
            setores = db.obter_setores(apenas_ativos=False)
            return render_template('aux_setor.html', setores=setores)
        except Exception as e:
            app.logger.error(f"Erro ao carregar setores: {str(e)}")
            flash('Erro ao carregar setores.', 'error')
            return redirect(url_for('index'))
    
    @app.route('/aux_setor/create', methods=['POST'])
    @login_required
    def create_setor():
        """Criar novo setor"""
        try:
            data = request.get_json()
            display = data.get('display', '').strip()
            status = data.get('status', True)
            
            if not display:
                return jsonify({'message': 'Display é obrigatório'}), 400
            
            setor_id = db.criar_setor(display, status)
            return jsonify({'message': 'Setor criado com sucesso', 'id': setor_id}), 201
        
        except Exception as e:
            app.logger.error(f"Erro ao criar setor: {str(e)}")
            return jsonify({'message': 'Erro ao criar setor'}), 500
    
    @app.route('/aux_setor/<int:setor_id>/toggle_status', methods=['PUT'])
    @login_required
    def toggle_status_setor(setor_id):
        """Alternar status do setor"""
        try:
            new_status = db.toggle_status_setor(setor_id)
            if new_status is not None:
                return jsonify({
                    'message': f'Status alterado para {"ativo" if new_status else "inativo"}',
                    'status': new_status
                }), 200
            return jsonify({'message': 'Setor não encontrado'}), 404
        
        except Exception as e:
            app.logger.error(f"Erro ao alterar status do setor: {str(e)}")
            return jsonify({'message': 'Erro ao alterar status'}), 500
            nova_senha = request.form.get('password', '').strip()
            confirm = request.form.get('confirm_password', '').strip()

            if not nova_senha or not confirm:
                flash('Preencha todos os campos!', 'error')
                return render_template('reset_password_tailwind.html', token=token, user=contato)

            if nova_senha != confirm:
                flash('Senhas não coincidem!', 'error')
                return render_template('reset_password_tailwind.html', token=token, user=contato)

            if len(nova_senha) < 6:
                flash('Senha deve ter 6+ caracteres!', 'error')
                return render_template('reset_password_tailwind.html', token=token, user=contato)

            try:
                db.atualizar_senha_contato(contato['id_contato_cliente'], nova_senha)
                db.limpar_reset_token(contato['id_contato_cliente'])
                send_password_changed_email(contato['email'], contato['nome_completo'])
                flash('Senha redefinida!', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                app.logger.error(f"Erro: {e}")
                flash('Erro ao redefinir.', 'error')

        return render_template('reset_password_tailwind.html', token=token, user=contato)
    
    # ==================== CLIENTES ====================
    
    @app.route('/clientes')
    @login_required
    def clientes():
        try:
            print("🔍 DEBUG: Iniciando rota /clientes")
            
            conn = db.get_db()
            if not conn:
                raise Exception("Falha na conexão com o banco de dados")
            
            cursor = conn.cursor()
            
            # Query com nomes CORRETOS das tabelas
            # Estatísticas por tipo de pessoa
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
            
            # Query principal de clientes
            query = """
                 SELECT 
                    c.id_cliente,
                    c.razao_social,
                    c.nome_fantasia,
                    c.cnpj,
                    c.status,
                    c.pessoa,
                    c.pk_id_aux_agencia,
                    ag.display as agencia_display,
                    ag.key as agencia_key,
                    (
                        SELECT COUNT(*) 
                        FROM tbl_contato_cliente ct 
                        WHERE ct.pk_id_tbl_cliente = c.id_cliente
                    ) as total_contatos
                FROM tbl_cliente c
                LEFT JOIN aux_agencia ag ON c.pk_id_aux_agencia = ag.id_aux_agencia
                ORDER BY c.id_cliente DESC
            """
            
            print(f"📝 DEBUG: Executando query")
            cursor.execute(query)
            
            resultados = cursor.fetchall()
            print(f"✅ DEBUG: Query executada. Resultados: {len(resultados) if resultados else 0}")
            
            clientes = []
            
            if resultados:
                for row in resultados:
                    try:
                        # ✅ ACESSAR COMO DICIONÁRIO
                        cliente = {
                            'id_cliente': row['id_cliente'],
                            'razao_social': row['razao_social'] or '',
                            'nome_fantasia': row['nome_fantasia'] or '',
                            'cnpj': row['cnpj'] or '',
                            'status': row['status'] if row['status'] is not None else False,
                            'total_contatos': row['total_contatos'] or 0,
                            'pk_id_aux_agencia': row['pk_id_aux_agencia'],
                            'agencia_display': row['agencia_display'],
                            'agencia_key': row['agencia_key']
                        }
                        clientes.append(cliente)
                        print(f"✅ Cliente {row['id_cliente']} - {row['razao_social'] or 'SEM NOME'} - {row['total_contatos']} contatos")
                    except Exception as e:
                        print(f"❌ DEBUG: Erro ao processar cliente: {row}")
                        print(f"   Erro: {str(e)}")
                        continue
            
            cursor.close()
            conn.close()
            
            print(f"✅ DEBUG: Total de clientes processados: {len(clientes)}")
            return render_template('clientes.html', 
                               clientes=clientes,
                               pessoas_stats=pessoas_stats)
            
        except Exception as e:
            print(f"❌ ERRO DETALHADO:")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensagem: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Erro ao buscar clientes: {str(e)}', 'error')
            return render_template('clientes.html', 
                                clientes=[],
                                pessoas_stats={'fisica': {'total': 0, 'ativos': 0},
                                             'juridica': {'total': 0, 'ativos': 0}})
    
    @app.route('/clientes/novo', methods=['GET', 'POST'])
    @login_required
    def cliente_novo():
        """Criar cliente"""
        planos = db.obter_planos()
        agencias = db.obter_aux_agencia()
        
        if request.method == 'POST':
            try:
                razao_social = request.form.get('razao_social', '').strip()
                nome_fantasia = request.form.get('nome_fantasia', '').strip()
                pessoa = request.form.get('pessoa', 'J').strip()
                cnpj = request.form.get('cnpj', '').strip()
                inscricao_estadual = request.form.get('inscricao_estadual', '').strip() or None
                pk_id_tbl_plano = request.form.get('pk_id_tbl_plano', type=int)
                inscricao_municipal = request.form.get('inscricao_municipal', '').strip() or None
                
                if not razao_social or not nome_fantasia:
                    flash('Razão Social e Nome Fantasia obrigatórios!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias)
                
                if pessoa not in ['F', 'J']:
                    flash('Tipo de pessoa inválido!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias)
                
                pk_id_aux_agencia = request.form.get('pk_id_aux_agencia', type=int)
                
                # Se for pessoa física, força agência 2
                if pessoa == 'F':
                    pk_id_aux_agencia = 2
                elif not pk_id_aux_agencia:
                    flash('Agência é obrigatória para Pessoa Jurídica!', 'error')
                    return render_template('cliente_form.html', planos=planos, agencias=agencias)

                id_cliente = db.criar_cliente(
                    razao_social=razao_social,
                    nome_fantasia=nome_fantasia,
                    pessoa=pessoa,
                    cnpj=cnpj,
                    inscricao_estadual=inscricao_estadual,
                    inscricao_municipal=inscricao_municipal,
                    pk_id_tbl_plano=pk_id_tbl_plano,
                    pk_id_aux_agencia=pk_id_aux_agencia
                )
                
                flash(f'Cliente "{nome_fantasia}" criado!', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                app.logger.error(f"Erro: {e}")
                flash('Erro ao criar.', 'error')
                return render_template('cliente_form.html', cliente=None, planos=planos, agencias=agencias)
        
        return render_template('cliente_form.html', cliente=None, planos=planos, agencias=agencias)
    
    @app.route('/clientes/<int:cliente_id>/editar', methods=['GET', 'POST'])
    @login_required
    def cliente_editar(cliente_id):
        """Editar cliente"""
        planos = db.obter_planos()
        agencias = db.obter_aux_agencia()
        cliente = db.obter_cliente_por_id(cliente_id)
        print("\n=== DEBUG EDITAR CLIENTE ===")
        print("Agências:", [{"id": a["id_aux_agencia"], "display": a["display"]} for a in agencias] if agencias else [])
        print("Cliente pk_id_aux_agencia:", cliente.get("pk_id_aux_agencia") if cliente else None)
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
                
                if not razao_social or not nome_fantasia:
                    flash('Campos obrigatórios!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias)
                
                pk_id_aux_agencia = request.form.get('pk_id_aux_agencia', type=int)
                
                # Se for pessoa física, força agência 2
                if pessoa == 'F':
                    pk_id_aux_agencia = 2
                elif not pk_id_aux_agencia:
                    flash('Agência é obrigatória para Pessoa Jurídica!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias)

                if not db.atualizar_cliente(
                    id_cliente=cliente_id,
                    razao_social=razao_social,
                    nome_fantasia=nome_fantasia,
                    pessoa=pessoa,
                    cnpj=cnpj,
                    inscricao_estadual=inscricao_estadual,
                    inscricao_municipal=inscricao_municipal,
                    pk_id_tbl_plano=pk_id_tbl_plano,
                    pk_id_aux_agencia=pk_id_aux_agencia
                ):
                    flash('Cliente não encontrado!', 'error')
                    return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias)
                
                flash(f'Cliente "{nome_fantasia}" atualizado!', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                app.logger.error(f"Erro ao atualizar cliente: {e}")
                flash('Erro ao atualizar.', 'error')
                return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias)
        
        return render_template('cliente_form.html', cliente=cliente, planos=planos, agencias=agencias)
    
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
                        c.inscricao_estadual,
                        c.inscricao_municipal,
                        c.status,
                        COALESCE(TO_CHAR(c.data_cadastro, 'DD/MM/YYYY HH24:MI:SS'), 'N/A') as data_criacao,
                        COALESCE(c.inscricao_estadual, '') as inscricao_estadual,
                        COALESCE(c.inscricao_municipal, '') as inscricao_municipal,
                        COALESCE(c.cnpj, '') as cnpj,
                        c.pk_id_aux_agencia,
                        ag.key as agencia_key,
                        p.id_plano,
                        p.descricao as plano_descricao,
                        p.tokens as plano_tokens,
                        p.status as plano_status,
                        COALESCE(c.total_token_gasto, 0) as total_tokens_gasto
                    FROM tbl_cliente c
                    LEFT JOIN aux_agencia ag ON c.pk_id_aux_agencia = ag.id_aux_agencia
                    LEFT JOIN tbl_plano p ON p.id_plano = c.pk_id_tbl_plano
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
                        id_contato_cliente,
                        nome_completo,
                        COALESCE(email, '') as email,
                        COALESCE(telefone, '') as telefone,
                        status,
                        COALESCE(TO_CHAR(data_cadastro, 'DD/MM/YYYY'), 'N/A') as data_criacao
                    FROM tbl_contato_cliente 
                    WHERE pk_id_tbl_cliente = %s 
                    ORDER BY nome_completo
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
                pk_id_tbl_cliente = request.form.get('pk_id_tbl_cliente')
                pk_id_tbl_cargo = request.form.get('pk_id_tbl_cargo')
                cohorts = request.form.get('cohorts', type=int) or 1
                
                if not all([nome_completo, email, senha, pk_id_tbl_cliente]):
                    flash('Preencha todos os campos obrigatórios!', 'error')
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT id_cliente, razao_social, nome_fantasia FROM tbl_cliente WHERE status = TRUE ORDER BY razao_social')
                        clientes = cursor.fetchall()
                        cargos = db.obter_cargos()
                    return render_template('contato_form.html', contato=None, clientes=clientes, cargos=cargos)
                
                db.criar_contato(
                    nome_completo=nome_completo,
                    email=email,
                    senha=senha,
                    pk_id_tbl_cliente=int(pk_id_tbl_cliente),
                    pk_id_tbl_cargo=int(pk_id_tbl_cargo) if pk_id_tbl_cargo else None,
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
                pk_id_tbl_cliente = request.form.get('pk_id_tbl_cliente')
                pk_id_aux_setor = request.form.get('pk_id_aux_setor')
                pk_id_tbl_cargo = request.form.get('pk_id_tbl_cargo')
                nova_senha = request.form.get('nova_senha', '').strip()
                cohorts = request.form.get('cohorts', type=int) or 1
                
                if not all([nome_completo, email, pk_id_tbl_cliente]):
                    flash('Campos obrigatórios!', 'error')
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
                            pk_id_tbl_cliente = %s, pk_id_aux_setor = %s, pk_id_tbl_cargo = %s, 
                            data_modificacao = CURRENT_TIMESTAMP
                        WHERE id_contato_cliente = %s
                    ''', (nome_completo, email, telefone, cohorts, int(pk_id_tbl_cliente),
                          int(pk_id_aux_setor) if pk_id_aux_setor else None,
                          int(pk_id_tbl_cargo) if pk_id_tbl_cargo else None, 
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
            
            # Busca setores e cargos
            setores = db.obter_setores()
            setor_id = contato.get('pk_id_aux_setor') if contato else None
            cargos = db.obter_cargos(setor_id)
        
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
    # The route /aux_setor/<int:setor_id>/toggle_status is already defined above

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
    
    app.logger.info("Rotas registradas com sucesso")