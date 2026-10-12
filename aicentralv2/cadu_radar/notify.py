"""E-mail do Radar: ao terminar a busca, entrega os ângulos, o buzz e o tempo que o Radar poupou.

Sai em segundo plano quando chamado pela tela (o Brevo demora) e uma falha de envio nunca derruba a busca.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from html import escape

from flask import current_app

from . import time_saved

logger = logging.getLogger(__name__)


def _day(value):
    if isinstance(value, datetime):
        # A data do buzz é gravada como meia-noite UTC: formatar em UTC mantém o dia da reportagem, em qualquer fuso do banco.
        return (value if value.tzinfo is None else value.astimezone(timezone.utc)).strftime('%d/%m')
    text = str(value or '')[:10]
    return f'{text[8:10]}/{text[5:7]}' if len(text) == 10 and text[4] == '-' else ''


def _safe_url(value):
    """Só http/https: os links do buzz vêm de páginas da web e não podem virar javascript: ou data:."""
    url = str(value or '').strip()
    return url if url.lower().startswith(('https://', 'http://')) else ''


def _layout(*, preheader, body, footer_note):
    """Casca do e-mail no padrão Cadu, cores do Planner. Pura: funciona fora do contexto Flask."""
    from ..services.brevo_service import email_asset_url, product_email_brand
    brand = product_email_brand('planner')
    band = email_asset_url('/static/images/cadu/email/bands/planner-band-v2.png')
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light only"><title>Radar de Oportunidades</title>'
        '<style>@media only screen and (max-width:620px){.shell{width:100%!important}.pad{padding:26px 22px!important}'
        '.btn{display:block!important;text-align:center!important}}</style></head>'
        '<body style="margin:0;background:#eef1f4;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Arial,sans-serif;color:#10213B">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</div>'
        '<table role="presentation" width="100%" bgcolor="#eef1f4"><tr><td style="padding:28px 12px">'
        '<table role="presentation" class="shell" width="600" align="center" style="max-width:600px;width:100%">'
        '<tr><td style="background:#fff;border-radius:18px;overflow:hidden">'
        f'<img src="{escape(band)}" width="600" height="66" alt="" style="display:block;width:100%;height:66px;object-fit:cover">'
        f'<div style="padding:16px 32px;background:{brand["soft"]};border-bottom:1px solid #e7eaed;text-align:center">'
        f'<img src="{escape(brand["icon_url"])}" width="38" height="38" alt="Planner" style="display:inline-block;width:38px;height:38px;'
        'background:#fff;border-radius:12px;padding:7px"></div>'
        f'<div class="pad" style="padding:32px 40px 34px;font-size:15px;line-height:1.65">{body}</div>'
        f'<div style="padding:22px 32px;background:{brand["accent"]};color:#fff;text-align:center;font-size:12px;line-height:1.55">'
        f'<b style="display:block;font-size:15px;margin-bottom:6px">Radar de Oportunidades · Planner</b>{footer_note}'
        '<div style="margin-top:6px;opacity:.92">Dúvidas? Responda este e-mail. · Powered by CentralComm</div></div>'
        '</td></tr></table></td></tr></table></body></html>')


def _line(angle):
    detail = angle.get('score_breakdown') or {}
    where = ', '.join([*(detail.get('formats') or [])[:2], *(detail.get('channels') or [])[:3]])
    return {'title': angle.get('title') or '', 'idea': angle.get('thesis') or '', 'why': detail.get('why_now') or '', 'where': where,
            'window': detail.get('window') or ''}


def compose(*, name, concept, brand, places, recency_days, angles, buzz, saved, tokens, run_url, radars_url, scheduled=False):
    """Assunto, texto e HTML. Puro, para testar sem enviar nada."""
    topic = concept or brand or 'a marca escolhida'
    where = f' em {places}' if places else ''
    hello = f'Olá, {name}!' if name else 'Olá!'
    run_url, radars_url = _safe_url(run_url) or run_url, _safe_url(radars_url) or radars_url
    footer = ('Você recebe este e-mail porque tem um radar ativo. Para pausar, abra '
              f'<a href="{escape(radars_url)}" style="color:#fff;text-decoration:underline">Meus radares</a>.'
              if scheduled else 'Você recebe este e-mail porque iniciou uma busca no Radar.')
    cards = [_line(item) for item in angles]
    if not cards:
        subject = f'Seu radar terminou: sem buzz recente sobre {topic}'[:150]
        message = (f'Não encontramos buzz com data recente e link que abre sobre «{topic}»{where}, nos últimos {recency_days} dias. '
                   'Tente uma janela maior (30 ou 60 dias) ou um conceito mais conhecido.')
        text = '\n'.join([hello, '', message, '', f'Abrir o Radar: {run_url}'])
        html = _layout(preheader=message, footer_note=footer, body=(
            f'<p style="margin:0 0 10px;color:#087D4D;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase">Radar de Oportunidades</p>'
            f'<h1 style="margin:0 0 14px;font-size:26px;line-height:1.2">O seu radar terminou</h1><p>{escape(hello)}</p><p>{escape(message)}</p>'
            f'{_button(run_url, "Abrir o Radar")}'))
        return subject, text, html
    count = f'{len(cards)} {"ângulo" if len(cards) == 1 else "ângulos"}'
    subject = (f'Radar: {count} {"novo" if len(cards) == 1 else "novos"} sobre {topic}' if scheduled
               else f'Seu radar terminou: {count} sobre {topic}')[:150]
    whose = f' para a marca {brand}' if brand and concept else ''
    summary = (f'Encontramos {len(buzz)} {"assunto" if len(buzz) == 1 else "assuntos"} em buzz{where} e montamos {len(cards)} '
               f'{"ângulo" if len(cards) == 1 else "ângulos"}{whose} falar de «{topic}».')
    saving = (f'Tempo economizado: cerca de {saved["label"]} de pesquisa e ideação.' if saved.get('label') else '')
    account = time_saved.account(saved) if saved.get('label') else ''
    cost = f'Esta busca usou {int(tokens):,} tokens dos seus créditos.'.replace(',', '.') if tokens else ''
    lines = [hello, '', 'O seu radar terminou.', summary, '']
    if saving:
        lines += [saving, f'(A conta: {account}. É uma estimativa com tempos de referência do trabalho manual.)', '']
    for index, card in enumerate(cards, 1):
        lines += [f'{index}. {card["title"]}', f'   {card["idea"]}']
        if card['why']:
            lines.append(f'   Por que agora: {card["why"]}')
        if card['where']:
            lines.append(f'   Formatos e canais: {card["where"]}')
        lines.append('')
    if buzz:
        lines.append('O buzz que sustenta os ângulos:')
        lines += [f'- {item.get("headline")} ({item.get("source") or "fonte"}, {_day(item.get("published_at"))}): {item.get("url")}' for item in buzz]
        lines.append('')
    lines += [f'Veja os ângulos e crie o planejamento: {run_url}']
    if cost:
        lines.append(cost)
    lines.append(f'Seus radares ativos ficam em Meus radares: {radars_url}')
    box = ''
    if saving:
        box = (f'<div style="margin:0 0 16px;padding:12px 14px;border-radius:10px;background:#E8F7EF"><b style="color:#087D4D">{escape(saving)}</b>'
               f'<div style="margin-top:4px;font-size:12px;color:#344054">A conta: {escape(account)}. Estimativa com tempos de referência do trabalho manual.</div></div>')
    items = ''.join(
        f'<li style="margin-bottom:14px"><b>{escape(card["title"])}</b><br>{escape(card["idea"])}'
        + (f'<br><span style="color:#344054"><b>Por que agora:</b> {escape(card["why"])}</span>' if card['why'] else '')
        + (f'<br><span style="color:#667085;font-size:13px">Formatos e canais: {escape(card["where"])}</span>' if card['where'] else '') + '</li>'
        for card in cards)
    def _source(item):
        headline = escape(str(item.get('headline') or ''))
        url = _safe_url(item.get('url'))
        link = f'<a href="{escape(url)}" style="color:#087D4D">{headline}</a>' if url else headline
        return (f'<li style="margin-bottom:6px">{link} <span style="color:#667085">'
                f'({escape(str(item.get("source") or "fonte"))}, {_day(item.get("published_at"))})</span></li>')
    sources = ''.join(_source(item) for item in buzz)
    body = (f'<p style="margin:0 0 10px;color:#087D4D;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase">Radar de Oportunidades</p>'
            f'<h1 style="margin:0 0 14px;font-size:26px;line-height:1.2">{"Novidades do seu radar" if scheduled else "O seu radar terminou"}</h1>'
            f'<p style="margin:0 0 16px">{escape(hello)} {escape(summary)}</p>{box}'
            f'<h2 style="margin:22px 0 10px;font-size:17px">Ângulos</h2><ol style="padding-left:20px;margin:0 0 12px">{items}</ol>'
            + (f'<h2 style="margin:22px 0 10px;font-size:17px">O buzz que sustenta os ângulos</h2><ul style="padding-left:20px;margin:0 0 18px">{sources}</ul>' if sources else '')
            + _button(run_url, 'Ver os ângulos e criar o planejamento')
            + (f'<p style="margin:18px 0 0;color:#667085;font-size:13px">{escape(cost)} Seus radares ativos ficam em '
               f'<a href="{escape(radars_url)}" style="color:#087D4D">Meus radares</a>.</p>'))
    html = _layout(preheader=summary, body=body, footer_note=footer)
    return subject, '\n'.join(lines), html


def _button(url, label):
    return (f'<p style="margin:24px 0 0"><a class="btn" href="{escape(url)}" style="display:inline-block;padding:14px 20px;border-radius:9px;'
            f'background:#087D4D;color:#fff;text-decoration:none;font-weight:700;font-size:15px">{escape(label)}</a></p>')


def _send(app, to_email, to_name, subject, text, html, *, client_id=None, scheduled=False):
    with app.app_context():
        result = {'success': False, 'error': 'not_sent'}
        try:
            from ..services.brevo_service import get_brevo_product_service
            result = get_brevo_product_service('planner').enviar_email(
                to_email=to_email, to_name=to_name or to_email.split('@')[0], subject=subject, html_content=html,
                text_content=text, tags=['radar:agendado' if scheduled else 'radar:manual'])
            if not result.get('success'):
                logger.warning('Radar: o e-mail de conclusão não foi aceito pelo provedor: %s', result.get('error'))
        except Exception as exc:  # noqa: BLE001 — o aviso é cortesia; o resultado já está salvo
            logger.exception('Radar: falha ao enviar o e-mail de conclusão')
            result = {'success': False, 'error': str(exc)}
        try:  # o registro torna o envio visível no monitoramento; nunca derruba nada
            from ..email_service import record_workspace_email_event
            record_workspace_email_event(recipient_email=to_email, event_type='planner.radar_finished',
                                         subject=subject, result=result, client_id=client_id)
        except Exception:  # noqa: BLE001
            logger.warning('Radar: não foi possível registrar o envio.', exc_info=True)


def run_finished(user, *, run, brand, run_url, radars_url, background=False):
    """Envia o e-mail de conclusão do run. Devolve False se não há e-mail ou se uma busca agendada não achou nada."""
    email = str((user or {}).get('email') or '').strip()
    angles, buzz = run.get('opportunities') or [], run.get('signals') or []
    if not email:
        return False
    if run.get('trigger') == 'agendado' and not angles:
        return False  # radar ativo sem novidade não incomoda ninguém
    params = run.get('params') or {}
    saved = run.get('time_saved') or time_saved.estimate(len(buzz), len(angles))
    scheduled = run.get('trigger') == 'agendado'
    subject, text, html = compose(name=(user.get('name') or '').split(' ')[0], concept=run.get('focus') or '', brand=brand,
                                  places=params.get('places'), recency_days=params.get('recency_days') or 30, angles=angles, buzz=buzz,
                                  saved=saved, tokens=run.get('tokens') or 0, run_url=run_url, radars_url=radars_url, scheduled=scheduled)
    extra = {'client_id': user.get('organization_id'), 'scheduled': scheduled}
    app = current_app._get_current_object()
    if background:
        threading.Thread(target=_send, args=(app, email, user.get('name'), subject, text, html), kwargs=extra,
                         daemon=True, name='cadu-radar-mail').start()
    else:
        _send(app, email, user.get('name'), subject, text, html, **extra)
    return True
