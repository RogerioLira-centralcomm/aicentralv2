"""Qualificação de primeiro acesso e contato comercial posterior."""
import logging

from flask import current_app, render_template

from aicentralv2.services.brevo_service import get_brevo_service

logger = logging.getLogger(__name__)


def enviar_notificacao_demetrius(*, usuario, onboarding, executivo):
    email = (executivo or {}).get('email') or current_app.config.get('DEMETRIUS_EMAIL')
    if not email:
        logger.warning('Onboarding concluído sem e-mail configurado para Demétrius.')
        return {'success': False, 'error': 'E-mail do executivo não configurado'}
    perfil = 'Agência' if onboarding['perfil'] == 'agencia' else 'Cliente final'
    html = render_template('emails/internos/onboarding-concluido.html', usuario=usuario,
                           onboarding=onboarding, perfil=perfil)
    return get_brevo_service().enviar_email(
        to_email=email, to_name=(executivo or {}).get('nome_completo') or 'Demétrius',
        subject=f'Novo onboarding: {usuario["nome_completo"]} ({perfil})', html_content=html,
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
