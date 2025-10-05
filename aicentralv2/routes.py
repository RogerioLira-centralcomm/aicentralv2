"""
Rotas da aplicação AIcentralv2
"""
from flask import render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import secrets
from functools import wraps  # ← ADICIONAR ESTA LINHA
from flask_mail import Message
from aicentralv2 import mail
from . import db



# ==================== DECORATORS ====================

def login_required(f):
    """
    Decorator para proteger rotas que exigem autenticação
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('⚠️ Você precisa estar logado para acessar esta página!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    Decorator para proteger rotas que exigem permissão de administrador
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('⚠️ Você precisa estar logado para acessar esta página!', 'warning')
            return redirect(url_for('login'))

        if not session.get('is_admin', False):
            flash('❌ Acesso negado! Apenas administradores podem acessar esta página.', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


# ==================== FUNÇÃO DE INICIALIZAÇÃO ====================

def init_routes(app):
    """Registra todas as rotas da aplicação"""

    # ==================== ROTA: LOGIN ====================

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Página de login"""
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')

            # Validar campos
            if not email or not password:
                flash('❌ Email e senha são obrigatórios!', 'error')
                return render_template('login.html')

            # Validar formato de email
            import re
            email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_regex, email):
                flash('❌ Email inválido!', 'error')
                return render_template('login.html')

            # Verificar credenciais
            user = db.verificar_credenciais(email, password)

            if user:
                # Login bem-sucedido
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['nome_completo'] = user['nome_completo']
                session['email'] = user['email']
                session['is_admin'] = user['is_admin']

                flash(f'✅ Bem-vindo, {user["nome_completo"]}!', 'success')
                return redirect(url_for('index'))
            else:
                # Credenciais inválidas
                flash('❌ Email ou senha incorretos!', 'error')
                return render_template('login.html')

        # GET - Exibir formulário de login
        return render_template('login.html')

    # ==================== ROTA: LOGOUT ====================

    @app.route('/logout')
    def logout():
        """Logout do usuário"""
        nome = session.get('nome_completo', 'Usuário')
        session.clear()
        flash(f'👋 Até logo, {nome}!', 'info')
        return redirect(url_for('login'))

    # ==================== ROTA: INDEX (DASHBOARD) ====================

    @app.route('/')
    @login_required
    def index():
        """Página principal (dashboard)"""
        usuarios = db.obter_usuarios()
        return render_template('index.html', usuarios=usuarios)

    # ==================== ROTA: ADICIONAR/EDITAR USUÁRIO ====================

    @app.route('/user/add', methods=['GET', 'POST'])
    @app.route('/user/edit/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def user_form(user_id=None):
        """Formulário para adicionar ou editar usuário"""

        # Buscar usuário se for edição
        usuario = None
        if user_id:
            usuario = db.obter_usuario_por_id_com_cliente(user_id)
            if not usuario:
                flash('❌ Usuário não encontrado!', 'error')
                return redirect(url_for('index'))

        # Buscar clientes para o select
        clientes = db.obter_clientes_ativos()

        if request.method == 'POST':
            # Dados do formulário
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            idade = request.form.get('idade', '').strip()
            id_cliente = request.form.get('id_cliente', '').strip()

            # Validações básicas
            if not nome or not email or not idade:
                flash('❌ Nome, email e idade são obrigatórios!', 'error')
                return render_template('user.html', usuario=usuario, clientes=clientes)

            # Validar formato do email
            import re
            email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_regex, email):
                flash('❌ Email inválido!', 'error')
                return render_template('user.html', usuario=usuario, clientes=clientes)

            # Validar idade
            try:
                idade = int(idade)
                if idade < 0 or idade > 150:
                    raise ValueError
            except ValueError:
                flash('❌ Idade inválida! Deve ser um número entre 0 e 150.', 'error')
                return render_template('user.html', usuario=usuario, clientes=clientes)

            # Converter id_cliente para inteiro ou None
            id_cliente = int(id_cliente) if id_cliente else None

            try:
                if usuario:
                    # EDITAR usuário existente
                    db.atualizar_usuario(
                        user_id=user_id,
                        nome=nome,
                        email=email,
                        idade=idade,
                        id_cliente=id_cliente
                    )
                    flash('✅ Usuário atualizado com sucesso!', 'success')
                else:
                    # CRIAR novo usuário
                    username = request.form.get('username', '').strip().lower()
                    password = request.form.get('password', '').strip()

                    # Gerar username se vazio
                    if not username:
                        username = db.gerar_username(nome)

                    # Usar senha padrão se vazio
                    if not password:
                        password = 'senha123'

                    # Criar usuário
                    novo_id = db.criar_usuario(
                        username=username,
                        password=password,
                        nome=nome,
                        email=email,
                        idade=idade,
                        id_cliente=id_cliente
                    )

                    # Mostrar credenciais
                    flash(f'✅ Usuário criado com sucesso!', 'success')
                    flash(f'🔑 Username: {username}', 'info')
                    flash(f'🔐 Senha: {password}', 'warning')
                    flash('⚠️ Anote as credenciais! O usuário deve alterar a senha no primeiro login.', 'warning')

                return redirect(url_for('index'))

            except Exception as e:
                flash(f'❌ Erro ao salvar usuário: {str(e)}', 'error')
                return render_template('user.html', usuario=usuario, clientes=clientes)

        # GET - Exibir formulário
        return render_template('user.html', usuario=usuario, clientes=clientes)

    # ==================== ROTA: ATIVAR/DESATIVAR USUÁRIO ====================

    @app.route('/user/toggle/<int:user_id>', methods=['POST'])
    @login_required
    @admin_required
    def toggle_user(user_id):
        """Ativa ou desativa um usuário"""
        try:
            usuario = db.obter_usuario_por_id(user_id)

            if not usuario:
                flash('❌ Usuário não encontrado!', 'error')
                return redirect(url_for('index'))

            # Não permitir desativar a si mesmo
            if user_id == session.get('user_id'):
                flash('⚠️ Você não pode desativar sua própria conta!', 'warning')
                return redirect(url_for('index'))

            # Alternar status
            novo_status = not usuario['is_active']
            db.alternar_status_usuario(user_id, novo_status)

            status_texto = 'ativado' if novo_status else 'desativado'
            flash(f'✅ Usuário {usuario["nome_completo"]} foi {status_texto}!', 'success')

        except Exception as e:
            flash(f'❌ Erro ao alterar status: {str(e)}', 'error')

        return redirect(url_for('index'))

    # ==================== ROTA: DELETAR USUÁRIO ====================

    @app.route('/user/delete/<int:user_id>', methods=['POST'])
    @login_required
    @admin_required
    def delete_user(user_id):
        """Deleta permanentemente um usuário"""
        try:
            usuario = db.obter_usuario_por_id(user_id)

            if not usuario:
                flash('❌ Usuário não encontrado!', 'error')
                return redirect(url_for('index'))

            # Não permitir deletar a si mesmo
            if user_id == session.get('user_id'):
                flash('⚠️ Você não pode deletar sua própria conta!', 'warning')
                return redirect(url_for('index'))

            # Deletar
            db.deletar_usuario(user_id)
            flash(f'✅ Usuário {usuario["nome_completo"]} foi deletado permanentemente!', 'success')

        except Exception as e:
            flash(f'❌ Erro ao deletar usuário: {str(e)}', 'error')

        return redirect(url_for('index'))

    # ==================== ROTA: PERFIL DO USUÁRIO ====================

    @app.route('/profile')
    @login_required
    def profile():
        """Página de perfil do usuário logado"""
        user_id = session.get('user_id')
        usuario = db.obter_usuario_por_id_com_cliente(user_id)

        if not usuario:
            flash('❌ Erro ao carregar perfil!', 'error')
            return redirect(url_for('index'))

        return render_template('profile.html', usuario=usuario)

    # ==================== ROTA: ALTERAR SENHA ====================

    @app.route('/change-password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        """Alterar senha do usuário logado"""
        if request.method == 'POST':
            senha_atual = request.form.get('senha_atual', '')
            senha_nova = request.form.get('senha_nova', '')
            senha_confirma = request.form.get('senha_confirma', '')

            # Validações
            if not senha_atual or not senha_nova or not senha_confirma:
                flash('❌ Todos os campos são obrigatórios!', 'error')
                return render_template('change_password.html')

            if senha_nova != senha_confirma:
                flash('❌ A nova senha e a confirmação não coincidem!', 'error')
                return render_template('change_password.html')

            if len(senha_nova) < 6:
                flash('❌ A nova senha deve ter pelo menos 6 caracteres!', 'error')
                return render_template('change_password.html')

            # Verificar senha atual
            user_id = session.get('user_id')
            usuario = db.obter_usuario_por_id(user_id)

            from werkzeug.security import check_password_hash, generate_password_hash

            if not check_password_hash(usuario['password_hash'], senha_atual):
                flash('❌ Senha atual incorreta!', 'error')
                return render_template('change_password.html')

            # Atualizar senha
            try:
                db.atualizar_senha(user_id, senha_nova)
                flash('✅ Senha alterada com sucesso!', 'success')
                return redirect(url_for('profile'))
            except Exception as e:
                flash(f'❌ Erro ao alterar senha: {str(e)}', 'error')
                return render_template('change_password.html')

        return render_template('change_password.html')
    

     # ==================== ROTA: RECUPERAÇÃO DE SENHA ====================

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        """Página de recuperação de senha"""
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
        
            # Validar email
            if not email:
                flash('❌ Email é obrigatório!', 'error')
                return render_template('forgot-password.html')
        
            # Buscar usuário
            user = db.buscar_usuario_por_email(email)
        
            if user:
                try:
                    # Gerar token de reset
                    reset_token = secrets.token_urlsafe(32)
                    expires = datetime.utcnow() + timedelta(hours=1)
                
                    # Atualizar no banco
                    db.atualizar_reset_token(email, reset_token, expires)
                
                    # Gerar link de reset
                    reset_link = url_for('reset_password', token=reset_token, _external=True)
                
                    # Criar mensagem de email
                    msg = Message(
                        subject='🔐 Recuperação de Senha - AICentral',
                        recipients=[email],
                        html=render_template('emails/reset_password.html', reset_link=reset_link)
                    )
                
                    # Enviar email
                    mail.send(msg)
                
                    flash('✅ Email de recuperação enviado com sucesso!', 'success')
                    flash('📧 Verifique sua caixa de entrada (e spam/lixo eletrônico).', 'info')
                
                except Exception as e:
                    # Se falhar, mostrar link na tela
                    flash(f'⚠️ Erro ao enviar email: {str(e)}', 'error')
                    flash(f'🔗 Link de recuperação: {reset_link}', 'warning')
                    flash('Copie e cole este link no navegador.', 'info')
            else:
                # Não revelar se email existe ou não (segurança)
                flash('✅ Se o email estiver cadastrado, você receberá um link de recuperação.', 'info')
        
            return redirect(url_for('login'))
    
        return render_template('forgot-password.html')


    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        """Página de redefinição de senha"""
        # Buscar usuário pelo token
        user = db.buscar_usuario_por_token(token)
    
        # Verificar se token existe e não expirou
        if not user:
            flash('❌ Link de recuperação inválido!', 'error')
            return redirect(url_for('forgot_password'))
    
        # Verificar expiração
        if user['reset_token_expires']:
            if isinstance(user['reset_token_expires'], str):
                expires = datetime.fromisoformat(user['reset_token_expires'])
            else:
                expires = user['reset_token_expires']
        
            if expires < datetime.utcnow():
                flash('⏰ Link de recuperação expirado!', 'error')
                return redirect(url_for('forgot_password'))
    
        if request.method == 'POST':
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
        
            # Validar senhas
            if not password or not confirm_password:
                flash('❌ Todos os campos são obrigatórios!', 'error')
                return render_template('reset_password.html', token=token)
        
            if password != confirm_password:
                flash('❌ As senhas não coincidem!', 'error')
                return render_template('reset_password.html', token=token)
        
            if len(password) < 6:
                flash('❌ A senha deve ter no mínimo 6 caracteres!', 'error')
                return render_template('reset_password.html', token=token)
        
            # Atualizar senha
            nova_senha_hash = generate_password_hash(password)
            db.atualizar_senha(user['id'], nova_senha_hash)
        
            flash('✅ Senha redefinida com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
    
        return render_template('reset_password.html', token=token)