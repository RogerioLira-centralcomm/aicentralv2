"""
Rotas da Aplicação
"""

from flask import session, redirect, url_for, flash, request, render_template
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
                
                dados = {
                    'total_clientes': total_clientes,
                    'clientes_ativos': clientes_ativos,
                    'clientes_inativos': clientes_inativos,
                    'total_contatos': total_contatos,
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
            query = """
                 SELECT 
                    c.id_cliente,
                    c.razao_social,
                    c.nome_fantasia,
                    c.cnpj,
                    c.status,
                    (
                        SELECT COUNT(*) 
                        FROM tbl_contato_cliente ct 
                        WHERE ct.pk_id_tbl_cliente = c.id_cliente
                    ) as total_contatos
                FROM tbl_cliente c
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
                            'total_contatos': row['total_contatos'] or 0
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
            return render_template('clientes.html', clientes=clientes)
            
        except Exception as e:
            print(f"❌ ERRO DETALHADO:")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensagem: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Erro ao buscar clientes: {str(e)}', 'error')
            return render_template('clientes.html', clientes=[])
    
    @app.route('/clientes/novo', methods=['GET', 'POST'])
    @login_required
    def cliente_novo():
        """Criar cliente"""
        if request.method == 'POST':
            try:
                razao_social = request.form.get('razao_social', '').strip()
                nome_fantasia = request.form.get('nome_fantasia', '').strip()
                cnpj = request.form.get('cnpj', '').strip()
                inscricao_estadual = request.form.get('inscricao_estadual', '').strip() or None
                inscricao_municipal = request.form.get('inscricao_municipal', '').strip() or None
                
                if not razao_social or not nome_fantasia:
                    flash('Razão Social e Nome Fantasia obrigatórios!', 'error')
                    return render_template('cliente_form.html')
                
                conn = db.get_db()
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO tbl_cliente (
                            razao_social, nome_fantasia, cnpj,
                            inscricao_estadual, inscricao_municipal, status
                        )
                        VALUES (%s, %s, %s, %s, %s, TRUE)
                    ''', (razao_social, nome_fantasia, cnpj, inscricao_estadual, inscricao_municipal))
                
                conn.commit()
                flash(f'Cliente "{nome_fantasia}" criado!', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                conn.rollback()
                app.logger.error(f"Erro: {e}")
                flash('Erro ao criar.', 'error')
        
        return render_template('cliente_form.html', cliente=None)
    
    @app.route('/clientes/<int:cliente_id>/editar', methods=['GET', 'POST'])
    @login_required
    def cliente_editar(cliente_id):
        """Editar cliente"""
        conn = db.get_db()
        
        if request.method == 'POST':
            try:
                razao_social = request.form.get('razao_social', '').strip()
                nome_fantasia = request.form.get('nome_fantasia', '').strip()
                cnpj = request.form.get('cnpj', '').strip()
                inscricao_estadual = request.form.get('inscricao_estadual', '').strip() or None
                inscricao_municipal = request.form.get('inscricao_municipal', '').strip() or None
                
                if not razao_social or not nome_fantasia:
                    flash('Campos obrigatórios!', 'error')
                    return redirect(url_for('cliente_editar', cliente_id=cliente_id))
                
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE tbl_cliente
                        SET razao_social = %s, nome_fantasia = %s, cnpj = %s,
                            inscricao_estadual = %s, inscricao_municipal = %s,
                            data_modificacao = CURRENT_TIMESTAMP
                        WHERE id_cliente = %s
                    ''', (razao_social, nome_fantasia, cnpj, inscricao_estadual, inscricao_municipal, cliente_id))
                
                conn.commit()
                flash(f'Cliente "{nome_fantasia}" atualizado!', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                conn.rollback()
                app.logger.error(f"Erro: {e}")
                flash('Erro ao atualizar.', 'error')
        
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM tbl_cliente WHERE id_cliente = %s', (cliente_id,))
            cliente = cursor.fetchone()
        
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('clientes'))
        
        return render_template('cliente_form.html', cliente=cliente)
    
    @app.route('/clientes/<int:cliente_id>/toggle-status', methods=['POST'])
    @login_required
    def cliente_toggle_status(cliente_id):
        """Ativar/desativar"""
        try:
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('SELECT status FROM tbl_cliente WHERE id_cliente = %s', (cliente_id,))
                cliente = cursor.fetchone()
                
                if cliente:
                    novo_status = not cliente['status']
                    cursor.execute('''
                        UPDATE tbl_cliente
                        SET status = %s, data_modificacao = CURRENT_TIMESTAMP
                        WHERE id_cliente = %s
                    ''', (novo_status, cliente_id))
                    conn.commit()
                    flash('Status atualizado!', 'success')
                else:
                    flash('Cliente não encontrado!', 'error')
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            flash('Erro ao alterar status.', 'error')
        
        return redirect(url_for('clientes'))

    @app.route('/clientes/<int:cliente_id>/detalhes')
    @login_required
    def cliente_detalhes(cliente_id):
        """Visualizar detalhes do cliente"""
        try:
            conn = db.get_db()
            cliente = None
            contatos = []
            
            # Busca dados do cliente
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        id_cliente,
                        razao_social,
                        nome_fantasia,
                        cnpj,
                        inscricao_estadual,
                        inscricao_municipal,
                        status,
                        COALESCE(TO_CHAR(data_cadastro, 'DD/MM/YYYY HH24:MI:SS'), 'N/A') as data_criacao,
                        COALESCE(inscricao_estadual, '') as inscricao_estadual,
                        COALESCE(inscricao_municipal, '') as inscricao_municipal,
                        COALESCE(cnpj, '') as cnpj
                    FROM tbl_cliente 
                    WHERE id_cliente = %s
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
            app.logger.error(f"Erro ao buscar detalhes do cliente: {str(e)}")
            flash('Erro ao carregar detalhes do cliente.', 'error')
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
                cohorts = 1
                
                if not all([nome_completo, email, senha, pk_id_tbl_cliente]):
                    flash('Preencha todos os campos obrigatórios!', 'error')
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT id_cliente, razao_social, nome_fantasia FROM tbl_cliente WHERE status = TRUE ORDER BY razao_social')
                        clientes = cursor.fetchall()
                    return render_template('contato_form.html', contato=None, clientes=clientes)
                
                db.criar_contato(
                    nome_completo=nome_completo,
                    email=email,
                    senha=senha,
                    pk_id_tbl_cliente=int(pk_id_tbl_cliente),
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
        
        return render_template('contato_form.html', contato=None, clientes=clientes)
    
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
                nova_senha = request.form.get('nova_senha', '').strip()
                
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
                        SET nome_completo = %s, email = %s, telefone = %s,cohorts = 1,
                            pk_id_tbl_cliente = %s, data_modificacao = CURRENT_TIMESTAMP
                        WHERE id_contato_cliente = %s
                    ''', (nome_completo, email, telefone, int(pk_id_tbl_cliente), contato_id))
                
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
        
        return render_template('contato_form.html', contato=contato, clientes=clientes)
    
    @app.route('/contatos/<int:contato_id>/toggle-status', methods=['POST'])
    @login_required
    def contato_toggle_status(contato_id):
        """Ativar/desativar"""
        try:
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute('SELECT status FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (contato_id,))
                result = cursor.fetchone()
                
                if result:
                    novo_status = not result['status']
                    cursor.execute('''
                        UPDATE tbl_contato_cliente
                        SET status = %s, data_modificacao = CURRENT_TIMESTAMP
                        WHERE id_contato_cliente = %s
                    ''', (novo_status, contato_id))
                    conn.commit()
                    flash('Status atualizado!', 'success')
                else:
                    flash('Contato não encontrado!', 'error')
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
    
    app.logger.info("Rotas registradas com sucesso")