"""
AIcentralv2 - Rotas Administrativas
Painel de administração para gestão de clientes, usuários, planos e faturamento
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from aicentralv2.auth import admin_required, superadmin_required
from aicentralv2 import db, audit
import logging

# Criar blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

logger = logging.getLogger(__name__)

# Helper para registro de auditoria
def registrar_auditoria(acao, modulo, descricao, registro_id=None, registro_tipo=None, dados_anteriores=None, dados_novos=None):
    """Helper para registrar auditoria automaticamente"""
    try:
        user_id = session.get('user_id')
        if user_id:
            ip = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')[:255]
            db.registrar_audit_log(
                fk_id_usuario=user_id,
                acao=acao,
                modulo=modulo,
                descricao=descricao,
                registro_id=registro_id,
                registro_tipo=registro_tipo,
                ip_address=ip,
                user_agent=user_agent,
                dados_anteriores=dados_anteriores,
                dados_novos=dados_novos
            )
    except Exception as e:
        logger.error(f"Erro ao registrar auditoria: {e}")


# ==================== DASHBOARD ====================

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    """Dashboard administrativo com métricas globais"""
    try:
        # Estatísticas principais
        stats = db.obter_dashboard_stats()
        
        # Logs recentes
        logs_recentes = audit.obter_logs_recentes(limite=10)
        
        # Planos próximos do limite
        planos_alerta = db.obter_planos_clientes({
            'plan_status': 'active'
        })
        
        # Filtrar apenas os que estão acima de 80%
        planos_alerta = [p for p in planos_alerta 
                        if p.get('tokens_usage_percentage', 0) > 80 
                        or p.get('images_usage_percentage', 0) > 80]
        
        return render_template('admin/dashboard.html',
                             stats=stats,
                             logs_recentes=logs_recentes,
                             planos_alerta=planos_alerta)
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard admin: {str(e)}")
        flash('Erro ao carregar dashboard.', 'error')
        return redirect(url_for('index'))


# ==================== GESTÃO DE USUÁRIOS ====================

@admin_bp.route('/usuarios')
@admin_required
def usuarios_lista():
    """Lista todos os usuários do sistema"""
    try:
        # Filtros
        filtros = {}
        
        if request.args.get('user_type'):
            filtros['user_type'] = request.args.get('user_type')
        
        if request.args.get('status'):
            filtros['status'] = request.args.get('status') == 'true'
        
        if request.args.get('cliente_id'):
            filtros['cliente_id'] = int(request.args.get('cliente_id'))
        
        if request.args.get('search'):
            filtros['search'] = request.args.get('search')
        
        usuarios = db.obter_usuarios_sistema(filtros)
        clientes = db.obter_clientes_sistema({'status': True})
        
        return render_template('admin/usuarios/lista.html',
                             usuarios=usuarios,
                             clientes=clientes,
                             filtros=filtros)
    except Exception as e:
        logger.error(f"Erro ao listar usuários: {str(e)}")
        flash('Erro ao carregar lista de usuários.', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/usuarios/<int:user_id>')
@admin_required
def usuario_detalhes(user_id):
    """Detalhes de um usuário específico"""
    try:
        usuario = db.obter_usuario_por_id(user_id)
        
        if not usuario:
            flash('Usuário não encontrado.', 'error')
            return redirect(url_for('admin.usuarios_lista'))
        
        # Logs do usuário
        logs = audit.obter_logs_recentes(limite=20, user_id=user_id)
        
        return render_template('admin/usuarios/detalhes.html',
                             usuario=usuario,
                             logs=logs)
    except Exception as e:
        logger.error(f"Erro ao carregar usuário {user_id}: {str(e)}")
        flash('Erro ao carregar dados do usuário.', 'error')
        return redirect(url_for('admin.usuarios_lista'))


@admin_bp.route('/usuarios/<int:user_id>/alterar-tipo', methods=['POST'])
@admin_required
def usuario_alterar_tipo(user_id):
    """Altera o tipo de usuário"""
    try:
        novo_tipo = request.form.get('user_type')
        
        if novo_tipo not in ['client', 'admin', 'superadmin', 'readonly']:
            flash('Tipo de usuário inválido.', 'error')
            return redirect(url_for('admin.usuario_detalhes', user_id=user_id))
        
        # Obter dados anteriores para auditoria
        usuario_anterior = db.obter_usuario_por_id(user_id)
        
        # Atualizar
        if db.atualizar_user_type(user_id, novo_tipo):
            # Registrar auditoria
            registrar_auditoria(
                acao='editar',
                modulo='usuarios',
                descricao=f"Alterou tipo de usuário de {usuario_anterior['user_type']} para {novo_tipo}",
                registro_id=user_id,
                registro_tipo='usuario',
                dados_anteriores={'user_type': usuario_anterior['user_type']},
                dados_novos={'user_type': novo_tipo}
            )
            
            flash(f'Tipo de usuário alterado para {novo_tipo} com sucesso!', 'success')
        else:
            flash('Erro ao alterar tipo de usuário.', 'error')
        
        return redirect(url_for('admin.usuario_detalhes', user_id=user_id))
    except Exception as e:
        logger.error(f"Erro ao alterar tipo do usuário {user_id}: {str(e)}")
        flash('Erro ao alterar tipo de usuário.', 'error')
        return redirect(url_for('admin.usuario_detalhes', user_id=user_id))


# ==================== GESTÃO DE CLIENTES ====================

@admin_bp.route('/clientes')
@admin_required
def clientes_lista():
    """Lista todos os clientes do sistema"""
    try:
        # Filtros
        filtros = {}
        
        if request.args.get('status'):
            filtros['status'] = request.args.get('status') == 'true'
        
        if request.args.get('tipo_cliente'):
            filtros['tipo_cliente'] = int(request.args.get('tipo_cliente'))
        
        if request.args.get('search'):
            filtros['search'] = request.args.get('search')
        
        clientes = db.obter_clientes_sistema(filtros)
        tipos_cliente = db.obter_tipos_cliente()
        
        return render_template('admin/clientes/lista.html',
                             clientes=clientes,
                             tipos_cliente=tipos_cliente,
                             filtros=filtros)
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {str(e)}")
        flash('Erro ao carregar lista de clientes.', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/clientes/<int:cliente_id>')
@admin_required
def cliente_detalhes(cliente_id):
    """Detalhes de um cliente específico"""
    try:
        cliente = db.obter_cliente_por_id(cliente_id)
        
        if not cliente:
            flash('Cliente não encontrado.', 'error')
            return redirect(url_for('admin.clientes_lista'))
        
        # Usuários do cliente
        usuarios = db.obter_usuarios_sistema({'cliente_id': cliente_id})
        
        # Plano do cliente
        planos = db.obter_planos_clientes({'cliente_id': cliente_id})
        plano_ativo = next((p for p in planos if p['plan_status'] == 'active'), None)
        
        # Faturas
        faturas = db.obter_invoices({'cliente_id': cliente_id})
        
        return render_template('admin/clientes/detalhes.html',
                             cliente=cliente,
                             usuarios=usuarios,
                             plano_ativo=plano_ativo,
                             faturas=faturas)
    except Exception as e:
        logger.error(f"Erro ao carregar cliente {cliente_id}: {str(e)}")
        flash('Erro ao carregar dados do cliente.', 'error')
        return redirect(url_for('admin.clientes_lista'))


# ==================== GESTÃO DE PLANOS ====================

@admin_bp.route('/planos')
@admin_required
def planos_lista():
    """Lista todos os planos de clientes"""
    try:
        # Filtros
        filtros = {}
        
        if request.args.get('plan_status'):
            filtros['plan_status'] = request.args.get('plan_status')
        
        if request.args.get('plan_type'):
            filtros['plan_type'] = request.args.get('plan_type')
        
        planos = db.obter_planos_clientes(filtros)
        
        return render_template('admin/planos/lista.html',
                             planos=planos,
                             filtros=filtros)
    except Exception as e:
        logger.error(f"Erro ao listar planos: {str(e)}")
        flash('Erro ao carregar lista de planos.', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/planos/novo', methods=['GET', 'POST'])
@admin_required
def plano_novo():
    """Criar novo plano para cliente"""
    if request.method == 'POST':
        try:
            dados = {
                'id_cliente': int(request.form.get('id_cliente')),
                'plan_type': request.form.get('plan_type'),
                'plan_name': request.form.get('plan_name'),
                'tokens_monthly_limit': int(request.form.get('tokens_monthly_limit', 100000)),
                'image_credits_monthly': int(request.form.get('image_credits_monthly', 50)),
                'max_users': int(request.form.get('max_users', 5)),
                'valid_from': request.form.get('valid_from'),
                'valid_until': request.form.get('valid_until') or None,
                'features': request.form.get('features', '{}'),
                'created_by': session['user_id']
            }
            
            plan_id = db.criar_client_plan(dados)
            
            # Auditoria
            registrar_auditoria(
                acao='criar',
                modulo='planos',
                descricao=f"Criou plano {dados['plan_type']} para cliente ID {dados['id_cliente']}",
                registro_id=plan_id,
                registro_tipo='plano',
                dados_novos=dados
            )
            
            flash('Plano criado com sucesso!', 'success')
            return redirect(url_for('admin.planos_lista'))
            
        except Exception as e:
            logger.error(f"Erro ao criar plano: {str(e)}")
            flash(f'Erro ao criar plano: {str(e)}', 'error')
    
    # GET - carregar formulário
    clientes = db.obter_clientes_sistema({'status': True})
    return render_template('admin/planos/form.html',
                         clientes=clientes,
                         plano=None)


@admin_bp.route('/planos/<int:plan_id>/editar', methods=['GET', 'POST'])
@admin_required
def plano_editar(plan_id):
    """Editar plano existente"""
    if request.method == 'POST':
        try:
            # Obter dados anteriores
            plano_anterior = db.obter_plano_por_id(plan_id)
            
            dados = {
                'plan_type': request.form.get('plan_type'),
                'plan_name': request.form.get('plan_name'),
                'tokens_monthly_limit': int(request.form.get('tokens_monthly_limit')),
                'image_credits_monthly': int(request.form.get('image_credits_monthly')),
                'max_users': int(request.form.get('max_users')),
                'plan_status': request.form.get('plan_status'),
                'valid_from': request.form.get('valid_from'),
                'valid_until': request.form.get('valid_until') or None,
                'features': request.form.get('features', '{}')
            }
            
            if db.atualizar_client_plan(plan_id, dados):
                # Auditoria
                registrar_auditoria(
                    acao='editar',
                    modulo='planos',
                    descricao=f"Atualizou plano ID {plan_id}",
                    registro_id=plan_id,
                    registro_tipo='plano',
                    dados_anteriores=dict(plano_anterior),
                    dados_novos=dados
                )
                
                flash('Plano atualizado com sucesso!', 'success')
                return redirect(url_for('admin.planos_lista'))
            else:
                flash('Erro ao atualizar plano.', 'error')
                
        except Exception as e:
            logger.error(f"Erro ao atualizar plano {plan_id}: {str(e)}")
            flash(f'Erro ao atualizar plano: {str(e)}', 'error')
    
    # GET - carregar formulário
    plano = db.obter_plano_por_id(plan_id)
    
    if not plano:
        flash('Plano não encontrado.', 'error')
        return redirect(url_for('admin.planos_lista'))
    
    return render_template('admin/planos/form.html',
                         plano=plano,
                         clientes=None)


# ==================== CONFIGURAÇÕES DO SISTEMA ====================

@admin_bp.route('/sistema/configuracoes', methods=['GET', 'POST'])
@superadmin_required
def sistema_configuracoes():
    """Configurações globais do sistema"""
    if request.method == 'POST':
        try:
            # Atualizar cada configuração
            for key in request.form.keys():
                if key.startswith('setting_'):
                    setting_key = key.replace('setting_', '')
                    value = request.form.get(key)
                    
                    db.atualizar_system_setting(
                        setting_key, 
                        value, 
                        updated_by=session['user_id']
                    )
            
            # Auditoria
            audit.registrar_acao_admin(
                user_id=session['user_id'],
                acao='UPDATE',
                modulo='configuracoes',
                descricao='Atualizou configurações do sistema'
            )
            
            flash('Configurações atualizadas com sucesso!', 'success')
            
        except Exception as e:
            logger.error(f"Erro ao atualizar configurações: {str(e)}")
            flash(f'Erro ao atualizar configurações: {str(e)}', 'error')
    
    # GET - carregar configurações
    settings = db.obter_system_settings()
    
    return render_template('admin/sistema/configuracoes.html',
                         settings=settings)


@admin_bp.route('/logs')
@admin_required
def admin_logs():
    """Visualizar logs de auditoria administrativa"""
    try:
        from datetime import datetime, timedelta
        
        # Filtros
        filtros = {}
        dias = int(request.args.get('dias', 30))
        
        if request.args.get('modulo'):
            filtros['modulo'] = request.args.get('modulo')
        
        if request.args.get('acao'):
            filtros['acao'] = request.args.get('acao')
        
        if request.args.get('usuario_id'):
            filtros['usuario_id'] = int(request.args.get('usuario_id'))
        
        # Calcular data de início baseado em dias
        data_inicio = datetime.now() - timedelta(days=dias)
        filtros['data_inicio'] = data_inicio
        
        # Paginação
        limit = 50
        offset = int(request.args.get('offset', 0))
        
        # Buscar logs
        logs = db.obter_audit_logs(filtros=filtros, limit=limit, offset=offset)
        
        # Contar total (para paginação)
        total_logs = len(db.obter_audit_logs(filtros=filtros, limit=10000, offset=0))
        
        # Estatísticas
        stats = db.obter_estatisticas_audit_log(dias=dias)
        
        # Lista de usuários para filtro - APENAS CENTRALCOMM
        usuarios_filtro = db.obter_usuarios_sistema({'status': True})
        # Filtrar apenas usuários da CENTRALCOMM
        usuarios_filtro = [u for u in usuarios_filtro if u.get('nome_fantasia') and 
                          ('centralcomm' in u['nome_fantasia'].lower() or 
                           'central comm' in u['nome_fantasia'].lower())]
        
        return render_template('admin_audit_logs.html',
                             logs=logs,
                             stats=stats,
                             filtros={'modulo': request.args.get('modulo', ''),
                                     'acao': request.args.get('acao', ''),
                                     'usuario_id': request.args.get('usuario_id', ''),
                                     'dias': str(dias)},
                             usuarios_filtro=usuarios_filtro,
                             limit=limit,
                             offset=offset,
                             total_logs=total_logs)
    except Exception as e:
        import traceback
        logger.error(f"Erro ao carregar logs: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Erro ao carregar logs: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))


# ==================== FATURAMENTO ====================

@admin_bp.route('/faturamento')
@admin_required
def faturamento_lista():
    """Lista todas as faturas"""
    try:
        # Filtros
        filtros = {}
        
        if request.args.get('invoice_status'):
            filtros['invoice_status'] = request.args.get('invoice_status')
        
        if request.args.get('cliente_id'):
            filtros['cliente_id'] = int(request.args.get('cliente_id'))
        
        faturas = db.obter_invoices(filtros)
        clientes = db.obter_clientes_sistema({'status': True})
        
        return render_template('admin/faturamento/lista.html',
                             faturas=faturas,
                             clientes=clientes,
                             filtros=filtros)
    except Exception as e:
        logger.error(f"Erro ao listar faturas: {str(e)}")
        flash('Erro ao carregar faturas.', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/faturamento/<int:invoice_id>/marcar-paga', methods=['POST'])
@admin_required
def faturamento_marcar_paga(invoice_id):
    """Marca uma fatura como paga"""
    try:
        from datetime import date
        
        if db.atualizar_invoice_status(invoice_id, 'paid', paid_date=date.today()):
            # Auditoria
            registrar_auditoria(
                acao='editar',
                modulo='faturamento',
                descricao=f"Marcou fatura #{invoice_id} como paga",
                registro_id=invoice_id,
                registro_tipo='invoice',
                dados_novos={'invoice_status': 'paid', 'paid_date': str(date.today())}
            )
            
            flash('Fatura marcada como paga!', 'success')
        else:
            flash('Erro ao atualizar fatura.', 'error')
        
        return redirect(url_for('admin.faturamento_lista'))
        
    except Exception as e:
        logger.error(f"Erro ao marcar fatura {invoice_id} como paga: {str(e)}")
        flash('Erro ao atualizar fatura.', 'error')
        return redirect(url_for('admin.faturamento_lista'))


# ==================== API ENDPOINTS ====================

@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """API para estatísticas do dashboard"""
    try:
        stats = db.obter_dashboard_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Erro API stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
