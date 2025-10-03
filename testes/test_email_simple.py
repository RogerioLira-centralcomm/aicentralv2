"""
Teste simples de email sem carregar todo o app
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

# Carregar .env
load_dotenv()


def test_smtp_connection():
    """Testa apenas a conexão SMTP"""
    print("=" * 70)
    print("📧 Teste de Conexão SMTP")
    print("=" * 70)

    # Configurações
    smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('MAIL_PORT', 587))
    username = os.getenv('MAIL_USERNAME')
    password = os.getenv('MAIL_PASSWORD')

    if not username or not password:
        print("\n❌ ERRO: Credenciais não encontradas no .env")
        print("\n💡 Adicione ao .env:")
        print("   MAIL_USERNAME=seu-email@gmail.com")
        print("   MAIL_PASSWORD=sua-senha-app-16-caracteres")
        return

    print(f"\n📋 Configurações:")
    print(f"   Servidor: {smtp_server}")
    print(f"   Porta: {smtp_port}")
    print(f"   Usuário: {username}")
    print(f"   Senha: {'*' * len(password)}")

    try:
        print("\n⏳ Conectando ao servidor SMTP...")

        # Conectar ao servidor
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(1)  # Mostrar debug

        print("✅ Conexão estabelecida!")

        # Iniciar TLS
        print("\n🔐 Iniciando TLS...")
        server.starttls()
        print("✅ TLS iniciado!")

        # Fazer login
        print("\n🔑 Fazendo login...")
        server.login(username, password)
        print("✅ Login bem-sucedido!")

        # Perguntar email de destino
        destinatario = input("\n📧 Digite o email de destino (Enter para usar o remetente): ").strip()
        if not destinatario:
            destinatario = username

        # Criar email
        print(f"\n📨 Enviando email de teste para: {destinatario}")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = '🧪 Teste de Email - AIcentralv2'
        msg['From'] = username
        msg['To'] = destinatario

        # Versão texto
        text = """
        Teste de Email - AIcentralv2

        Este é um email de teste simples.
        Se você está recebendo isto, o sistema está funcionando!

        ✅ Conexão SMTP: OK
        ✅ Autenticação: OK
        ✅ Envio: OK
        """

        # Versão HTML
        html = """
        <html>
          <body>
            <h2>🧪 Teste de Email - AIcentralv2</h2>
            <p>Este é um email de teste simples.</p>
            <p>Se você está recebendo isto, o sistema está funcionando!</p>
            <ul>
              <li>✅ Conexão SMTP: OK</li>
              <li>✅ Autenticação: OK</li>
              <li>✅ Envio: OK</li>
            </ul>
          </body>
        </html>
        """

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        msg.attach(part1)
        msg.attach(part2)

        # Enviar
        server.send_message(msg)
        print("\n✅ Email enviado com sucesso!")

        # Fechar conexão
        server.quit()

        print("\n" + "=" * 70)
        print("✅ Teste concluído com sucesso!")
        print(f"📬 Verifique a caixa de entrada de: {destinatario}")
        print("=" * 70)

    except smtplib.SMTPAuthenticationError:
        print("\n❌ Erro de autenticação!")
        print("\n💡 Possíveis causas:")
        print("   1. Senha de app incorreta")
        print("   2. Verificação em duas etapas não habilitada")
        print("   3. Senha de app não foi gerada")
        print("\n📖 Solução:")
        print("   1. Acesse: https://myaccount.google.com/apppasswords")
        print("   2. Crie uma senha de app")
        print("   3. Use essa senha (16 dígitos) no .env")

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print("\n💡 Verifique:")
        print("   1. Credenciais no .env")
        print("   2. Conexão com a internet")
        print("   3. Firewall não está bloqueando porta 587")


if __name__ == '__main__':
    test_smtp_connection()