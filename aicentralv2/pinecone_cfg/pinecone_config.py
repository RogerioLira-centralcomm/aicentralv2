"""
Configurações do Pinecone para o CADU (copiadas de aicentralv2/config/pinecone_config.py)
"""

PINECONE_CONFIG = {
    'api_key': 'pcsk_4pgNhm_8GkhGWp44uAqjfqFJP9gb3nQSTwYEot9Fq5VZi2MnbXm7BUwqQXJE1AuuDtgUCd',
    'environment': 'aped-4627-b74a',  # Extraído do host
    'index_name': 'cadu-v2',
    'host': 'https://cadu-v2-phka0d2.svc.aped-4627-b74a.pinecone.io',
    'dimension': 512,
    'metric': 'cosine',
    'region': 'us-east-1'
}
