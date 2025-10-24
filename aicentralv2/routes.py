"""
=====================================================
ROUTES - Rotas da Aplicação
=====================================================
"""

from flask import session, redirect, url_for, flash, request, render_template
from datetime import datetime, timedelta
import secrets
from aicentralv2 import db
from aicentralv2.email_service import send_password_reset_email, send_password_changed_email


def init_routes(app):
    """
    Inicializa todas as rotas da aplicação
    
    Args:
        app: Instância do Flask
    """
        # ==================== FAVICON ====================
    
    @app.route('/favicon.ico')
    def favicon():
        """Retorna favicon ou 204 No Content"""
        from flask import send_from_directory
        import os
        
        # Tentar enviar favicon se existir
        favicon_path = os.path.join(app.root_path, 'static', 'favicon.ico')
        if os.path.exists(favicon_path):
            return send_from_directory(
                os.path.join(app.root_path, 'static'),
                'favicon.ico',
                mimetype='image/vnd.microsoft.icon'
            )
        
        # Se não existir, retornar 204 No Content (sem erro)
        return '', 204
    
    # ==================== HOME ====================
    
    @app.route('/')
    def index():
        """Página inicial"""
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        return render_template('index.html')
    
    
    # ==================== LOGIN ====================
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Página de login"""
        
        # Se já está logado, redirecionar
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            if not email or not password:
                flash('❌ Email e senha são obrigatórios!', 'error')
                return render_template('login.html')
            
            # Verificar credenciais
            user = db.verificar_credenciais(email, password)
            
            if user:
                # Salvar na sessão
                session['user_id'] = user['id_contato_cliente']
                session['user_email'] = user['email']
                session['user_nome'] = user['nome_completo']
                session['id_cliente'] = user['pk_id_tbl_cliente']
                session['cliente_nome'] = user['nome_fantasia']
                
                flash(f'✅ Bem-vindo, {user["nome_completo"]}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('❌ Email ou senha incorretos!', 'error')
                return render_template('login.html')
        
        return render_template('login.html')
    
    
    @app.route('/logout')
    def logout():
        """Faz logout do usuário"""
        session.clear()
        flash('✅ Logout realizado com sucesso!', 'success')
        return redirect(url_for('login'))
    
    
    # ==================== FORGOT PASSWORD ====================
    
    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        """Página de recuperação de senha"""
        
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
    
            if not email:
                flash('❌ Email é obrigatório!', 'error')
                return render_template('forgot_password.html')
    
            # Buscar contato
            contato = db.obter_contato_por_email(email)
    
            if contato:
                try:
                    # Gerar token
                    reset_token = secrets.token_urlsafe(32)
                    expires = datetime.utcnow() + timedelta(hours=1)
    
                    # Atualizar no banco
                    db.atualizar_reset_token(email, reset_token, expires)
    
                    # Gerar link
                    reset_link = url_for('reset_password', token=reset_token, _external=True)
    
                    # ENVIAR EMAIL
                    email_enviado = send_password_reset_email(
                        user_email=contato['email'],
                        user_name=contato['nome_completo'],
                        reset_link=reset_link,
                        expires_hours=1
                    )
    
                    if email_enviado:
                        flash('✅ Email de recuperação enviado! Verifique sua caixa de entrada.', 'success')
                    else:
                        flash('⚠️ Erro ao enviar email. Tente novamente.', 'error')
                    
                    # DEBUG
                    app.logger.info(f"🔗 Link de recuperação: {reset_link}")
    
                except Exception as e:
                    app.logger.error(f"❌ Erro: {e}")
                    flash('❌ Erro ao processar recuperação.', 'error')
            else:
                # Não revelar se email existe
                flash('✅ Se o email estiver cadastrado, você receberá instruções.', 'info')
    
            return render_template('forgot_password.html')
    
        return render_template('forgot_password.html')
    
    
    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        """Página de redefinição de senha"""
        
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        # Buscar contato pelo token
        contato = db.buscar_contato_por_token(token)
    
        if not contato:
            flash('❌ Link inválido ou expirado!', 'error')
            return redirect(url_for('forgot_password'))
    
        if request.method == 'POST':
            nova_senha = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
    
            if not nova_senha or not confirm_password:
                flash('❌ Todos os campos são obrigatórios!', 'error')
                return render_template('reset_password.html', token=token, user=contato)
    
            if nova_senha != confirm_password:
                flash('❌ As senhas não coincidem!', 'error')
                return render_template('reset_password.html', token=token, user=contato)
    
            if len(nova_senha) < 6:
                flash('❌ A senha deve ter no mínimo 6 caracteres!', 'error')
                return render_template('reset_password.html', token=token, user=contato)
    
            try:
                # Atualizar senha
                db.atualizar_senha_contato(contato['id_contato_cliente'], nova_senha)
                
                # Limpar token
                db.limpar_reset_token(contato['id_contato_cliente'])
                
                # ENVIAR EMAIL DE CONFIRMAÇÃO
                send_password_changed_email(
                    user_email=contato['email'],
                    user_name=contato['nome_completo']
                )
                
                flash('✅ Senha redefinida com sucesso! Faça login.', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                app.logger.error(f"❌ Erro: {e}")
                flash('❌ Erro ao redefinir senha.', 'error')
                return render_template('reset_password.html', token=token, user=contato)
    
        return render_template('reset_password.html', token=token, user=contato)
    
    
    # ==================== PERFIL ====================
    
    @app.route('/perfil', methods=['GET', 'POST'])
    def perfil():
        """Página de perfil do usuário"""
        
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        contato = db.obter_contato_por_id(session['user_id'])
        
        if not contato:
            flash('❌ Erro ao carregar perfil!', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip().lower()
            telefone = request.form.get('telefone', '').strip()
            
            try:
                db.atualizar_perfil(session['user_id'], nome, email, telefone)
                
                # Atualizar sessão
                session['user_email'] = email
                session['user_nome'] = nome
                
                flash('✅ Perfil atualizado com sucesso!', 'success')
                return redirect(url_for('perfil'))
                
            except Exception as e:
                flash(f'❌ Erro: {str(e)}', 'error')
        
        return render_template('perfil.html', contato=contato)
    
    
    @app.route('/alterar-senha', methods=['GET', 'POST'])
    def alterar_senha():
        """Página de alteração de senha"""
        
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            senha_atual = request.form.get('senha_atual', '')
            nova_senha = request.form.get('nova_senha', '')
            confirmar_senha = request.form.get('confirmar_senha', '')
            
            if nova_senha != confirmar_senha:
                flash('❌ As senhas não coincidem!', 'error')
                return render_template('alterar_senha.html')
            
            sucesso, mensagem = db.alterar_senha_com_validacao(
                session['user_id'],
                senha_atual,
                nova_senha
            )
            
            if sucesso:
                flash(f'✅ {mensagem}', 'success')
                return redirect(url_for('perfil'))
            else:
                flash(f'❌ {mensagem}', 'error')
        
        return render_template('alterar_senha.html')
    
    
    # ==================== DASHBOARD ====================
    
    @app.route('/dashboard')
    def dashboard():
        """Dashboard principal"""
        
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        return render_template('dashboard.html')
    
    
    # ==================== ERROR HANDLERS ====================
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Página de erro 404"""
        return render_template('errors/404.html'), 404
    
    
    @app.errorhandler(500)
    def internal_error(error):
        """Página de erro 500"""
        app.logger.error(f'Server Error: {error}')
        return render_template('errors/500.html'), 500
    
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Página de erro 403"""
        return render_template('errors/403.html'), 403
    
    
    # Log de rotas registradas
    app.logger.info("✅ Rotas registradas com sucesso")