"""
Testa o envio de email
"""
from aicentralv2 import create_app
from flask_mail import Mail, Message

app = create_app()

with app.app_context():
    mail = Mail(app)

    msg = Message(
        subject='Teste de Email - AIcentralv2',
        recipients=['seu-email@gmail.com'],  # ALTERE AQUI
        body='Este é um email de teste do sistema AIcentralv2.'
    )

    try:
        mail.send(msg)
        print("✅ Email enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")