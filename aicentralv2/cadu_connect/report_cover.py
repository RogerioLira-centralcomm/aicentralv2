"""Relatórios → capa gerada no Studio. O prompt nasce dos dados do relatório (tema, foco, plataformas e a tendência do
período), a pessoa vê a estimativa de créditos e confirma; a geração e a cobrança são as do Studio (custo real em tokens,
idempotente pelo request_id). A capa fica ligada ao relatório pela sessão do Studio, sem coluna nova no banco."""
import json
import uuid

from flask import abort, jsonify, request

from ..auth import login_required_api
from .report_previews import build_previews
from .reports_v1 import _rows, _selection, _write_guard

ASPECT_RATIO = '4:5'
QUALITY = 'padrão'
PLATFORM_NAMES = {'google_ads': 'Google Ads', 'meta_ads': 'Meta Ads', 'microsoft_ads': 'Microsoft Ads', 'linkedin_ads': 'LinkedIn Ads',
                  'tiktok_ads': 'TikTok Ads', 'dv360': 'DV360', 'amazon_ads': 'Amazon Ads', 'spotify_ads': 'Spotify Ads'}


def build_cover_prompt(report, preview):
    """Briefing em português para o diretor do Studio. Sem texto nem números na imagem: os números do card vêm do código."""
    document = report.get('document') or {}
    scope = 'a jornada de um fluxo do site' if document.get('flow_id') else 'uma campanha de mídia paga' if report.get('media_campaign_id') else 'um relatório de resultados'
    lines = [f'Capa editorial para o relatório "{report["campaign_name"]}", sobre {scope}.']
    objective = ' '.join(str(document.get('objective') or '').split())[:400]
    if objective:
        lines.append(f'Tema do relatório: {objective}')
    platforms = [PLATFORM_NAMES.get(item, item.replace('_', ' ')) for item in (preview or {}).get('platforms') or []]
    if platforms:
        lines.append('Canais envolvidos: ' + ', '.join(platforms) + '. Sugira esses canais pelo contexto da cena, sem logotipos.')
    total, previous = (preview or {}).get('total'), (preview or {}).get('previous')
    if total is not None and previous:
        lines.append('Clima da cena: ' + ('crescimento e conquista.' if total >= previous else 'análise atenta e ajuste de rota.'))
    lines.append('Fotografia ou ilustração realista, luz natural, composição limpa com um único assunto principal, em formato retrato 4:5.')
    lines.append('Não escreva nenhum texto, número, gráfico com valores, logotipo ou marca d’água na imagem.')
    return '\n'.join(lines)[:3900]


def _estimate(context):
    try:
        from ..cadu_workspace.mcp.tools.media import creation_capabilities
        estimate = creation_capabilities(context, {'quality': QUALITY}).get('image_cost_estimate') or {}
        return estimate.get('estimated_total')
    except Exception:
        return None


def _report(selected, report_id):
    found = _rows('''SELECT id,campaign_name,media_campaign_id,document FROM cadu_connect_report_workspaces
        WHERE id=%s AND client_id=%s''', (report_id, selected['client_id']))
    if not found:
        abort(404)
    return found[0]


def _preview(selected, report):
    document = report.get('document') or {}
    row = {'id': report['id'], 'media_campaign_id': report['media_campaign_id'], 'flow_campaigns': document.get('flow_campaigns'),
           'start_date': document.get('start_date'), 'end_date': document.get('end_date')}
    try:
        return build_previews(selected['client_id'], [row])[0]
    except Exception:
        return None


def _context(selected):
    from ..cadu_workspace.agent_v2.contracts import RequestContext
    return RequestContext(client_id=int(selected['client_id']), user_id=int(selected['user_id']), conversation_id=None,
                          surface='reports', request_id=None)


def register(bp):
    @bp.get('/api/v2/reports/workspaces/<int:report_id>/cover')
    @login_required_api
    def reports_cover_brief(report_id):
        """Prompt sugerido e estimativa de créditos. Nada é gerado nem cobrado aqui."""
        selected = _selection()
        report = _report(selected, report_id)
        return jsonify(prompt=build_cover_prompt(report, _preview(selected, report)), estimate=_estimate(_context(selected)),
                       aspect_ratio=ASPECT_RATIO, quality=QUALITY)

    @bp.post('/api/v2/reports/workspaces/<int:report_id>/cover')
    @login_required_api
    def reports_cover_generate(report_id):
        """Gera a capa depois da confirmação do custo. Cobrança pelo caminho do Studio; repetir o request_id não gera de novo."""
        from ..cadu_tool_billing import InsufficientToolCredits
        from ..cadu_workspace.media_creation_service import generate_studio_image
        from ..cadu_workspace.mcp.registry import ToolInputError
        from ..db import get_db
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if payload.get('confirmed_cost') is not True:
            abort(400, description='Confirme o custo estimado antes de gerar a capa.')
        report = _report(selected, report_id)
        prompt = str(payload.get('prompt') or '').strip()
        if not 3 <= len(prompt) <= 4000:
            abort(400, description='Escreva o pedido da capa (até 4.000 caracteres).')
        try:
            request_id = str(uuid.UUID(str(payload.get('request_id'))))
        except ValueError:
            abort(400, description='Pedido inválido: falta o identificador da geração.')
        try:
            result = generate_studio_image(_context(selected), {'request_id': request_id, 'prompt': prompt,
                                                                'aspect_ratio': ASPECT_RATIO, 'quality': QUALITY})
        except InsufficientToolCredits as exc:
            return jsonify(error=str(exc), code='insufficient_credits'), 402
        except ToolInputError as exc:
            abort(400, description=str(exc))
        # Liga a sessão do Studio ao relatório: a biblioteca lê a capa daqui.
        metadata = {'origin': 'cadu_reports', 'reports_client_id': int(selected['client_id']), 'reports_report_id': int(report['id']),
                    'reports_cover_url': result['image_url']}
        if report.get('media_campaign_id'):
            metadata['reports_campaign_id'] = int(report['media_campaign_id'])
        with get_db().cursor() as cursor:
            cursor.execute('UPDATE cx_studio_sessions SET metadata=metadata||%s::jsonb WHERE id=%s', (json.dumps(metadata), result['session_id']))
        get_db().commit()
        return jsonify(cover_url=result['image_url'], studio_url=result.get('studio_url'), charged_credits=result.get('charged_credits'),
                       remaining_credits=result.get('remaining_credits'))
