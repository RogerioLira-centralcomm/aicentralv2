"""
Configurações do Pinecone para o CADU (copiadas de aicentralv2/config/pinecone_config.py)
"""
import os
from dotenv import load_dotenv

load_dotenv()

PINECONE_CONFIG = {
    'api_key': os.getenv('PINECONE_API_KEY', ''),
    'environment': 'aped-4627-b74a',  # Extraído do host
    'index_name': 'cadu-v2',
    'host': os.getenv('PINECONE_HOST', 'https://cadu-v2-phka0d2.svc.aped-4627-b74a.pinecone.io'),
    'dimension': 512,
    'metric': 'cosine',
    'region': 'us-east-1'
}
