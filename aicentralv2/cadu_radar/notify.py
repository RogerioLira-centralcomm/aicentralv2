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


def _line(angle):
    detail = angle.get('score_breakdown') or {}
    where = ', '.join([*(detail.get('formats') or [])[:2], *(detail.get('channels') or [])[:3]])
    return {'title': angle.get('title') or '', 'idea': angle.get('thesis') or '', 'why': detail.get('why_now') or '', 'where': where,
            'window': detail.get('window') or ''}


def compose(*, name, concept, brand, places, recency_days, angles, buzz, saved, tokens, run_url, radars_url):
    """Assunto, texto e HTML. Puro, para testar sem enviar nada."""
    topic = concept or brand or 'a marca escolhida'
    where = f' em {places}' if places else ''
    hello = f'Olá, {name or "tudo bem"}!'
    cards = [_line(item) for item in angles]
    if not cards:
        subject = f'Seu radar terminou: sem buzz recente sobre {topic}'[:150]
        message = (f'Não encontramos buzz com data recente e link que abre sobre «{topic}»{where}, nos últimos {recency_days} dias. '
                   'Tente uma janela maior (30 ou 60 dias) ou um conceito mais conhecido.')
        text = '\n'.join([hello, '', message, '', f'Abrir o Radar: {run_url}'])
        html = (f'<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;color:#101828;line-height:1.5">'
                f'<h2 style="margin:0 0 8px">O seu radar terminou</h2><p>{escape(hello)}</p><p>{escape(message)}</p>{_button(run_url, "Abrir o Radar")}</div>')
        return subject, text, html
    subject = f'Seu radar terminou: {len(cards)} {"ângulo" if len(cards) == 1 else "ângulos"} sobre {topic}'[:150]
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
        box = (f'<div style="margin:0 0 16px;padding:12px 14px;border-radius:10px;background:#e3f8ee"><b style="color:#067647">{escape(saving)}</b>'
               f'<div style="margin-top:4px;font-size:12px;color:#344054">A conta: {escape(account)}. Estimativa com tempos de referência do trabalho manual.</div></div>')
    items = ''.join(
        f'<li style="margin-bottom:14px"><b>{escape(card["title"])}</b><br>{escape(card["idea"])}'
        + (f'<br><span style="color:#344054"><b>Por que agora:</b> {escape(card["why"])}</span>' if card['why'] else '')
        + (f'<br><span style="color:#667085;font-size:13px">Formatos e canais: {escape(card["where"])}</span>' if card['where'] else '') + '</li>'
        for card in cards)
    sources = ''.join(f'<li><a href="{escape(str(item.get("url") or ""))}" style="color:#067647">{escape(str(item.get("headline") or ""))}</a>'
                      f' <span style="color:#667085">({escape(str(item.get("source") or "fonte"))}, {_day(item.get("published_at"))})</span></li>' for item in buzz)
    html = (f'<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;color:#101828;line-height:1.5">'
            f'<h2 style="margin:0 0 8px">O seu radar terminou</h2><p style="margin:0 0 12px">{escape(hello)} {escape(summary)}</p>{box}'
            f'<h3 style="margin:16px 0 8px">Ângulos</h3><ol style="padding-left:20px;margin:0 0 12px">{items}</ol>'
            + (f'<h3 style="margin:16px 0 8px">O buzz que sustenta os ângulos</h3><ul style="padding-left:20px;margin:0 0 16px">{sources}</ul>' if sources else '')
            + _button(run_url, 'Ver os ângulos e criar o planejamento')
            + (f'<p style="margin:16px 0 0;color:#667085;font-size:13px">{escape(cost)} Seus radares ativos ficam em '
               f'<a href="{escape(radars_url)}" style="color:#067647">Meus radares</a>.</p>') + '</div>')
    return subject, '\n'.join(lines), html


def _button(url, label):
    return (f'<a href="{escape(url)}" style="display:inline-block;padding:10px 18px;border-radius:8px;background:#067647;color:#fff;'
            f'text-decoration:none;font-weight:600">{escape(label)}</a>')


def _send(app, to_email, to_name, subject, text, html):
    with app.app_context():
        try:
            from ..services.brevo_service import get_brevo_service
            result = get_brevo_service().enviar_email(to_email=to_email, to_name=to_name or to_email.split('@')[0], subject=subject,
                                                      html_content=html, text_content=text)
            if not result.get('success'):
                logger.warning('Radar: o e-mail de conclusão não foi aceito pelo provedor: %s', result.get('error'))
        except Exception:  # noqa: BLE001 — o aviso é cortesia; o resultado já está salvo
            logger.exception('Radar: falha ao enviar o e-mail de conclusão')


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
    subject, text, html = compose(name=(user.get('name') or '').split(' ')[0], concept=run.get('focus') or '', brand=brand,
                                  places=params.get('places'), recency_days=params.get('recency_days') or 30, angles=angles, buzz=buzz,
                                  saved=saved, tokens=run.get('tokens') or 0, run_url=run_url, radars_url=radars_url)
    app = current_app._get_current_object()
    if background:
        threading.Thread(target=_send, args=(app, email, user.get('name'), subject, text, html), daemon=True, name='cadu-radar-mail').start()
    else:
        _send(app, email, user.get('name'), subject, text, html)
    return True
