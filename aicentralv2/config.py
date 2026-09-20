"""
AIcentralv2 - Configurações da aplicação

Todas as configurações centralizadas neste arquivo, incluindo
configurações de terceiros (ex.: Pinecone).
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Raiz do repositório (pai do pacote `aicentralv2/`), onde está o `.env`.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

# Carregar `.env` pelo caminho fixo para funcionar mesmo quando o cwd não é a raiz do projeto.
load_dotenv(_ENV_PATH)
load_dotenv()


class Config:
	"""Classe base de configuração"""
	# Flask
	SECRET_KEY = os.getenv('SECRET_KEY', 'chave-padrao-desenvolvimento')
	DEBUG = False
	TESTING = False
	
	# Upload de arquivos (reembolsos: importação em lote sem limite de quantidade)
	FINANCE_MAX_FILE_SIZE = int(os.getenv('FINANCE_MAX_FILE_SIZE_MB', '25')) * 1024 * 1024
	MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH_MB', '256')) * 1024 * 1024
	
	# URL base da aplicação (para acesso externo às imagens)
	BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
	CENTRALX_URL = os.getenv('CENTRALX_URL', BASE_URL)
	CADU_URL = os.getenv('CADU_URL', 'https://cadu.centralcomm.media')
	STUDIO_URL = os.getenv('STUDIO_URL', 'https://studio.centralcomm.media')
	SKILLS_URL = os.getenv('SKILLS_URL', 'https://skills.centralcomm.media')
	PLANNER_URL = os.getenv('PLANNER_URL', 'https://planner.centralcomm.media')
	CONNECT_URL = os.getenv('CONNECT_URL', 'https://reports.centralcomm.media')
	WORKSPACE_URL = os.getenv('WORKSPACE_URL', 'https://workspace.centralcomm.media')
	AUTH_URL = os.getenv('AUTH_URL', 'https://auth.centralcomm.media')
	# O PHP permanece dono destas telas; os caminhos podem ser ajustados sem
	# duplicar regras de usuários, assinatura, créditos ou cobrança no Flask.
	CADU_USERS_URL = os.getenv('CADU_USERS_URL', f"{CADU_URL.rstrip('/')}/usuarios")
	CADU_PLANS_URL = os.getenv('CADU_PLANS_URL', f"{CADU_URL.rstrip('/')}/planos")
	CADU_CREDITS_URL = os.getenv('CADU_CREDITS_URL', f"{CADU_URL.rstrip('/')}/creditos")
	CADU_FINANCE_URL = os.getenv('CADU_FINANCE_URL', f"{CADU_URL.rstrip('/')}/financeiro")
	CADU_INTEGRATIONS_URL = os.getenv('CADU_INTEGRATIONS_URL', f"{CADU_URL.rstrip('/')}/integracoes")
	CADU_HELP_URL = os.getenv('CADU_HELP_URL', f"{CADU_URL.rstrip('/')}/ajuda")
	# Endpoint PHP que troca um ticket único pelo PHPSESSID local. Mantém os
	# cookies separados, mas permite que o Auth seja a porta única de entrada.
	CADU_SSO_CONSUME_URL = os.getenv(
		'CADU_SSO_CONSUME_URL',
		f"{CADU_URL.rstrip('/')}/sso-consume.php",
	)
	# Fallback legado para instalações que ainda não migraram o Google SSO.
	CADU_GOOGLE_LOGIN_URL = os.getenv(
		'CADU_GOOGLE_LOGIN_URL',
		f"{CADU_URL.rstrip('/')}/google-login.php",
	)
	# Login Google centralizado: cliente interno e cliente externo separados.
	GOOGLE_CENTRALX_CLIENT_ID = os.getenv('GOOGLE_CENTRALX_CLIENT_ID', '')
	GOOGLE_CENTRALX_CLIENT_SECRET = os.getenv('GOOGLE_CENTRALX_CLIENT_SECRET', '')
	GOOGLE_CENTRALX_REDIRECT_URI = os.getenv('GOOGLE_CENTRALX_REDIRECT_URI', f"{AUTH_URL.rstrip('/')}/auth/google/callback")
	GOOGLE_CENTRALX_DOMAIN = os.getenv('GOOGLE_CENTRALX_DOMAIN', 'centralcomm.media')
	GOOGLE_CADU_CLIENT_ID = os.getenv('GOOGLE_CADU_CLIENT_ID', '')
	# O Auth Cadu é o único iniciador do SSO. As credenciais são lidas da
	# configuração criptografada `google_login_cadu` no banco; a variável só
	# permite desativar explicitamente esse caminho durante uma contingência.
	CADU_GOOGLE_NATIVE_ENABLED = os.getenv('CADU_GOOGLE_NATIVE_ENABLED', '1') == '1'
	GOOGLE_CADU_CLIENT_SECRET = os.getenv('GOOGLE_CADU_CLIENT_SECRET', '')
	GOOGLE_CADU_REDIRECT_URI = os.getenv('GOOGLE_CADU_REDIRECT_URI', f"{AUTH_URL.rstrip('/')}/auth/google/callback")
	# Aplicação OAuth exclusiva para dados Google Workspace dos clientes.
	GOOGLE_WORKSPACE_CLIENT_ID = os.getenv('GOOGLE_WORKSPACE_CLIENT_ID', '')
	GOOGLE_WORKSPACE_CLIENT_SECRET = os.getenv('GOOGLE_WORKSPACE_CLIENT_SECRET', '')
	GOOGLE_WORKSPACE_REDIRECT_URI = os.getenv(
		'GOOGLE_WORKSPACE_REDIRECT_URI',
		f"{AUTH_URL.rstrip('/')}/auth/google/workspace/callback",
	)
	GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv('GOOGLE_TOKEN_ENCRYPTION_KEY', '')
	GOOGLE_ADS_API_VERSION = os.getenv('GOOGLE_ADS_API_VERSION', 'v25')
	GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN', '')
	GOOGLE_ADS_LOGIN_CUSTOMER_ID = os.getenv('GOOGLE_ADS_LOGIN_CUSTOMER_ID', '')

	# Sessão persistente: o login permanece neste dispositivo sem checkbox.
	SESSION_LIFETIME_DAYS = int(os.getenv('SESSION_LIFETIME_DAYS', '180'))
	PERMANENT_SESSION_LIFETIME = timedelta(days=SESSION_LIFETIME_DAYS)
	SESSION_REFRESH_EACH_REQUEST = True
	SESSION_COOKIE_HTTPONLY = True
	SESSION_COOKIE_SAMESITE = 'Lax'
	# A família Cadu é um único SSO: Workspace, Connect, Studio, Skills e
	# Planner precisam reconhecer a mesma sessão ao trocar de subdomínio.
	# Um nome novo evita que cookies host-only da versão anterior concorram com
	# o cookie compartilhado durante a migração.
	SESSION_COOKIE_NAME = 'cadu_sso_session'
	CENTRALX_SESSION_COOKIE_NAME = 'centralx_session'
	CADU_SESSION_COOKIE_NAME = 'cadu_sso_session'
	# Em produção, o cookie Cadu é emitido para todos os subdomínios. Localhost
	# continua host-only, pois navegadores não aceitam Domain=localhost.
	CADU_SESSION_COOKIE_DOMAIN = os.getenv('CADU_SESSION_COOKIE_DOMAIN', None)
	SESSION_COOKIE_DOMAIN = None
	SESSION_COOKIE_SECURE = os.getenv(
		'SESSION_COOKIE_SECURE',
		'true' if BASE_URL.startswith('https') else 'false',
	).lower() in ('true', '1', 'yes')

	# Rollout da família Cadu. Todos os recursos mutáveis permanecem fechados
	# por padrão e só podem ser habilitados explicitamente no ambiente depois
	# das migrações e verificações de produção.
	CADU_FAMILY_ENABLED = os.getenv('CADU_FAMILY_ENABLED', '0').lower() in ('true', '1', 'yes', 'on')
	CADU_FAMILY_WRITES_ENABLED = os.getenv('CADU_FAMILY_WRITES_ENABLED', '0').lower() in ('true', '1', 'yes', 'on')
	# The provider/settings check remains the final gate. Chat is a released
	# Cadu surface and must not stay disabled merely because an environment
	# omitted this legacy rollout flag.
	CADU_FAMILY_CHAT_ENABLED = os.getenv('CADU_FAMILY_CHAT_ENABLED', '1').lower() in ('true', '1', 'yes', 'on')
	CADU_CHAT_WORKER_ENABLED = os.getenv('CADU_CHAT_WORKER_ENABLED', '0').lower() in ('true', '1', 'yes', 'on')
	# Minimum balance required before a Conversas request reaches Dify. The
	# final debit still follows measured provider usage.
	CADU_CHAT_ADMISSION_TOKENS = int(os.getenv('CADU_CHAT_ADMISSION_TOKENS', '8000'))
	# Conversations V2 is the published Workspace surface. Separate credentials
	# keep runtime modes isolated while the legacy renderer remains compatibility-only.
	CADU_CONVERSATIONS_V2_ENABLED = os.getenv('CADU_CONVERSATIONS_V2_ENABLED', '1').lower() in ('true', '1', 'yes', 'on')
	CADU_CONVERSATIONS_V2_UI_ENABLED = os.getenv(
		'CADU_CONVERSATIONS_V2_UI_ENABLED', os.getenv('CADU_CONVERSATIONS_V2_ENABLED', '1')
	).lower() in ('true', '1', 'yes', 'on')
	# Cache-busting compartilhado pelas páginas React do Workspace. O valor
	# pode ser avançado no ambiente sem editar cada template individualmente.
	CADU_WORKSPACE_ASSET_VERSION = os.getenv('CADU_WORKSPACE_ASSET_VERSION', '29')
	CADU_CONVERSATIONS_V2_DIFY_URL = os.getenv('CADU_CONVERSATIONS_V2_DIFY_URL', '')
	CADU_CONVERSATIONS_V2_DIFY_KEY = os.getenv('CADU_CONVERSATIONS_V2_DIFY_KEY', '')
	# Three isolated language runtimes. Empty mode-specific values fall back to
	# the V2 app during rollout, so deploying code does not force a cutover.
	CADU_DIFY_FAST_URL = os.getenv('CADU_DIFY_FAST_URL', '')
	CADU_DIFY_FAST_KEY = os.getenv('CADU_DIFY_FAST_KEY', '')
	CADU_DIFY_ANALYST_URL = os.getenv('CADU_DIFY_ANALYST_URL', '')
	CADU_DIFY_ANALYST_KEY = os.getenv('CADU_DIFY_ANALYST_KEY', '')
	CADU_DIFY_OPERATOR_URL = os.getenv('CADU_DIFY_OPERATOR_URL', '')
	CADU_DIFY_OPERATOR_KEY = os.getenv('CADU_DIFY_OPERATOR_KEY', '')
	# Brand discovery may run for several minutes. It is dispatched to a durable
	# worker after its database migration; routes retain a short-lived fallback
	# thread only when the migration is not installed yet.
	CADU_BRAND_AUDIT_WORKER_ENABLED = os.getenv('CADU_BRAND_AUDIT_WORKER_ENABLED', '0').lower() in ('true', '1', 'yes', 'on')
	CADU_PROJECT_INDEX_ASYNC_ENABLED = os.getenv('CADU_PROJECT_INDEX_ASYNC_ENABLED', '1').lower() in ('true', '1', 'yes', 'on')
	CADU_DIFY_API_KEY = os.getenv('CADU_DIFY_API_KEY', '')
	CADU_DIFY_BASE_URL = os.getenv('CADU_DIFY_BASE_URL', 'https://api.dify.ai/v1').rstrip('/')
	CADU_LEGACY_ASSET_BASE_URL = os.getenv('CADU_LEGACY_ASSET_BASE_URL', '')
	# Volume persistente para fontes privadas dos projetos do Workspace. Sem
	# configuração, preserva o diretório de instância usado pelos ambientes legados.
	WORKSPACE_SOURCE_STORAGE_DIR = os.getenv('WORKSPACE_SOURCE_STORAGE_DIR', '')
    
	# Projeto
	PROJECT_NAME = 'AIcentralv2'
	VERSION = '2.0.0'

	# Frontend/CSS
	# Quando True, usa CDN de Tailwind + daisyUI nos templates; quando False, usa apenas build local
	USE_CSS_CDN = False
    
	# PostgreSQL
	DB_HOST = os.getenv('DB_HOST', 'localhost')
	DB_PORT = os.getenv('DB_PORT', '5432')
	DB_NAME = os.getenv('DB_NAME', 'aicentralv2')
	DB_USER = os.getenv('DB_USER', 'postgres')
	DB_PASSWORD = os.getenv('DB_PASSWORD', '')
	STUDIO_PROJECTS_POSTGRES = os.getenv('STUDIO_PROJECTS_POSTGRES', 'true').lower() in ('true', '1', 'yes', 'on')
	
	# Email (Flask-Mail)
	MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
	MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
	MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
	MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
	MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
	MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
	MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '')
	MAIL_APP_NAME = os.getenv('MAIL_APP_NAME', 'AIcentral v2')
    
	# Brevo (Email API)
	BREVO_API_KEY = os.getenv('BREVO_API_KEY', '')
	BREVO_SENDER_NAME = os.getenv('BREVO_SENDER_NAME', 'Cadu')
	BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL', 'contato@centralcomm.media')
	# Product receipts are enabled automatically only when Brevo is configured;
	# an explicit environment value can still mute every transactional product e-mail.
	CADU_PRODUCT_EMAILS_ENABLED = os.getenv(
		'CADU_PRODUCT_EMAILS_ENABLED', '1' if BREVO_API_KEY else '0'
	).lower() in ('true', '1', 'yes', 'on')
	# Premissas transparentes usadas apenas na estimativa comparativa do recibo
	# de finalização do Studio. Não representam folha ou promessa de economia.
	STUDIO_DESIGNER_MONTHLY_SALARY_BRL = os.getenv('STUDIO_DESIGNER_MONTHLY_SALARY_BRL', '3500')
	STUDIO_DESIGNER_MONTHLY_HOURS = os.getenv('STUDIO_DESIGNER_MONTHLY_HOURS', '220')
	STUDIO_DESIGNER_CLT_FACTOR = os.getenv('STUDIO_DESIGNER_CLT_FACTOR', '1.7')
	CADU_CREDIT_SALE_PRICE_BRL_PER_CREDIT = os.getenv('CADU_CREDIT_SALE_PRICE_BRL_PER_CREDIT', '8')
	# Um único endereço operacional no Brevo; o nome e a identidade visual
	# mudam por produto. Workspace é dono dos e-mails de acesso e senha.
	BREVO_WORKSPACE_SENDER_NAME = os.getenv('BREVO_WORKSPACE_SENDER_NAME', 'Cadu Workspace')
	BREVO_WORKSPACE_SENDER_EMAIL = BREVO_SENDER_EMAIL
	BREVO_WORKSPACE_WEBHOOK_TOKEN = os.getenv('BREVO_WORKSPACE_WEBHOOK_TOKEN', '')
	BREVO_STUDIO_SENDER_NAME = os.getenv('BREVO_STUDIO_SENDER_NAME', 'Studio CentralComm')
	BREVO_STUDIO_SENDER_EMAIL = BREVO_SENDER_EMAIL
	BREVO_PLANNER_SENDER_NAME = os.getenv('BREVO_PLANNER_SENDER_NAME', 'Planner CentralComm')
	BREVO_PLANNER_SENDER_EMAIL = BREVO_SENDER_EMAIL
	BREVO_SKILLS_SENDER_NAME = os.getenv('BREVO_SKILLS_SENDER_NAME', 'Skills CentralComm')
	BREVO_SKILLS_SENDER_EMAIL = BREVO_SENDER_EMAIL
	BREVO_CONNECT_SENDER_NAME = os.getenv('BREVO_CONNECT_SENDER_NAME', 'Connect CentralComm')
	BREVO_CONNECT_SENDER_EMAIL = BREVO_SENDER_EMAIL
	# Comercial: endereço real que recebe as respostas aos contatos de onboarding.
	DEMETRIUS_EMAIL = os.getenv('DEMETRIUS_EMAIL', '')
	DEMETRIUS_NAME = os.getenv('DEMETRIUS_NAME', 'Demétrius Decottignies')
	FINANCEIRO_HANDOFF_EMAILS = os.getenv('FINANCEIRO_HANDOFF_EMAILS', '')
	PI_HANDOFF_GATE = os.getenv('PI_HANDOFF_GATE', 'true').lower() in ('true', '1', 'yes', 'on')
	CAMADAS_V2_ENABLED = os.getenv('CAMADAS_V2_ENABLED', 'false').lower() in ('true', '1', 'yes', 'on')
	CREATIVE_ANALYZER_WRITES_ENABLED = os.getenv('CREATIVE_ANALYZER_WRITES_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
	CAMADAS_V2_IMAGE_MODEL = os.getenv('CAMADAS_V2_IMAGE_MODEL', '')
	CAMADAS_V2_IMAGE_RESOLUTION = os.getenv('CAMADAS_V2_IMAGE_RESOLUTION', '1K')
	BREVO_HANDOFF_INTERNO = os.getenv('BREVO_HANDOFF_INTERNO', 'true').lower() in ('true', '1', 'yes', 'on')
	MAKE_HANDOFF_FALLBACK = os.getenv('MAKE_HANDOFF_FALLBACK', 'false').lower() in ('true', '1', 'yes', 'on')
	PI_HANDOFF_BLOQUEIA_RISCO = os.getenv('PI_HANDOFF_BLOQUEIA_RISCO', 'false').lower() in ('true', '1', 'yes', 'on')
	
	# Cache (Redis ou SimpleCache)
	CACHE_TYPE = os.getenv('CACHE_TYPE', 'SimpleCache')  # 'RedisCache' para Redis
	CACHE_REDIS_URL = os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0')
	CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', '900'))  # 15 minutos
	
	# Paginação de listagens
	CLIENTES_PER_PAGE = int(os.getenv('CLIENTES_PER_PAGE', '25'))

	# Display & Video 360 + Bid Manager (relatórios); não versionar segredos. Refresh token tem de incluir os scopes em dv360_client.DV360_SCOPES.
	DV360_CLIENT_ID = os.getenv('DV360_CLIENT_ID', '')
	DV360_CLIENT_SECRET = os.getenv('DV360_CLIENT_SECRET', '')
	DV360_REFRESH_TOKEN = os.getenv('DV360_REFRESH_TOKEN', '')
	DV360_PARTNER_ID = os.getenv('DV360_PARTNER_ID', '')
	DV360_API_BASE_URL = os.getenv(
		'DV360_API_BASE_URL',
		'https://displayvideo.googleapis.com/v4',
	).rstrip('/')
	DV360_TIMEOUT = int(os.getenv('DV360_TIMEOUT', '30'))

	# Google Workspace por usuário (Calendar + Meet). O redirect precisa estar
	# cadastrado no Google Cloud Console. A chave Fernet protege refresh tokens.
	GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
	GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
	GOOGLE_OAUTH_REDIRECT_URI = os.getenv(
		'GOOGLE_OAUTH_REDIRECT_URI',
		f"{BASE_URL.rstrip('/')}/perfil/google/callback",
	)
	GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv('GOOGLE_TOKEN_ENCRYPTION_KEY', '')
	GOOGLE_CALENDAR_TIMEOUT = int(os.getenv('GOOGLE_CALENDAR_TIMEOUT', '20'))
	INTEGRATION_CREDENTIALS_KEY = os.getenv('INTEGRATION_CREDENTIALS_KEY', '')
	HIGGSFIELD_API_KEY = os.getenv('HIGGSFIELD_API_KEY', '')
	HIGGSFIELD_WORKSPACE_ID = os.getenv('HIGGSFIELD_WORKSPACE_ID', '')
	HIGGSFIELD_DEFAULT_MODEL = os.getenv('HIGGSFIELD_DEFAULT_MODEL', '')

	# Campanha PI: ID da plataforma DV360 em cadu_pi_camp_plataforma (opcional). Vazio → deteção por descrição na BD.
	_PI_PLT_DV360_RAW = os.getenv('PI_PLATAFORMA_DV360_ID', '').strip()
	PI_PLATAFORMA_DV360_ID = int(_PI_PLT_DV360_RAW) if _PI_PLT_DV360_RAW.isdigit() else None

	# Imposto (%) usado no cálculo de preço unitário — cotações teste cálculo; ex.: 17 ou 17.5
	_PI_IMP_RAW = os.getenv('PI_IMPOSTO_PERCENTUAL', os.getenv('IMPOSTO_PERCENTUAL', '17')).strip()
	try:
		PI_IMPOSTO_PERCENTUAL = float(_PI_IMP_RAW.replace(',', '.'))
	except ValueError:
		PI_IMPOSTO_PERCENTUAL = 17.0

	# Desvio aceitável (%) default das zonas de andamento do PI; .env DESVIO_ACEITAVEL.
	_PI_DESVIO_RAW = os.getenv('DESVIO_ACEITAVEL', '5').strip()
	try:
		PI_DESVIO_ACEITAVEL_PERCENTUAL = float(_PI_DESVIO_RAW.replace(',', '.'))
	except ValueError:
		PI_DESVIO_ACEITAVEL_PERCENTUAL = 5.0
	_CAMP_DIARIO_LIMITE_RAW = os.getenv('CAMPANHA_DIARIO_LIMITE_DIAS', '3').strip()
	try:
		CAMPANHA_DIARIO_LIMITE_DIAS = max(1, int(_CAMP_DIARIO_LIMITE_RAW))
	except ValueError:
		CAMPANHA_DIARIO_LIMITE_DIAS = 3

	# Spedy — emissão NFS-e (sandbox: https://sandbox-api.spedy.com.br/v1)
	SPEDY_API_KEY = os.getenv('SPEDY_API_KEY', '')
	SPEDY_API_BASE_URL = os.getenv('SPEDY_API', 'https://sandbox-api.spedy.com.br/v1').rstrip('/')
	SPEDY_PRODUCT_ID = os.getenv(
		'SPEDY_PRODUCT_ID',
		'1dcacc78-34d8-43f9-806f-a2500b483275',
	)
	SPEDY_PRODUCT_CODE = os.getenv('SPEDY_PRODUCT_CODE', 'MIDIA-PI')
	SPEDY_PRODUCT_NAME = os.getenv(
		'SPEDY_PRODUCT_NAME',
		'Servicos de midia e publicidade digital',
	)
	SPEDY_SEND_EMAIL_TO_CUSTOMER = os.getenv('SPEDY_SEND_EMAIL_TO_CUSTOMER', 'False').lower() in (
		'true', '1', 'yes',
	)

	# WasenderAPI (WhatsApp standalone — página Comercial)
	WASENDER_API_KEY = os.getenv('WASENDER_API_KEY', '')
	WASENDER_SESSION_ID = os.getenv('WASENDER_SESSION_ID', '')
	WASENDER_WEBHOOK_SECRET = os.getenv('WASENDER_WEBHOOK_SECRET', '')
	WASENDER_API_BASE_URL = os.getenv(
		'WASENDER_API_BASE_URL',
		'https://www.wasenderapi.com/api',
	).rstrip('/')

	# Multiplicador do desvio aceitável que define a fronteira da Ruptura (Zona 5).
	# Ruptura = orçado × (1 + N × desvio). N=10 → desvio 5% gera ruptura a +50%.
	_PI_RUPT_MULT_RAW = os.getenv('PI_RUPTURA_MULT_DESVIO', '10').strip()
	try:
		PI_RUPTURA_MULT_DESVIO = float(_PI_RUPT_MULT_RAW.replace(',', '.'))
	except ValueError:
		PI_RUPTURA_MULT_DESVIO = 10.0

	@property
	def DATABASE_URI(self):
		"""Retorna a URI completa do banco de dados"""
		return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


class DevelopmentConfig(Config):
	"""Configuração de desenvolvimento"""
	DEBUG = True
	TESTING = False
	USE_CSS_CDN = False


class ProductionConfig(Config):
	"""Configuração de produção"""
	DEBUG = False
	TESTING = False
	USE_CSS_CDN = False
	SESSION_COOKIE_SECURE = True
	CADU_SESSION_COOKIE_DOMAIN = os.getenv('CADU_SESSION_COOKIE_DOMAIN', '.centralcomm.media')


class TestingConfig(Config):
	"""Configuração de testes"""
	DEBUG = True
	TESTING = True
	DB_NAME = os.getenv('DB_NAME_TEST', 'aicentralv2_test')
	SESSION_COOKIE_SECURE = False


# Dicionário de configurações
config = {
	'development': DevelopmentConfig,
	'production': ProductionConfig,
	'testing': TestingConfig,
	'default': DevelopmentConfig
}


# ----------------------
# Pinecone configuration
# ----------------------
PINECONE_CONFIG = {
	'api_key': os.getenv('PINECONE_API_KEY'),
	'environment': os.getenv('PINECONE_ENVIRONMENT', 'aped-4627-b74a'),  # Extraído do host
	'index_name': os.getenv('PINECONE_INDEX_NAME', 'cadu-v2'),
	'host': os.getenv('PINECONE_HOST'),
	'dimension': int(os.getenv('PINECONE_DIMENSION', '512')),
	'metric': os.getenv('PINECONE_METRIC', 'cosine'),
	'region': os.getenv('PINECONE_REGION', 'us-east-1'),
}

# ----------------------
# Alertas e Limites
# ----------------------
# Percentual de consumo de tokens para gerar alerta (ex: 80 = 80%)
ALERTA_CONSUMO_TOKEN = int(os.getenv('ALERTA_CONSUMO_TOKEN', '80'))

# Dias de antecedência para alertar sobre vencimento de planos
AVISO_PLAN = int(os.getenv('AVISO_PLAN', '20'))
