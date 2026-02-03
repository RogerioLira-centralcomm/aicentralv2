"""
=====================================================
EMAIL SERVICE
Serviço de envio de emails (usando Brevo API)
=====================================================
"""

from flask import render_template, current_app
from threading import Thread
from aicentralv2.services.brevo_service import (
    get_brevo_service,
    enviar_email_convite,
    enviar_email_boas_vindas,
    enviar_email_reset_senha,
    enviar_email_senha_alterada
)
import logging

logger = logging.getLogger(__name__)


def send_email(subject, recipients, text_body=None, html_body=None, sender=None):
    """
    Envia email via Brevo API
    
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
    
    # Debug mode - não enviar, só mostrar
    if app.config.get('MAIL_DEBUG', False):
        print("\n" + "="*60)
        print("EMAIL DEBUG MODE")
        print("="*60)
        print(f"Para: {', '.join(recipients)}")
        print(f"Assunto: {subject}")
        print(f"\nTexto:\n{text_body}")
        if html_body:
            print(f"\nHTML:\n{html_body[:200]}...")
        print("="*60 + "\n")
        return True
    
    # Enviar via Brevo
    try:
        service = get_brevo_service()
        
        for recipient in recipients:
            result = service.enviar_email(
                to_email=recipient,
                to_name=recipient.split('@')[0],  # Nome básico do email
                subject=subject,
                html_content=html_body or f"<p>{text_body}</p>",
                text_content=text_body
            )
            
            if not result.get('success'):
                logger.error(f"Falha ao enviar email para {recipient}: {result.get('error')}")
                return False
        
        logger.info(f"Email enviado com sucesso para {recipients}")
        return True
        
    except Exception as e:
        logger.error(f"FALHA ao enviar email: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def send_password_reset_email(user_email, user_name, reset_link, expires_hours=1):
    """
    Envia email de recuperação de senha via Brevo
    
    Args:
        user_email: Email do usuário
        user_name: Nome do usuário
        reset_link: Link completo de reset
        expires_hours: Horas até expiração do link
    
    Returns:
        bool: True se enviado com sucesso
    """
    result = enviar_email_reset_senha(
        to_email=user_email,
        to_name=user_name,
        reset_link=reset_link,
        expires_hours=expires_hours
    )
    return result.get('success', False)


def send_password_changed_email(user_email, user_name):
    """
    Envia email de confirmação de senha alterada via Brevo
    
    Args:
        user_email: Email do usuário
        user_name: Nome do usuário
    
    Returns:
        bool: True se enviado com sucesso
    """
    result = enviar_email_senha_alterada(
        to_email=user_email,
        to_name=user_name
    )
    return result.get('success', False)


def send_welcome_email(user_email, user_name):
    """
    Envia email de boas-vindas via Brevo
    
    Args:
        user_email: Email do usuário
        user_name: Nome do usuário
    
    Returns:
        bool: True se enviado com sucesso
    """
    result = enviar_email_boas_vindas(
        to_email=user_email,
        to_name=user_name
    )
    return result.get('success', False)


def send_invite_email(to_email, invite_token, cliente_nome, invited_by_name, expires_at):
    """
    Envia email de convite para novo usuário via Brevo
    
    Args:
        to_email: Email do convidado
        invite_token: Token do convite
        cliente_nome: Nome do cliente/empresa
        invited_by_name: Nome de quem convidou
        expires_at: Data de expiração do convite
    
    Returns:
        bool: True se enviado com sucesso
    """
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    
    # Link de aceite do convite (usando query param conforme padrão documentado)
    invite_link = f"{base_url}/aceitar-convite?token={invite_token}"
    
    logger.info(f"Link do convite gerado: {invite_link}")
    
    # Formatar data de expiração
    expires_str = expires_at.strftime('%d/%m/%Y às %H:%M') if hasattr(expires_at, 'strftime') else str(expires_at)
    
    result = enviar_email_convite(
        to_email=to_email,
        to_name=to_email.split('@')[0],
        invite_link=invite_link,
        invited_by=invited_by_name,
        cliente_nome=cliente_nome,
        expires_at=expires_str
    )
    return result.get('success', False)


# ==================== TEMPLATES HTML (LEGADO) ====================

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