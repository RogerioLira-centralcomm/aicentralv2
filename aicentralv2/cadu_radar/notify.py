"""E-mail do Radar: avisa o usuário, assim que a busca começa, o que vai ser feito.

Sai em segundo plano (o Brevo demora e a tela não pode esperar) e uma falha de envio nunca derruba a busca.
"""
from __future__ import annotations

import logging
import threading
from html import escape

from flask import current_app

logger = logging.getLogger(__name__)

FREQUENCY_LABELS = {1: ('1 vez por dia', 'às 8h'), 2: ('2 vezes por dia', 'às 8h e às 17h'), 3: ('3 vezes por dia', 'às 8h, 13h e 18h')}


def compose(*, name, concept, brand, places, recency_days, estimated_tokens, run_url, radars_url, repeat=None):
    """Assunto, texto e HTML do e-mail. Puro, para testar sem enviar nada."""
    topic = concept or brand or 'a marca escolhida'
    where = f' em {places}' if places else ''
    whose = f' para a marca {brand}' if brand and concept else ''
    steps = [
        f'Buscar o que está em buzz agora sobre «{topic}»{where}, nos últimos {recency_days} dias.',
        'Conferir cada fonte: só fica o que tem data recente e link que abre.',
        f'Montar de 3 a 5 ângulos{whose or " para a marca"} falar do conceito, cada um ligado ao buzz que o sustenta.']
    cost = f'Reservamos até {int(estimated_tokens):,} tokens dos seus créditos e você paga só o que for usado.'.replace(',', '.')
    lines = [f'Olá, {name or "tudo bem"}!', '', 'O seu radar começou. Isto é o que vai ser feito:', *[f'{i}. {item}' for i, item in enumerate(steps, 1)], '', cost,
             f'Acompanhe o andamento e veja o resultado: {run_url}']
    block = ''
    if repeat in FREQUENCY_LABELS:
        label, hours = FREQUENCY_LABELS[repeat]
        lines += ['', f'Este radar vai se repetir {label} ({hours}, horário de Brasília) e fica em Meus radares: {radars_url}. Dá para pausar quando quiser.']
        block = (f'<p style="margin:16px 0 0;color:#344054">Este radar vai se repetir <b>{label}</b> ({hours}, horário de Brasília) e fica em '
                 f'<a href="{escape(radars_url)}" style="color:#067647">Meus radares</a>. Dá para pausar quando quiser.</p>')
    html = (f'<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;color:#101828;line-height:1.5">'
            f'<h2 style="margin:0 0 8px">O seu radar começou</h2><p style="margin:0 0 12px">Olá, {escape(name or "tudo bem")}! Isto é o que vai ser feito:</p>'
            f'<ol style="padding-left:20px;margin:0 0 12px">{"".join(f"<li style=margin-bottom:6px>{escape(item)}</li>" for item in steps)}</ol>'
            f'<p style="margin:0 0 16px;color:#344054">{escape(cost)}</p>'
            f'<a href="{escape(run_url)}" style="display:inline-block;padding:10px 18px;border-radius:8px;background:#067647;color:#fff;text-decoration:none;font-weight:600">Acompanhar o radar</a>'
            f'{block}</div>')
    return f'Seu radar começou: {topic}'[:150], '\n'.join(lines), html


def _send(app, to_email, to_name, subject, text, html):
    with app.app_context():
        try:
            from ..services.brevo_service import get_brevo_service
            result = get_brevo_service().enviar_email(to_email=to_email, to_name=to_name or to_email.split('@')[0], subject=subject,
                                                      html_content=html, text_content=text)
            if not result.get('success'):
                logger.warning('Radar: o e-mail de início não foi aceito pelo provedor: %s', result.get('error'))
        except Exception:  # noqa: BLE001 — o aviso é cortesia; a busca segue
            logger.exception('Radar: falha ao enviar o e-mail de início')


def run_started(user, *, concept, brand, params, estimated_tokens, run_url, radars_url, repeat=None, background=True):
    """Dispara o e-mail "o que será feito". Devolve False se o usuário não tem e-mail."""
    email = str((user or {}).get('email') or '').strip()
    if not email:
        return False
    params = params or {}
    subject, text, html = compose(name=(user.get('name') or '').split(' ')[0], concept=concept, brand=brand, places=params.get('places'),
                                  recency_days=params.get('recency_days') or 30, estimated_tokens=estimated_tokens, run_url=run_url,
                                  radars_url=radars_url, repeat=repeat)
    app = current_app._get_current_object()
    if background:
        threading.Thread(target=_send, args=(app, email, user.get('name'), subject, text, html), daemon=True, name='cadu-radar-mail').start()
    else:
        _send(app, email, user.get('name'), subject, text, html)
    return True
