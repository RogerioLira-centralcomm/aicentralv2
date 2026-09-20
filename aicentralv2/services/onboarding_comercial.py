"""Qualificação de primeiro acesso e contato comercial posterior."""
import logging

from flask import current_app, render_template

from aicentralv2.services.brevo_service import get_brevo_service

logger = logging.getLogger(__name__)


def _internal_recipients(executivo=None):
    """Keep the commercial owner and the internal Cadu owner in the loop."""
    configured = str(current_app.config.get('ONBOARDING_INTERNAL_EMAILS') or '').split(',')
    recipients = [email.strip().lower() for email in configured if '@' in email.strip()]
    executive_email = str((executivo or {}).get('email') or '').strip().lower()
    if executive_email and executive_email not in recipients:
        recipients.insert(0, executive_email)
    return list(dict.fromkeys(recipients))


def obter_executivo_comercial():
    """Resolve Demetrius Decottignies, with the legacy name fallback."""
    from aicentralv2 import db

    return db.obter_executivo_demetrius()


def provisionar_conta_publica(*, nome, email, senha=None):
    """Create one CRM client/contact pair for a new public Cadu account."""
    from aicentralv2 import db

    email = str(email or '').strip().lower()
    nome = ' '.join(str(nome or '').split())[:180]
    if db.obter_contato_por_email(email):
        raise ValueError('Este e-mail já possui uma conta. Entre ou recupere sua senha.')
    executivo = obter_executivo_comercial()
    if not executivo or not executivo.get('id_contato_cliente'):
        raise ValueError('Não foi possível associar o executivo comercial agora.')
    tipos = db.obter_tipos_cliente() or []
    tipo = next(
        (item for item in tipos if 'prospec' in str(item.get('display') or '').lower()),
        tipos[0] if tipos else None,
    )
    if not tipo or not tipo.get('id_tipo_cliente'):
        raise ValueError('Não foi possível preparar o tipo de conta agora.')
    client_id = db.criar_cliente(
        razao_social=nome,
        nome_fantasia=nome,
        id_tipo_cliente=tipo['id_tipo_cliente'],
        pessoa='J',
        vendas_central_comm=executivo['id_contato_cliente'],
        classificacao_cliente='Prospecção',
    )
    try:
        contact_id = db.criar_contato(
            nome_completo=nome,
            email=email,
            senha=senha,
            pk_id_tbl_cliente=client_id,
            user_type='client',
        )
    except Exception:
        logger.exception('Cliente %s criado sem contato para o cadastro público %s', client_id, email)
        raise
    user = db.obter_contato_por_id(contact_id) or {
        'id_contato_cliente': contact_id,
        'nome_completo': nome,
        'email': email,
        'pk_id_tbl_cliente': client_id,
        'user_type': 'client',
    }
    user['pk_id_tbl_cliente'] = client_id
    return user, executivo


def enviar_notificacao_cadastro(*, usuario, executivo, auth_method='form'):
    """Notify the commercial owner and Apolo immediately after account creation."""
    recipients = _internal_recipients(executivo)
    if not recipients:
        logger.warning('Cadastro criado sem destinatários internos configurados.')
        return {'success': False, 'error': 'Destinatários internos não configurados'}
    html = render_template(
        'emails/internos/novo-cadastro-cadu.html',
        usuario=usuario,
        auth_method='Google' if auth_method == 'google' else 'formulário',
    )
    return get_brevo_service().enviar_email(
        to_email=recipients,
        to_name='Equipe comercial Cadu',
        subject=f'Novo cadastro no Cadu · {usuario.get("nome_completo") or usuario.get("email")}',
        html_content=html,
    )


def enviar_notificacao_demetrius(*, usuario, onboarding, executivo):
    recipients = _internal_recipients(executivo)
    if not recipients:
        logger.warning('Onboarding concluído sem e-mail configurado para Demétrius.')
        return {'success': False, 'error': 'Destinatários internos não configurados'}
    perfil = 'Agência' if onboarding['perfil'] == 'agencia' else 'Cliente final'
    html = render_template('emails/internos/onboarding-concluido.html', usuario=usuario,
                           onboarding=onboarding, perfil=perfil)
    return get_brevo_service().enviar_email(
        to_email=recipients, to_name='Equipe comercial Cadu',
        subject=f'Novo onboarding: {usuario["nome_completo"]} ({perfil})', html_content=html,
    )


def enviar_email_onboarding_usuario(*, usuario, organization_name, brand_name, project_name,
                                    perfil=None):
    """Confirm the Workspace base after the first brand/project is created."""
    from aicentralv2.services.brevo_service import get_brevo_product_service, product_email_brand

    brand = product_email_brand('workspace')
    return get_brevo_product_service('workspace').enviar_email_com_template(
        template_name='workspace-onboarding-concluido.html',
        template_folder='emails/externos',
        to_email=usuario.get('email'),
        to_name=usuario.get('nome_completo') or 'pessoa do time',
        subject='Sua primeira base está pronta no Cadu Workspace',
        params={
            'PRIMEIRO_NOME': (usuario.get('nome_completo') or 'pessoa do time').split()[0],
            'EMPRESA': organization_name or 'sua organização',
            'MARCA': brand_name or 'sua marca',
            'PROJETO': project_name or 'seu projeto',
            'PERFIL': perfil or 'cliente_final',
            'WORKSPACE_URL': current_app.config.get('WORKSPACE_URL', 'https://workspace.centralcomm.media'),
            'BRAND': brand,
            # `welcome.png` is part of the published Workspace email set;
            # keep onboarding on an asset that is available in production.
            'ILLUSTRATION_URL': brand['illustrations_url'] + 'welcome.png',
        },
    )


def processar_followups_onboarding(limit=50):
    """Envia apenas itens persistidos e vencidos; seguro para execução recorrente."""
    from aicentralv2 import db

    enviados = falhas = 0
    for item in db.obter_followups_onboarding_vencidos(limit=limit):
        reply_email = item.get('executivo_email') or current_app.config.get('DEMETRIUS_EMAIL')
        if not reply_email:
            db.registrar_resultado_followup_onboarding(item['id'], success=False,
                                                       error='E-mail do Demétrius não configurado')
            falhas += 1
            continue
        perfil = 'agência' if item['perfil'] == 'agencia' else 'cliente final'
        html = render_template('emails/externos/onboarding-demetrius.html', usuario=item,
                               perfil=perfil, demetrius_nome=item.get('executivo_nome') or
                               current_app.config.get('DEMETRIUS_NAME'))
        result = get_brevo_service().enviar_email(
            to_email=item['email'], to_name=item['nome_completo'],
            subject='Posso ajudar você a começar no Cadu?', html_content=html,
            reply_to={'email': reply_email,
                      'name': item.get('executivo_nome') or current_app.config.get('DEMETRIUS_NAME')},
        )
        db.registrar_resultado_followup_onboarding(item['id'], success=result.get('success', False),
                                                   error=result.get('error'))
        enviados += int(bool(result.get('success')))
        falhas += int(not result.get('success'))
    return {'enviados': enviados, 'falhas': falhas}
