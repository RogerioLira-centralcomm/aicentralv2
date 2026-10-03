"""Configuração do Gunicorn para Produção"""
import multiprocessing

# Bind
bind = "127.0.0.1:8001"

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Timeout
# O Studio gera a imagem, o revisor automático avalia e, se rejeitar, gera outra versão.
timeout = 300
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "/var/www/aicentralv2/logs/access.log"
errorlog = "/var/www/aicentralv2/logs/error.log"
loglevel = "info"

# Process
proc_name = "aicentralv2"

# Daemon mode - IMPORTANTE: False para systemd
daemon = False
