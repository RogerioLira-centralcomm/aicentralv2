"""
AIcentralv2 - Configurações da aplicação
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
    
    # Projeto
    PROJECT_NAME = 'AIcentralv2'
    VERSION = '2.0.0'
    
    # PostgreSQL
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'aicentralv2')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    @property
    def DATABASE_URI(self):
        """Retorna a URI completa do banco de dados"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


class DevelopmentConfig(Config):
    """Configuração de desenvolvimento"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Configuração de produção"""
    DEBUG = False
    TESTING = False


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