"""
AIcentralv2 - Configurações da aplicação

Todas as configurações centralizadas neste arquivo, incluindo
configurações de terceiros (ex.: Pinecone).
"""
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()


class Config:
	"""Classe base de configuração"""
	# Flask
	SECRET_KEY = os.getenv('SECRET_KEY', 'chave-padrao-desenvolvimento')
	DEBUG = False
	TESTING = False
	
	# Upload de arquivos
	MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB máximo
	
	# URL base da aplicação (para acesso externo às imagens)
	BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
    
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
	
	# Cache (Redis ou SimpleCache)
	CACHE_TYPE = os.getenv('CACHE_TYPE', 'SimpleCache')  # 'RedisCache' para Redis
	CACHE_REDIS_URL = os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0')
	CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', '900'))  # 15 minutos
	
	# Paginação de listagens
	CLIENTES_PER_PAGE = int(os.getenv('CLIENTES_PER_PAGE', '25'))
    
	@property
	def DATABASE_URI(self):
		"""Retorna a URI completa do banco de dados"""
		return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


class DevelopmentConfig(Config):
	"""Configuração de desenvolvimento"""
	DEBUG = True
	TESTING = False
	USE_CSS_CDN = True


class ProductionConfig(Config):
	"""Configuração de produção"""
	DEBUG = False
	TESTING = False
	USE_CSS_CDN = False


class TestingConfig(Config):
	"""Configuração de testes"""
	DEBUG = True
	TESTING = True
	DB_NAME = os.getenv('DB_NAME_TEST', 'aicentralv2_test')


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
