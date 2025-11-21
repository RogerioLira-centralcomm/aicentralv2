"""
AIcentralv2 - Sistema de Auditoria
Registra todas as ações administrativas para rastreabilidade
"""
import json
from datetime import datetime
from flask import request, current_app
from aicentralv2 import db


def registrar_acao_admin(user_id, acao, modulo, descricao=None, registro_id=None, 
                        registro_tipo=None, dados_anteriores=None, dados_novos=None):
    """
    Registra uma ação administrativa no log de auditoria
    
    Args:
        user_id (int): ID do usuário que realizou a ação
        acao (str): Tipo de ação (CREATE, UPDATE, DELETE, APPROVE, REJECT, etc)
        modulo (str): Módulo do sistema (usuarios, clientes, planos, configuracoes, etc)
        descricao (str, optional): Descrição da ação
        registro_id (int, optional): ID do registro afetado
        registro_tipo (str, optional): Tipo do registro (usuario, cliente, plano, etc)
        dados_anteriores (dict, optional): Dados antes da modificação
        dados_novos (dict, optional): Dados após a modificação
        
    Returns:
        int: ID do log criado
    """
    try:
        conn = db.get_db()
        
        # Obter informações da requisição
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get('User-Agent', '') if request else ''
        
        # Converter dicts para JSON
        dados_anteriores_json = json.dumps(dados_anteriores) if dados_anteriores else None
        dados_novos_json = json.dumps(dados_novos) if dados_novos else None
        
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO tbl_admin_audit_log (
                    fk_id_usuario, acao, modulo, descricao, 
                    registro_id, registro_tipo, 
                    ip_address, user_agent,
                    dados_anteriores, dados_novos
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                ) RETURNING id_log
            ''', (
                user_id, acao, modulo, descricao,
                registro_id, registro_tipo,
                ip_address, user_agent,
                dados_anteriores_json, dados_novos_json
            ))
            
            log_id = cursor.fetchone()['id_log']
            conn.commit()
            
            current_app.logger.info(
                f"Audit Log #{log_id}: {acao} em {modulo} por user_id={user_id}"
            )
            
            return log_id
            
    except Exception as e:
        current_app.logger.error(f"Erro ao registrar audit log: {str(e)}")
        conn.rollback()
        return None


def obter_logs_recentes(limite=50, modulo=None, user_id=None, acao=None):
    """
    Obtém logs de auditoria recentes
    
    Args:
        limite (int): Número máximo de logs a retornar
        modulo (str, optional): Filtrar por módulo
        user_id (int, optional): Filtrar por usuário
        acao (str, optional): Filtrar por ação
        
    Returns:
        list: Lista de logs de auditoria
    """
    conn = db.get_db()
    
    try:
        query = '''
            SELECT 
                l.id_log,
                l.fk_id_usuario,
                l.acao,
                l.modulo,
                l.descricao,
                l.registro_id,
                l.registro_tipo,
                l.ip_address,
                l.data_acao,
                u.nome_completo as usuario_nome,
                u.email as usuario_email
            FROM tbl_admin_audit_log l
            LEFT JOIN tbl_contato_cliente u ON l.fk_id_usuario = u.id_contato_cliente
            WHERE 1=1
        '''
        
        params = []
        
        if modulo:
            query += ' AND l.modulo = %s'
            params.append(modulo)
        
        if user_id:
            query += ' AND l.fk_id_usuario = %s'
            params.append(user_id)
        
        if acao:
            query += ' AND l.acao = %s'
            params.append(acao)
        
        query += ' ORDER BY l.data_acao DESC LIMIT %s'
        params.append(limite)
        
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
            
    except Exception as e:
        current_app.logger.error(f"Erro ao obter logs de auditoria: {str(e)}")
        return []


def obter_log_detalhado(log_id):
    """
    Obtém detalhes completos de um log específico, incluindo dados JSON
    
    Args:
        log_id (int): ID do log
        
    Returns:
        dict: Dados completos do log ou None
    """
    conn = db.get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    l.*,
                    u.nome_completo as usuario_nome,
                    u.email as usuario_email
                FROM tbl_admin_audit_log l
                LEFT JOIN tbl_contato_cliente u ON l.fk_id_usuario = u.id_contato_cliente
                WHERE l.id_log = %s
            ''', (log_id,))
            
            log = cursor.fetchone()
            
            # Parsear JSON fields se existirem
            if log and log.get('dados_anteriores'):
                log['dados_anteriores'] = json.loads(log['dados_anteriores']) if isinstance(log['dados_anteriores'], str) else log['dados_anteriores']
            
            if log and log.get('dados_novos'):
                log['dados_novos'] = json.loads(log['dados_novos']) if isinstance(log['dados_novos'], str) else log['dados_novos']
            
            return log
            
    except Exception as e:
        current_app.logger.error(f"Erro ao obter log detalhado: {str(e)}")
        return None


def estatisticas_auditoria(periodo_dias=30):
    """
    Obtém estatísticas de auditoria dos últimos N dias
    
    Args:
        periodo_dias (int): Número de dias para análise
        
    Returns:
        dict: Estatísticas agregadas
    """
    conn = db.get_db()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_acoes,
                    COUNT(DISTINCT fk_id_usuario) as usuarios_distintos,
                    COUNT(DISTINCT modulo) as modulos_distintos,
                    COUNT(DISTINCT DATE(data_acao)) as dias_com_atividade
                FROM tbl_admin_audit_log
                WHERE data_acao >= CURRENT_DATE - INTERVAL '%s days'
            ''', (periodo_dias,))
            
            stats = cursor.fetchone()
            
            # Top ações por módulo
            cursor.execute('''
                SELECT 
                    modulo,
                    COUNT(*) as total
                FROM tbl_admin_audit_log
                WHERE data_acao >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY modulo
                ORDER BY total DESC
                LIMIT 10
            ''', (periodo_dias,))
            
            stats['top_modulos'] = cursor.fetchall()
            
            # Top usuários mais ativos
            cursor.execute('''
                SELECT 
                    u.nome_completo,
                    u.email,
                    COUNT(*) as total_acoes
                FROM tbl_admin_audit_log l
                JOIN tbl_contato_cliente u ON l.fk_id_usuario = u.id_contato_cliente
                WHERE l.data_acao >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY u.id_contato_cliente, u.nome_completo, u.email
                ORDER BY total_acoes DESC
                LIMIT 10
            ''', (periodo_dias,))
            
            stats['top_usuarios'] = cursor.fetchall()
            
            return stats
            
    except Exception as e:
        current_app.logger.error(f"Erro ao obter estatísticas de auditoria: {str(e)}")
        return {}
