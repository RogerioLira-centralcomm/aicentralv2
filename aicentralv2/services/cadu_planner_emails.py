"""Internal transactional notifications for the customer Smart Planner."""
from __future__ import annotations

from flask import current_app

from .brevo_service import get_brevo_product_service, product_email_brand


DEFAULT_INTERNAL_RECIPIENTS = ('apolo@centralcomm.media', 'alexandre@centralcom.media')


def _enabled() -> bool:
    return bool(current_app.config.get('CADU_PLANNER_EMAILS_ENABLED', False))


def _internal_recipients() -> list[str]:
    configured = str(current_app.config.get('CADU_PLANNER_INTERNAL_NOTIFICATION_EMAILS', '')).strip()
    return [item.strip() for item in configured.split(',') if item.strip()] if configured else list(DEFAULT_INTERNAL_RECIPIENTS)


def notify_quote_request(*, executive_email: str, executive_name: str, client_name: str,
                         requester_name: str, plan_title: str, scope: str, message: str = '') -> dict:
    """Notify the assigned executive and copy Planner leadership without exposing pricing."""
    if not _enabled():
        return {'success': True, 'skipped': True}
    internal = _internal_recipients()
    recipient = executive_email or internal[0]
    cc = [email for email in internal if email.lower() != recipient.lower()]
    return get_brevo_product_service('planner').enviar_email_com_template(
        template_name='planner-solicitacao-cotacao.html', template_folder='emails/internos',
        to_email=recipient, to_name=executive_name or 'Time comercial',
        cc_email=cc, subject='Nova solicitação de cotação pelo Planner',
        params={'BRAND': product_email_brand('planner'), 'CLIENT_NAME': client_name,
                'REQUESTER_NAME': requester_name, 'PLAN_TITLE': plan_title,
                'SCOPE': scope, 'MESSAGE': message},
    )


def notify_new_planner_user(*, user_name: str, user_email: str, client_name: str) -> dict:
    if not _enabled():
        return {'success': True, 'skipped': True}
    recipients = _internal_recipients()
    return get_brevo_product_service('planner').enviar_email_com_template(
        template_name='planner-novo-usuario.html', template_folder='emails/internos',
        to_email=recipients, to_name='Time Smart Planner', subject='Novo usuário no Smart Planner',
        params={'BRAND': product_email_brand('planner'), 'USER_NAME': user_name,
                'USER_EMAIL': user_email, 'CLIENT_NAME': client_name},
    )
