"""
Testa envio real de email
"""

from aicentralv2 import create_app
import os

app = create_app()

print("\n" + "="*60)
print("📧 TESTE DE ENVIO DE EMAIL")
print("="*60)

with app.app_context():
    # Verificar configurações
    print("\n1. Configurações atuais:")
    print(f"   MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
    print(f"   MAIL_PORT: {app.config.get('MAIL_PORT')}")
    print(f"   MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
    print(f"   MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    print(f"   MAIL_PASSWORD: {'*' * 8 if app.config.get('MAIL_PASSWORD') else 'NÃO CONFIGURADO'}")
    print(f"   MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")
    print(f"   MAIL_DEBUG: {app.config.get('MAIL_DEBUG')}")
    
    # Tentar enviar email de teste
    print("\n2. Enviando email de teste...")
    
    from aicentralv2.email_service import send_email
    
    # ALTERE PARA SEU EMAIL AQUI
    email_destino = input("\n   Digite seu email para teste: ").strip()
    
    if not email_destino:
        print("   ❌ Email não fornecido!")
    else:
        try:
            resultado = send_email(
                subject='🧪 Teste de Email - AIcentral',
                recipients=email_destino,
                text_body='Este é um email de teste do sistema AIcentral v2.',
                html_body='<h1>✅ Email funcionando!</h1><p>Este é um email de teste.</p>'
            )
            
            if resultado:
                print(f"   ✅ Email enviado para {email_destino}!")
                print("   ℹ️ Verifique sua caixa de entrada (e spam)")
            else:
                print("   ❌ Falha ao enviar email!")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            import traceback
            traceback.print_exc()

print("\n" + "="*60 + "\n")