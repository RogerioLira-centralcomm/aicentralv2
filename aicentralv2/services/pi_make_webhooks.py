"""
Webhooks Make.com para fluxo operacional de PI (pastas Drive + produção).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import requests
from flask import current_app

from aicentralv2 import db

logger = logging.getLogger(__name__)


class PiMakeWebhookError(Exception):
    """Falha ao comunicar com webhook Make do PI."""


def _is_dev() -> bool:
    try:
        return bool(current_app.config.get('DEBUG', False))
    except RuntimeError:
        return False


def _fmt_data_curta(val) -> str:
    if not val:
        return ''
    if isinstance(val, str):
        try:
            val = datetime.strptime(val, '%Y-%m-%d')
        except ValueError:
            return val
    return val.strftime('%d/%m/%Y %H:%M:%S')


def _fmt_data_invite(val) -> str:
    if not val:
        return ''
    if isinstance(val, str):
        try:
            val = datetime.strptime(val, '%Y-%m-%d')
        except ValueError:
            return val
    return val.strftime('%m/%d/%Y 06:00:00')


def _parse_periodo_inicio(pi: dict) -> datetime | None:
    periodo_inicio = pi.get('periodo_inicio')
    if not periodo_inicio:
        return None
    if isinstance(periodo_inicio, str):
        try:
            return datetime.strptime(periodo_inicio, '%Y-%m-%d')
        except ValueError:
            return None
    return periodo_inicio


def _montar_nomeagencia(pi: dict) -> str:
    ref_id = pi.get('id_agencia') or pi.get('id_cliente')
    prefixo = 'AG' if pi.get('id_agencia') else 'CL'
    razao_social = ''
    if ref_id:
        cli_info = db.obter_cliente_por_id(ref_id)
        if cli_info:
            razao_social = cli_info.get('razao_social') or cli_info.get('nome_fantasia') or ''
    return f'{prefixo} | {razao_social}'


def gerar_pastas_drive_pi(pi: dict, *, strict: bool = False) -> dict[str, str]:
    """
    Cria pastas no Google Drive via Make e persiste links no PI.

    Returns dict com googled_pi_princ, googled_pi_financ, googled_pi_pecas, googled_pi_arq_ass.
    """
    id_pi = pi.get('id_pi')
    if not id_pi:
        raise PiMakeWebhookError('PI sem id_pi')

    if pi.get('googled_pi_princ'):
        if strict:
            raise PiMakeWebhookError('Pastas já foram geradas para este PI')
        return {
            'googled_pi_princ': pi.get('googled_pi_princ') or '',
            'googled_pi_financ': pi.get('googled_pi_financ') or '',
            'googled_pi_pecas': pi.get('googled_pi_pecas') or '',
            'googled_pi_arq_ass': pi.get('googled_pi_arq_ass') or '',
        }

    numero = pi.get('codigo_pi_cc') or ''
    if not numero:
        raise PiMakeWebhookError('PI sem código (codigo_pi_cc)')

    webhook_url = os.getenv('MAKE_WEBHOOK_GDRIVE')
    if not webhook_url:
        msg = 'Webhook de criação de pastas não configurado (MAKE_WEBHOOK_GDRIVE)'
        if strict:
            raise PiMakeWebhookError(msg)
        raise PiMakeWebhookError(msg)

    nomeagencia = _montar_nomeagencia(pi)

    try:
        resp = requests.get(
            webhook_url,
            params={'numero': numero, 'nomeagencia': nomeagencia},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error('Erro webhook MAKE_WEBHOOK_GDRIVE: %s', exc)
        raise PiMakeWebhookError(f'Erro ao comunicar com webhook de pastas: {exc}') from exc

    partes = resp.text.strip().split('*****')
    if len(partes) < 4:
        logger.error(
            'Webhook GDrive retornou resposta inesperada (%s partes): %s',
            len(partes),
            resp.text[:200],
        )
        raise PiMakeWebhookError('Resposta do webhook de pastas com formato inesperado')

    princ, financ, pecas, arq_ass = partes[0], partes[1], partes[2], partes[3]
    db.atualizar_cadu_pi_gdrive(id_pi, princ, financ, pecas, arq_ass)

    return {
        'googled_pi_princ': princ,
        'googled_pi_financ': financ,
        'googled_pi_pecas': pecas,
        'googled_pi_arq_ass': arq_ass,
    }


def _atualizar_status_pi_producao(id_pi: int) -> None:
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                UPDATE cadu_pi
                SET id_status_pi = (SELECT id FROM cadu_pi_aux_status WHERE descricao = 'Campanha em análise' LIMIT 1),
                    id_sub_status_pi = (SELECT key FROM cadu_pi_sub_status WHERE display = 'Em aprovação' LIMIT 1),
                    updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                WHERE id_pi = %s
                ''',
                (id_pi,),
            )
            conn.commit()
    except Exception as exc:
        conn.rollback()
        raise PiMakeWebhookError(f'Erro ao atualizar status do PI: {exc}') from exc


def disparar_webhooks_producao_pi(pi: dict, *, strict: bool = False) -> list[str]:
    """
    Atualiza status do PI para Em aprovação e dispara webhooks CONFIGURACAO + INVITES.

    Em strict=True levanta PiMakeWebhookError na primeira falha.
    Em strict=False retorna lista de erros (comportamento legado do botão manual).
    """
    id_pi = pi.get('id_pi')
    if not id_pi:
        raise PiMakeWebhookError('PI sem id_pi')

    numero = pi.get('codigo_pi_cc') or ''
    is_dev = _is_dev()
    dt_inicio = _parse_periodo_inicio(pi)
    periodo_inicio = pi.get('periodo_inicio')
    tem_agencia = bool(pi.get('id_agencia'))
    webhook_erros: list[str] = []

    _atualizar_status_pi_producao(id_pi)

    url_config = os.getenv('MAKE_WEBHOOK_PI_CONFIGURACAO')
    if url_config:
        params_config = {
            'testeparam': 'yes' if is_dev else 'no',
            'codPI': numero,
            'razaosccliente': pi.get('cliente_razao_social') or '',
            'nomefcliente': pi.get('cliente_nome') or '',
            'razaoscagencia': pi.get('agencia_razao_social') or '',
            'nomefagencia': pi.get('agencia_nome') or '',
            'pastagoogleprinc': pi.get('googled_pi_princ') or '',
            'valorliquidopi': pi.get('vr_liquido_pi') or '',
            'emailresponsavelpi': pi.get('resp_comercial_email') or '',
            'mesref': _fmt_data_curta(pi.get('mes_ref')),
            'datainicio': _fmt_data_curta(pi.get('periodo_inicio')),
            'datafim': _fmt_data_curta(pi.get('periodo_fim')),
            'pastagooglepecas': pi.get('googled_pi_pecas') or '',
            'instrucoesoperacao': (pi.get('observacoes_operacao') or '').strip() or 'Sem instruções',
            'instrucoesfinanceiro': (pi.get('observacoes_financeiro') or '').strip() or 'Sem instruções',
            'nomerespPI': pi.get('resp_comercial_nome') or '',
            'titulo': pi.get('titulo_pi') or '',
            'pi_tem_agencia': 'sim' if tem_agencia else 'não',
        }
        try:
            resp = requests.get(url_config, params=params_config, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            logger.error('Erro webhook PI_CONFIGURACAO: %s', exc)
            if strict:
                raise PiMakeWebhookError(f'Erro webhook PI_CONFIGURACAO: {exc}') from exc
            webhook_erros.append(str(exc))
    elif strict:
        raise PiMakeWebhookError('Webhook não configurado (MAKE_WEBHOOK_PI_CONFIGURACAO)')

    url_invites = os.getenv('MAKE_WEBHOOK_PI_INVITES')
    if url_invites:
        params_invites = {
            'testeparam': 'yes' if is_dev else 'no',
            'dteveinicio': _fmt_data_invite(periodo_inicio),
            'nomerespcc': pi.get('resp_comercial_nome') or '',
            'emailrespcc': pi.get('resp_comercial_email') or '',
            'codPI': numero,
            'dteven5dias': _fmt_data_invite(dt_inicio + timedelta(days=5)) if dt_inicio else '',
            'tituloPI': pi.get('titulo_pi') or '',
            'dtevenfim': _fmt_data_invite(pi.get('periodo_fim')),
        }
        try:
            resp = requests.get(url_invites, params=params_invites, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            logger.error('Erro webhook PI_INVITES: %s', exc)
            if strict:
                raise PiMakeWebhookError(f'Erro webhook PI_INVITES: {exc}') from exc
            webhook_erros.append(str(exc))
    elif strict:
        raise PiMakeWebhookError('Webhook não configurado (MAKE_WEBHOOK_PI_INVITES)')

    return webhook_erros


def executar_fluxo_producao_completo(id_pi: int) -> None:
    """
    Fluxo completo: pastas Drive (se necessário) + webhooks de produção.
    Levanta PiMakeWebhookError em qualquer falha (uso na aprovação cotação teste).
    """
    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi:
        raise PiMakeWebhookError('PI não encontrado')

    if not pi.get('id_cliente'):
        raise PiMakeWebhookError('PI sem cliente vinculado')
    if not pi.get('codigo_pi_cc'):
        raise PiMakeWebhookError('PI sem código (codigo_pi_cc)')

    if not pi.get('googled_pi_princ'):
        gerar_pastas_drive_pi(pi, strict=True)
        pi = db.obter_cadu_pi_por_id(id_pi)
        if not pi or not pi.get('googled_pi_princ'):
            raise PiMakeWebhookError('Pastas do Google Drive não foram persistidas')

    disparar_webhooks_producao_pi(pi, strict=True)
