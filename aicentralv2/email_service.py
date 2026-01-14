"""
=====================================================
EMAIL SERVICE
Serviço de envio de emails
=====================================================
"""

from flask import render_template, current_app
from flask_mail import Message
from threading import Thread
from aicentralv2 import mail


def send_async_email(app, msg):
    """Envia email de forma assíncrona"""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"OK Email enviado para: {msg.recipients}")
        except Exception as e:
            print(f"FALHA Erro ao enviar email: {e}")


def send_email(subject, recipients, text_body=None, html_body=None, sender=None):
    """
    Envia email
    
    Args:
        subject: Assunto do email
        recipients: Lista de destinatários ou string única
        text_body: Corpo em texto plano (opcional)
        html_body: Corpo em HTML (opcional)
        sender: Remetente (opcional, usa padrão da config)
    
    Returns:
        bool: True se enviado com sucesso
    """
    app = current_app._get_current_object()
    
    # Se recipients é string, converter para lista
    if isinstance(recipients, str):
        recipients = [recipients]
    
    # Usar sender padrão se não fornecido
    if not sender:
        sender = app.config.get('MAIL_DEFAULT_SENDER', 'noreply@aicentral.com')
    
    # Criar mensagem
    msg = Message(
        subject=subject,
        sender=sender,
        recipients=recipients
    )
    
    # Adicionar corpo
    if text_body:
        msg.body = text_body
    if html_body:
        msg.html = html_body
    
    # Debug mode - não enviar, só mostrar
    if app.config.get('MAIL_DEBUG', False):
        print("\n" + "="*60)
        print("EMAIL DEBUG MODE")
        print("="*60)
        print(f"De: {sender}")
        print(f"Para: {', '.join(recipients)}")
        print(f"Assunto: {subject}")
        print(f"\nTexto:\n{text_body}")
        if html_body:
            print(f"\nHTML:\n{html_body[:200]}...")
        print("="*60 + "\n")
        return True
    
    # Enviar email (síncrono para debug)
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Tentando enviar email para {recipients}...")
        mail.send(msg)
        logger.info(f"Email enviado com sucesso para {recipients}")
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"FALHA ao enviar email: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def send_password_reset_email(user_email, user_name, reset_link, expires_hours=1):
    """
    Envia email de recuperação de senha
    
    Args:
        user_email: Email do usuário
        user_name: Nome do usuário
        reset_link: Link completo de reset
        expires_hours: Horas até expiração do link
    
    Returns:
        bool: True se enviado com sucesso
    """
    app_name = current_app.config.get('MAIL_APP_NAME', 'AIcentral v2')
    
    # Assunto
    subject = f"Recuperação de Senha - {app_name}"
    
    # Corpo em texto plano
    text_body = f"""
Olá {user_name},

Você solicitou a recuperação de senha no {app_name}.

Clique no link abaixo para redefinir sua senha:
{reset_link}

ATENÇÃO: Este link expira em {expires_hours} hora(s).

Se você não solicitou esta recuperação, ignore este email.

---
Equipe {app_name}
    """.strip()
    
    # Corpo em HTML
    html_body = render_template_string(
        get_reset_password_template(),
        user_name=user_name,
        reset_link=reset_link,
        expires_hours=expires_hours,
        app_name=app_name
    )
    
    # Enviar email
    return send_email(
        subject=subject,
        recipients=user_email,
        text_body=text_body,
        html_body=html_body
    )


def send_password_changed_email(user_email, user_name):
    """
    Envia email de confirmação de senha alterada
    
    Args:
        user_email: Email do usuário
        user_name: Nome do usuário
    
    Returns:
        bool: True se enviado com sucesso
    """
    app_name = current_app.config.get('MAIL_APP_NAME', 'AIcentral v2')
    
    subject = f"OK Senha Alterada - {app_name}"
    
    text_body = f"""
Olá {user_name},

Sua senha foi alterada com sucesso no {app_name}.

Se você não realizou esta alteração, entre em contato imediatamente.

---
Equipe {app_name}
    """.strip()
    
    html_body = render_template_string(
        get_password_changed_template(),
        user_name=user_name,
        app_name=app_name
    )
    
    return send_email(
        subject=subject,
        recipients=user_email,
        text_body=text_body,
        html_body=html_body
    )


def send_welcome_email(user_email, user_name):
    """
    Envia email de boas-vindas
    
    Args:
        user_email: Email do usuário
        user_name: Nome do usuário
    
    Returns:
        bool: True se enviado com sucesso
    """
    app_name = current_app.config.get('MAIL_APP_NAME', 'AIcentral v2')
    
    subject = f"Bem-vindo ao {app_name}!"
    
    text_body = f"""
Olá {user_name},

Bem-vindo ao {app_name}!

Sua conta foi criada com sucesso.

---
Equipe {app_name}
    """.strip()
    
    html_body = render_template_string(
        get_welcome_template(),
        user_name=user_name,
        app_name=app_name
    )
    
    return send_email(
        subject=subject,
        recipients=user_email,
        text_body=text_body,
        html_body=html_body
    )


def send_invite_email(to_email, invite_token, cliente_nome, invited_by_name, expires_at):
    """
    Envia email de convite para novo usuário
    
    Args:
        to_email: Email do convidado
        invite_token: Token do convite
        cliente_nome: Nome do cliente/empresa
        invited_by_name: Nome de quem convidou
        expires_at: Data de expiração do convite
    
    Returns:
        bool: True se enviado com sucesso
    """
    import logging
    logger = logging.getLogger(__name__)
    
    app_name = current_app.config.get('MAIL_APP_NAME', 'CentralX')
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    
    logger.info(f"BASE_URL configurado: {base_url}")
    
    # Link de aceite do convite
    invite_link = f"{base_url}/aceitar-convite/{invite_token}"
    
    logger.info(f"Link do convite gerado: {invite_link}")
    
    # Formatar data de expiração
    expires_str = expires_at.strftime('%d/%m/%Y às %H:%M') if hasattr(expires_at, 'strftime') else str(expires_at)
    
    subject = f"Você foi convidado para o {app_name}"
    
    text_body = f"""
Olá!

{invited_by_name} convidou você para fazer parte da equipe de {cliente_nome} no {app_name}.

Para aceitar o convite e criar sua conta, clique no link abaixo:
{invite_link}

ATENÇÃO: Este convite expira em {expires_str}.

Se você não esperava este convite, pode ignorar este email.

---
Equipe {app_name}
    """.strip()
    
    html_body = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Convite - {app_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .email-container {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #72cd80;
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .content {{
            margin-bottom: 30px;
        }}
        .btn {{
            display: inline-block;
            background-color: #72cd80;
            color: white !important;
            text-decoration: none;
            padding: 14px 30px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            margin: 20px 0;
        }}
        .btn:hover {{
            background-color: #5fb96c;
        }}
        .warning {{
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            font-size: 14px;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>Você foi convidado!</h1>
        </div>
        
        <div class="content">
            <p>Olá!</p>
            
            <p><strong>{invited_by_name}</strong> convidou você para fazer parte da equipe de <strong>{cliente_nome}</strong> no <strong>{app_name}</strong>.</p>
            
            <p style="text-align: center;">
                <a href="{invite_link}" class="btn">Aceitar Convite</a>
            </p>
            
            <div class="warning">
                <strong>⚠️ Atenção:</strong> Este convite expira em <strong>{expires_str}</strong>.
            </div>
            
            <p style="font-size: 14px; color: #666;">
                Se você não esperava este convite, pode ignorar este email.
            </p>
        </div>
        
        <div class="footer">
            <p>Equipe {app_name}</p>
        </div>
    </div>
</body>
</html>
    """
    
    return send_email(
        subject=subject,
        recipients=to_email,
        text_body=text_body,
        html_body=html_body
    )


# ==================== TEMPLATES HTML ====================

def render_template_string(template_string, **context):
    """
    Renderiza template string (fallback se arquivo não existir)
    """
    try:
        from flask import render_template
        # Tentar renderizar de arquivo primeiro
        return render_template('emails/reset_password.html', **context)
    except:
        # Usar template inline
        from jinja2 import Template
        return Template(template_string).render(**context)


def get_reset_password_template():
    """Template HTML de reset de senha"""
    return """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recuperação de Senha</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .email-container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #667eea;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .content p {
            margin-bottom: 15px;
            font-size: 16px;
        }
        .btn-reset {
            display: inline-block;
            padding: 16px 32px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            text-align: center;
            margin: 20px 0;
        }
        .warning {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 14px;
        }
        .link-backup {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin-top: 20px;
            word-break: break-all;
            font-size: 13px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>Recuperação de Senha</h1>
        </div>
        
        <div class="content">
            <p>Olá <strong>{{ user_name }}</strong>,</p>
            
            <p>Você solicitou a recuperação de senha no <strong>{{ app_name }}</strong>.</p>
            
            <p>Clique no botão abaixo para redefinir sua senha:</p>
            
            <div style="text-align: center;">
                <a href="{{ reset_link }}" class="btn-reset">
                    Redefinir Senha
                </a>
            </div>
            
            <div class="warning">
                <p style="margin:0;"><strong>Atenção:</strong> Este link expira em {{ expires_hours }} hora(s).</p>
            </div>
            
            <p>Se o botão não funcionar, copie e cole este link no navegador:</p>
            
            <div class="link-backup">
                {{ reset_link }}
            </div>
            
            <p style="margin-top: 30px; color: #666; font-size: 14px;">
                Se você não solicitou esta recuperação, ignore este email. Sua senha permanecerá segura.
            </p>
        </div>
        
        <div class="footer">
            <p>Equipe {{ app_name }}</p>
            <p style="font-size: 12px; color: #999;">
                Este é um email automático. Por favor, não responda.
            </p>
        </div>
    </div>
</body>
</html>
    """


def get_password_changed_template():
    """Template HTML de senha alterada"""
    return """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Senha Alterada</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .email-container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #4caf50;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .success-box {
            background: #d4edda;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>OK Senha Alterada</h1>
        </div>
        
        <div class="content">
            <p>Olá <strong>{{ user_name }}</strong>,</p>
            
            <div class="success-box">
                <p style="margin:0;">OK Sua senha foi alterada com sucesso no <strong>{{ app_name }}</strong>.</p>
            </div>
            
            <p>Se você não realizou esta alteração, entre em contato com o suporte imediatamente.</p>
        </div>
        
        <div class="footer">
            <p>Equipe {{ app_name }}</p>
        </div>
    </div>
</body>
</html>
    """


def get_welcome_template():
    """Template HTML de boas-vindas"""
    return """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bem-vindo</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .email-container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #667eea;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>Bem-vindo!</h1>
        </div>
        
        <div class="content">
            <p>Olá <strong>{{ user_name }}</strong>,</p>
            
            <p>Bem-vindo ao <strong>{{ app_name }}</strong>!</p>
            
            <p>Sua conta foi criada com sucesso.</p>
        </div>
        
        <div class="footer">
            <p>Equipe {{ app_name }}</p>
        </div>
    </div>
</body>
</html>
    """