"""Área autenticada de conta e administração do workspace.centralcomm.media."""

from pathlib import Path
import calendar
from datetime import date, datetime, timedelta, timezone
from html import escape
from io import BytesIO
from hashlib import sha256
import json
import os
import re
import threading
from typing import Optional
from urllib.parse import quote, urlencode, urlparse
from uuid import uuid4
import secrets

from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException
from markupsafe import Markup

from flask import Blueprint, Response, abort, current_app, g, jsonify, redirect, render_template, request, send_file, session, url_for

from ..auth import login_required
from ..cadu_family import repository as family_repository
from ..cadu_connect.repository import accounts_for_workspace_context
from ..cadu_credit_connector import CaduCreditConnector
from ..cadu_skills.repository import CaduCreditUnavailable, charge_project_rag, credit_position, list_customizations
from ..db import close_db, get_db
from ..product_domains import product_url, workspace_public_url
from ..smart_planner.logos import public_logo
from . import project_index_service, project_knowledge, project_resource_service, project_sources


def _utc_timestamp() -> str:
    """RFC 3339 UTC timestamp without the deprecated naive ``utcnow`` API."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _send_brand_approval_email(brand: dict, pack: dict, client_id: int, brand_id: int) -> None:
    """Send a readable approval recap without making approval depend on mail delivery."""
    recipient = str(session.get('user_email') or '').strip()
    if not recipient or '@' not in recipient:
        return
    metadata = brand.get('analysis_metadata') or {}
    sources = metadata.get('sources') or []
    if not isinstance(sources, list):
        sources = []
    links = [item for item in sources if isinstance(item, str) and item.startswith(('http://', 'https://'))]
    reviews = pack.get('reviews') or []
    methods = metadata.get('methods') or metadata.get('applied_methods') or ['Leitura do site oficial', 'Síntese de evidências', 'Revisão de estratégia e direção criativa']
    info = pack.get('analysis') or {}
    analysis_fields = [
        ('Essência', info.get('brand_summary') or info.get('positioning')),
        ('Público', info.get('target_audience') or info.get('audience_segments')),
        ('Oferta', info.get('products_services') or info.get('differentiators')),
        ('Tom de voz', info.get('tone_of_voice')),
        ('Direção criativa', info.get('creative_guidelines') or info.get('visual_motifs')),
        ('Oportunidades', info.get('campaign_opportunities') or info.get('proof_points')),
    ]
    highlights = [{'title': title, 'text': str(value)[:420]} for title, value in analysis_fields if value][:6]
    information_size = sum(len(str(value)) for value in info.values()) if isinstance(info, dict) else 0
    hourly_cost = 3500 * 1.70 / 220
    saved_hours = max(1.0, round((len(links) * 0.35) + (len(reviews) * 1.25) + (information_size / 18000), 1))
    saved_value = saved_hours * hourly_cost
    try:
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT COALESCE(SUM(tokens_cobrados), 0) AS credits FROM cadu_tools_token_usage WHERE id_cliente = %s AND metadata->>'job_id' = %s AND status = 'charged'""", (client_id, str(pack.get('job_id') or '')))
            credits_used = int((cursor.fetchone() or {}).get('credits') or 0)
    except Exception:
        current_app.logger.exception('Não foi possível calcular créditos do resumo da marca %s', brand_id)
        credits_used = 0
    from ..services.cadu_email_connector import send_cadu_event
    money = lambda value: f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    send_cadu_event(product='workspace', event='workspace.brand_approved', template='marca-sintese-aprovada.html',
        recipient=recipient, recipient_name=str(session.get('user_name') or 'time da agência'),
        subject=f"Síntese aprovada · {brand.get('name') or 'Marca'}",
        params={'MARCA': brand.get('name') or 'Marca',
                'LOGO_URL': brand.get('display_logo') or brand.get('logo_url') or '',
                'LINK_MARCA': product_url('workspace', f'/marcas/{brand_id}'), 'LINKS': len(links),
                'REVISOES': len(reviews), 'METODOS': methods, 'TAMANHO_INFO': information_size,
                'HORAS_ECONOMIZADAS': saved_hours, 'VALOR_ECONOMIZADO': money(saved_value),
                'CREDITOS': credits_used, 'CUSTO_HORA': money(hourly_cost),
                'CUSTO_CREDITOS': money(credits_used * 0.01), 'HIGHLIGHTS': highlights,
                'FONTES': links},
    )


bp = Blueprint("cadu_workspace", __name__)
# The advanced brand editor has a Workspace-owned API prefix.  Its handlers
# are registered during app setup, alongside this product blueprint.
brand_api_bp = Blueprint("workspace_brand_api", __name__, url_prefix="/workspace")


_BREVO_EMAIL_EVENT_STATUS = {
    'request': 'sent', 'sent': 'sent', 'delivered': 'delivered',
    'opened': 'opened', 'unique_opened': 'opened', 'click': 'clicked',
    'soft_bounce': 'failed', 'hard_bounce': 'failed', 'invalid_email': 'failed',
    'blocked': 'failed', 'error': 'failed', 'spam': 'failed', 'deferred': 'deferred',
}


def _workspace_rich_text(value: str) -> Markup:
    """Render the small, safe Markdown dialect used in project context."""
    from ..cadu_planner.docs import markdown_to_safe_html

    return Markup(markdown_to_safe_html(value))


@bp.before_request
def prepare_shared_cadu_chat():
    if session.get("user_id"):
        session.setdefault("family_csrf", secrets.token_urlsafe(32))


@bp.post('/workspace/api/email-events/brevo')
def workspace_brevo_email_event():
    """Receive only authenticated Brevo lifecycle events for Workspace mail."""
    expected_token = str(current_app.config.get('BREVO_WORKSPACE_WEBHOOK_TOKEN') or '')
    supplied_token = request.headers.get('X-Brevo-Webhook-Token', '')
    if not expected_token or not secrets.compare_digest(supplied_token, expected_token):
        abort(403)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        abort(400)
    status = _BREVO_EMAIL_EVENT_STATUS.get(str(payload.get('event') or '').lower())
    message_id = str(payload.get('message-id') or '').strip()
    if not status or not message_id:
        return '', 204
    event_timestamp = payload.get('ts_event') or payload.get('ts')
    error = str(payload.get('reason') or payload.get('event') or '')[:4000] or None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_workspace_email_events
                       SET status = %s,
                           provider_error = CASE WHEN %s = 'failed' THEN %s ELSE provider_error END,
                           last_event_at = CASE WHEN %s ~ '^[0-9]+$'
                                                THEN TO_TIMESTAMP(%s::double precision)
                                                ELSE NOW() END
                     WHERE provider_message_id = %s""",
                (status, status, error, str(event_timestamp or ''), str(event_timestamp or '0'), message_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível registrar evento Brevo do Workspace')
        abort(503)
    return '', 204


def _php_account_data(client_id: int) -> dict:
    """Read the established Cadu PHP records; Workspace owns no account copy."""
    from .. import db

    try:
        people = [dict(row) for row in db.obter_contatos_por_cliente(client_id)]
        plans = [dict(row) for row in db.obter_planos_clientes({"cliente_id": client_id})]
    except Exception:
        people, plans = [], []

    plan = next((row for row in plans if row.get("plan_status") == "active"), plans[0] if plans else {})
    # The Workspace must report the same lot-based balance that is charged by
    # Studio and the other AI tools.  The former plan/image-credit figures are
    # legacy administrative values and can disagree with the live balance.
    credit = credit_position(client_id)
    granted = int(credit.get("monthly") or 0)
    used = max(0, granted - int(credit.get("available") or 0))
    position = {
        "allowance": granted,
        "adjustments": 0,
        "used": used,
        "available": int(credit.get("available") or 0),
        "effective_limit": granted,
        "usage_percentage": round((used / granted) * 100, 1) if granted else 0,
    } if credit.get("configured") else None
    try:
        invites = [dict(row) for row in db.obter_invites_cliente(client_id)]
    except Exception:
        invites = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, 'usage' AS movement_type, tokens_cobrados AS amount,
                          CONCAT('Ferramenta: ', ferramenta,
                                 CASE WHEN etapa IS NULL THEN '' ELSE ' · ' || etapa END) AS reason,
                          idempotency_key AS reference, NULL::varchar AS created_by_name,
                          COALESCE(charged_at, created_at) AS created_at
                     FROM cadu_tools_token_usage
                    WHERE id_cliente = %s AND status = 'charged'
                    ORDER BY COALESCE(charged_at, created_at) DESC, id DESC LIMIT 20""",
                (client_id,),
            )
            movements = [dict(row) for row in cursor.fetchall()]
    except Exception:
        movements = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, 'Lote de créditos' AS package_name,
                          tokens_amount AS credits, tokens_used,
                          tokens_amount - tokens_used AS available,
                          expires_at, status AS payment_status,
                          NULL::varchar AS reference, purchased_at
                     FROM cadu_credits_extras
                    WHERE id_cliente = %s
                      AND status = 'active'
                      AND tokens_used < tokens_amount
                      AND (expires_at IS NULL OR expires_at > NOW())
                 ORDER BY expires_at ASC NULLS LAST, purchased_at DESC NULLS LAST, id DESC LIMIT 20""",
                (client_id,),
            )
            purchases = [dict(row) for row in cursor.fetchall()]
    except Exception:
        purchases = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT recipient_email, event_type, subject, status, provider_message_id, created_at
                     FROM cadu_workspace_email_events
                    WHERE id_cliente = %s
                 ORDER BY created_at DESC, id DESC LIMIT 30""",
                (client_id,),
            )
            email_events = [dict(row) for row in cursor.fetchall()]
    except Exception:
        email_events = []
    insights = _workspace_account_insights(plan, position, people)
    return {"people": people, "invites": invites, "plan": plan, "credit": credit,
            "position": position, "movements": movements, "purchases": purchases,
            "insights": insights, "email_catalog": _workspace_account_email_catalog(),
            "email_events": email_events}


def _workspace_account_email_catalog() -> tuple[dict, ...]:
    """Document the transactional e-mails the account journey can dispatch.

    This is a catalogue of real application triggers, not a delivery log. A
    provider delivery history needs its own durable event table before it can
    be presented as one.
    """
    return (
        {
            "page": "Equipe", "action": "Convidar ou reenviar convite",
            "recipient": "Pessoa convidada", "subject": "Você foi convidado",
            "template": "convite-usuario.html", "timing": "Ao enviar ou reenviar",
        },
        {
            "page": "Aceitar convite", "action": "Criar acesso",
            "recipient": "Nova pessoa da equipe", "subject": "Sua conta está pronta",
            "template": "bem-vindo.html", "timing": "Depois de aceitar o convite",
        },
        {
            "page": "Boas-vindas", "action": "Apresentar bônus inicial",
            "recipient": "Nova pessoa da equipe", "subject": "100.000 créditos para começar",
            "template": "bonus-creditos.html", "timing": "Depois de aceitar o convite, se o bônus estiver ativo",
        },
        {
            "page": "Acesso", "action": "Recuperar senha",
            "recipient": "Pessoa com acesso ativo", "subject": "Redefina sua senha",
            "template": "reset-senha.html", "timing": "Ao solicitar recuperação",
        },
        {
            "page": "Acesso", "action": "Confirmar nova senha",
            "recipient": "Pessoa que redefiniu a senha", "subject": "Senha alterada",
            "template": "senha-alterada.html", "timing": "Depois de trocar a senha",
        },
        {
            "page": "Faturamento", "action": "Ativar assinatura",
            "recipient": "E-mail financeiro da agência", "subject": "Plano ativado",
            "template": "assinatura-confirmacao.html", "timing": "Após a ativação do plano",
        })


def _workspace_account_insights(plan: dict, position: Optional[dict], people: list[dict]) -> dict:
    """Derive customer-facing plan usage without creating another source of truth."""
    def integer(value) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def percentage(used, limit) -> float:
        return round((integer(used) / integer(limit)) * 100, 1) if integer(limit) else 0

    def plan_date(value):
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value, value.strftime('%d/%m/%Y')
        if isinstance(value, str) and value:
            try:
                parsed = date.fromisoformat(value[:10])
                return parsed, parsed.strftime('%d/%m/%Y')
            except ValueError:
                return None, value
        return None, 'Não informado'

    token_limit = integer(plan.get('pd_tokens_monthly_limit') or plan.get('tokens_monthly_limit'))
    token_used = integer(plan.get('tokens_used_current_month'))
    user_limit = integer(plan.get('pd_max_users') or plan.get('max_users'))
    active_users = sum(bool(person.get('status')) for person in people)
    features = plan.get('features') or {}
    if isinstance(features, str):
        try:
            features = json.loads(features)
        except (TypeError, ValueError):
            features = {}
    if not isinstance(features, dict):
        features = {}

    start_date, start_label = plan_date(plan.get('valid_from') or plan.get('plan_start_date'))
    end_date, end_label = plan_date(plan.get('valid_until') or plan.get('plan_end_date'))
    days_remaining = (end_date - date.today()).days if isinstance(end_date, date) else None
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    credit_used = integer((position or {}).get('used'))
    effective_limit = integer((position or {}).get('effective_limit'))
    projected = round((credit_used / max(today.day, 1)) * days_in_month) if credit_used else 0
    feature_labels = {
        'all_modes': 'Todos os modos de trabalho',
        'unlimited_docs': 'Documentos sem limite',
        'unlimited_conversations': 'Conversas sem limite',
        'brand_management': 'Gestão de marcas',
        'project_knowledge': 'Base de conhecimento dos projetos',
        'studio': 'Cadu Studio',
        'planner': 'Cadu Planner',
        'connect': 'Cadu Connect',
        'skills': 'Cadu Skills',
    }
    return {
        'tokens': {'used': token_used, 'limit': token_limit,
                   'available': max(token_limit - token_used, 0),
                   'percentage': percentage(token_used, token_limit)},
        'users': {'used': active_users, 'limit': user_limit,
                  'available': max(user_limit - active_users, 0),
                  'percentage': percentage(active_users, user_limit)},
        'credits': {'projected': projected,
                    'projected_percentage': percentage(projected, effective_limit)},
        'features': [feature_labels.get(key, key.replace('_', ' ').capitalize())
                     for key, enabled in features.items() if enabled is True],
        'validity': {'start': start_label, 'end': end_label},
        'days_remaining': days_remaining,
    }


def _workspace_settings_data(client_id: int, user_id: int) -> dict:
    """Read the canonical organization and signed-in profile records."""
    from .. import db

    try:
        organization = dict(db.obter_cliente_por_id(client_id) or {})
    except Exception:
        organization = {}
    try:
        current_user = dict(db.obter_contato_por_id(user_id) or {})
    except Exception:
        current_user = {}
    try:
        states = [dict(row) for row in db.obter_estados()]
    except Exception:
        states = []
    return {"organization": organization, "current_user": current_user, "states": states}


def _workspace_billing_data(client_id: int) -> dict:
    """Normalize the two historical invoice schemas into one read-only ledger."""
    from .. import db

    try:
        records = [dict(row) for row in db.obter_invoices({"cliente_id": client_id})]
    except Exception:
        records = []
    invoices = []
    for record in records:
        status = record.get('invoice_status') or record.get('status') or 'pending'
        raw_pdf = str(record.get('pdf_url') or '').strip()
        parsed_pdf = urlparse(raw_pdf) if raw_pdf else None
        safe_pdf = raw_pdf if raw_pdf and (
            raw_pdf.startswith('/') or (parsed_pdf and parsed_pdf.scheme in {'http', 'https'})
        ) else None
        invoices.append({
            **record,
            'number': record.get('invoice_number') or f"Fatura {record.get('id_invoice') or record.get('id') or ''}".strip(),
            'status_normalized': status,
            'reference': record.get('reference_month') or record.get('billing_month'),
            'paid_on': record.get('paid_date') or record.get('paid_at'),
            'type_normalized': record.get('invoice_type') or 'subscription',
            'pdf_safe_url': safe_pdf,
        })

    def money(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    open_statuses = {'pending', 'sent', 'overdue'}
    return {
        'invoices': invoices,
        'summary': {
            'open_total': round(sum(money(item.get('total')) for item in invoices
                                    if item['status_normalized'] in open_statuses), 2),
            'open_count': sum(item['status_normalized'] in open_statuses for item in invoices),
            'overdue_count': sum(item['status_normalized'] == 'overdue' for item in invoices),
            'paid_count': sum(item['status_normalized'] == 'paid' for item in invoices),
        },
    }


def _workspace_integration_data(client_id: int, organization_id: int) -> dict:
    """Expose connection metadata only; Connect remains owner of credentials and actions."""
    accounts = accounts_for_workspace_context(
        organization_id or client_id, workspace_client_id=client_id,
    )
    providers = {
        'google_ads': 'Google Ads', 'google_analytics': 'Google Analytics',
        'google_search_console': 'Search Console', 'meta_ads': 'Meta Ads',
        'linkedin_ads': 'LinkedIn Ads', 'tiktok_ads': 'TikTok Ads',
        'dv360': 'Display & Video 360', 'custom': 'Integração personalizada',
    }
    for account in accounts:
        key = str(account.get('provider') or '').lower()
        account['provider_label'] = providers.get(key, key.replace('_', ' ').title() or 'Plataforma')
    google = {
        'connection': None,
        'resources': [],
        'meet_artifacts': [],
        'projects': [],
        'services': [],
        'summary': {'enabled_count': 0, 'total_count': 0, 'pending_count': 0},
        'configuration': {'configured': False, 'missing': [], 'redirect_uri': ''},
        'connect_url': product_url('auth', '/auth/google/workspace') + '?' + urlencode({'next': product_url('workspace', '/integracoes')}),
        'configured': False,
    }
    try:
        from ..services import google_workspace
        connection = google_workspace.get_connection(organization_id)
        google = {
            **google,
            'connection': connection,
            'resources': google_workspace.list_resources(organization_id, limit=120),
            'meet_artifacts': google_workspace.list_meet_artifacts(organization_id, limit=80),
            'configured': bool(connection and connection.get('status') == 'connected'),
            **google_workspace.service_matrix(organization_id),
        }
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id::text AS id, nome AS name
                     FROM cadu_ci_projetos
                    WHERE id_cliente=%s AND status <> 'arquivado'
                 ORDER BY nome LIMIT 200""",
                (int(client_id),),
            )
            google['projects'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        # A migration may be rolled out after the application code. Keep the
        # account page usable and show the connection as not yet available.
        current_app.logger.info('Google Workspace ainda não está disponível nesta instalação', exc_info=True)
    return {
        'accounts': accounts,
        'connected_count': sum(str(item.get('status') or '').lower() in {'active', 'connected', 'ready'}
                               for item in accounts),
        'google': google,
        'slack_configured': bool(_slack_config('SLACK_CLIENT_ID') and _slack_config('SLACK_CLIENT_SECRET') and _slack_config('SLACK_SIGNING_SECRET')),
        'slack_connect_url': url_for('cadu_workspace.slack_connect'),
        # These are product capabilities, not tenant connections.  A connector
        # only becomes an account in the list above after its authorization is
        # completed in Reports, where credentials stay isolated from Workspace.
        'priority_connectors': (
            {
                'name': 'Canva', 'icon': 'fa-solid fa-wand-magic-sparkles',
                'summary': 'Leve kits de marca, criativos e aprovações para o mesmo fluxo de trabalho.',
                'scope': 'Criação e identidade',
            },
            {
                'name': 'Google Drive', 'icon': 'fa-brands fa-google-drive',
                'summary': 'Vincule pastas e arquivos de briefing à marca, ao projeto e às conversas.',
                'scope': 'Arquivos e contexto',
            },
            {
                'name': 'ERP da agência', 'icon': 'fa-solid fa-building-columns',
                'summary': 'Conecte jobs, clientes e aprovações da operação sem duplicar cadastros.',
                'scope': 'Operação e jobs',
            },
        ),
        'coming_soon_connectors': (
            {
                'name': 'ClickUp', 'icon': 'fa-solid fa-check-double',
                'summary': 'Tarefas, checklists e entregas conectados ao job.',
                'scope': 'Planejamento e execução',
            },
            {
                'name': 'Trello', 'icon': 'fa-brands fa-trello',
                'summary': 'Quadros visuais para acompanhar produção e aprovações.',
                'scope': 'Operação visual',
            },
            {
                'name': 'Slack', 'icon': 'fa-brands fa-slack',
                'summary': 'Alertas e contexto de projetos perto da equipe.',
                'scope': 'Comunicação e alertas',
            },
        ),
    }


def _workspace_host_only():
    expected = (urlparse(str(current_app.config.get("WORKSPACE_URL") or "")).hostname or "").lower()
    actual = request.host.split(":", 1)[0].lower()
    if actual not in {expected, "localhost", "127.0.0.1"}:
        abort(404)


def _workspace_api_csrf() -> bool:
    """Check the same session-bound token used by the Cadu chat APIs."""
    token = session.get('family_csrf')
    supplied = request.headers.get('X-CSRF-Token', '') or request.form.get('_csrf', '')
    return bool(token and secrets.compare_digest(token, supplied))


def _workspace_onboarding_table_available() -> bool:
    """Return whether the additive Workspace onboarding migration is ready."""
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.cadu_workspace_onboarding') AS relation")
            return bool((cursor.fetchone() or {}).get('relation'))
    except Exception:
        # The migration is deployed separately from the application. Existing
        # Workspace users must continue to access their account while it rolls
        # out, instead of being blocked by a progressive enhancement.
        current_app.logger.warning('Tabela de onboarding do Workspace indisponível', exc_info=True)
        try:
            get_db().rollback()
        except Exception:
            pass
        return False


def _workspace_onboarding_record(contact_id: int, client_id: int) -> Optional[dict]:
    """Load the setup record without changing the current client boundary."""
    if not contact_id or not client_id or not _workspace_onboarding_table_available():
        return None
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, contato_id, id_cliente, operation_type,
                          organization_name, client_name, brand_id,
                          project_id::text AS project_id, current_step, status,
                          metadata, created_at, updated_at, completed_at
                     FROM cadu_workspace_onboarding
                    WHERE contato_id=%s AND id_cliente=%s""",
                (contact_id, client_id),
            )
            row = cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        current_app.logger.warning('Não foi possível ler o onboarding do Workspace', exc_info=True)
        try:
            get_db().rollback()
        except Exception:
            pass
        return None


def _workspace_onboarding_form(record: Optional[dict] = None) -> dict:
    """Build a safe form state from the existing organization and setup row."""
    values = dict((record or {}).get('metadata') or {})
    operation_type = str((record or {}).get('operation_type') or values.get('operation_type') or 'client')
    if operation_type not in {'client', 'agency'}:
        operation_type = 'client'
    return {
        'operation_type': operation_type,
        'organization_name': str((record or {}).get('organization_name') or values.get('organization_name') or ''),
        'client_name': str((record or {}).get('client_name') or values.get('client_name') or ''),
        'brand_name': str(values.get('brand_name') or ''),
        'website_url': str(values.get('website_url') or ''),
        'project_name': str(values.get('project_name') or ''),
        'project_description': str(values.get('project_description') or ''),
    }


def _workspace_onboarding_render(form: dict, *, error: str = '', organization: Optional[dict] = None, status_code: int = 200):
    """Render the compact setup flow while retaining submitted values."""
    response = render_template(
        'cadu_workspace/onboarding.html',
        form=form,
        error=error,
        organization=organization or {},
    )
    return response, status_code


def _dock_shortcuts_available() -> bool:
    """Allow the Workspace to keep rendering while the migration is rolling out."""
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.cadu_workspace_dock_shortcuts') AS relation")
            return bool((cursor.fetchone() or {}).get('relation'))
    except Exception:
        # The dock is a progressive enhancement. A stale connection or a
        # partially applied migration must never take down the Workspace home.
        current_app.logger.warning('Workspace dock indisponível; seguindo sem atalhos pessoais', exc_info=True)
        return False


def _user_dock_shortcuts(client_id: int, user_id: int) -> list[dict]:
    """Explicit preferences only; automatic shortcuts are never persisted."""
    try:
        if not _dock_shortcuts_available():
            return []
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT id::text, shortcut_type, target_ref, project_ref, brand_ref,
                                     position, metadata
                                FROM cadu_workspace_dock_shortcuts
                               WHERE client_id=%s AND user_id=%s
                            ORDER BY position, updated_at DESC""", (client_id, user_id))
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        # Personal shortcuts are not required to render the home surface. Keep
        # the suggested dock available while the database catches up.
        current_app.logger.warning('Workspace dock pessoal não pôde ser carregada', exc_info=True)
        return []


def _dock_visual_variant(kind: str, value: object) -> int:
    """Pick one of the fixed avatar treatments without storing presentation state."""
    digest = sha256(f'{kind}:{value}'.encode('utf-8')).digest()
    return int.from_bytes(digest[:2], 'big') % 10


_DOCK_RESOURCE_KINDS = {'resource', 'file', 'image', 'artifact', 'video', 'media_plan', 'report', 'analysis', 'link'}


def _workspace_dock_resource_items(client_id: int, project_rows: list[dict]) -> list[dict]:
    """Build launchable resource entries without putting them in the dock by default."""
    projects_by_ref = {f"ci:{row.get('id')}": row for row in project_rows if row.get('id')}
    try:
        resources = project_resource_service.list_recent_resources(client_id, list(projects_by_ref), limit=80)
    except Exception:
        current_app.logger.warning('Não foi possível carregar recursos para a dock do cliente %s', client_id, exc_info=True)
        return []
    items = []
    for resource in resources:
        resource_ref = str(resource.get('id') or '').strip()
        project_ref = str(resource.get('project_ref') or '').strip()
        project_id = project_ref[3:] if project_ref.startswith('ci:') else ''
        if not resource_ref or not project_id or project_ref not in projects_by_ref:
            continue
        resource_type = str(resource.get('resource_type') or 'resource').strip().lower()
        title = str(resource.get('title') or 'Recurso')
        locator = str(resource.get('locator') or '').strip()
        preview = locator if resource_type == 'image' and urlparse(locator).scheme in {'http', 'https'} else ''
        project = projects_by_ref[project_ref]
        items.append({
            'id': f'resource:{resource_ref}', 'kind': 'resource', 'title': title,
            'name': title, 'resourceRef': resource_ref, 'resourceType': resource_type,
            'projectRef': project_ref, 'projectName': str(project.get('nome') or 'Projeto'),
            'href': url_for('cadu_workspace.clean_project_detail', project_id=project_id, resource=resource_ref),
            'previewUrl': preview, 'visualInitials': resource_type[:2].upper(),
            'visualColor': str(project.get('thumbnail_color') or project.get('cor') or '#176b5e'),
        })
    return items


def _workspace_common_dock_items(client_id: int, user_id: int, *, projects: Optional[list[dict]] = None,
                                  brands: Optional[list[dict]] = None) -> list[dict]:
    """Return the one shared visual dock used by every Workspace surface.

    Pages may add their own secondary navigation, but the dock itself is a
    persistent workspace shelf. Keeping its catalog here prevents account,
    conversation and legacy pages from replacing projects and brands with
    page-specific links.
    """
    project_rows = _workspace_projects(client_id) if projects is None else projects
    brand_rows = _workspace_brands(client_id) if brands is None else brands
    brand_project_counts: dict[str, int] = {}
    try:
        project_brand_links = family_repository.project_brand_links(client_id)
    except Exception:
        current_app.logger.warning('Não foi possível carregar contagens de vínculos de marcas do cliente %s', client_id, exc_info=True)
        project_brand_links = []
    for link in project_brand_links:
        brand_ref = str(link.get('brand_ref') or '')
        if brand_ref.startswith('studio:'):
            brand_project_counts[brand_ref] = brand_project_counts.get(brand_ref, 0) + 1
    # A brand logo can be resolved while attaching project identity even when
    # the brand row itself has no direct display_logo. Reuse that canonical
    # project-linked mark so the shared dock never regresses to initials.
    brand_logo_by_name: dict[str, str] = {}
    for project in project_rows:
        brand_name = str(project.get('thumbnail_label') or '').casefold()
        brand_logo = str(project.get('brand_logo_url') or '').strip()
        if brand_name and brand_logo:
            brand_logo_by_name.setdefault(brand_name, brand_logo)

    brand_items = [{
        'id': str(item.get('id')), 'kind': 'brand', 'title': str(item.get('name') or 'Marca'),
        'name': str(item.get('name') or 'Marca'),
        'logoUrl': str(item.get('display_logo') or brand_logo_by_name.get(str(item.get('name') or '').casefold()) or ''),
        'visualInitials': str(item.get('display_initials') or 'M'),
        'visualColor': str(item.get('display_color') or item.get('primary_color') or '#176b5e'),
        'visualVariant': _dock_visual_variant('brand', item.get('id')),
        'href': url_for('cadu_workspace.clean_brand_detail', brand_id=int(item.get('id'))),
        'brandRef': f"studio:{item.get('id')}",
        'projectCount': brand_project_counts.get(f"studio:{item.get('id')}", 0),
    } for item in brand_rows]
    # Keep logo-less brands in the shared dock too; React supplies the stable
    # initials/gradient identity when no custom mark is available.
    project_items = [{
        'id': f"ci:{item.get('id')}", 'kind': 'project', 'title': str(item.get('nome') or 'Projeto'),
        'name': str(item.get('nome') or 'Projeto'), 'href': url_for('cadu_workspace.clean_project_detail', project_id=str(item.get('id'))),
        'previewUrl': str(item.get('thumbnail_url') or item.get('brand_logo_url') or ''), 'projectRef': f"ci:{item.get('id')}",
        'logoUrl': str(item.get('brand_logo_url') or ''),
        'brandName': str(item.get('thumbnail_label') or ''),
        'visualInitials': str(item.get('thumbnail_initials') or 'P'),
        'visualColor': str(item.get('thumbnail_color') or item.get('cor') or '#176b5e'),
        'visualVariant': _dock_visual_variant('project', item.get('id')),
    } for item in project_rows]
    resource_items = _workspace_dock_resource_items(client_id, project_rows)

    catalog = {('brand', item['id']): item for item in brand_items}
    catalog.update({('project', item['projectRef']): item for item in project_items})
    catalog.update({('resource', item['resourceRef']): item for item in resource_items})
    explicit = []
    for row in _user_dock_shortcuts(client_id, user_id):
        key = (row['shortcut_type'], row['target_ref'])
        if key not in catalog and row['shortcut_type'] in _DOCK_RESOURCE_KINDS:
            key = ('resource', row['target_ref'])
        item = catalog.get(key)
        if item:
            explicit.append({**item, 'shortcutId': row['id'], 'pinned': True})
    if explicit:
        return explicit[:8]
    # Before the user personalizes the dock, show only a small brand shelf.
    # Projects enter the dock through an explicit shortcut, never by catalog size.
    return brand_items[:3]


@bp.get('/workspace/api/dock/shortcuts')
@login_required
def list_dock_shortcuts():
    return jsonify(shortcuts=_user_dock_shortcuts(int(session.get('cliente_id') or 0), int(session.get('user_id') or 0)))


def _authorized_dock_target(client_id: int, kind: str, target_ref: str) -> Optional[dict]:
    if kind == 'project':
        return next((item for item in _workspace_projects(client_id, status='todos')
                     if f"ci:{item.get('id')}" == target_ref), None)
    if kind == 'brand':
        return next((item for item in _workspace_brands(client_id)
                     if str(item.get('id')) == target_ref
                     and str(item.get('display_logo') or item.get('resolved_logo_path')
                               or item.get('logo_upload_path') or item.get('logo_url') or '').strip()), None)
    if kind == 'resource':
        try:
            with get_db().cursor() as cursor:
                cursor.execute("""SELECT id::text, project_ref, resource_type, title, locator
                                   FROM cadu_project_resources
                                  WHERE id=%s AND client_id=%s AND status <> 'archived'""",
                               (target_ref, client_id))
                row = cursor.fetchone()
            return dict(row) if row else None
        except Exception:
            connection = getattr(g, 'db', None)
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
            current_app.logger.warning('Não foi possível autorizar o recurso %s para a dock', target_ref, exc_info=True)
    return None


@bp.post('/workspace/api/dock/shortcuts')
@login_required
def save_dock_shortcut():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    if not _dock_shortcuts_available():
        abort(409, description='Os atalhos ainda estão sendo atualizados. Atualize a página em instantes.')
    payload = request.get_json(silent=True) or {}
    kind = str(payload.get('shortcut_type') or '').strip().lower()
    target_ref = str(payload.get('target_ref') or '').strip()[:500]
    if kind in _DOCK_RESOURCE_KINDS:
        kind = 'resource'
    if kind not in {'brand', 'project', 'resource'} or not target_ref:
        abort(400, description='Atalho inválido.')
    client_id, user_id = int(session.get('cliente_id') or 0), int(session.get('user_id') or 0)
    authorized_target = _authorized_dock_target(client_id, kind, target_ref)
    if not authorized_target:
        abort(403, description='O item não pertence à sua agência ou não está disponível para a dock.')
    project_ref = str(authorized_target.get('project_ref') or payload.get('project_ref') or '')[:500] or None
    brand_ref = str(authorized_target.get('brand_ref') or payload.get('brand_ref') or '')[:500] or None
    metadata = json.dumps(payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {})
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            # Do not rely on a particular name for the legacy unique index. Some
            # installations created the dock table before the named conflict
            # target was present; a target-less conflict clause works with any
            # unique constraint on the table and keeps the action idempotent.
            cursor.execute("""INSERT INTO cadu_workspace_dock_shortcuts
                    (id,client_id,user_id,shortcut_type,target_ref,project_ref,brand_ref,position,metadata,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,
                        COALESCE((SELECT MAX(position)+1 FROM cadu_workspace_dock_shortcuts WHERE client_id=%s AND user_id=%s),0),
                        %s,NOW(),NOW())
                ON CONFLICT DO UPDATE
                    SET project_ref=EXCLUDED.project_ref,brand_ref=EXCLUDED.brand_ref,metadata=EXCLUDED.metadata,updated_at=NOW()
                RETURNING id::text,shortcut_type,target_ref,project_ref,brand_ref,position,metadata""",
                (str(uuid4()), client_id, user_id, kind, target_ref, project_ref, brand_ref,
                 client_id, user_id, metadata))
            row = cursor.fetchone()
            if not row:
                raise RuntimeError('O banco não retornou o atalho salvo.')
            shortcut = dict(row)
        connection.commit()
    except Exception:
        connection.rollback()
        current_app.logger.exception('Falha ao salvar atalho da dock: tipo=%s alvo=%s', kind, target_ref)
        abort(503, description='Não foi possível salvar este atalho agora. Tente novamente.')
    return jsonify(shortcut=shortcut), 201


@bp.delete('/workspace/api/dock/shortcuts/<uuid:shortcut_id>')
@login_required
def delete_dock_shortcut(shortcut_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    if not _dock_shortcuts_available():
        abort(409, description='Os atalhos ainda estão sendo atualizados. Atualize a página em instantes.')
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM cadu_workspace_dock_shortcuts WHERE id=%s AND client_id=%s AND user_id=%s',
                           (str(shortcut_id), int(session.get('cliente_id') or 0), int(session.get('user_id') or 0)))
            found = cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        current_app.logger.exception('Falha ao remover atalho da dock: %s', shortcut_id)
        abort(503, description='Não foi possível remover este atalho agora. Tente novamente.')
    if not found:
        abort(404, description='Atalho não encontrado.')
    return '', 204


@bp.post('/workspace/api/dock/shortcuts/order')
@login_required
def reorder_dock_shortcuts():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    if not _dock_shortcuts_available():
        abort(409, description='Os atalhos ainda estão sendo atualizados. Atualize a página em instantes.')
    values = (request.get_json(silent=True) or {}).get('ids')
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        abort(400, description='Ordem de atalhos inválida.')
    if len(values) > 32 or len(values) != len(set(values)):
        abort(400, description='Ordem de atalhos inválida.')
    client_id, user_id = int(session.get('cliente_id') or 0), int(session.get('user_id') or 0)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id::text FROM cadu_workspace_dock_shortcuts WHERE client_id=%s AND user_id=%s FOR UPDATE',
                           (client_id, user_id))
            expected = {row['id'] for row in cursor.fetchall()}
            if expected != set(values):
                abort(400, description='Envie a lista completa dos seus atalhos para reorganizá-los.')
            for position, shortcut_id in enumerate(values):
                cursor.execute("""UPDATE cadu_workspace_dock_shortcuts
                                 SET position=%s,updated_at=NOW()
                               WHERE id=%s AND client_id=%s AND user_id=%s""",
                             (position, shortcut_id, client_id, user_id))
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Falha ao ordenar atalhos da dock')
        abort(503, description='Não foi possível reorganizar os atalhos agora. Tente novamente.')
    return jsonify(shortcuts=_user_dock_shortcuts(client_id, user_id))


_WORKSPACE_HOME_WIDGETS = ('resume', 'next', 'projects', 'brands', 'activity', 'usage')


def _home_preferences_available() -> bool:
    """Keep the Home usable while its additive preference migration rolls out."""
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.cadu_workspace_home_preferences') AS relation")
            return bool((cursor.fetchone() or {}).get('relation'))
    except Exception:
        current_app.logger.warning('Preferências da Home indisponíveis; usando padrão', exc_info=True)
        return False


def _user_home_preferences(client_id: int, user_id: int) -> dict:
    """Read the signed-in user's durable Home layout preference."""
    if not _home_preferences_available():
        return {}
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT widget_order, visible_widgets
                     FROM cadu_workspace_home_preferences
                    WHERE client_id=%s AND user_id=%s""",
                (client_id, user_id),
            )
            row = cursor.fetchone()
        if not row:
            return {}
        order = row.get('widget_order') if isinstance(row.get('widget_order'), list) else []
        visible = row.get('visible_widgets') if isinstance(row.get('visible_widgets'), list) else []
        return {'order': order, 'visible': visible}
    except Exception:
        current_app.logger.warning('Preferências da Home não puderam ser carregadas', exc_info=True)
        return {}


def _validated_home_preferences(payload: dict) -> tuple[list[str], list[str]]:
    order = payload.get('order')
    visible = payload.get('visible')
    allowed = set(_WORKSPACE_HOME_WIDGETS)
    if (not isinstance(order, list) or any(not isinstance(item, str) for item in order)
            or set(order) != allowed or len(order) != len(_WORKSPACE_HOME_WIDGETS)):
        abort(400, description='A ordem dos blocos da Home é inválida.')
    if (not isinstance(visible, list) or any(not isinstance(item, str) or item not in allowed for item in visible)
            or len(visible) != len(set(visible))):
        abort(400, description='A visibilidade dos blocos da Home é inválida.')
    return [str(item) for item in order], [str(item) for item in visible]


@bp.get('/workspace/api/home/preferences')
@login_required
def get_home_preferences():
    client_id, user_id = int(session.get('cliente_id') or 0), int(session.get('user_id') or 0)
    return jsonify(preferences=_user_home_preferences(client_id, user_id))


@bp.put('/workspace/api/home/preferences')
@login_required
def save_home_preferences():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    if not _home_preferences_available():
        abort(409, description='As preferências da Home ainda estão sendo atualizadas. Atualize a página em instantes.')
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        abort(400, description='Envie as preferências da Home em formato JSON.')
    order, visible = _validated_home_preferences(payload)
    client_id, user_id = int(session.get('cliente_id') or 0), int(session.get('user_id') or 0)
    connection = get_db()
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO cadu_workspace_home_preferences
                    (id, client_id, user_id, widget_order, visible_widgets, created_at, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, NOW(), NOW())
                ON CONFLICT (client_id, user_id) DO UPDATE
                    SET widget_order=EXCLUDED.widget_order,
                        visible_widgets=EXCLUDED.visible_widgets,
                        updated_at=NOW()
                RETURNING widget_order, visible_widgets""",
            (str(uuid4()), client_id, user_id, json.dumps(order), json.dumps(visible)),
        )
        saved = cursor.fetchone() or {}
    connection.commit()
    return jsonify(preferences={'order': saved.get('widget_order') or order, 'visible': saved.get('visible_widgets') or visible})


@bp.get('/workspace/api/creditos/resumo')
@login_required
def workspace_credit_summary():
    """Expose the live, lot-based balance for read-only Workspace cues."""
    return jsonify(credit_position(int(session.get('cliente_id') or 0)))


def _workspace_team_admin() -> None:
    if session.get('user_type') not in {'admin', 'superadmin'}:
        abort(403, description='Somente administradores podem gerenciar acessos da organização.')


def _normalized_website_url(value: str, *, required: bool = False) -> str:
    """Accept a normal domain and retain only a usable public web URL."""
    url = str(value or '').strip()[:2000]
    if url and not re.match(r'^https?://', url, re.I):
        if re.match(r'^[a-z][a-z0-9+.-]*:', url, re.I):
            abort(400, description='Informe uma URL http ou https válida.')
        url = 'https://' + url.lstrip('/')
    if not url:
        if required:
            abort(400, description='Informe o site oficial da marca.')
        return ''
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        abort(400, description='Informe um domínio válido, como centralcomm.media.')
    return url


def _workspace_brand_form() -> dict:
    """Normalize the small, durable identity contract owned by Workspace."""
    website_url = _normalized_website_url(request.form.get('website_url') or '')
    name = ' '.join((request.form.get('name') or '').split())[:150]
    name_autogenerated = False
    if len(name) < 2 and website_url:
        host = (urlparse(website_url).hostname or '').removeprefix('www.')
        name = re.sub(r'[-_.]+', ' ', host.split('.')[0]).title()[:150]
        name_autogenerated = True
    if len(name) < 2:
        abort(400, description='Informe o site oficial ou um nome de marca com ao menos dois caracteres.')
    colors = {}
    for field in ('primary_color', 'secondary_color'):
        value = (request.form.get(field) or '').strip()
        if value and not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            abort(400, description='Use cores no formato hexadecimal, como #176B5E.')
        colors[field] = value or None

    values = [
        ' '.join(item.split())[:160]
        for item in (request.form.get('brand_values') or '').splitlines()
        if item.strip()
    ][:12]
    palette = []
    for index, raw_line in enumerate((request.form.get('color_palette') or '').splitlines()[:8]):
        parts = [part.strip() for part in raw_line.split('|')]
        match = re.search(r'#[0-9a-fA-F]{6}', parts[0] if parts else '')
        if not match:
            continue
        color = match.group(0).upper()
        palette.append({
            'hex': color,
            'name': (parts[1] if len(parts) > 1 else f'Cor {index + 1}')[:80],
            'role': (parts[2] if len(parts) > 2 else ('primary' if index == 0 else 'accent' if index == 1 else 'support'))[:32],
            'source': 'manual',
            'confidence': 1.0,
        })
    selected_fonts = [
        (role, ' '.join((request.form.get(f'font_{role}') or '').split())[:100])
        for role in ('display', 'body', 'accent', 'legal')
    ]
    fonts = []
    for role, family in selected_fonts:
        if family:
            fonts.append({'role': role, 'family': family, 'classification': '', 'weight': '', 'source': 'manual', 'confidence': 1.0})
    for index, raw_line in enumerate((request.form.get('fonts') or '').splitlines()[:6]):
        parts = [part.strip() for part in raw_line.split('|')]
        if len(parts) >= 2:
            role, family = parts[0].lower()[:24], parts[1][:100]
            classification = parts[2][:100] if len(parts) > 2 else ''
            weight = parts[3][:32] if len(parts) > 3 else ''
        else:
            role, family, classification, weight = ('display' if index == 0 else 'body'), (parts[0] if parts else '')[:100], '', ''
        if not family:
            continue
        candidate = {
            'role': role if role in {'display', 'body', 'accent', 'legal', 'ui'} else 'body',
            'family': family,
            'classification': classification,
            'weight': weight,
            'source': 'manual',
            'confidence': 1.0,
        }
        if not any(item['role'] == candidate['role'] and item['family'].lower() == candidate['family'].lower() for item in fonts):
            fonts.append(candidate)
    return {
        'name': name,
        'sector': ' '.join((request.form.get('sector') or '').split())[:80] or None,
        'website_url': website_url or None,
        'primary_color': colors['primary_color'],
        'secondary_color': colors['secondary_color'],
        'profile': {
            'tone_of_voice': (request.form.get('tone_of_voice') or '').strip()[:4000],
            'target_audience': (request.form.get('target_audience') or '').strip()[:4000],
            'positioning': (request.form.get('positioning') or '').strip()[:4000],
            'brand_values': values,
            'color_palette': palette,
            'fonts': fonts,
            'name_autogenerated': name_autogenerated,
        },
    }


def _cadu_area(config_key: str, path: str) -> str:
    return str(current_app.config.get(config_key) or product_url("cadu", path))


def _workspace_brands(client_id: int, query: str = "", *, raise_on_error: bool = False) -> list[dict]:
    """Read brand records owned by the active Workspace organization."""
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT c.id, c.crm_client_id, c.name, c.sector, c.tone_of_voice, c.website_url, c.primary_color,
                          c.secondary_color, c.logo_url, c.logo_upload_path,
                          COALESCE(c.logo_upload_path, c.logo_url, (
                              SELECT COALESCE(a_logo.asset_path, a_logo.source_url)
                                FROM cx_client_brand_assets a_logo
                               WHERE a_logo.client_id = c.id
                                 AND a_logo.role = 'logo'
                                 AND a_logo.status = 'approved'
                            ORDER BY a_logo.is_primary DESC, a_logo.score DESC NULLS LAST, a_logo.id DESC
                               LIMIT 1
                          )) AS resolved_logo_path, c.brand_profile,
                          c.analysis_metadata, c.created_at AS updated_at,
                          COUNT(a.id) FILTER (WHERE a.status = 'approved') AS asset_count,
                          COUNT(a.id) FILTER (WHERE a.role = 'logo' AND a.status = 'approved') AS has_logo
                     FROM cx_clients c
                LEFT JOIN cx_client_brand_assets a ON a.client_id = c.id
                    WHERE c.crm_client_id = %s
                      AND c.name ILIKE %s
                 GROUP BY c.id
                 ORDER BY c.created_at DESC NULLS LAST, c.name""",
                (client_id, '%' + query[:100] + '%'),
            )
            brands = [dict(row) for row in cursor.fetchall()]
            for brand in brands:
                for field in ('brand_profile', 'analysis_metadata'):
                    if isinstance(brand.get(field), str):
                        try:
                            brand[field] = json.loads(brand[field])
                        except (TypeError, ValueError):
                            brand[field] = {}
                    elif not isinstance(brand.get(field), dict):
                        brand[field] = {}
                name = str(brand.get('name') or '').strip()
                brand['display_logo'] = public_logo(brand.get('resolved_logo_path'))
                seed_visuals = brand['brand_profile'].get('seed_visuals') or {}
                # Project headers need the same approved art direction used by
                # the brand dossier. The previous thumbnail-only lookup often
                # returned nothing even when the brand had a hero visual.
                brand['visual_hero'] = public_logo(seed_visuals.get('hero') or seed_visuals.get('thumbnail')) if isinstance(seed_visuals, dict) else ''
                brand['visual_thumbnail'] = brand['visual_hero']
                analysis = brand.get('analysis_metadata') or {}
                brand['display_summary'] = (
                    brand['brand_profile'].get('brand_summary')
                    or brand['brand_profile'].get('positioning')
                    or analysis.get('brand_summary')
                    or analysis.get('positioning')
                    or ''
                )
                brand['display_initials'] = ''.join(
                    word[0] for word in re.findall(r"[\wÀ-ÿ]+", name)[:2]
                ).upper() or 'M'
                brand['display_color'] = brand.get('primary_color') or '#176b5e'
            return brands
    except Exception:
        if raise_on_error:
            raise
        # The brand catalog must not disappear just because the optional
        # assets table/query is unavailable during a deploy or migration. The
        # ownership boundary is still the CRM client id; this fallback only
        # omits asset counts and logo enrichment and lets the UI render the
        # brand identity with initials.
        current_app.logger.warning(
            'Consulta enriquecida de marcas falhou para o cliente %s; usando catálogo básico por crm_client_id',
            client_id,
            exc_info=True,
        )
        try:
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT id, crm_client_id, name, sector, tone_of_voice,
                              website_url, primary_color, secondary_color,
                              logo_url, logo_upload_path, brand_profile,
                              analysis_metadata, created_at AS updated_at
                         FROM cx_clients
                        WHERE crm_client_id = %s
                          AND name ILIKE %s
                     ORDER BY created_at DESC NULLS LAST, name""",
                    (client_id, '%' + query[:100] + '%'),
                )
                brands = []
                for row in cursor.fetchall():
                    brand = dict(row)
                    for field in ('brand_profile', 'analysis_metadata'):
                        if isinstance(brand.get(field), str):
                            try:
                                brand[field] = json.loads(brand[field])
                            except (TypeError, ValueError):
                                brand[field] = {}
                        elif not isinstance(brand.get(field), dict):
                            brand[field] = {}
                    name = str(brand.get('name') or '').strip()
                    brand['display_logo'] = public_logo(brand.get('logo_upload_path') or brand.get('logo_url'))
                    brand['visual_hero'] = ''
                    brand['visual_thumbnail'] = ''
                    analysis = brand.get('analysis_metadata') or {}
                    brand['display_summary'] = (
                        brand['brand_profile'].get('brand_summary')
                        or brand['brand_profile'].get('positioning')
                        or analysis.get('brand_summary')
                        or analysis.get('positioning')
                        or ''
                    )
                    brand['display_initials'] = ''.join(
                        word[0] for word in re.findall(r"[\wÀ-ÿ]+", name)[:2]
                    ).upper() or 'M'
                    brand['display_color'] = brand.get('primary_color') or '#176b5e'
                    brand['asset_count'] = 0
                    brand['has_logo'] = 1 if brand['display_logo'] else 0
                    brands.append(brand)
                return brands
        except Exception:
            current_app.logger.warning(
                'Consulta básica de marcas também falhou para o cliente %s',
                client_id,
                exc_info=True,
            )
            return []


def _workspace_brand(client_id: int, brand_id: int) -> Optional[dict]:
    brands = _workspace_brands(client_id)
    brand = next((item for item in brands if int(item['id']) == brand_id), None)
    if not brand:
        return None
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, role, source_kind, source_url, page_url, asset_path,
                          mime_type, width, height, score, status, is_primary,
                          metadata, created_at
                     FROM cx_client_brand_assets
                    WHERE client_id = %s
                 ORDER BY is_primary DESC, score DESC NULLS LAST, id DESC""",
                (brand_id,),
            )
            brand['assets'] = [dict(row) for row in cursor.fetchall()]
            for asset in brand['assets']:
                asset['display_url'] = public_logo(asset.get('asset_path') or asset.get('source_url'))
                if isinstance(asset.get('metadata'), str):
                    try:
                        asset['metadata'] = json.loads(asset['metadata'])
                    except (TypeError, ValueError):
                        asset['metadata'] = {}
                elif not isinstance(asset.get('metadata'), dict):
                    asset['metadata'] = {}
    except Exception:
        brand['assets'] = []
    for field in ('brand_profile', 'analysis_metadata'):
        value = brand.get(field)
        if isinstance(value, str):
            try:
                brand[field] = json.loads(value)
            except (TypeError, ValueError):
                brand[field] = {}
        elif not isinstance(value, dict):
            brand[field] = {}
    profile = brand['brand_profile']
    seed_visuals = profile.get('seed_visuals') if isinstance(profile.get('seed_visuals'), dict) else {}
    brand['seed_visuals'] = {key: public_logo(value) for key, value in seed_visuals.items() if value}
    if isinstance(profile.get('brand_values'), str):
        profile['brand_values'] = [
            item.strip() for item in re.split(r'[\n,;]+', profile['brand_values']) if item.strip()
        ]
    identity_fields = ('tone_of_voice', 'target_audience', 'positioning', 'brand_values')
    identity_total = sum(bool(profile.get(field)) for field in identity_fields)
    score = round((identity_total / len(identity_fields)) * 55)
    score += 25 if brand.get('analysis_metadata') else 0
    score += 10 if brand.get('has_logo') else 0
    score += 10 if brand.get('assets') else 0
    missing = []
    if not brand.get('has_logo'):
        missing.append('logo principal')
    if not brand.get('analysis_metadata'):
        missing.append('auditoria de marca')
    if identity_total < len(identity_fields):
        missing.append('diretrizes de identidade')
    brand['readiness'] = {'score': score, 'missing': missing}
    brand['activity'] = sorted((
        {'title': 'Ativo registrado', 'detail': item.get('role') or 'Ativo de marca', 'at': item.get('created_at')}
        for item in brand['assets'] if item.get('created_at')
    ), key=lambda item: str(item['at']), reverse=True)[:6]
    return brand


def _merge_brand_analysis(brand: dict, analysis: dict) -> dict:
    """Add extracted evidence without overwriting choices already reviewed by people."""
    profile = dict(brand.get('brand_profile') or {})
    field_map = {
        'brand_summary': 'brand_summary',
        'tone_of_voice': 'tone_of_voice',
        'target_audience': 'target_audience',
        'audience_segments': 'audience_segments',
        'personas': 'personas',
        'archetype': 'archetype',
        'ad_segments': 'ad_segments',
        'creative_guidelines': 'creative_guidelines',
        'campaign_opportunities': 'campaign_opportunities',
        'products_services': 'products_services',
        'differentiators': 'differentiators',
        'proof_points': 'proof_points',
        'visual_motifs': 'visual_motifs',
        'mandatory_elements': 'mandatory_elements',
        'forbidden_elements': 'forbidden_elements',
        'color_palette': 'color_palette',
        'fonts': 'fonts',
    }
    for source, target in field_map.items():
        current = profile.get(target)
        if current in (None, '', [] , {}):
            candidate = analysis.get(source)
            if candidate not in (None, '', [], {}):
                profile[target] = candidate
    metadata = dict(brand.get('analysis_metadata') or {})
    metadata.update(analysis.get('analysis_metadata') or {})
    return {'profile': profile, 'metadata': metadata}


def _brand_audit_public_error(value) -> str:
    """Keep implementation exceptions out of the brand-facing audit UI."""
    message = str(value or '').strip()
    technical_markers = ('cannot access local variable', 'unboundlocalerror', 'traceback')
    if not message or any(marker in message.lower() for marker in technical_markers):
        return 'O processamento foi interrompido antes de concluir a proposta. Tente novamente; nenhuma informação da marca foi alterada.'
    return message[:360]


def _brand_review_pack(brand: dict) -> dict:
    """Normalize the pending/approved analysis contract stored with a brand."""
    metadata = brand.get('analysis_metadata') or {}
    pack = metadata.get('review_pack') if isinstance(metadata, dict) else {}
    if not isinstance(pack, dict):
        pack = {}
    reviews = [item for item in pack.get('reviews', []) if isinstance(item, dict)]
    return {
        'status': str(pack.get('status') or 'not_started'),
        'job_id': pack.get('job_id'),
        'stage': str(pack.get('stage') or ''),
        'index': int(pack.get('index') or 0),
        'total': int(pack.get('total') or 4),
        'message': str(pack.get('message') or ''),
        'error': _brand_audit_public_error(pack.get('error')) if pack.get('status') == 'failed' else '',
        'input': pack.get('input') if isinstance(pack.get('input'), dict) else {},
        'created_at': pack.get('created_at'),
        'updated_at': pack.get('updated_at'),
        'approved_at': pack.get('approved_at'),
        'reviews': reviews[:3],
        'analysis': pack.get('analysis') if isinstance(pack.get('analysis'), dict) else {},
    }


def _brand_analysis_proposal(analysis: dict) -> dict:
    """Keep only the reviewable proposal, not scrape candidates or provider traces."""
    allowed = {
        'name', 'sector', 'website_url', 'brand_summary', 'tone_of_voice',
        'primary_color', 'secondary_color', 'color_palette', 'logo_url',
        'target_audience', 'audience_segments', 'personas', 'archetype',
        'products_services', 'differentiators', 'proof_points',
        'ad_segments', 'creative_guidelines', 'campaign_opportunities',
        'visual_motifs', 'mandatory_elements', 'forbidden_elements', 'fonts',
        'confidence', 'sources', 'social_links',
    }
    return {key: value for key, value in analysis.items() if key in allowed}


def _ensure_brand_audit_credit(client_id: int) -> None:
    """Avoid starting a paid provider workflow when the client has no balance."""
    # This is a read-only preflight. A request can occasionally inherit a
    # connection interrupted between page load and submission, so discard that
    # request connection and retry once before preventing the whole import.
    # The paid job still uses the same ledger authorization when it runs.
    for attempt in range(2):
        try:
            # Brand audits are a Workspace entry point, but their balance must
            # be read through the same connector used when the provider is
            # charged. Reading the ledger here directly had left this flow
            # outside the shared credit contract.
            available = CaduCreditConnector().balance(client_id)
            break
        except Exception:
            if attempt == 1:
                current_app.logger.exception('Não foi possível consultar créditos para auditoria de marca')
                abort(503, description='Não foi possível consultar os créditos da organização agora.')
            current_app.logger.warning('Falha transitória ao consultar créditos para auditoria de marca; tentando novamente.')
            try:
                get_db().rollback()
            except Exception:
                pass
            close_db()
    if available <= 0:
        abort(409, description='Não há créditos disponíveis para analisar esta marca. Abra Créditos e consumo para verificar ou comprar um novo lote.')


def _brand_audit_credit_gate(client_id: int):
    """Keep a useful credit message when the audit form submits with fetch."""
    try:
        _ensure_brand_audit_credit(client_id)
    except HTTPException as exc:
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'ok': False, 'error': exc.description}), exc.code
        raise
    return None


def _brand_review_is_stale(pack: dict) -> bool:
    """A web worker cannot survive a process restart; make that recoverable."""
    if pack.get('status') not in {'queued', 'running'}:
        return False
    value = str(pack.get('updated_at') or pack.get('created_at') or '')
    try:
        updated = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - updated > timedelta(minutes=15)


def _save_brand_review_job(client_id: int, brand_id: int, job_id: str, **changes) -> bool:
    """Atomically update the current job without letting an older worker win."""
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT analysis_metadata FROM cx_clients
                     WHERE id = %s AND crm_client_id = %s FOR UPDATE""",
                (brand_id, client_id),
            )
            row = cursor.fetchone()
            if not row:
                connection.rollback()
                return False
            metadata = row.get('analysis_metadata') if isinstance(row, dict) else row[0]
            if isinstance(metadata, str):
                metadata = json.loads(metadata or '{}')
            metadata = dict(metadata or {})
            current = dict(metadata.get('review_pack') or {})
            if current.get('job_id') != job_id:
                connection.rollback()
                return False
            analysis_metadata = changes.pop('analysis_metadata', None)
            if isinstance(analysis_metadata, dict):
                # These are useful audit metrics, while the proposed identity
                # remains inside review_pack until a human approves it.
                metadata.update(analysis_metadata)
            current.update(changes)
            current['updated_at'] = _utc_timestamp()
            metadata['review_pack'] = current
            cursor.execute(
                """UPDATE cx_clients SET analysis_metadata = %s::jsonb
                     WHERE id = %s AND crm_client_id = %s""",
                (json.dumps(metadata), brand_id, client_id),
            )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise


def _start_brand_review_job(client_id: int, user_id: int, brand_id: int, job_id: str, website_url: str, images: list[dict], proposal=None, *, background=True):
    """Run an audit now or enqueue it for the durable Workspace worker.

    ``background=False`` is intentionally used only by the worker.  It keeps
    the provider work in the durable job's process instead of creating a child
    thread that would disappear when a one-shot worker exits.
    """
    app = current_app._get_current_object()

    def runner():
        with app.app_context():
            try:
                _save_brand_review_job(client_id, brand_id, job_id,
                    status='running', stage='evidence', index=1, total=4,
                    message='Organizando evidências oficiais.', error='')
                restored_images = [
                    FileStorage(stream=BytesIO(item['content']), filename=item['filename'], content_type=item.get('content_type'))
                    for item in images
                ]
                from ..creative_modeling_service import CreativeModelingService
                from ..cadu_credit_connector import CaduCreditConnector, CreditActor
                service = CreativeModelingService()
                credits = CaduCreditConnector()
                actor = CreditActor.from_values(client_id, user_id)

                def bill(stage, provider_result, model):
                    """One durable, idempotent ledger movement per provider call."""
                    credits.charge_provider(
                        actor=actor, idempotency_key=f'workspace-brand:{job_id}:{stage}',
                        app='Auditoria de marca', stage=stage,
                        provider_result=provider_result, model=model,
                        metadata={'brand_id': brand_id, 'job_id': job_id, 'source': 'workspace'},
                    )

                analysis_metadata = {}
                review_proposal = dict(proposal) if isinstance(proposal, dict) else {}
                if isinstance(review_proposal, dict) and review_proposal:
                    # A prior attempt already paid for and saved the evidence
                    # extraction. Resume from that durable checkpoint.
                    review_proposal = _brand_analysis_proposal(review_proposal)
                    _save_brand_review_job(client_id, brand_id, job_id,
                        status='running', stage='evidence_reused', index=1, total=4,
                        message='Retomando a proposta já extraída.')
                else:
                    analysis = service.analyze_brand(website_url, restored_images, billing_callback=bill)
                    if not isinstance(analysis, dict) or not analysis.get('analysis_metadata'):
                        raise ValueError('A análise não retornou evidências suficientes.')
                    analysis_metadata = analysis.get('analysis_metadata') or {}
                    pages = max(1, int(analysis_metadata.get('pages_analyzed') or 1))
                    credits.charge_firecrawl(
                        actor=actor, idempotency_key=f'workspace-brand:{job_id}:firecrawl-scrape',
                        operation='scrape', pages=pages, app='Auditoria de marca', stage='pesquisa_web',
                        metadata={'brand_id': brand_id, 'job_id': job_id, 'pages_analyzed': pages},
                    )
                    if analysis_metadata.get('firecrawl_image_search'):
                        credits.charge_firecrawl(
                            actor=actor, idempotency_key=f'workspace-brand:{job_id}:firecrawl-image-search',
                            operation='search', results=10, app='Auditoria de marca', stage='busca_de_ativos',
                            metadata={'brand_id': brand_id, 'job_id': job_id, 'purpose': 'brand_assets'},
                        )
                    if analysis_metadata.get('firecrawl_market_search'):
                        credits.charge_firecrawl(
                            actor=actor, idempotency_key=f'workspace-brand:{job_id}:firecrawl-market-search',
                            operation='search', results=5, app='Auditoria de marca', stage='pesquisa_mercado',
                            metadata={'brand_id': brand_id, 'job_id': job_id, 'purpose': 'market_context'},
                        )
                    # Preserve Firecrawl visual evidence for review. Its logo
                    # classification remains a suggestion, never an automatic
                    # principal-logo decision.
                    candidates = list(analysis.get('asset_candidates') or [])
                    screenshot = analysis.get('screenshot')
                    if isinstance(screenshot, str) and screenshot.startswith(('http://', 'https://')):
                        candidates.insert(0, {
                            'url': screenshot, 'page_url': website_url,
                            'kind': 'reference', 'category': 'Captura do site',
                            'score': 100,
                            'reason': 'Captura da página inicial gerada pelo Firecrawl.',
                        })
                    imported_assets = service.import_website_brand_assets(brand_id, candidates)
                    review_proposal = _brand_analysis_proposal(analysis)
                    analysis_metadata = analysis.get('analysis_metadata') or {}
                    analysis_metadata = {
                        **analysis_metadata,
                        'firecrawl_assets_imported': len(imported_assets),
                        'firecrawl_logo_suggested': bool(analysis.get('logo_url')),
                    }
                    _save_brand_review_job(client_id, brand_id, job_id,
                        status='running', stage='evidence_complete', index=1, total=4,
                        message='Evidências organizadas. Iniciando os pareceres.',
                        analysis=review_proposal, analysis_metadata=analysis_metadata)

                def progress(review_id, title, position, total):
                    _save_brand_review_job(client_id, brand_id, job_id,
                        status='running', stage=review_id, index=position + 1, total=total + 1,
                        message=f'{title}: preparando parecer.')

                reviews = service.review_brand_analysis(review_proposal, progress=progress, billing_callback=bill)
                if not isinstance(reviews, list) or len(reviews) != 3:
                    raise ValueError('As três revisões da marca não foram concluídas.')
                _save_brand_review_job(client_id, brand_id, job_id,
                    status='pending_approval', stage='complete', index=4, total=4,
                    message='Três pareceres estão prontos para decisão.', error='',
                    analysis=review_proposal, reviews=reviews,
                    analysis_metadata=analysis_metadata)
                # Email delivery is best-effort and never changes the audit state.
                try:
                    from .. import db
                    from ..services.cadu_product_emails import send_brand_audit_ready
                    person = db.obter_contato_por_id(user_id) or {}
                    send_brand_audit_ready(
                        recipient_email=str(person.get('email') or ''),
                        recipient_name=str(person.get('nome_completo') or ''),
                        brand_name=str(review_proposal.get('name') or ''),
                        summary=str(review_proposal.get('brand_summary') or ''),
                        differentiators=list(review_proposal.get('differentiators') or []),
                        url=product_url('workspace', f'/marcas/{brand_id}'),
                    )
                except Exception:
                    current_app.logger.exception('Não foi possível enviar aviso da auditoria da marca %s', brand_id)
            except Exception as exc:
                current_app.logger.exception('Não foi possível auditar a marca %s', brand_id)
                _save_brand_review_job(client_id, brand_id, job_id,
                    status='failed', stage='failed', message='A análise precisa ser tentada novamente.',
                    error=str(exc)[:360])
                return False
            return True

    if not background:
        return runner()

    # The worker queue is deliberately preferred.  The thread remains a safe
    # fallback for an old deployment while its additive migration is applied.
    if current_app.config.get('CADU_BRAND_AUDIT_WORKER_ENABLED', True):
        try:
            from .brand_audit_jobs import enqueue
            enqueue({
                'job_id': job_id, 'client_id': client_id, 'user_id': user_id,
                'brand_id': brand_id, 'website_url': website_url,
                'images': images, 'proposal': proposal,
            })
            return True
        except Exception:
            current_app.logger.exception('Fila durável indisponível para auditoria da marca %s; usando contingência.', brand_id)
    threading.Thread(target=runner, daemon=True, name=f'brand-review-{job_id[:12]}').start()
    return True


def _brand_linked_projects(client_id: int, brand_id: int) -> list[dict]:
    """Return only projects from this organization that explicitly use a brand."""
    try:
        links = family_repository.project_brand_links(client_id)
        project_refs = {
            str(item.get('project_ref') or '')
            for item in links
            if str(item.get('brand_ref') or '') == f'studio:{brand_id}'
        }
    except Exception:
        return []
    return [
        project for project in _workspace_projects(client_id, status='todos')
        if f"ci:{project['id']}" in project_refs
    ]


def _project_brand_guidance(brand: dict) -> dict:
    """Small, approved-only identity projection for a project dossier."""
    profile = brand.get('brand_profile') or {}
    pack = _brand_review_pack(brand)
    return {
        'id': brand.get('id'),
        'name': brand.get('name') or 'Marca',
        'color': brand.get('primary_color') or '#176b5e',
        'status': pack.get('status') or 'not_reviewed',
        'summary': profile.get('brand_summary') or profile.get('positioning') or '',
        'tone': profile.get('tone_of_voice') or '',
        'mandatory': list(profile.get('mandatory_elements') or [])[:3],
        'forbidden': list(profile.get('forbidden_elements') or [])[:3],
    }


def _fill_empty_project_identity_from_brand(client_id: int, brand_id: int, profile: dict) -> None:
    """Seed linked projects from approved brand context without overwriting edits."""
    audience = str(profile.get('target_audience') or '').strip()
    tone = str(profile.get('tone_of_voice') or '').strip()
    positioning = str(profile.get('positioning') or profile.get('brand_summary') or '').strip()
    if not any((audience, tone, positioning)):
        return
    try:
        project_ids = {
            str(link.get('project_ref') or '')[3:]
            for link in family_repository.project_brand_links(client_id)
            if str(link.get('brand_ref') or '') == f'studio:{brand_id}'
            and str(link.get('project_ref') or '').startswith('ci:')
        }
        if not project_ids:
            return
        connection = get_db()
        with connection.cursor() as cursor:
            for project_id in project_ids:
                cursor.execute(
                    '''UPDATE cadu_ci_projetos
                          SET publico = COALESCE(NULLIF(publico, ''), %s),
                              tom_de_voz = COALESCE(NULLIF(tom_de_voz, ''), %s),
                              posicionamento = COALESCE(NULLIF(posicionamento, ''), %s),
                              updated_at = NOW()
                        WHERE id = %s AND id_cliente = %s''',
                    (audience, tone, positioning, project_id, client_id),
                )
        connection.commit()
    except Exception:
        try:
            get_db().rollback()
        except Exception:
            pass
        current_app.logger.exception('Não foi possível preencher a identidade dos projetos da marca %s', brand_id)


def _brand_project_documents(brand: dict, analysis: dict) -> list[tuple[str, str, str]]:
    """Create compact, retrieval-friendly projections without copying the whole audit."""
    profile = brand.get('brand_profile') or {}
    sources = '\n'.join(f'- {item}' for item in (analysis.get('sources') or [])[:8]) or '- Fontes oficiais aprovadas na auditoria.'
    personas = analysis.get('personas') or profile.get('personas') or []
    persona_lines = []
    for item in personas[:3]:
        if not isinstance(item, dict):
            continue
        label = item.get('name') or 'Persona de trabalho'
        detail = '; '.join(str(item.get(key) or '').strip() for key in ('context', 'needs', 'barriers') if item.get(key))
        if detail:
            persona_lines.append(f'- **{label}:** {detail} ({"fato" if item.get("status") == "fact" else "hipótese a validar"})')
    archetype = analysis.get('archetype') or profile.get('archetype') or {}
    archetype_text = ''
    if isinstance(archetype, dict) and archetype.get('primary'):
        archetype_text = f"{archetype.get('primary')} — {archetype.get('rationale') or 'leitura a validar'}"
    return [
        ('Marca em uma página', '\n\n'.join(filter(None, [
            f"# {brand.get('name') or 'Marca'}", analysis.get('brand_summary') or profile.get('brand_summary'),
            f"**Posicionamento:** {profile.get('positioning') or analysis.get('brand_summary') or ''}",
            f"**Oferta:** {', '.join(analysis.get('products_services') or profile.get('products_services') or [])}",
            f"**Diferenciais:** {'; '.join(analysis.get('differentiators') or profile.get('differentiators') or [])}",
            '## Fontes\n' + sources,
        ])), 'brand_projection:overview'),
        ('Públicos e personas', '\n\n'.join(filter(None, [
            '# Públicos e personas', analysis.get('target_audience') or profile.get('target_audience'),
            '## Segmentos\n' + '\n'.join(f"- **{item.get('name')}** — {item.get('needs') or ''}" for item in (analysis.get('audience_segments') or profile.get('audience_segments') or [])[:5]),
            '## Personas\n' + ('\n'.join(persona_lines) or 'Sem personas confirmadas; use o público prioritário como base.'),
        ])), 'brand_projection:audience'),
        ('Mensagem e direção de marca', '\n\n'.join(filter(None, [
            '# Mensagem e direção de marca', f"**Tom:** {analysis.get('tone_of_voice') or profile.get('tone_of_voice') or ''}",
            f"**Arquétipo:** {archetype_text}",
            f"**Direção criativa:** {analysis.get('creative_guidelines') or profile.get('creative_guidelines') or ''}",
            f"**Preservar:** {'; '.join(analysis.get('mandatory_elements') or profile.get('mandatory_elements') or [])}",
            f"**Evitar:** {'; '.join(analysis.get('forbidden_elements') or profile.get('forbidden_elements') or [])}",
        ])), 'brand_projection:messaging'),
        ('Mercado, diferenciais e fontes', '\n\n'.join(filter(None, [
            '# Mercado, diferenciais e fontes',
            '## Provas\n' + '\n'.join(f'- {item}' for item in (analysis.get('proof_points') or profile.get('proof_points') or [])[:8]),
            '## Diferenciais\n' + '\n'.join(f'- {item}' for item in (analysis.get('differentiators') or profile.get('differentiators') or [])[:8]),
            '## Fontes\n' + sources,
        ])), 'brand_projection:market'),
    ]


def _sync_approved_brand_to_projects(client_id: int, user_id: int, brand_id: int, brand: dict, analysis: dict) -> None:
    """Reuse approved evidence in linked project dossiers without a new crawl."""
    try:
        links = family_repository.project_brand_links(client_id)
    except Exception:
        current_app.logger.exception('Não foi possível carregar vínculos da marca %s', brand_id)
        return
    project_ids = [str(item.get('project_ref') or '')[3:] for item in links
                   if str(item.get('brand_ref') or '') == f'studio:{brand_id}'
                   and str(item.get('project_ref') or '').startswith('ci:')]
    if not project_ids:
        return
    metadata = brand.get('analysis_metadata') or {}
    pack = metadata.get('review_pack') or {}
    version = str(pack.get('approved_at') or '')[:32]
    include_sources = bool((pack.get('input') or {}).get('include_project_sources'))
    evidence_pages = (metadata.get('evidence_pages') or [])[:15] if include_sources else []
    for project_id in project_ids:
        try:
            existing = {str(item.get('storage_path') or '') for item in (_workspace_project(client_id, project_id) or {}).get('files', [])}
            for title, content, kind in _brand_project_documents(brand, analysis):
                path = f'brand-approved:{brand_id}:{version}:{kind}'
                if path not in existing and len(content.strip()) >= 20:
                    _persist_project_source(client_id, project_id, title, content, 'text/markdown', len(content.encode('utf-8')), path, kind, user_id)
            for position, page in enumerate(evidence_pages, start=1):
                if not isinstance(page, dict):
                    continue
                content = str(page.get('content') or '').strip()
                source_url = str(page.get('url') or '').strip()
                if len(content) < 20 or not source_url:
                    continue
                path = f'brand-evidence:{brand_id}:{version}:{position}'
                if path not in existing:
                    title = str(page.get('title') or source_url)[:220]
                    source_text = f'# Fonte oficial da marca\n\nURL: {source_url}\n\n{content}'
                    _persist_project_source(client_id, project_id, title, source_text, 'text/markdown', len(source_text.encode('utf-8')), path, 'brand_evidence', user_id)
            known_links = {str(item.get('url') or '') for item in _workspace_project_links(client_id, project_id)}
            for social_url in (analysis.get('social_links') or [])[:12]:
                try:
                    link = _project_link_metadata(social_url, 'Canal oficial da marca')
                except ValueError:
                    continue
                if link['url'] in known_links:
                    continue
                with get_db().cursor() as cursor:
                    cursor.execute(
                        '''INSERT INTO cadu_ci_projeto_links
                           (id, projeto_id, id_cliente, criado_por, provider, url, titulo, position)
                           VALUES (%s, %s, %s, %s, %s, %s, %s,
                               COALESCE((SELECT MAX(position) + 1 FROM cadu_ci_projeto_links WHERE projeto_id = %s AND id_cliente = %s), 0))''',
                        (str(uuid4()), project_id, client_id, user_id, link['provider'], link['url'], link['title'], project_id, client_id),
                    )
                get_db().commit()
                known_links.add(link['url'])
        except Exception:
            try:
                get_db().rollback()
            except Exception:
                pass
            current_app.logger.exception('Não foi possível projetar a marca %s no projeto %s', brand_id, project_id)


def _workspace_projects(client_id: int, query: str = "", status: str = "ativos", *, raise_on_error: bool = False) -> list[dict]:
    """Project dossiers retained from Cadu, always isolated by organization."""
    status = status if status in {'ativos', 'arquivados', 'todos'} else 'ativos'
    status_clause = "p.status = 'ativo'" if status == 'ativos' else "p.status = 'arquivado'" if status == 'arquivados' else "p.status <> 'deletado'"
    params = (client_id, '%' + query[:100] + '%', '%' + query[:100] + '%')

    def retry_database_connection() -> None:
        # A long-lived worker can retain a connection closed by PostgreSQL or
        # by an intermediate network. Drop it before the second read so the
        # request gets a fresh connection instead of repeating the same error.
        try:
            get_db().rollback()
        except Exception:
            pass
        close_db()

    for attempt in range(2):
        try:
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT p.id, p.nome, p.descricao, p.tipo, p.cor, p.status,
                              p.instrucoes, p.tom_de_voz, p.publico, p.posicionamento,
                              p.total_arquivos, p.total_conversas, p.updated_at,
                              COUNT(DISTINCT a.id) FILTER (WHERE a.indexing_status = 'completed') AS fontes_prontas,
                              COUNT(DISTINCT a.id) AS fontes_total, COUNT(DISTINCT ch.id) AS chunks_total
                         FROM cadu_ci_projetos p
                    LEFT JOIN cadu_ci_projeto_arquivos a ON a.projeto_id = p.id
                    LEFT JOIN cadu_ci_chunks ch ON ch.projeto_id = p.id
                        WHERE p.id_cliente = %s AND """ + status_clause + """
                          AND (p.nome ILIKE %s OR COALESCE(p.descricao, '') ILIKE %s)
                     GROUP BY p.id ORDER BY p.updated_at DESC""",
                    params,
                )
                records = [dict(row) for row in cursor.fetchall()]
            return _attach_project_identity(client_id, records)
        except Exception:
            if attempt == 0:
                retry_database_connection()
                continue
            break

    # Older Cadu databases may still be missing narrative/RAG migrations.
    # Keep the dossier visible and let its missing capabilities read as empty.
    for attempt in range(2):
        try:
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT id, nome, descricao, tipo, cor, status, instrucoes,
                              total_arquivos, total_conversas, updated_at,
                              0 AS fontes_prontas, 0 AS fontes_total, 0 AS chunks_total
                         FROM cadu_ci_projetos
                        WHERE id_cliente = %s AND """ + status_clause.replace('p.', '') + """
                          AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s)
                     ORDER BY updated_at DESC""",
                    params,
                )
                records = [dict(row) for row in cursor.fetchall()]
            for record in records:
                record.update({'tom_de_voz': '', 'publico': '', 'posicionamento': ''})
            return _attach_project_identity(client_id, records)
        except Exception:
            if attempt == 0:
                retry_database_connection()
                continue
            if raise_on_error:
                raise
            return []


def _attach_project_identity(client_id: int, projects: list[dict]) -> list[dict]:
    """Add the linked brand mark while keeping older dossiers presentable."""
    if not projects:
        return projects
    def brand_key(value: object) -> str:
        return re.sub(r"[^\w]+", "", str(value or "").casefold())

    brands_by_name: dict[str, dict] = {}
    links_by_project: dict[str, list[dict]] = {}
    project_images: dict[str, str] = {}
    try:
        project_ids = [str(project.get('id')) for project in projects if project.get('id')]
        if project_ids:
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT DISTINCT ON (projeto_id) projeto_id, id
                         FROM cadu_docs_client_images
                        WHERE id_cliente = %s AND ativo = true
                          AND projeto_id = ANY(%s::uuid[])
                          AND file_bytes IS NOT NULL
                          AND octet_length(file_bytes) > 0
                          AND LOWER(COALESCE(mime, '')) IN
                              ('image/jpeg', 'image/png', 'image/webp', 'image/gif')
                     ORDER BY projeto_id, created_at DESC""",
                    (client_id, project_ids),
                )
                project_images = {
                    str(row['projeto_id']): url_for('cadu_workspace.project_image', project_id=str(row['projeto_id']), image_id=row['id'])
                    for row in cursor.fetchall()
                }
    except Exception:
        project_images = {}
    try:
        brands = _workspace_brands(client_id)
        brands_by_ref = {f"studio:{brand['id']}": brand for brand in brands}
        # Older projects predate the explicit project↔brand link. When their
        # names match exactly, show the brand identity rather than an arbitrary
        # initial; the explicit link remains the source of truth when present.
        brands_by_name = {brand_key(brand.get('name')): brand for brand in brands if brand_key(brand.get('name'))}
        for link in family_repository.project_brand_links(client_id):
            brand = brands_by_ref.get(str(link.get('brand_ref') or ''))
            if brand:
                links_by_project.setdefault(str(link.get('project_ref') or ''), []).append(brand)
    except Exception:
        pass

    for project in projects:
        name = str(project.get('nome') or '').strip()
        brand = next(iter(links_by_project.get(f"ci:{project.get('id')}", [])), None)
        brand = brand or brands_by_name.get(brand_key(name), {})
        # `_workspace_brands` resolves the primary approved logo from both legacy
        # fields and the brand-assets library. Reusing it here keeps the home
        # dashboard from silently falling back to initials for asset-backed marks.
        project['brand_logo_url'] = public_logo(
            brand.get('resolved_logo_path') or brand.get('logo_upload_path') or brand.get('logo_url')
        ) if brand else ''
        project['thumbnail_url'] = project['brand_logo_url']
        if project_images.get(str(project.get('id'))):
            project['thumbnail_url'] = project_images[str(project.get('id'))]
            project['thumbnail_kind'] = 'project-image'
        else:
            project['thumbnail_kind'] = 'brand-logo' if project['thumbnail_url'] else 'initials'
        project['thumbnail_label'] = str(brand.get('name') or name)
        project['thumbnail_initials'] = ''.join(word[0] for word in re.findall(r"[\wÀ-ÿ]+", name)[:2]).upper() or 'P'
        project['thumbnail_color'] = brand.get('primary_color') or project.get('cor') or '#176b5e'
    return projects


def _workspace_data_health() -> dict:
    """Expose missing Workspace schema/data access instead of a blank dashboard."""
    required = ('cadu_ci_projetos', 'cadu_ci_projeto_arquivos', 'cadu_ci_chunks')
    for attempt in range(2):
        try:
            with get_db().cursor() as cursor:
                # Resolve each relation explicitly so a database may contain only a
                # partial rollout without appearing healthy.
                cursor.execute("SELECT to_regclass(%s) AS relation", ('public.cadu_ci_projetos',))
                if not (cursor.fetchone() or {}).get('relation'):
                    return {'ready': False, 'message': 'A estrutura de projetos ainda não foi ativada.'}
                for table in required[1:]:
                    cursor.execute("SELECT to_regclass(%s) AS relation", (f'public.{table}',))
                    if not (cursor.fetchone() or {}).get('relation'):
                        return {'ready': False, 'message': 'A estrutura de fontes do projeto ainda não foi ativada.'}
            return {'ready': True, 'message': ''}
        except Exception:
            # A pooled worker may hold a connection closed by the server. Drop
            # it once and establish a fresh one before showing a false outage.
            connection = g.pop('db', None)
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            if attempt == 0:
                continue
            current_app.logger.warning('Workspace sem acesso à base de dados após reconexão', exc_info=True)
    return {'ready': False, 'message': 'Os dados do Workspace estão temporariamente indisponíveis.'}


def _workspace_source_root() -> str:
    """Use a configured persistent volume; preserve legacy instance storage by default."""
    return str(current_app.config.get('WORKSPACE_SOURCE_STORAGE_DIR') or current_app.instance_path)


_WORKSPACE_RECENT_PROJECTS_KEY = 'workspace_recent_project_ids'


def _remember_workspace_project(project_id: str) -> None:
    """Keep a small, account-safe recency trail for the Workspace rail."""
    project_ref = str(project_id)
    recent = [
        str(item) for item in session.get(_WORKSPACE_RECENT_PROJECTS_KEY, [])
        if item and str(item) != project_ref
    ]
    session[_WORKSPACE_RECENT_PROJECTS_KEY] = [project_ref, *recent][:6]


def _workspace_sidebar_projects(client_id: int) -> list[dict]:
    """Return up to six active projects, prioritizing the ones last opened."""
    if not client_id:
        return []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, nome
                     FROM cadu_ci_projetos
                    WHERE id_cliente = %s AND status = 'ativo'
                 ORDER BY updated_at DESC NULLS LAST, nome ASC""",
                (client_id,),
            )
            projects = [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []

    recent_refs = [str(item) for item in session.get(_WORKSPACE_RECENT_PROJECTS_KEY, []) if item]
    recent_position = {project_ref: position for position, project_ref in enumerate(recent_refs)}
    original_position = {str(item.get('id')): position for position, item in enumerate(projects)}
    projects.sort(key=lambda item: (
        recent_position.get(str(item.get('id')), len(recent_position)),
        original_position.get(str(item.get('id')), len(original_position)),
    ))
    return projects[:6]


@bp.context_processor
def workspace_sidebar_context():
    if not session.get('user_id'):
        return {}
    client_id = int(session.get('cliente_id') or 0)
    try:
        usage = credit_position(client_id) or {}
        dock_items = _workspace_common_dock_items(client_id, int(session.get('user_id') or 0))
        usage_percent = round(float(usage.get('monthly_usage_percentage') or 0), 1)
    except Exception:
        current_app.logger.exception('Não foi possível preparar o shell compartilhado do Workspace')
        dock_items = []
        usage_percent = 0
    return {
        'workspace_sidebar_projects': _workspace_sidebar_projects(client_id),
        'workspace_dock_items': dock_items,
        'workspace_usage_percent': usage_percent,
    }


def _project_context_health(project: dict) -> dict:
    """Make the readiness of a dossier explicit from records the team owns."""
    score = 0
    missing = []
    if project.get('descricao'):
        score += 15
    else:
        missing.append('uma descrição')
    if int(project.get('fontes_prontas') or 0):
        score += 25
    elif int(project.get('fontes_total') or 0):
        score += 12
        missing.append('fontes indexadas')
    else:
        missing.append('fontes para consulta')
    identity_fields = ('publico', 'tom_de_voz', 'posicionamento', 'instrucoes')
    identity_total = sum(bool(project.get(field)) for field in identity_fields)
    score += round(identity_total * 25 / len(identity_fields))
    if identity_total < len(identity_fields):
        missing.append('orientações de identidade')
    if project.get('conversations'):
        score += 15
    else:
        missing.append('conversas de trabalho')
    if project.get('images'):
        score += 10
    else:
        missing.append('referências produzidas')
    if project.get('brands'):
        score += 10
    else:
        missing.append('uma marca vinculada')
    # A high score is not a completed context when a required decision is still
    # absent. The page should not say it is ready while reporting a gap.
    if score >= 80 and not missing:
        label = 'Pronto para orientar o trabalho'
    elif score >= 45:
        label = 'Contexto em construção'
    else:
        label = 'Comece estruturando o contexto'
    return {'score': score, 'label': label, 'missing': missing[:3]}


_PROJECT_LINK_PROVIDERS = {
    'drive.google.com': ('google_drive', 'Google Drive'),
    'docs.google.com': ('google_drive', 'Google Drive'),
    'clickup.com': ('clickup', 'ClickUp'),
    'trello.com': ('trello', 'Trello'),
    'miro.com': ('miro', 'Miro'),
}


def _project_link_metadata(value: str, title: str = '') -> dict:
    """Normalize a pasted project reference without fetching the remote URL."""
    raw = str(value or '').strip()
    if raw and '://' not in raw:
        raw = f'https://{raw}'
    parsed = urlparse(raw)
    host = (parsed.hostname or '').lower().rstrip('.')
    if parsed.scheme != 'https' or not host or parsed.username or parsed.password:
        raise ValueError('Use um link HTTPS válido.')
    matched = next((data for domain, data in _PROJECT_LINK_PROVIDERS.items()
                    if host == domain or host.endswith(f'.{domain}')), None)
    provider, suggested = matched or ('generic', host.removeprefix('www.'))
    normalized = parsed._replace(fragment='').geturl()
    return {'url': normalized, 'provider': provider,
            'title': str(title or '').strip()[:180] or suggested}


def _workspace_project_links(client_id: int, project_id: str) -> list[dict]:
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, provider, url, titulo, position, created_at, updated_at
                     FROM cadu_ci_projeto_links
                    WHERE projeto_id = %s AND id_cliente = %s
                 ORDER BY position ASC, created_at ASC""",
                (project_id, client_id),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def _workspace_project_memory(client_id: int, project_id: str) -> dict:
    """Project detail is resilient while the shared-memory migration rolls out."""
    try:
        organization_id = int(session.get('organization_id') or client_id)
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, kind, summary, status, source_conversation_id, updated_at
                     FROM cadu_working_memories
                    WHERE organization_id = %s AND client_id = %s AND project_ref = %s
                      AND status IN ('confirmed', 'proposed')
                 ORDER BY updated_at DESC LIMIT 24""",
                (organization_id, client_id, f'ci:{project_id}'),
            )
            records = [dict(row) for row in cursor.fetchall()]
    except Exception:
        records = []
    return {
        'confirmed': [record for record in records if record.get('status') == 'confirmed'],
        'proposals': [record for record in records if record.get('status') == 'proposed'],
    }


def _workspace_project_plans(client_id: int, project_id: str) -> list[dict]:
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, title, status, updated_at
                     FROM cadu_planner_plans
                    WHERE client_id = %s AND project_ref = %s AND archived_at IS NULL
                 ORDER BY updated_at DESC LIMIT 8""",
                (client_id, f'ci:{project_id}'),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def _project_recent_activity(project: dict) -> list[dict]:
    """A chronological, factual timeline assembled from the dossier records."""
    activity = []
    if project.get('updated_at'):
        activity.append({'title': 'Projeto atualizado', 'detail': project.get('nome'), 'at': project['updated_at']})
    for item in project.get('files', [])[:4]:
        activity.append({'title': 'Fonte adicionada', 'detail': item.get('nome_arquivo') or 'Arquivo', 'at': item.get('created_at')})
    for item in project.get('conversations', [])[:3]:
        activity.append({'title': 'Conversa atualizada', 'detail': item.get('titulo') or 'Conversa sem título', 'at': item.get('updated_at')})
    for item in project.get('images', [])[:3]:
        activity.append({'title': 'Referência visual adicionada', 'detail': item.get('title') or 'Imagem sem título', 'at': item.get('created_at')})
    for item in project.get('plans', [])[:3]:
        activity.append({'title': 'Plano atualizado', 'detail': item.get('title') or 'Plano sem título', 'at': item.get('updated_at')})
    for item in project.get('creative_analyses', [])[:3]:
        activity.append({'title': 'Criativo analisado', 'detail': item.get('original_name') or 'Criativo', 'at': item.get('created_at')})
    for item in project.get('links', [])[:3]:
        activity.append({'title': 'Atalho adicionado', 'detail': item.get('titulo') or 'Link externo', 'at': item.get('created_at')})
    activity.sort(key=lambda item: item.get('at') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return activity[:10]


def _workspace_continuity_feed(client_id: int, projects: list[dict], user: dict) -> list[dict]:
    """Return recent work from the Registry and Conversations in one bounded feed."""
    feed = []
    projects_by_ref = {f"ci:{project.get('id')}": project for project in projects if project.get('id')}
    labels = {'file': 'Fonte', 'artifact': 'Artefato', 'media_plan': 'Plano de mídia', 'report': 'Relatório', 'image': 'Imagem', 'video': 'Vídeo', 'analysis': 'Análise', 'link': 'Link'}
    try:
        resources = project_resource_service.list_recent_resources(client_id, list(projects_by_ref), limit=24)
    except Exception:
        current_app.logger.warning('Não foi possível montar recursos recentes do workspace do cliente %s', client_id, exc_info=True)
        resources = []
    for resource in resources:
        updated = resource.get('source_updated_at') or resource.get('source_created_at') or resource.get('last_seen_at')
        if not updated:
            continue
        project = projects_by_ref.get(str(resource.get('project_ref') or ''), {})
        kind = str(resource.get('resource_type') or 'artifact')
        label = labels.get(kind, 'Recurso')
        feed.append({'id': str(resource.get('id')), 'kind': kind,
                     'title': str(resource.get('title') or label), 'context': str(project.get('thumbnail_label') or project.get('nome') or 'Projeto'),
                     'status': str(resource.get('status') or 'Atualizado'), 'updatedAt': updated,
                     # The resource inspector lives inside the canonical project surface.
                     # It preserves the exact Registry record instead of opening the project
                     # with no indication of which item the user selected.
                     'href': url_for('cadu_workspace.project_detail', project_id=str(project.get('id')), resource=str(resource.get('id'))),
                     'resourceRef': str(resource.get('id')), 'projectRef': str(resource.get('project_ref') or ''),
                     'previewUrl': '', 'visualColor': str(project.get('thumbnail_color') or project.get('cor') or '#176b5e')})
    try:
        conversations = family_repository.conversation_history(user, client_id, limit=16)
    except Exception:
        current_app.logger.warning('Não foi possível montar conversas recentes do workspace do cliente %s', client_id, exc_info=True)
        conversations = []
    for conversation in conversations:
        updated = conversation.get('updated_at')
        if not updated:
            continue
        project = projects_by_ref.get(str(conversation.get('project_ref') or ''), {})
        feed.append({'id': f"conversation:{conversation.get('id')}", 'kind': 'conversation',
                     'title': str(conversation.get('title') or 'Conversa sem título'),
                     'context': str(project.get('thumbnail_label') or project.get('nome') or 'Conversa pessoal'),
                     'status': 'Conversa atualizada', 'updatedAt': updated,
                     'href': url_for('cadu_agent_v2_lab.conversations_v2_lab',
                                     conversation_id=str(conversation.get('id')), history='1',
                                     project_ref=str(conversation.get('project_ref') or '')),
                     'conversationId': str(conversation.get('id')), 'projectRef': str(conversation.get('project_ref') or ''),
                     'previewUrl': '', 'visualColor': str(project.get('thumbnail_color') or project.get('cor') or '#176b5e')})
    feed.sort(key=lambda item: item.get('updatedAt') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    # Keep enough history for the compact sidebar to decide whether it has a
    # meaningful five-conversation fallback, while the home widgets still
    # render only their own small slices.
    return feed[:max(8, len(conversations) + 3)]


def _chunk_project_note(content: str, limit: int = 1800) -> list[str]:
    """Compatibility wrapper kept for tests and callers of the first native slice."""
    return project_sources.chunks(content, limit)


def _persist_project_source(client_id: int, project_id: str, title: str, content: str,
                            mime: str, size: int, storage_path: str, source: str,
                            user_id: Optional[int] = None) -> int:
    source_chunks, embedding_tokens, embedding_model = project_index_service.indexed_content(content)
    tokens = embedding_tokens
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            charged_tokens = charge_project_rag(
                cursor, client_id=client_id, user_id=int(user_id if user_id is not None else session.get('user_id') or 0), project_id=project_id,
                tokens=tokens, stage='indexacao', idempotency_key='workspace-rag-index:' + uuid4().hex,
            )
            file_id = project_index_service.persist_indexed_source(
                cursor, project_id=project_id, client_id=client_id,
                user_id=user_id if user_id is not None else session.get('user_id'),
                name=title, mime=mime, size=size, storage_path=storage_path,
                source=source, content=content, chunks=source_chunks,
                embedding_model=embedding_model, charged_tokens=charged_tokens,
            )
        connection.commit()
        return int(file_id)
    except Exception:
        connection.rollback()
        raise


def _persist_project_source_index_error(client_id: int, project_id: str, title: str, content: str,
                                        mime: str, size: int, storage_path: str, source: str,
                                        error: Exception, user_id: Optional[int] = None) -> int:
    """Keep an accepted source when embeddings are temporarily unavailable."""
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            source_id = project_index_service.persist_pending_source(
                cursor, project_id=project_id, client_id=client_id,
                user_id=user_id if user_id is not None else session.get('user_id'),
                name=title, mime=mime, size=size, storage_path=storage_path,
                content=content, metadata={'source': source, 'indexing_deferred': True},
            )
            cursor.execute(
                """UPDATE cadu_ci_projeto_arquivos
                      SET indexing_status = 'error', erro_msg = %s, updated_at = NOW()
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s""",
                (str(error)[:500], source_id, project_id, client_id),
            )
        connection.commit()
        return int(source_id)
    except Exception:
        connection.rollback()
        raise


def _try_queue_project_source(client_id: int, project_id: str, title: str, content: str,
                              mime: str, size: int, storage_path: str, source: str,
                              user_id: Optional[int] = None) -> Optional[dict]:
    """Register a source and enqueue embedding when the durable queue is available.

    The queue migration is additive, so local/test environments may still need the
    original synchronous path. A pending source is committed before enqueueing
    because the job has a foreign key to it; if the queue table is not installed,
    the provisional row is removed and callers can safely fall back to sync.
    """
    if not current_app.config.get('CADU_PROJECT_INDEX_ASYNC_ENABLED', False):
        return None

    effective_user_id = user_id if user_id is not None else session.get('user_id')
    connection = get_db()
    source_id = None
    try:
        with connection.cursor() as cursor:
            source_id = project_index_service.persist_pending_source(
                cursor, project_id=project_id, client_id=client_id,
                user_id=effective_user_id, name=title, mime=mime, size=size,
                storage_path=storage_path, content=content,
                metadata={'source': source},
            )
        connection.commit()

        try:
            from .project_index_jobs import enqueue
            job_id = enqueue(client_id, project_id, source_id, int(effective_user_id or 0))
        except Exception:
            # A queue migration can be present but temporarily unhealthy. The
            # source is still valid, so let the caller use the synchronous path.
            current_app.logger.warning(
                'Não foi possível enfileirar a fonte %s; tentando indexação síncrona',
                source_id, exc_info=True,
            )
            job_id = None
        if job_id:
            return {'source_id': int(source_id), 'job_id': str(job_id)}

        _remove_pending_project_source(client_id, project_id, int(source_id))
        return None
    except Exception:
        connection.rollback()
        if source_id is not None:
            try:
                _remove_pending_project_source(client_id, project_id, int(source_id))
            except Exception:
                current_app.logger.exception('Não foi possível limpar fonte pendente %s', source_id)
        raise


def _remove_pending_project_source(client_id: int, project_id: str, source_id: int) -> None:
    """Remove a provisional source created when the durable queue is unavailable."""
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """DELETE FROM cadu_ci_projeto_arquivos
                    WHERE id=%s AND projeto_id=%s AND id_cliente=%s
                    RETURNING id""",
                (source_id, project_id, client_id),
            )
            removed = cursor.fetchone()
            if removed:
                cursor.execute(
                    """UPDATE cadu_ci_projetos
                          SET total_arquivos=GREATEST(COALESCE(total_arquivos, 0)-1, 0),
                              updated_at=NOW()
                        WHERE id=%s AND id_cliente=%s""",
                    (project_id, client_id),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _queue_project_url_source(client_id: int, project_id: str, user_id: int, url: str) -> int:
    """Persist the pending URL before starting network work.

    A URL may take minutes to fetch or may fail after the browser has moved on.
    Keeping a real source row means the project status endpoint can show both
    progress and an actionable error instead of leaving a silent background job.
    """
    parsed = urlparse(url)
    title = parsed.netloc or url
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_ci_projeto_arquivos
                       (projeto_id, id_cliente, criado_por, nome_arquivo, mime, tamanho,
                        storage_path, doc_form, indexing_status, word_count, tokens,
                        purpose, category, classification_status, classification_confidence,
                        classification_reason, classification_metadata, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 'text/uri-list', 0, %s,
                            'text_model', 'queued', 0, 0, 'knowledge_source', 'research',
                            'classified', 0.70, 'Página pública importada como referência de pesquisa.',
                            '{"classifier":"workspace-v1","content_inspected":false}'::jsonb, NOW(), NOW())
                 RETURNING id""",
                (project_id, client_id, user_id, title, f'workspace-url:{url}'),
            )
            source_id = int(cursor.fetchone()['id'])
            cursor.execute(
                """UPDATE cadu_ci_projetos
                      SET total_arquivos = COALESCE(total_arquivos, 0) + 1, updated_at = NOW()
                    WHERE id = %s AND id_cliente = %s""",
                (project_id, client_id),
            )
        connection.commit()
        return source_id
    except Exception:
        connection.rollback()
        raise


def _complete_queued_project_url_source(client_id: int, project_id: str, user_id: int,
                                        source_id: int, source: dict) -> None:
    """Index a queued URL source in place, preserving its visible status row."""
    content = str(source.get('text') or '')
    source_chunks, embedding_tokens, embedding_model = project_knowledge.index(content)
    title = str(source.get('name') or source.get('url') or 'Página pública')[:255]
    word_count = len(re.findall(r'\b\w+\b', content, flags=re.UNICODE))
    tokens = embedding_tokens
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            charged_tokens = charge_project_rag(
                cursor, client_id=client_id, user_id=user_id, project_id=project_id,
                tokens=tokens, stage='indexacao',
                idempotency_key=f'workspace-rag-index:{source_id}',
            )
            cursor.execute(
                'DELETE FROM cadu_ci_chunks WHERE arquivo_id = %s AND projeto_id = %s AND id_cliente = %s',
                (source_id, project_id, client_id),
            )
            for chunk in source_chunks:
                cursor.execute(
                    """INSERT INTO cadu_ci_chunks
                           (projeto_id, id_cliente, arquivo_id, ordem, titulo, conteudo,
                            search_vector, metadata, embedding, embedding_model, content_hash, tokens, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('portuguese', %s), %s::jsonb, %s::vector,
                                %s, %s, %s, NOW())""",
                    (project_id, client_id, source_id, chunk.order, title, chunk.content,
                     chunk.content, json.dumps({'source': 'workspace_url', 'arquivo_id': source_id, 'section': chunk.section}),
                     project_knowledge.vector_literal(chunk.embedding), embedding_model,
                     chunk.content_hash, chunk.tokens),
                )
            cursor.execute(
                """UPDATE cadu_ci_projeto_arquivos
                      SET nome_arquivo = %s, mime = %s, storage_path = %s,
                          extracted_text = %s, indexing_status = 'completed', erro_msg = NULL, word_count = %s,
                          tokens = %s, updated_at = NOW()
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s""",
                (title, str(source.get('mime') or 'text/html'),
                 f"workspace-url:{source.get('url') or ''}", content, word_count, charged_tokens,
                 source_id, project_id, client_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _mark_project_source_error(client_id: int, project_id: str, source_id: int, error: Exception) -> None:
    """Best-effort status update for failures that occur after the HTTP response."""
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_ci_projeto_arquivos
                      SET indexing_status = 'error', erro_msg = %s, updated_at = NOW()
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s""",
                (str(error)[:500], source_id, project_id, client_id),
            )
        connection.commit()
    except Exception:
        current_app.logger.exception('Não foi possível registrar erro da fonte %s', source_id)


def _project_source(client_id: int, project_id: str, source_id: int) -> Optional[dict]:
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, nome_arquivo, mime, tamanho, storage_path, extracted_text, indexing_status,
                          word_count, tokens, erro_msg, purpose, category, classification_status,
                          classification_confidence, classification_reason, classification_metadata,
                          created_at, updated_at
                     FROM cadu_ci_projeto_arquivos
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s""",
                (source_id, project_id, client_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def _workspace_project(client_id: int, project_id: str) -> Optional[dict]:
    # Archived dossiers remain readable and can be reactivated from their detail page.
    project = next((item for item in _workspace_projects(client_id, status='todos') if str(item['id']) == project_id), None)
    if not project:
        return None
    try:
        refs = family_repository.project_brand_links(client_id)
        linked = {str(item.get('brand_ref') or '') for item in refs if item.get('project_ref') == f'ci:{project_id}'}
        project['brands'] = [brand for brand in _workspace_brands(client_id) if f"studio:{brand['id']}" in linked]
    except Exception:
        project['brands'] = []
    # Existing links may predate the projection job. Keep the project useful
    # immediately by reading the approved brand profile as a fallback for the
    # fields that are still empty in the dossier.
    if project.get('brands'):
        brand_profile = project['brands'][0].get('brand_profile') or {}
        if not brand_profile:
            brand_profile = (_brand_review_pack(project['brands'][0]).get('analysis') or {})
        project['publico'] = project.get('publico') or brand_profile.get('target_audience') or ''
        project['tom_de_voz'] = project.get('tom_de_voz') or brand_profile.get('tone_of_voice') or ''
        project['posicionamento'] = project.get('posicionamento') or brand_profile.get('positioning') or brand_profile.get('brand_summary') or ''
    project['brand_guidance'] = [_project_brand_guidance(brand) for brand in project['brands']]
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, nome_arquivo, mime, tamanho, storage_path, doc_form, indexing_status,
                          word_count, tokens, erro_msg, purpose, category, classification_status,
                          classification_confidence, classification_reason, classification_metadata, created_at
                     FROM cadu_ci_projeto_arquivos
                    WHERE projeto_id = %s AND id_cliente = %s ORDER BY created_at DESC""",
                (project_id, client_id),
            )
            project['files'] = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT to_regclass('public.cadu_family_conversation_context') IS NOT NULL AS available")
            context_table_available = bool(cursor.fetchone()['available'])
            if context_table_available:
                cursor.execute(
                    """SELECT c.id, c.titulo, c.total_mensagens, c.updated_at,
                              COALESCE(x.project_ref, CASE WHEN c.projeto_id IS NOT NULL
                                  THEN 'ci:' || c.projeto_id::text END) AS project_ref
                         FROM cadu_conversations c
                    LEFT JOIN cadu_family_conversation_context x ON x.conversation_id = c.id
                        WHERE c.id_cliente = %s
                          AND (c.projeto_id = %s OR x.project_ref = %s)
                          AND (x.conversation_id IS NULL OR
                               (x.user_id = %s AND x.organization_id = %s AND x.client_id = %s))
                     ORDER BY c.updated_at DESC LIMIT 50""",
                    (client_id, project_id, f'ci:{project_id}', session.get('user_id'), client_id, client_id),
                )
            else:
                cursor.execute(
                    """SELECT id, titulo, total_mensagens, updated_at,
                              CASE WHEN projeto_id IS NOT NULL THEN 'ci:' || projeto_id::text END AS project_ref
                         FROM cadu_conversations
                        WHERE projeto_id = %s AND id_cliente = %s ORDER BY updated_at DESC LIMIT 50""",
                    (project_id, client_id),
                )
            project['conversations'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        project['files'] = []
        project['conversations'] = []
    # The PHP SmartDocs projection is intentionally not part of the new
    # project experience. Its data remains available to legacy routes, while
    # the React dossier uses only versioned V2 artifacts below.
    project['smartdocs'] = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id::text, type, title, status, current_version, conversation_id, updated_at
                     FROM cadu_workspace_artifacts
                    WHERE client_id = %s AND project_ref = %s
                 ORDER BY updated_at DESC LIMIT 50""",
                (client_id, f'ci:{project_id}'),
            )
            project['workspace_artifacts'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        # The V2 artifact migration is additive. Older installations can still
        # render the project dossier using its legacy documents and resources.
        project['workspace_artifacts'] = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, title, source, mime, file_path, created_at,
                          (file_bytes IS NOT NULL AND octet_length(file_bytes) > 0
                           AND LOWER(COALESCE(mime, '')) IN
                               ('image/jpeg', 'image/png', 'image/webp', 'image/gif')) AS has_preview
                     FROM cadu_docs_client_images
                    WHERE projeto_id = %s AND id_cliente = %s AND ativo = true
                 ORDER BY created_at DESC LIMIT 12""",
                (project_id, client_id),
            )
            project['images'] = [dict(row) for row in cursor.fetchall()]
            # Some historical records retain metadata but no binary payload.
            # Do not point <img> at their former PHP uploads path or at a route
            # that must return 404; the dossier shows these as intentional
            # "preview unavailable" history instead.
            for image in project['images']:
                image['preview_url'] = url_for(
                    'cadu_workspace.project_image',
                    project_id=project_id,
                    image_id=image['id'],
                ) if image.get('has_preview') else ''
    except Exception:
        project['images'] = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT public_id, original_name, media_type, thumbnail_url, status, created_at
                     FROM studio_creative_analyses
                    WHERE client_id = %s AND project_ref = %s
                 ORDER BY created_at DESC LIMIT 24""",
                (client_id, f'ci:{project_id}'),
            )
            project['creative_analyses'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        project['creative_analyses'] = []
    project['links'] = _workspace_project_links(client_id, project_id)
    project['memory'] = _workspace_project_memory(client_id, project_id)
    project['plans'] = _workspace_project_plans(client_id, project_id)
    evidence = (
        bool(project.get('descricao') or project.get('instrucoes') or project.get('publico')),
        bool(project.get('brands')),
        bool(project.get('files')),
        bool(project.get('conversations') or project['memory']['confirmed']),
        bool(project['plans'] or project.get('images') or project.get('creative_analyses')),
    )
    project['experience_state'] = 'not_started' if not any(evidence) else ('forming' if sum(evidence) < 3 else 'active')
    project['hero_image'] = next(
        (image.get('preview_url') for image in project['images'] if image.get('preview_url')),
        '',
    )
    project['identity_html'] = {
        field: _workspace_rich_text(project.get(field) or '')
        for field in ('publico', 'tom_de_voz', 'posicionamento', 'instrucoes')
    }
    project['context_health'] = _project_context_health(project)
    project['activity'] = _project_recent_activity(project)
    try:
        from .project_resource_service import list_resources
        registry = list_resources(client_id, f'ci:{project_id}', actor_id=session.get('user_id'))
        project['resources'] = registry.get('resources') or []
        project['resource_summary'] = registry.get('summary') or {}
        project['resource_registry_available'] = registry.get('available', True)
    except Exception:
        current_app.logger.exception('Não foi possível reconciliar os recursos do projeto %s', project_id)
        project['resources'], project['resource_summary'] = [], {}
        project['resource_registry_available'] = False
    return project


def _editable_workspace_project(client_id: int, project_id: str) -> dict:
    project = _workspace_project(client_id, project_id)
    if not project:
        abort(404)
    if project.get('status') == 'arquivado':
        abort(409, description='Reative o projeto antes de alterar seu conteúdo.')
    return project


@bp.get("/workspace")
@bp.get("/workspace/")
def index():
    # Authenticated people have one Workspace, not a marketing page followed
    # by a second application entry. Keep the public overview for visitors.
    if session.get("user_id"):
        return redirect(url_for("cadu_workspace.dashboard"), code=302)
    return render_template(
        "cadu_workspace/public.html",
        canonical=product_url("workspace"),
        description="O ambiente Cadu que mantém cliente, marca, projeto, time e decisões conectados em cada campanha.",
        hero=secrets.choice(WORKSPACE_PUBLIC_HEROES),
    )


PUBLIC_PAGES = {
    "como-funciona": {
        "title": "Como funciona",
        "description": "Veja como o Workspace leva contexto de marcas e projetos para cada etapa do trabalho.",
        "lead": "Organize a base, leve o briefing para a ferramenta certa e continue com o histórico por perto.",
    },
    "planos": {
        "title": "Planos",
        "description": "Compare capacidade, créditos e pacotes para a operação da sua equipe.",
        "lead": "A mesma conta atende todo o time. O plano define capacidade e os créditos acompanham o uso real.",
    },
    "ajuda": {
        "title": "Ajuda",
        "description": "Respostas sobre acesso, projetos, créditos, privacidade e produtos Cadu.",
        "lead": "Orientações curtas para começar e saber onde administrar cada parte da conta.",
    },
    "contato": {
        "title": "Contato",
        "description": "Fale com a CentralComm sobre acesso, implantação ou suporte ao Cadu Workspace.",
        "lead": "Conte o que sua equipe precisa organizar. Direcionamos a conversa para produto, implantação ou suporte.",
    },
}

PRODUCT_ENTRIES = {
    "cadu": ("Cadu", "Inteligência de mídia", "Traga a decisão de mídia para um só lugar.", "Pesquise públicos, formatos, canais e ferramentas de campanha a partir do contexto do seu time."),
    "workspace": ("Workspace", "Conta e contexto", "Comece pelo contexto certo.", "Organize o time, os projetos, os créditos e os acessos antes de abrir uma solução especializada."),
    "planner": ("Planner", "Planejamento de mídia", "Planeje antes de investir.", "Estruture objetivos, público, canais e recomendações em um plano pronto para a próxima decisão."),
    "studio": ("Studio", "Criação de conteúdo", "Crie para o formato que importa.", "Transforme uma direção criativa em peças, variações e formatos preparados para a campanha."),
    "skills": ("Skills", "Conhecimento especialista", "Aplique o método certo no momento certo.", "Encontre skills e agentes especializados para pesquisar, decidir e executar com mais contexto."),
    "connect": ("Reports", "Relatórios e operação", "Conecte a operação ao trabalho.", "Organize integrações, campanhas e agentes que fazem os sistemas avançarem juntos."),
}

# Cada carregamento escolhe no servidor um recorte editorial diferente, sem
# troca tardia da imagem depois que a página já foi exibida.
WORKSPACE_PUBLIC_HEROES = (
    {"image": "public-people-v1.jpg", "tone": "light"},
    {"image": "public-people-v3.jpg", "tone": "dark"},
)
WORKSPACE_APP_HEROES = (
    {"image": "app-team-v1.jpg", "tone": "dark"},
    {"image": "app-team-v2.jpg", "tone": "dark"},
    {"image": "app-team-v3.jpg", "tone": "dark"},
)


@bp.get("/entrada/<product>")
def product_entry(product):
    if not session.get("user_id"):
        return redirect(workspace_public_url(), code=302)
    product = str(product or "").lower()
    if product == 'cadu':
        return redirect(url_for('cadu_workspace.index'), code=301)
    item = PRODUCT_ENTRIES.get(product)
    if not item:
        abort(404)
    entry = dict(zip(("name", "eyebrow", "title", "description"), item))
    entry["icon_family"] = "workspace" if product == "cadu" else product
    # A página pública do Cadu também mora no Workspace: o domínio cadu.* é a
    # aplicação PHP autenticada e não deve receber links para uma rota Flask.
    entry_host = "workspace" if product == "cadu" else product
    return render_template("cadu_workspace/product_entry.html", product=product, entry=entry, canonical=product_url(entry_host, f"/entrada/{product}"))


@bp.route('/workspace/onboarding', methods=['GET', 'POST'])
@login_required
def workspace_onboarding():
    """Create the first Workspace context inside the already logged-in client."""
    client_id = int(session.get('cliente_id') or 0)
    contact_id = int(session.get('user_id') or 0)
    if not client_id or not contact_id:
        abort(403)
    if not _workspace_onboarding_table_available():
        abort(503, description='A configuração inicial do Workspace ainda está sendo publicada. Tente novamente em instantes.')

    from .. import db

    organization = {}
    try:
        organization = db.obter_cliente_por_id(client_id) or {}
    except Exception:
        current_app.logger.warning('Não foi possível carregar o nome da organização %s', client_id, exc_info=True)
    record = _workspace_onboarding_record(contact_id, client_id)
    if record and record.get('project_id') and record.get('brand_id'):
        return redirect(url_for('cadu_workspace.project_detail', project_id=str(record['project_id']), onboarding='1'), code=303)

    default_operation = 'agency' if (
        organization.get('agencia_key') is True
        or str(organization.get('agencia_display') or '').strip().lower() in {'sim', 's', 'true'}
    ) else 'client'
    form = _workspace_onboarding_form(record)
    if not (record or form.get('organization_name')):
        form['organization_name'] = str(
            organization.get('nome_fantasia')
            or organization.get('razao_social')
            or session.get('client_name')
            or session.get('cliente_nome')
            or ''
        )[:180]
    if not record and form.get('operation_type') == 'client' and default_operation == 'agency':
        form['operation_type'] = default_operation

    if request.method == 'GET':
        return _workspace_onboarding_render(form, organization=organization)
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')

    form.update({
        'operation_type': str(request.form.get('operation_type') or '').strip(),
        'organization_name': ' '.join((request.form.get('organization_name') or '').split())[:180],
        'client_name': ' '.join((request.form.get('client_name') or '').split())[:180],
        'brand_name': ' '.join((request.form.get('brand_name') or '').split())[:150],
        'website_url': str(request.form.get('website_url') or '').strip()[:2000],
        'project_name': ' '.join((request.form.get('project_name') or '').split())[:150],
        'project_description': str(request.form.get('project_description') or '').strip()[:4000],
    })
    error = ''
    if form['operation_type'] not in {'client', 'agency'}:
        error = 'Escolha se esta conta representa uma empresa ou uma agência.'
    elif len(form['organization_name']) < 2:
        error = 'Informe o nome da empresa, agência ou marca.'
    elif len(form['brand_name']) < 2:
        error = 'Informe o nome da primeira marca.'
    elif len(form['project_name']) < 2:
        error = 'Informe o nome do primeiro projeto.'
    try:
        website_url = _normalized_website_url(form['website_url'])
    except HTTPException as exc:
        website_url = ''
        error = error or str(exc.description)
    files = [item for item in request.files.getlist('images') if item and item.filename][:4]
    image_payload = []
    for item in files:
        image_payload.append({
            'filename': item.filename,
            'content_type': item.mimetype,
            'content': item.read(),
        })
        item.stream.seek(0)
    if not error and not website_url and not image_payload:
        error = 'Informe o site oficial ou envie ao menos uma referência visual para iniciar a auditoria.'
    if error:
        return _workspace_onboarding_render(form, error=error, organization=organization, status_code=400)

    # The audit is optional only when its shared credit balance is unavailable:
    # organization/brand/project creation should not be lost for that reason.
    audit_job_id = ''
    audit_error = ''
    if website_url or image_payload:
        try:
            _ensure_brand_audit_credit(client_id)
            audit_job_id = uuid4().hex
        except HTTPException as exc:
            audit_error = str(exc.description or 'A auditoria ficará disponível quando houver créditos.')[:360]
        except Exception:
            audit_error = 'A auditoria ficará disponível quando os créditos da organização puderem ser consultados.'
            current_app.logger.exception('Não foi possível preparar a auditoria do onboarding da organização %s', client_id)

    audit_metadata = {}
    if audit_job_id:
        audit_metadata = {'review_pack': {
            'job_id': audit_job_id,
            'status': 'queued',
            'stage': 'queued',
            'index': 0,
            'total': 4,
            'message': 'A auditoria entrou na fila.',
            'error': '',
            'created_at': _utc_timestamp(),
            'input': {'website_url': website_url, 'has_images': bool(image_payload)},
            'analysis': {},
            'reviews': [],
        }}
    connection = get_db()
    brand_id = None
    project_id = None
    brand_was_created = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, website_url, analysis_metadata
                     FROM cx_clients
                    WHERE crm_client_id=%s AND LOWER(name)=LOWER(%s)
                    ORDER BY id
                    LIMIT 1""",
                (client_id, form['brand_name']),
            )
            existing_brand = cursor.fetchone() or {}
            if existing_brand:
                brand_id = int(existing_brand['id'])
                current_metadata = existing_brand.get('analysis_metadata') or {}
                if isinstance(current_metadata, str):
                    current_metadata = json.loads(current_metadata or '{}')
                if not isinstance(current_metadata, dict):
                    current_metadata = {}
                if audit_job_id:
                    # Avoid resetting an already-running or approved audit when
                    # a browser retries the final onboarding submit.
                    current_pack = dict(current_metadata.get('review_pack') or {})
                    if current_pack.get('status') in {'queued', 'running', 'pending_approval', 'approved'}:
                        # The existing worker already owns this audit. Do not
                        # start a second thread from a repeated form submit.
                        audit_job_id = ''
                        audit_metadata = {}
                if website_url and not existing_brand.get('website_url'):
                    cursor.execute(
                        """UPDATE cx_clients SET website_url=%s
                             WHERE id=%s AND crm_client_id=%s""",
                        (website_url, brand_id, client_id),
                    )
            else:
                brand_metadata = audit_metadata or {'onboarding': {'source': 'workspace'}}
                cursor.execute(
                    """INSERT INTO cx_clients
                           (crm_client_id, name, website_url, primary_color, secondary_color,
                            brand_profile, analysis_metadata, price_policy)
                        VALUES (%s, %s, %s, '#176b5e', '#dcece6', '{}'::jsonb, %s::jsonb, 'hide_price')
                     RETURNING id""",
                    (client_id, form['brand_name'], website_url, json.dumps(brand_metadata)),
                )
                brand_id = int(cursor.fetchone()['id'])
                brand_was_created = True

            if audit_metadata:
                cursor.execute(
                    """UPDATE cx_clients SET analysis_metadata=%s::jsonb
                         WHERE id=%s AND crm_client_id=%s""",
                    (json.dumps(audit_metadata), brand_id, client_id),
                )
            cursor.execute(
                """SELECT id::text AS id
                     FROM cadu_ci_projetos
                    WHERE id_cliente=%s AND LOWER(nome)=LOWER(%s)
                    ORDER BY created_at
                    LIMIT 1""",
                (client_id, form['project_name']),
            )
            existing_project = cursor.fetchone()
            if existing_project:
                project_id = str(existing_project['id'])
            else:
                project_id = str(uuid4())
                cursor.execute(
                    """INSERT INTO cadu_ci_projetos
                           (id, id_cliente, criado_por, nome, descricao, instrucoes, tipo, cor, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'projeto', '#176b5e', 'ativo')""",
                    (
                        project_id,
                        client_id,
                        contact_id,
                        form['project_name'],
                        form['project_description'] or f"Primeiro projeto de {form['brand_name']}.",
                        'Use este projeto para concentrar briefing, fontes, decisões e entregas da marca.',
                    ),
                )

            metadata = {
                'source': 'workspace_onboarding',
                'operation_type': form['operation_type'],
                'organization_name': form['organization_name'],
                'client_name': form['client_name'],
                # This is intentionally the agency's own CRM id. A managed
                # client is a later context, never a replacement for it.
                'agency_client_id': client_id if form['operation_type'] == 'agency' else None,
                'brand_name': form['brand_name'],
                'website_url': website_url,
                'project_name': form['project_name'],
                'project_description': form['project_description'],
                'audit_error': audit_error,
            }
            status = 'audit_pending' if audit_job_id else 'completed'
            cursor.execute(
                """INSERT INTO cadu_workspace_onboarding
                       (contato_id, id_cliente, operation_type, organization_name, client_name,
                        brand_id, project_id, current_step, status, metadata, updated_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'complete', %s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (contato_id, id_cliente) DO UPDATE
                       SET operation_type=EXCLUDED.operation_type,
                           organization_name=EXCLUDED.organization_name,
                           client_name=EXCLUDED.client_name,
                           brand_id=EXCLUDED.brand_id,
                           project_id=EXCLUDED.project_id,
                           current_step=EXCLUDED.current_step,
                           status=EXCLUDED.status,
                           metadata=EXCLUDED.metadata,
                           updated_at=NOW(),
                           completed_at=EXCLUDED.completed_at""",
                (
                    contact_id,
                    client_id,
                    form['operation_type'],
                    form['organization_name'],
                    form['client_name'] or None,
                    brand_id,
                    project_id,
                    status,
                    json.dumps(metadata),
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível concluir o onboarding do Workspace para %s', client_id)
        return _workspace_onboarding_render(
            form,
            error='Não foi possível criar sua primeira base agora. Atualize a página e tente novamente.',
            organization=organization,
            status_code=503,
        )

    if files and brand_id and brand_was_created:
        try:
            from ..creative_modeling_service import CreativeModelingService
            CreativeModelingService().upload_client_brand_assets(
                brand_id, files, True, 'reference',
            )
        except ValueError as exc:
            current_app.logger.warning('Marca inicial %s criada sem todos os ativos: %s', brand_id, exc)
        except Exception:
            current_app.logger.exception('Marca inicial %s criada, mas não foi possível salvar os ativos', brand_id)
    try:
        family_repository.set_project_brand_link(
            client_id, contact_id, f'ci:{project_id}', f'studio:{brand_id}', True,
        )
    except Exception:
        current_app.logger.exception('Não foi possível vincular marca %s ao projeto %s', brand_id, project_id)
    if audit_job_id:
        try:
            _start_brand_review_job(
                client_id, contact_id, int(brand_id), audit_job_id,
                website_url, image_payload,
            )
        except Exception:
            current_app.logger.exception('Não foi possível iniciar a auditoria da marca inicial %s', brand_id)

    # The Workspace setup is also the commercial qualification checkpoint. It
    # reuses the same CRM lead/onboarding records as the legacy flow and keeps
    # Demetrius as owner without changing the current agency client_id.
    try:
        from .. import db
        from ..services.onboarding_comercial import (
            enviar_email_onboarding_usuario,
            enviar_notificacao_demetrius,
            obter_executivo_comercial,
        )

        usuario = db.obter_contato_por_id(contact_id) or {
            'id_contato_cliente': contact_id,
            'nome_completo': session.get('user_name') or 'Pessoa do Workspace',
            'email': session.get('user_email') or '',
        }
        executivo = obter_executivo_comercial()
        onboarding = {
            'perfil': 'agencia' if form['operation_type'] == 'agency' else 'cliente_final',
            'empresa': form['organization_name'],
            'cargo': '',
            'telefone': '',
            'site_url': website_url,
            'objetivo': form['project_description'],
        }
        if executivo and executivo.get('id_contato_cliente'):
            lead_id = db.criar_cadu_lead({
                'nome': usuario.get('nome_completo'),
                'email': usuario.get('email'),
                'empresa': form['organization_name'],
                'mensagem': form['project_description'],
                'origem': 'onboarding_workspace',
                'canal': 'produto',
                'interesse': 'Cadu Workspace',
                'fonte': 'cadastro',
                'status': 'inbox',
                'qualificacao_score': 1,
                'qualificacao_notas': f"Perfil declarado: {onboarding['perfil']}. Marca: {form['brand_name']}. Projeto: {form['project_name']}.",
                'id_executivo': executivo['id_contato_cliente'],
                'atribuido_em': datetime.now(),
            })
            db.salvar_onboarding_comercial(
                contato_id=contact_id, executivo_id=executivo['id_contato_cliente'],
                lead_id=lead_id, **onboarding,
            )
            try:
                enviar_notificacao_demetrius(usuario=usuario, onboarding=onboarding, executivo=executivo)
            except Exception:
                current_app.logger.exception('Workspace criado, mas a notificação interna de onboarding falhou')
        try:
            enviar_email_onboarding_usuario(
                usuario=usuario,
                organization_name=form['organization_name'],
                brand_name=form['brand_name'],
                project_name=form['project_name'],
                perfil=onboarding['perfil'],
            )
        except Exception:
            current_app.logger.exception('Workspace criado, mas o e-mail de onboarding ao usuário falhou')
    except Exception:
        # Commercial CRM/email must not undo a completed Workspace setup.
        current_app.logger.exception('Workspace criado, mas o fluxo comercial pós-onboarding falhou')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id, onboarding='1'), code=303)


@bp.get("/workspace/design-system")
@bp.get("/design-system")
def public_design_system():
    """Public, unlisted reference for the current Workspace product language."""
    return render_template(
        "cadu_workspace/design_system.html",
        canonical=product_url("workspace", "/design-system"),
    )


@bp.get("/workspace/<page>")
def public_page(page):
    content = PUBLIC_PAGES.get(page)
    if not content:
        abort(404)
    return render_template(
        "cadu_workspace/public_page.html", page=page, content=content,
        canonical=product_url("workspace", f"/{page}"), description=content["description"],
        help_url=_cadu_area("CADU_HELP_URL", "/ajuda"),
    )


@bp.get("/workspace/assets/workspace-icon-<int:size>.png")
def workspace_icon(size):
    if size not in {32, 64, 128, 192}:
        abort(404)
    asset = Path(__file__).resolve().parents[2] / "output" / "mockups" / "brand-assets" / "icons-2d" / "workspace" / f"icon-{size}.png"
    return send_file(asset, mimetype="image/png", max_age=86400)


@bp.get("/app")
@login_required
def dashboard():
    client_id = int(session.get("cliente_id") or 0)
    try:
        from .. import db
        organization = dict(db.obter_cliente_por_id(client_id) or {})
    except Exception:
        organization = {}
    client_name = str(
        organization.get('nome_fantasia')
        or organization.get('razao_social')
        or session.get('client_name')
        or session.get('cliente_nome')
        or session.get('organization_name')
        or f'Cliente {client_id}'
    ).strip()
    projects = _workspace_projects(client_id)
    brands = _workspace_brands(client_id)
    # New authenticated organizations start with a focused setup instead of
    # landing on an empty enterprise shell. Existing records remain untouched.
    if (
        _workspace_onboarding_table_available()
        and not projects
        and not brands
        and not _workspace_onboarding_record(int(session.get('user_id') or 0), client_id)
    ):
        return redirect(url_for('cadu_workspace.workspace_onboarding'), code=302)
    customizations = list_customizations(client_id=client_id)
    sections = (
        ("Usuários e equipe", "Pessoas, convites e permissões da organização.", url_for("cadu_workspace.account_page", section="equipe"), "Workspace"),
        ("Planos", "Plano contratado, limites e recursos habilitados.", url_for("cadu_workspace.account_page", section="planos"), "Workspace"),
        ("Créditos", "Saldo, consumo e histórico compartilhado entre produtos.", url_for("cadu_workspace.account_page", section="creditos"), "Workspace"),
        ("Financeiro", "Faturas, pagamentos e dados de cobrança.", url_for("cadu_workspace.account_page", section="faturamento"), "Conta"),
        ("Integrações", "Conexões autorizadas para os produtos da organização.", url_for("cadu_workspace.integrations"), "Workspace"),
        ("Ajuda", "Orientação de uso e canais de atendimento.", url_for("cadu_workspace.public_page", page="ajuda"), "Suporte"),
    )
    credit = credit_position(client_id)
    usage = float(credit.get('monthly_usage_percentage') or 0)
    brand_project_counts: dict[str, int] = {}
    try:
        project_brand_links = family_repository.project_brand_links(client_id)
    except Exception:
        current_app.logger.warning('Não foi possível carregar contagens de vínculos de marcas do cliente %s', client_id, exc_info=True)
        project_brand_links = []
    for link in project_brand_links:
        brand_ref = str(link.get('brand_ref') or '')
        if brand_ref.startswith('studio:'):
            brand_project_counts[brand_ref] = brand_project_counts.get(brand_ref, 0) + 1
    brand_items = [{'id': str(item.get('id')), 'kind': 'brand', 'title': str(item.get('name') or 'Marca'),
                    'name': str(item.get('name') or 'Marca'), 'logoUrl': str(item.get('display_logo') or ''),
                    'visualInitials': str(item.get('display_initials') or 'M'),
                    'visualColor': str(item.get('display_color') or item.get('primary_color') or '#176b5e'),
                    'visualVariant': _dock_visual_variant('brand', item.get('id')),
                    'href': url_for('cadu_workspace.brand_detail', brand_id=int(item.get('id'))),
                    'projectCount': brand_project_counts.get(f"studio:{item.get('id')}", 0)}
                   for item in brands]
    # The dock and the workspace sidebar both render a deterministic initials
    # fallback when a brand has no usable logo. Do not hide those brands here.
    visible_brands = brand_items[:8]
    project_items = [{'id': f"ci:{item.get('id')}", 'kind': 'project', 'title': str(item.get('nome') or 'Projeto'),
                      'name': str(item.get('nome') or 'Projeto'), 'href': url_for('cadu_workspace.project_detail', project_id=str(item.get('id'))),
                      'previewUrl': str(item.get('thumbnail_url') or ''), 'projectRef': f"ci:{item.get('id')}",
                      'dockLogoUrl': str(item.get('brand_logo_url') or ''),
                      'brandName': str(item.get('thumbnail_label') or ''),
                      'visualInitials': str(item.get('thumbnail_initials') or 'P'),
                      'visualColor': str(item.get('thumbnail_color') or item.get('cor') or '#176b5e'),
                      'visualVariant': _dock_visual_variant('project', item.get('id'))} for item in projects]
    dock_items = _workspace_common_dock_items(
        client_id, int(session.get('user_id') or 0), projects=projects, brands=brands,
    )
    dock_resource_items = _workspace_dock_resource_items(client_id, projects)
    continuity_feed = _workspace_continuity_feed(client_id, projects, {
        'id': int(session.get('user_id') or 0),
        # Older Workspace sessions do not carry organization_id. In that
        # case the client is the organization boundary used by Cadu Family.
        'organization_id': int(session.get('organization_id') or session.get('organizacao_id') or client_id),
    })
    decisions = []
    for item in projects[:8]:
        missing = []
        if not item.get('descricao'):
            missing.append('descrever o contexto')
        if not int(item.get('fontes_prontas') or 0):
            missing.append('adicionar fontes')
        if not any(item.get(field) for field in ('publico', 'tom_de_voz', 'posicionamento', 'instrucoes')):
            missing.append('definir orientações')
        project_id = str(item.get('id') or '')
        project_name = str(item.get('nome') or 'Projeto')
        decisions.append({
            'id': f'project-decision:{project_id}',
            'title': f"{'Complete' if missing else 'Revise'} o contexto de {project_name}",
            'context': ', '.join(missing[:2]) if missing else 'Escolha o próximo resultado para este projeto.',
            'detail': ', '.join(missing),
            'href': url_for('cadu_workspace.project_detail', project_id=project_id),
            'projectRef': f'ci:{project_id}',
        })
    home_data = {
        'agency': {'id': str(client_id), 'name': client_name},
        # Every brand has a visual identity in the React shell. A principal logo
        # is preferred, but the approved initials and color are a deliberate
        # fallback when a logo is still being prepared or cannot be loaded.
        'brands': visible_brands,
        'catalogBrands': brand_items,
        'projects': project_items,
        'dock': {'items': dock_items, 'isSuggested': not any(item.get('shortcutId') for item in dock_items)},
        'resources': dock_resource_items,
        'recentConversations': [item for item in continuity_feed if item.get('kind') == 'conversation'],
        'resumeCards': continuity_feed,
        'decisions': decisions,
        'activity': continuity_feed,
        'usagePercent': round(usage, 1),
        'preferences': _user_home_preferences(client_id, int(session.get('user_id') or 0)),
    }
    return render_template(
        "cadu_workspace/workspace_home_chat.html", sections=sections, projects=projects, brands=brands,
        customizations=customizations, credit=credit, hero=secrets.choice(WORKSPACE_APP_HEROES),
        data_health=_workspace_data_health(), home_data=home_data,
    )


@bp.get("/workspace/app/visao-geral")
@login_required
def legacy_dashboard_overview():
    """Keep the previous dashboard available while the prompt-first home evolves."""
    client_id = int(session.get("cliente_id") or 0)
    return render_template(
        "cadu_workspace/index.html", sections=[], projects=_workspace_projects(client_id),
        brands=_workspace_brands(client_id), customizations=list_customizations(client_id=client_id),
        credit=credit_position(client_id), hero=secrets.choice(WORKSPACE_APP_HEROES),
        data_health=_workspace_data_health(),
    )


@bp.get("/workspace/app")
@login_required
def legacy_dashboard_url():
    """Preserve favoritos antigos e exponha a entrada curta do produto."""
    return redirect(url_for("cadu_workspace.dashboard"), code=308)


@bp.get('/workspace/app/conversas')
@bp.get('/conversas')
@login_required
def conversations():
    """Compatibility entry; the customer-facing conversation surface is React V2."""
    target = '/workspace/conversas-v2-lab'
    if request.query_string:
        target = f'{target}?{request.query_string.decode("utf-8")}'
    return redirect(target, code=308)


@bp.get('/workspace/app/marcas')
@login_required
def brands():
    if request.path.startswith('/workspace/app/'):
        return redirect(url_for('cadu_workspace.clean_brands'), code=308)
    client_id = int(session.get('cliente_id') or 0)
    query = request.args.get('q', '')
    filter_name = request.args.get('filtro', 'todas')
    filter_name = filter_name if filter_name in {'todas', 'auditadas', 'com-ativos'} else 'todas'
    records = _workspace_brands(client_id, query)
    if filter_name == 'auditadas':
        records = [brand for brand in records if brand.get('analysis_metadata')]
    elif filter_name == 'com-ativos':
        records = [brand for brand in records if int(brand.get('asset_count') or 0)]
    if request.args.get('legacy') != '1':
        projects = _workspace_projects(client_id)
        catalog_error = ''
        try:
            all_brands = _workspace_brands(client_id, raise_on_error=True)
        except Exception:
            current_app.logger.exception('Não foi possível carregar o catálogo de marcas do cliente %s', client_id)
            all_brands = []
            catalog_error = 'As marcas estão temporariamente indisponíveis. Atualize a página para tentar novamente.'
        catalog_records = all_brands
        if filter_name == 'auditadas':
            catalog_records = [brand for brand in catalog_records if brand.get('analysis_metadata')]
        elif filter_name == 'com-ativos':
            catalog_records = [brand for brand in catalog_records if int(brand.get('asset_count') or 0)]
        brand_items = [{'id': str(item.get('id')), 'kind': 'brand', 'name': str(item.get('name') or 'Marca'),
                        'title': str(item.get('name') or 'Marca'), 'logoUrl': str(item.get('display_logo') or ''),
                        'visualInitials': str(item.get('display_initials') or 'M'),
                        'visualColor': str(item.get('display_color') or item.get('primary_color') or '#176b5e'),
                        'visualVariant': _dock_visual_variant('brand', item.get('id')),
                        'sector': str(item.get('sector') or ''), 'summary': str(item.get('display_summary') or ''),
                        'assetCount': int(item.get('asset_count') or 0), 'audited': bool(item.get('analysis_metadata')),
                        'href': url_for('cadu_workspace.clean_brand_detail', brand_id=int(item.get('id')))} for item in catalog_records]
        project_items = [{'id': f"ci:{item.get('id')}", 'kind': 'project', 'title': str(item.get('nome') or 'Projeto'),
                          'projectRef': f"ci:{item.get('id')}", 'previewUrl': str(item.get('brand_logo_url') or ''),
                          'visualInitials': str(item.get('thumbnail_initials') or 'P'), 'visualColor': str(item.get('thumbnail_color') or item.get('cor') or '#176b5e'),
                          'visualVariant': _dock_visual_variant('project', item.get('id')),
                          'href': url_for('cadu_workspace.project_detail', project_id=str(item.get('id')))} for item in projects]
        dock_items = _workspace_common_dock_items(client_id, int(session.get('user_id') or 0))
        return render_template('cadu_workspace/brands_react.html', brand_items=brand_items, project_items=project_items, dock_items=dock_items,
                               query=query, filter_name=filter_name, catalog_error=catalog_error,
                               usage_percent=round(float(credit_position(client_id).get('monthly_usage_percentage') or 0), 1))
    return render_template('cadu_workspace/brands.html', brands=records, query=query, filter_name=filter_name)


@bp.get('/marcas')
@login_required
def clean_brands():
    return brands()


@bp.get('/docs')
@login_required
def documents():
    client_id = int(session.get('cliente_id') or 0)
    actor_id = int(session.get('user_id') or 0)
    try:
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT id, titulo, tipo, status, updated_at
                                FROM cadu_artifacts
                               WHERE id_cliente = %s
                                 AND (id_contato_cliente = %s OR share_enabled = TRUE)
                            ORDER BY updated_at DESC LIMIT 60""", (client_id, actor_id))
            records = [dict(row) for row in cursor.fetchall()]
    except Exception:
        records = []
    return render_template('cadu_workspace/documents.html', documents=records)


@bp.get('/docs/<document_id>')
@login_required
def document_editor(document_id):
    """Open a Smart Doc in the Workspace-owned editing surface."""
    from ..cadu_planner import docs
    document = docs.get_document(
        int(session.get('cliente_id') or 0), int(session['user_id']), document_id,
    )
    document['html'] = docs.sanitize_html(document.get('html'))
    project = _workspace_project(int(session.get('cliente_id') or 0), str(document['project_id'])) if document.get('project_id') else None
    return render_template('cadu_workspace/document_editor.html', document=document, project=project)


@bp.post('/docs/<document_id>')
@login_required
def save_workspace_document(document_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    from ..cadu_planner import docs
    docs.save_document(
        int(session.get('cliente_id') or 0), int(session['user_id']), document_id,
        {'title': request.form.get('title'), 'status': request.form.get('status'),
         'html': request.form.get('html')},
    )
    return redirect(url_for('cadu_workspace.document_editor', document_id=document_id, saved='1'), code=303)


def _workspace_document(document_id):
    from ..cadu_planner import docs
    return docs, docs.get_document(int(session.get('cliente_id') or 0), int(session['user_id']), document_id)


def _workspace_document_sources(document, source_ids):
    """Return a bounded, authorized source pack for a document review."""
    project_id = document.get('project_id')
    if not project_id or not source_ids:
        return ''
    try:
        source_ids = [int(item) for item in source_ids][:8]
    except (TypeError, ValueError):
        abort(400, description='Uma das fontes selecionadas é inválida.')
    if not source_ids:
        return ''
    try:
        with get_db().cursor() as cursor:
            cursor.execute('''SELECT f.nome_arquivo, string_agg(c.conteudo, E'\\n' ORDER BY c.ordem) AS content
                                FROM cadu_ci_projeto_arquivos f
                                JOIN cadu_ci_chunks c ON c.arquivo_id = f.id AND c.projeto_id = f.projeto_id
                               WHERE f.projeto_id = %s AND f.id_cliente = %s AND f.id = ANY(%s)
                            GROUP BY f.id, f.nome_arquivo ORDER BY f.nome_arquivo''',
                           (str(project_id), int(session.get('cliente_id') or 0), source_ids))
            rows = [dict(row) for row in cursor.fetchall()]
    except Exception:
        abort(503, description='Não foi possível carregar as fontes do projeto agora.')
    return '\n\n'.join('Fonte: %s\n%s' % (row['nome_arquivo'], str(row.get('content') or '')[:6000]) for row in rows)[:24000]


@bp.put('/docs/<document_id>/content')
@login_required
def save_workspace_document_content(document_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    docs, _ = _workspace_document(document_id)
    payload = request.get_json(silent=True) or {}
    document = docs.save_document(int(session.get('cliente_id') or 0), int(session['user_id']), document_id, payload)
    return jsonify(document=document)


@bp.get('/docs/<document_id>/context')
@login_required
def workspace_document_context(document_id):
    _, document = _workspace_document(document_id)
    project_id = document.get('project_id')
    project = _workspace_project(int(session.get('cliente_id') or 0), str(project_id)) if project_id else None
    return jsonify(project=({key: project.get(key) for key in ('id', 'nome', 'descricao')} if project else None),
                   files=(project or {}).get('files', []))


@bp.post('/docs/<document_id>/duplicate')
@login_required
def duplicate_workspace_document(document_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    docs, _ = _workspace_document(document_id)
    document = docs.duplicate_document(int(session.get('cliente_id') or 0), int(session['user_id']), document_id)
    return jsonify(document=document), 201


@bp.post('/docs/<document_id>/share')
@login_required
def share_workspace_document(document_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    docs, _ = _workspace_document(document_id)
    payload = request.get_json(silent=True) or {}
    document = docs.share_document(int(session.get('cliente_id') or 0), int(session['user_id']), document_id, payload.get('enabled', True))
    return jsonify(document=document)


@bp.get('/docs/<document_id>/export')
@login_required
def export_workspace_document(document_id):
    docs, document = _workspace_document(document_id)
    safe_name = re.sub(r'[^\w.-]+', '-', str(document.get('title') or 'documento'), flags=re.UNICODE).strip('-') or 'documento'
    return send_file(BytesIO(docs.export_pdf(document)), mimetype='application/pdf', as_attachment=True,
                     download_name=f'{safe_name}.pdf')


@bp.get('/docs/<document_id>/review/estimate')
@login_required
def workspace_document_review_estimate(document_id):
    from ..cadu_planner import revisions
    _workspace_document(document_id)
    estimate = revisions.document_estimate(int(session.get('cliente_id') or 0), int(session['user_id']), document_id)
    return jsonify(estimated_tokens=estimate, passes=3)


@bp.post('/docs/<document_id>/review')
@login_required
def review_workspace_document(document_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    from ..cadu_planner import revisions
    _, document = _workspace_document(document_id)
    payload = request.get_json(silent=True) or {}
    source_context = _workspace_document_sources(document, payload.get('source_ids') or [])
    return jsonify(revisions.review_document(int(session.get('cliente_id') or 0), int(session['user_id']), document_id,
                                             source_context=source_context))


@bp.post('/workspace/app/marcas')
@login_required
def create_brand():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    data = _workspace_brand_form()
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cx_clients
                       (crm_client_id, name, sector, tone_of_voice, primary_color,
                        secondary_color, website_url, brand_profile, analysis_metadata,
                        price_policy)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, '{}'::jsonb,
                            'hide_price')
                 RETURNING id""",
                (client_id, data['name'], data['sector'], data['profile']['tone_of_voice'],
                 data['primary_color'], data['secondary_color'], data['website_url'],
                 json.dumps(data['profile'])),
            )
            brand_id = int(cursor.fetchone()['id'])
        connection.commit()
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível criar uma marca no Workspace')
        abort(503, description='Não foi possível criar a marca agora. Tente novamente.')
    # The creation modal can carry the first logo and visual references.  Save
    # them with the new record so its first detail screen is already useful.
    files = [item for item in request.files.getlist('images') if item and item.filename][:8]
    if files:
        try:
            from ..creative_modeling_service import CreativeModelingService
            CreativeModelingService().upload_client_brand_assets(
                brand_id, files, request.form.get('primary_logo') == 'true', 'reference',
            )
        except ValueError as exc:
            current_app.logger.warning('Marca %s criada sem ativos: %s', brand_id, exc)
        except Exception:
            current_app.logger.exception('Marca %s criada, mas não foi possível salvar seus ativos', brand_id)
    # A brand without a project leaves its approved context orphaned. Create a
    # small dossier immediately; it will receive projections only after review.
    try:
        project_id = str(uuid4())
        with get_db().cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_ci_projetos
                       (id, id_cliente, criado_por, nome, descricao, instrucoes, tipo, cor, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'projeto', %s, 'ativo')""",
                (project_id, client_id, session.get('user_id'), data['name'],
                 f'Dossiê operacional da marca {data["name"]}.',
                 'Contexto de marca vinculado; decisões de campanha devem ser registradas neste projeto.',
                 data['primary_color'] or '#176b5e'),
            )
        get_db().commit()
        family_repository.set_project_brand_link(client_id, session.get('user_id'), f'ci:{project_id}', f'studio:{brand_id}', True)
    except Exception:
        try:
            get_db().rollback()
        except Exception:
            pass
        current_app.logger.exception('Marca %s criada sem projeto-dossiê automático', brand_id)
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id,
                            audit='start' if request.form.get('analyze') == 'true' else None), code=303)


@bp.get('/workspace/app/projetos')
@login_required
def projects():
    if request.path.startswith('/workspace/app/'):
        return redirect(url_for('cadu_workspace.clean_projects'), code=308)
    client_id = int(session.get('cliente_id') or 0)
    query = request.args.get('q', '')
    status = request.args.get('status', 'ativos')
    status = status if status in {'ativos', 'arquivados', 'todos'} else 'ativos'
    records = _workspace_projects(client_id, query, status)
    if request.args.get('legacy') != '1':
        catalog_error = ''
        try:
            catalog_records = _workspace_projects(client_id, status=status, raise_on_error=True)
        except Exception:
            current_app.logger.exception('Não foi possível carregar o catálogo de projetos do cliente %s', client_id)
            catalog_records = []
            catalog_error = 'Os projetos estão temporariamente indisponíveis. Atualize a página para tentar novamente.'
        items = [{'id': f"ci:{item.get('id')}", 'kind': 'project', 'name': str(item.get('nome') or 'Projeto'), 'title': str(item.get('nome') or 'Projeto'), 'projectRef': f"ci:{item.get('id')}", 'previewUrl': str(item.get('thumbnail_url') or ''), 'dockLogoUrl': str(item.get('brand_logo_url') or ''), 'visualInitials': str(item.get('thumbnail_initials') or 'P'), 'visualColor': str(item.get('thumbnail_color') or item.get('cor') or '#176b5e'), 'visualVariant': _dock_visual_variant('project', item.get('id')), 'description': str(item.get('descricao') or ''), 'brandName': str(item.get('thumbnail_label') or ''), 'status': str(item.get('status') or 'ativo'), 'sources': int(item.get('fontes_prontas') or 0), 'href': url_for('cadu_workspace.clean_project_detail', project_id=str(item.get('id')))} for item in catalog_records]
        brands = [{'id': str(item.get('id')), 'kind': 'brand', 'name': str(item.get('name') or 'Marca'), 'title': str(item.get('name') or 'Marca'), 'logoUrl': str(item.get('display_logo') or ''), 'visualInitials': str(item.get('display_initials') or 'M'), 'visualColor': str(item.get('display_color') or item.get('primary_color') or '#176b5e'), 'visualVariant': _dock_visual_variant('brand', item.get('id')), 'href': url_for('cadu_workspace.clean_brand_detail', brand_id=int(item.get('id')))} for item in _workspace_brands(client_id)]
        dock_items = _workspace_common_dock_items(client_id, int(session.get('user_id') or 0))
        return render_template('cadu_workspace/projects_react.html', project_items=items, brand_items=brands, dock_items=dock_items,
                               query=query, status=status, catalog_error=catalog_error,
                               usage_percent=round(float(credit_position(client_id).get('monthly_usage_percentage') or 0), 1))
    return render_template('cadu_workspace/projects.html', projects=records, query=query, status=status)


@bp.get('/projetos')
@login_required
def clean_projects():
    return projects()


@bp.post('/workspace/app/projetos')
@login_required
def create_project():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    name = ' '.join((request.form.get('name') or '').split())[:150]
    if len(name) < 2:
        abort(400, description='Informe um nome de projeto com ao menos dois caracteres.')
    client_id = int(session.get('cliente_id') or 0)
    project_id = str(uuid4())
    description = (request.form.get('description') or '').strip()[:4000]
    instructions = (request.form.get('instructions') or '').strip()[:12000]
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_ci_projetos
                       (id, id_cliente, criado_por, nome, descricao, instrucoes, tipo, cor, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'projeto', %s, 'ativo')""",
                (project_id, client_id, session.get('user_id'), name, description, instructions,
                 '#176b5e'),
            )
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        abort(503, description='Não foi possível criar o projeto agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.get('/workspace/app/projetos/<project_id>')
@login_required
def project_detail(project_id):
    if request.path.startswith('/workspace/app/'):
        return redirect(url_for('cadu_workspace.clean_project_detail', project_id=project_id,
                                **request.args.to_dict(flat=True)), code=308)
    client_id = int(session.get('cliente_id') or 0)
    project = _workspace_project(client_id, project_id)
    if not project:
        abort(404)
    _remember_workspace_project(project_id)
    # Keep the established dossier available as a continuity surface while the
    # React view becomes the default. This makes the migration reversible for
    # the few administrative flows that are still being consolidated.
    if request.args.get('legacy') != '1':
        projects = _workspace_projects(client_id)
        brands = _workspace_brands(client_id)
        project_items = [{
            'id': f"ci:{item.get('id')}", 'kind': 'project',
            'title': str(item.get('nome') or 'Projeto'),
            'previewUrl': str(item.get('brand_logo_url') or ''),
            'visualInitials': str(item.get('thumbnail_initials') or 'P'),
            'visualColor': str(item.get('thumbnail_color') or item.get('cor') or '#176b5e'),
            'visualVariant': _dock_visual_variant('project', item.get('id')),
            'projectRef': f"ci:{item.get('id')}",
            'href': url_for('cadu_workspace.project_detail', project_id=str(item.get('id'))),
        } for item in projects]
        brand_items = [{
            'id': str(item.get('id')), 'kind': 'brand', 'title': str(item.get('name') or 'Marca'),
            'name': str(item.get('name') or 'Marca'), 'logoUrl': str(item.get('display_logo') or ''),
            'visualInitials': str(item.get('display_initials') or 'M'),
            'visualColor': str(item.get('display_color') or item.get('primary_color') or '#176b5e'),
            'visualVariant': _dock_visual_variant('brand', item.get('id')),
            'href': url_for('cadu_workspace.brand_detail', brand_id=int(item.get('id'))),
        } for item in brands]
        dock_items = _workspace_common_dock_items(client_id, int(session.get('user_id') or 0))
        active_brand = next(iter(project.get('brands') or []), {})
        project_conversation_url = url_for(
            'cadu_agent_v2_lab.conversations_v2_lab',
            project_ref=f'ci:{project_id}', history='1',
        )
        conversation_items = []
        for item in project.get('conversations') or []:
            conversation_id = str(item.get('id') or '').strip()
            if not conversation_id:
                continue
            message_count = int(item.get('total_mensagens') or 0)
            conversation_items.append({
                'id': conversation_id,
                'title': str(item.get('titulo') or 'Conversa sem título'),
                'detail': f"{message_count} mensagem{'s' if message_count != 1 else ''}",
                'updatedAt': item.get('updated_at'),
                'href': url_for(
                    'cadu_agent_v2_lab.conversations_v2_lab',
                    conversation_id=conversation_id, project_ref=f'ci:{project_id}', history='1',
                ),
            })

        artifact_items = []
        workspace_artifact_labels = {
            'html': ('html', 'HTML'), 'note': ('text', 'Texto'), 'brief': ('text', 'Briefing'),
            'document': ('text', 'Documento'), 'executive_summary': ('text', 'Resumo'),
            'meeting_summary': ('text', 'Resumo de reunião'), 'meeting_agenda': ('text', 'Pauta'),
            'media_plan': ('plan', 'Plano de mídia'), 'scenario': ('text', 'Cenário'),
            'research': ('text', 'Pesquisa'), 'project_map': ('text', 'Mapa do projeto'),
        }
        status_labels = {'draft': 'Rascunho', 'active': 'Ativo', 'published': 'Publicado', 'archived': 'Arquivado'}
        source_status_labels = {'completed': 'Pronta para consulta', 'indexing': 'Indexando', 'queued': 'Na fila', 'error': 'Requer atenção', 'paused': 'Somente anexo'}
        for item in project.get('workspace_artifacts') or []:
            artifact_id = str(item.get('id') or '').strip()
            if not artifact_id:
                continue
            artifact_type = str(item.get('type') or 'document').lower()
            kind, kind_label = workspace_artifact_labels.get(artifact_type, ('text', 'Documento'))
            conversation_id = str(item.get('conversation_id') or '').strip()
            artifact_items.append({
                'id': f'workspace-artifact:{artifact_id}',
                'kind': kind,
                'kindLabel': kind_label,
                'title': str(item.get('title') or 'Artefato sem título'),
                'detail': f"{kind_label} · v{int(item.get('current_version') or 1)} · {status_labels.get(str(item.get('status') or ''), 'Salvo')}"
                          + (" · Retomar no projeto" if not conversation_id else ''),
                'status': str(item.get('status') or 'saved'),
                'updatedAt': item.get('updated_at'),
                'href': url_for(
                    'cadu_agent_v2_lab.conversations_v2_lab',
                    conversation_id=conversation_id, project_ref=f'ci:{project_id}', history='1',
                ) if conversation_id else project_conversation_url,
            })
        for item in project.get('files') or []:
            source_id = str(item.get('id') or '').strip()
            if not source_id:
                continue
            mime = str(item.get('mime') or '').lower()
            filename = str(item.get('nome_arquivo') or '')
            suffix = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if mime == 'application/pdf' or suffix == 'pdf':
                kind, kind_label = 'pdf', 'PDF'
            elif mime.startswith('image/'):
                kind, kind_label = 'image', 'Imagem'
            elif 'html' in mime or suffix in {'htm', 'html'}:
                kind, kind_label = 'html', 'HTML'
            elif mime.startswith('text/') or suffix in {'md', 'txt', 'csv', 'json'}:
                kind, kind_label = 'text', 'Texto'
            else:
                kind, kind_label = 'file', 'Arquivo'
            artifact_items.append({
                'id': f'file:{source_id}', 'kind': kind, 'kindLabel': kind_label,
                'title': filename or 'Arquivo do projeto',
                'detail': f"{kind_label} · {source_status_labels.get(str(item.get('indexing_status') or ''), 'Arquivo preservado')}",
                'status': str(item.get('indexing_status') or 'saved'),
                'updatedAt': item.get('created_at'),
                'href': url_for('cadu_workspace.download_project_source', project_id=project_id, source_id=source_id)
                if str(item.get('storage_path') or '').startswith('workspace_project_sources/') else '',
            })
        for item in project.get('images') or []:
            image_id = str(item.get('id') or '').strip()
            if not image_id:
                continue
            artifact_items.append({
                'id': f'image:{image_id}', 'kind': 'image', 'kindLabel': 'Imagem',
                'title': str(item.get('title') or 'Imagem do projeto'),
                'detail': f"Imagem · {item.get('mime') or 'prévia indisponível'}",
                'status': 'available' if item.get('preview_url') else 'saved',
                'updatedAt': item.get('created_at'), 'href': str(item.get('preview_url') or ''),
            })
        artifact_items.sort(key=lambda item: str(item.get('updatedAt') or ''), reverse=True)
        project_resources = [
            item for item in project.get('resources') or []
            if str(item.get('source_system') or '') != 'planner_docs'
        ]
        project_data = {
            'id': str(project.get('id')), 'name': str(project.get('nome') or 'Projeto'),
            'description': str(project.get('descricao') or ''),
            'instructions': str(project.get('instrucoes') or ''),
            'status': str(project.get('status') or 'ativo'),
            'color': str(project.get('cor') or '#176b5e'),
            'visualVariant': _dock_visual_variant('project', project.get('id')),
            'identity': {field: str(project.get(field) or '') for field in ('publico', 'tom_de_voz', 'posicionamento')},
            'brand': {
                'id': str(active_brand.get('id') or ''),
                'name': str(active_brand.get('name') or ''),
                'crmClientId': str(active_brand.get('crm_client_id') or ''),
                'href': url_for('cadu_workspace.clean_brand_detail', brand_id=active_brand['id']) if active_brand else '',
                'auditHref': f"{url_for('cadu_workspace.clean_brand_detail', brand_id=active_brand['id'])}?audit=start" if active_brand else '',
                'logoUrl': str(active_brand.get('display_logo') or ''),
                'initials': str(active_brand.get('display_initials') or ''),
                'color': str(active_brand.get('primary_color') or ''),
                'secondaryColor': str(active_brand.get('secondary_color') or ''),
                'profile': {
                    'colorPalette': (active_brand.get('brand_profile') or {}).get('color_palette') if isinstance(active_brand.get('brand_profile'), dict) else [],
                    'fonts': (active_brand.get('brand_profile') or {}).get('fonts') if isinstance(active_brand.get('brand_profile'), dict) else [],
                },
                'visualVariant': _dock_visual_variant('brand', active_brand.get('id')) if active_brand else 0,
            },
            'files': [{'id': str(item.get('id')), 'title': str(item.get('nome_arquivo') or 'Fonte'),
                       'mime': str(item.get('mime') or 'Arquivo'), 'status': str(item.get('indexing_status') or 'queued'),
                       'purpose': str(item.get('purpose') or 'project_attachment'),
                       'category': str(item.get('category') or 'other'),
                       'classificationStatus': str(item.get('classification_status') or 'pending'),
                       'classificationConfidence': float(item.get('classification_confidence') or 0),
                       'classificationReason': str(item.get('classification_reason') or ''),
                       'canIndex': int(item.get('word_count') or 0) >= 20,
                       'requiresReview': str(item.get('purpose') or 'project_attachment') == 'project_attachment' and str(item.get('indexing_status') or '') == 'paused' and str(item.get('classification_status') or '') in {'pending', 'classified', 'needs_review'},
                       'confirmUrl': url_for('cadu_workspace.confirm_project_source', project_id=project_id, source_id=item.get('id')),
                       'words': int(item.get('word_count') or 0)} for item in project.get('files') or []],
            'conversations': conversation_items,
            'artifacts': artifact_items,
            'deliveries': ([{'id': f"plan:{item.get('id')}", 'title': str(item.get('title') or 'Plano de mídia'),
                             'kind': 'Planejamento', 'status': str(item.get('status') or ''),
                             'href': product_url('planner', f"/planos/{item.get('id')}")} for item in project.get('plans') or []] +
                           [{'id': f"image:{item.get('id')}", 'title': str(item.get('title') or 'Imagem do projeto'),
                             'kind': 'Criação visual', 'status': 'Prévia disponível' if item.get('preview_url') else 'Registro visual',
                             'href': str(item.get('preview_url') or '')} for item in project.get('images') or []] +
                           [{'id': f"analysis:{item.get('public_id')}", 'title': str(item.get('original_name') or 'Criativo analisado'),
                             'kind': 'Análise criativa', 'status': str(item.get('status') or ''),
                             'href': product_url('studio', f"/analyzer/{item.get('public_id')}")} for item in project.get('creative_analyses') or []]),
            'resources': [{'id': str(item.get('id') or item.get('resource_id') or item.get('title')), 'title': str(item.get('title') or 'Recurso'),
                           'kind': str(item.get('category') or item.get('resource_type') or 'Recurso'),
                           'resourceType': str(item.get('resource_type') or ''), 'mime': str(item.get('mime_type') or ''),
                           'locator': str(item.get('locator') or ''), 'status': str(item.get('status') or '')} for item in project_resources],
            'resourceRegistryAvailable': bool(project.get('resource_registry_available')),
            'memory': [{'id': str(item.get('id')), 'kind': str(item.get('kind') or 'Memória'),
                        'summary': str(item.get('summary') or '')} for item in (project.get('memory') or {}).get('confirmed', [])],
            'activity': [{'id': f"{index}:{item.get('title')}", 'title': str(item.get('title') or 'Atualização'),
                          'detail': str(item.get('detail') or '')} for index, item in enumerate(project.get('activity') or [])],
            'links': [{'id': str(item.get('id')), 'title': str(item.get('titulo') or 'Atalho'), 'url': str(item.get('url') or ''),
                       'provider': str(item.get('provider') or '')} for item in project.get('links') or []],
            'health': project.get('context_health') or {},
        }
        return render_template(
            'cadu_workspace/project_detail_react.html', project_data=project_data,
            project_items=project_items, brand_items=brand_items, dock_items=dock_items,
            usage_percent=round(float(credit_position(client_id).get('monthly_usage_percentage') or 0), 1),
        )
    return render_template('cadu_workspace/project_detail.html', project=project, brands=_workspace_brands(client_id),
                           can_manage_brand=session.get('user_type') in {'admin', 'superadmin'})


@bp.get('/projetos/<project_id>')
@login_required
def clean_project_detail(project_id):
    return project_detail(project_id)


@bp.post('/projetos/<project_id>/atalhos')
@login_required
def create_project_link(project_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    try:
        link = _project_link_metadata(request.form.get('url'), request.form.get('title'))
    except ValueError as error:
        return redirect(url_for('cadu_workspace.project_detail', project_id=project_id, link_error=str(error)), code=303)
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_ci_projeto_links
                    (id, projeto_id, id_cliente, criado_por, provider, url, titulo, position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s,
                            COALESCE((SELECT MAX(position) + 1 FROM cadu_ci_projeto_links
                                      WHERE projeto_id = %s AND id_cliente = %s), 0))""",
                (str(uuid4()), project_id, client_id, session.get('user_id'), link['provider'],
                 link['url'], link['title'], project_id, client_id),
            )
        connection.commit()
    except Exception:
        if connection:
            connection.rollback()
        current_app.logger.exception('Não foi possível salvar atalho do projeto %s', project_id)
        return redirect(url_for('cadu_workspace.project_detail', project_id=project_id,
                                link_error='Não foi possível salvar o atalho agora.'), code=303)
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id,
                            link_notice='Atalho adicionado ao projeto.'), code=303)


@bp.post('/projetos/<project_id>/atalhos/<link_id>')
@login_required
def update_project_link(project_id, link_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    try:
        link = _project_link_metadata(request.form.get('url'), request.form.get('title'))
    except ValueError as error:
        return redirect(url_for('cadu_workspace.project_detail', project_id=project_id, link_error=str(error)), code=303)
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                '''UPDATE cadu_ci_projeto_links
                      SET provider = %s, url = %s, titulo = %s, updated_at = NOW()
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s''',
                (link['provider'], link['url'], link['title'], link_id, project_id, client_id),
            )
            if not cursor.rowcount:
                abort(404)
        connection.commit()
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception:
        if connection:
            connection.rollback()
        current_app.logger.exception('Não foi possível atualizar atalho do projeto %s', project_id)
        return redirect(url_for('cadu_workspace.project_detail', project_id=project_id,
                                link_error='Não foi possível atualizar o atalho agora.'), code=303)
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id,
                            link_notice='Atalho atualizado.'), code=303)


@bp.post('/projetos/<project_id>/atalhos/<link_id>/remover')
@login_required
def remove_project_link(project_id, link_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM cadu_ci_projeto_links WHERE id = %s AND projeto_id = %s AND id_cliente = %s',
                           (link_id, project_id, client_id))
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        abort(503, description='Não foi possível remover o atalho agora.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id,
                            link_notice='Atalho removido do projeto.'), code=303)


@bp.get('/workspace/app/projetos/<project_id>/imagens/<int:image_id>')
@login_required
def project_image(project_id, image_id):
    """Serve a legacy project image stored in PostgreSQL within its owner scope."""
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_project(client_id, project_id):
        abort(404)
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT file_bytes, mime, title
                     FROM cadu_docs_client_images
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s
                      AND ativo = true""",
                (image_id, project_id, client_id),
            )
            image = cursor.fetchone()
    except Exception:
        current_app.logger.exception('Não foi possível carregar a imagem %s do projeto %s', image_id, project_id)
        abort(404)

    content = image.get('file_bytes') if image else None
    if not content:
        abort(404)
    mime = str(image.get('mime') or '').lower()
    if mime not in {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}:
        abort(404)
    filename = re.sub(r'[^\\w.-]+', '-', str(image.get('title') or 'imagem'))[:100] or 'imagem'
    extension = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif'}[mime]
    if not filename.lower().endswith(extension):
        filename += extension
    return send_file(
        BytesIO(bytes(content)),
        mimetype=mime,
        download_name=filename,
        conditional=True,
        max_age=0,
    )


@bp.post('/workspace/app/projetos/<project_id>/contexto')
@login_required
def update_project_context(project_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    name = ' '.join((request.form.get('name') or '').split())[:150]
    if len(name) < 2:
        abort(400, description='O projeto precisa de um nome com ao menos dois caracteres.')
    description = (request.form.get('description') or '').strip()[:4000]
    instructions = (request.form.get('instructions') or '').strip()[:12000]
    tone = (request.form.get('tone_of_voice') or '').strip()[:4000]
    audience = (request.form.get('audience') or '').strip()[:4000]
    positioning = (request.form.get('positioning') or '').strip()[:4000]
    color = (request.form.get('color') or '#176b5e').strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        abort(400, description='Use uma cor hexadecimal válida para o projeto.')
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_ci_projetos SET nome = %s, descricao = %s, instrucoes = %s,
                          tom_de_voz = %s, publico = %s, posicionamento = %s, cor = %s, updated_at = NOW()
                    WHERE id = %s AND id_cliente = %s""",
                (name, description, instructions, tone, audience, positioning, color, project_id, client_id),
            )
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        abort(503, description='Não foi possível salvar o contexto agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/marcas')
@login_required
def update_project_brands(project_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    valid_ids = {str(item['id']) for item in _workspace_brands(client_id)}
    project_ref = f'ci:{project_id}'
    additive_brand_id = str(request.form.get('add_brand_id') or '').strip()
    if additive_brand_id and additive_brand_id not in valid_ids:
        abort(404)
    try:
        existing = {str(item.get('brand_ref') or '') for item in family_repository.project_brand_links(client_id)
                    if item.get('project_ref') == project_ref and str(item.get('brand_ref') or '').startswith('studio:')}
        if additive_brand_id:
            selected = existing | {f'studio:{additive_brand_id}'}
        else:
            wanted = {value for value in request.form.getlist('brand_ids') if value in valid_ids}
            selected = {f'studio:{brand_id}' for brand_id in wanted}
        for brand_ref in existing - selected:
            family_repository.set_project_brand_link(client_id, session.get('user_id'), project_ref, brand_ref, False)
        for brand_ref in selected - existing:
            family_repository.set_project_brand_link(client_id, session.get('user_id'), project_ref, brand_ref, True)
    except Exception:
        current_app.logger.exception('Não foi possível atualizar marcas do projeto')
        abort(503, description='Não foi possível atualizar as marcas agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/marcas/importar')
@login_required
def import_project_brand(project_id):
    """Create, attach and audit a brand from the project decision surface."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    credit_response = _brand_audit_credit_gate(client_id)
    if credit_response is not None:
        return credit_response
    name = ' '.join((request.form.get('brand_name') or '').split())[:150]
    website_url = _normalized_website_url(request.form.get('website_url') or '', required=True)
    if len(name) < 2:
        abort(400, description='Informe o nome da marca.')
    job_id = uuid4().hex
    logo = request.files.get('logo')
    references = [item for item in request.files.getlist('images') if item and item.filename][:8]
    uploaded = ([logo] if logo and logo.filename else []) + references
    image_payload = []
    for item in uploaded[:4]:
        image_payload.append({
            'filename': item.filename,
            'content_type': item.mimetype,
            'content': item.read(),
        })
        item.stream.seek(0)
    metadata = {'review_pack': {
        'job_id': job_id, 'status': 'queued', 'stage': 'queued', 'index': 0, 'total': 4,
        'message': 'A importação entrou na fila.', 'error': '',
        'created_at': _utc_timestamp(),
        'input': {'website_url': website_url, 'has_images': bool(image_payload)}, 'analysis': {}, 'reviews': [],
    }}
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''INSERT INTO cx_clients
                       (crm_client_id, name, website_url, primary_color, secondary_color,
                        brand_profile, analysis_metadata, price_policy)
                   VALUES (%s, %s, %s, '#176b5e', '#dcece6', '{}'::jsonb, %s::jsonb, 'hide_price')
                RETURNING id''', (client_id, name, website_url, json.dumps(metadata)))
            brand_id = int(cursor.fetchone()['id'])
        connection.commit()
        project_ref = f'ci:{project_id}'
        for link in family_repository.project_brand_links(client_id):
            brand_ref = str(link.get('brand_ref') or '')
            if link.get('project_ref') == project_ref and brand_ref.startswith('studio:'):
                family_repository.set_project_brand_link(client_id, session.get('user_id'), project_ref, brand_ref, False)
        family_repository.set_project_brand_link(
            client_id, session.get('user_id'), project_ref, f'studio:{brand_id}', True,
        )
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível importar a marca para o projeto %s', project_id)
        abort(503, description='Não foi possível iniciar a importação da marca agora.')
    if uploaded:
        try:
            from ..creative_modeling_service import CreativeModelingService
            service = CreativeModelingService()
            if logo and logo.filename:
                service.upload_client_brand_assets(brand_id, [logo], True, 'logo')
            if references:
                service.upload_client_brand_assets(brand_id, references, False, 'reference')
        except ValueError as exc:
            current_app.logger.warning('Marca %s criada sem todos os ativos enviados: %s', brand_id, exc)
        except Exception:
            current_app.logger.exception('Marca %s criada, mas não foi possível salvar os ativos enviados', brand_id)
    _start_brand_review_job(client_id, int(session.get('user_id') or 0), brand_id, job_id, website_url, image_payload)
    payload = {
        'ok': True, 'brand_id': brand_id, 'status': 'queued',
        'status_url': url_for('cadu_workspace.brand_audit_status', brand_id=brand_id),
        'brand_url': url_for('cadu_workspace.brand_detail', brand_id=brand_id),
    }
    if request.accept_mimetypes.best == 'application/json':
        return jsonify(payload), 202
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/fontes/notas')
@login_required
def create_project_note(project_id):
    """Add a user-reviewed text source to the existing project knowledge base."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    title = ' '.join((request.form.get('title') or '').split())[:180]
    content = (request.form.get('content') or '').strip()[:50000]
    if len(title) < 2:
        abort(400, description='Dê um título para identificar esta fonte.')
    if len(content) < 20:
        abort(400, description='A nota precisa ter ao menos 20 caracteres de contexto.')
    if not _chunk_project_note(content):
        abort(400, description='A nota não contém texto que possa ser indexado.')
    storage_path = f'workspace://project-notes/{uuid4()}'
    try:
        queued = _try_queue_project_source(
            client_id, project_id, title, content, 'text/markdown',
            len(content.encode('utf-8')), storage_path, 'workspace_note',
        )
        if queued:
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'ok': True, **queued, 'status': 'queued'}), 202
            return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)
        _persist_project_source(
            client_id, project_id, title, content, 'text/markdown',
            len(content.encode('utf-8')), storage_path, 'workspace_note',
        )
    except project_knowledge.KnowledgeIndexError as exc:
        try:
            source_id = _persist_project_source_index_error(
                client_id, project_id, title, content, 'text/markdown',
                len(content.encode('utf-8')), storage_path, 'workspace_note', exc,
            )
        except Exception:
            current_app.logger.exception('Não foi possível preservar a nota pendente no projeto %s', project_id)
            abort(503, description='Não foi possível adicionar a fonte agora. Tente novamente.')
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'ok': True, 'source_id': source_id, 'status': 'error', 'error': str(exc)}), 202
        return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)
    except CaduCreditUnavailable as exc:
        abort(409, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível registrar nota no projeto %s', project_id)
        abort(503, description='Não foi possível adicionar a fonte agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/fontes/arquivos')
@login_required
def upload_project_source(project_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    uploaded = request.files.get('file')
    if uploaded is None:
        abort(400, description='Escolha um arquivo para adicionar.')

    # The React project library uses an explicit triage pass. The original
    # form path remains as a progressive-enhancement fallback for clients that
    # cannot run the library UI.
    if request.accept_mimetypes.best == 'application/json' and request.headers.get('X-Cadu-Triage') == '1':
        source = project_sources.inspect_upload(uploaded, require_text=False)
        source_key = uuid4().hex
        target = project_sources.private_path(
            _workspace_source_root(), client_id, project_id, source['suffix'], source_key,
        )
        target.write_bytes(source['data'])
        storage_path = target.relative_to(Path(_workspace_source_root())).as_posix()
        content_hash = sha256(source['data']).hexdigest()
        connection = None
        try:
            connection = get_db()
            with connection.cursor() as cursor:
                source_id = project_index_service.persist_attachment_source(
                    cursor, project_id=project_id, client_id=client_id,
                    user_id=int(session.get('user_id') or 0), name=source['name'],
                    mime=source['mime'], size=len(source['data']), storage_path=storage_path,
                    extracted_text=source.get('text') or '',
                    classification=source.get('classification'),
                    metadata={'sha256': content_hash, 'processing': source.get('processing'),
                              'can_index': bool(source.get('can_index')), 'triage': True},
                )
            connection.commit()
        except Exception:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
            target.unlink(missing_ok=True)
            current_app.logger.exception('Não foi possível preparar o arquivo para triagem no projeto %s', project_id)
            abort(503, description='Não foi possível preparar o arquivo agora. Tente novamente.')
        classification = source.get('classification') or {}
        return jsonify({
            'ok': True, 'source_id': source_id, 'status': 'awaiting_confirmation',
            'name': source['name'], 'mime': source['mime'], 'size': len(source['data']),
            'processing': source.get('processing') or 'metadata_only',
            'can_index': bool(source.get('can_index')), 'text_preview': (source.get('text') or '')[:1200],
            'classification': classification,
            'confirm_url': url_for('cadu_workspace.confirm_project_source', project_id=project_id, source_id=source_id),
        }), 202

    source = project_sources.validate_upload(uploaded)
    source_key = uuid4().hex
    target = project_sources.private_path(
        _workspace_source_root(), client_id, project_id, source['suffix'], source_key,
    )
    target.write_bytes(source['data'])
    storage_path = target.relative_to(Path(_workspace_source_root())).as_posix()
    try:
        queued = _try_queue_project_source(
            client_id, project_id, source['name'], source['text'], source['mime'],
            len(source['data']), storage_path, 'workspace_upload',
        )
        if queued:
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'ok': True, **queued, 'status': 'queued'}), 202
            return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)
        _persist_project_source(
            client_id, project_id, source['name'], source['text'], source['mime'],
            len(source['data']), storage_path, 'workspace_upload',
        )
    except project_knowledge.KnowledgeIndexError as exc:
        try:
            source_id = _persist_project_source_index_error(
                client_id, project_id, source['name'], source['text'], source['mime'],
                len(source['data']), storage_path, 'workspace_upload', exc,
            )
        except Exception:
            target.unlink(missing_ok=True)
            current_app.logger.exception('Não foi possível preservar o arquivo pendente no projeto %s', project_id)
            abort(503, description='Não foi possível adicionar o arquivo agora. Tente novamente.')
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'ok': True, 'source_id': source_id, 'status': 'error', 'error': str(exc)}), 202
        return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)
    except CaduCreditUnavailable as exc:
        target.unlink(missing_ok=True)
        abort(409, description=str(exc))
    except Exception:
        target.unlink(missing_ok=True)
        current_app.logger.exception('Não foi possível registrar arquivo no projeto %s', project_id)
        abort(503, description='Não foi possível adicionar o arquivo agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/fontes/<int:source_id>/confirmar')
@login_required
def confirm_project_source(project_id, source_id):
    """Apply the user's purpose/category decision after OCR and triage."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    payload = request.get_json(silent=True) or request.form
    purpose = str(payload.get('purpose') or 'project_attachment').strip().lower()
    category = str(payload.get('category') or 'other').strip().lower()
    if purpose not in {'knowledge_source', 'project_attachment'}:
        abort(400, description='Escolha se o arquivo será fonte ou apenas anexo.')
    if category not in {'brief', 'research', 'media_plan', 'report', 'brand_asset', 'reference', 'contract', 'spreadsheet', 'other'}:
        abort(400, description='Categoria de arquivo inválida.')
    source = _project_source(client_id, project_id, source_id)
    if not source:
        abort(404)
    if purpose == 'knowledge_source' and len(str(source.get('extracted_text') or '').strip()) < 20:
        abort(409, description='Este arquivo foi preservado, mas ainda não tem texto suficiente para indexação. Mantenha-o como anexo ou adicione um adapter.')
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_ci_projeto_arquivos
                      SET purpose=%s, category=%s, classification_status='manual',
                          classification_confidence=1, classification_reason=%s,
                          indexing_status=%s, erro_msg=NULL, updated_at=NOW()
                    WHERE id=%s AND projeto_id=%s AND id_cliente=%s""",
                (purpose, category, 'Decisão confirmada pelo usuário.',
                 'queued' if purpose == 'knowledge_source' else 'paused',
                 source_id, project_id, client_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    if purpose == 'project_attachment':
        return jsonify({'ok': True, 'source_id': source_id, 'status': 'attached', 'purpose': purpose, 'category': category})
    job_id = None
    try:
        from .project_index_jobs import enqueue
        job_id = enqueue(client_id, project_id, source_id, int(session.get('user_id') or 0))
    except Exception:
        current_app.logger.warning('Fila de indexação indisponível para a fonte %s; usando modo síncrono', source_id, exc_info=True)
    if job_id:
        return jsonify({'ok': True, 'source_id': source_id, 'job_id': job_id, 'status': 'queued', 'purpose': purpose, 'category': category}), 202
    try:
        result = project_index_service.reindex_source(client_id, project_id, source_id, int(session.get('user_id') or 0))
    except CaduCreditUnavailable as exc:
        abort(409, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível indexar a fonte confirmada %s', source_id)
        abort(503, description='O arquivo foi preservado, mas a indexação precisa ser reprocessada.')
    return jsonify({'ok': True, **result, 'purpose': purpose, 'category': category})


@bp.post('/workspace/app/projetos/<project_id>/fontes/urls')
@login_required
def import_project_url(project_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    from ..training_studio.extract import validate_public_url
    try:
        url = validate_public_url(request.form.get('url'))
    except ValueError as exc:
        abort(400, description=str(exc))
    app = current_app._get_current_object()
    user_id = int(session.get('user_id') or 0)
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    credits = CaduCreditConnector()
    actor = CreditActor.from_values(client_id, user_id)
    try:
        credits.authorize_firecrawl(actor, 'scrape', pages=1)
        source_id = _queue_project_url_source(client_id, project_id, user_id, url)
    except Exception:
        current_app.logger.exception('Não foi possível enfileirar URL no projeto %s', project_id)
        abort(503, description='Não foi possível iniciar a importação agora. Tente novamente.')

    def runner():
        with app.app_context():
            try:
                source = project_sources.extract_public_url(url)
                credits.charge_firecrawl(
                    actor=actor, idempotency_key=f'workspace-project-url:{source_id}:firecrawl-scrape',
                    operation='scrape', pages=1, app='Projeto', stage='fonte_url',
                    metadata={'project_id': str(project_id), 'source_id': source_id, 'url': url},
                )
                _complete_queued_project_url_source(client_id, project_id, user_id, source_id, source)
            except Exception as exc:
                app.logger.exception('Não foi possível importar URL no projeto %s', project_id)
                _mark_project_source_error(client_id, project_id, source_id, exc)

    threading.Thread(target=runner, daemon=True, name=f'workspace-url-{project_id[:12]}').start()
    if request.accept_mimetypes.best == 'application/json':
        return jsonify({'ok': True, 'source_id': source_id, 'status': 'queued',
                        'status_url': url_for('cadu_workspace.project_sources_status', project_id=project_id)}), 202
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.get('/workspace/app/projetos/<project_id>/fontes/<int:source_id>/download')
@login_required
def download_project_source(project_id, source_id):
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_project(client_id, project_id):
        abort(404)
    source = _project_source(client_id, project_id, source_id)
    if not source:
        abort(404)
    storage_path = str(source.get('storage_path') or '')
    if not storage_path.startswith('workspace_project_sources/'):
        abort(404)
    path = project_sources.resolve_private_path(_workspace_source_root(), storage_path)
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype=source.get('mime') or 'application/octet-stream',
                     as_attachment=True, download_name=source.get('nome_arquivo') or path.name)


@bp.get('/workspace/api/projetos/<project_id>/fontes')
@login_required
def project_sources_status(project_id):
    client_id = int(session.get('cliente_id') or 0)
    project = _workspace_project(client_id, project_id)
    if not project:
        abort(404)
    files = []
    for item in project.get('files', []):
        record = {'id': item.get('id'), 'name': item.get('nome_arquivo'),
                  'status': item.get('indexing_status'), 'words': item.get('word_count') or 0,
                  'error': item.get('erro_msg') or ''}
        if 'purpose' in item:
            record.update({'purpose': item.get('purpose') or 'project_attachment',
                           'category': item.get('category') or 'other',
                           'classification_status': item.get('classification_status') or 'pending',
                           'classification_confidence': float(item.get('classification_confidence') or 0),
                           'classification_reason': item.get('classification_reason') or ''})
        files.append(record)
    return jsonify({'sources': files})


@bp.post('/workspace/app/projetos/<project_id>/fontes/<int:source_id>/reprocessar')
@login_required
def reprocess_project_source(project_id, source_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    source = _project_source(client_id, project_id, source_id)
    if not source:
        abort(404)
    storage_path = str(source.get('storage_path') or '')
    if storage_path.startswith(('workspace://project-notes/', 'workspace_project_sources/')):
        job_id = None
        try:
            from .project_index_jobs import enqueue
            job_id = enqueue(client_id, project_id, source_id, int(session.get('user_id') or 0))
        except Exception:
            current_app.logger.warning(
                'Não foi possível enfileirar a reindexação da fonte %s; tentando modo síncrono',
                source_id, exc_info=True,
            )
        if not job_id:
            # The queue migration is additive. Older deployments keep the
            # existing synchronous reprocessing path until it is applied.
            pass
        elif request.accept_mimetypes.best == 'application/json':
            return jsonify({'ok': True, 'source_id': source_id, 'job_id': job_id, 'status': 'queued'}), 202
        else:
            return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)
    reprocess_id = uuid4().hex
    user_id = int(session.get('user_id') or 0)
    try:
        if storage_path.startswith('workspace://project-notes/'):
            extracted = {'text': str(source.get('extracted_text') or '')}
            if not extracted['text']:
                abort(409, description='Esta nota é anterior à nova base e não tem conteúdo preservado para reprocessar.')
        elif storage_path.startswith('workspace-url:'):
            from ..cadu_credit_connector import CaduCreditConnector, CreditActor
            credits = CaduCreditConnector()
            actor = CreditActor.from_values(client_id, user_id)
            credits.authorize_firecrawl(actor, 'scrape', pages=1)
            extracted = project_sources.extract_public_url(storage_path.removeprefix('workspace-url:'))
            credits.charge_firecrawl(
                actor=actor, idempotency_key=f'workspace-project-url:{source_id}:reprocess:{reprocess_id}',
                operation='scrape', pages=1, app='Projeto', stage='reprocessar_url',
                metadata={'project_id': str(project_id), 'source_id': source_id},
            )
        elif storage_path.startswith('workspace_project_sources/'):
            path = project_sources.resolve_private_path(_workspace_source_root(), storage_path)
            if not path.is_file():
                abort(404)
            extracted = project_sources.reextract(
                source.get('nome_arquivo') or path.name, path.read_bytes(), source.get('mime') or '',
            )
        else:
            abort(409, description='Esta fonte continua sob gestão do sistema anterior.')
        content = extracted['text']
        source_chunks, embedding_tokens, embedding_model = project_knowledge.index(content)
        connection = get_db()
        with connection.cursor() as cursor:
            charged_tokens = charge_project_rag(
                cursor, client_id=client_id, user_id=user_id, project_id=project_id,
                tokens=embedding_tokens, stage='reindexacao',
                idempotency_key='workspace-rag-reindex:' + reprocess_id,
            )
            cursor.execute(
                'DELETE FROM cadu_ci_chunks WHERE arquivo_id = %s AND projeto_id = %s AND id_cliente = %s',
                (source_id, project_id, client_id),
            )
            for chunk in source_chunks:
                cursor.execute(
                    """INSERT INTO cadu_ci_chunks
                           (projeto_id, id_cliente, arquivo_id, ordem, titulo, conteudo,
                            search_vector, metadata, embedding, embedding_model, content_hash, tokens, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('portuguese', %s), %s::jsonb, %s::vector,
                                %s, %s, %s, NOW())""",
                    (project_id, client_id, source_id, chunk.order, source.get('nome_arquivo'), chunk.content,
                     chunk.content, json.dumps({'source': 'workspace_reprocessed', 'arquivo_id': source_id, 'section': chunk.section}),
                     project_knowledge.vector_literal(chunk.embedding), embedding_model,
                     chunk.content_hash, chunk.tokens),
                )
            cursor.execute(
                """UPDATE cadu_ci_projeto_arquivos
                      SET extracted_text = %s, indexing_status = 'completed', erro_msg = NULL, word_count = %s,
                          tokens = %s, updated_at = NOW()
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s""",
                (content, len(re.findall(r'\b\w+\b', content, flags=re.UNICODE)),
                 charged_tokens, source_id, project_id, client_id),
            )
        connection.commit()
    except HTTPException:
        raise
    except CaduCreditUnavailable as exc:
        abort(409, description=str(exc))
    except Exception as exc:
        current_app.logger.exception('Não foi possível reprocessar a fonte %s', source_id)
        try:
            connection = get_db()
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE cadu_ci_projeto_arquivos SET indexing_status = 'error', erro_msg = %s,
                              updated_at = NOW() WHERE id = %s AND projeto_id = %s AND id_cliente = %s""",
                    (str(exc)[:500], source_id, project_id, client_id),
                )
            connection.commit()
        except Exception:
            current_app.logger.exception('Não foi possível registrar erro da fonte %s', source_id)
        abort(503, description='Não foi possível reprocessar essa fonte agora.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/fontes/<int:source_id>/remover')
@login_required
def remove_project_source(project_id, source_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    source = _project_source(client_id, project_id, source_id)
    if not source:
        abort(404)
    storage_path = str(source.get('storage_path') or '')
    if not storage_path.startswith(('workspace://project-notes/', 'workspace-url:', 'workspace_project_sources/')):
        abort(409, description='Esta fonte continua sob gestão do sistema anterior.')
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'DELETE FROM cadu_ci_chunks WHERE arquivo_id = %s AND projeto_id = %s AND id_cliente = %s',
                (source_id, project_id, client_id),
            )
            cursor.execute(
                'DELETE FROM cadu_ci_projeto_arquivos WHERE id = %s AND projeto_id = %s AND id_cliente = %s',
                (source_id, project_id, client_id),
            )
            cursor.execute(
                """UPDATE cadu_ci_projetos SET total_arquivos = GREATEST(COALESCE(total_arquivos, 0) - 1, 0),
                          updated_at = NOW() WHERE id = %s AND id_cliente = %s""",
                (project_id, client_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível remover a fonte %s', source_id)
        abort(503, description='Não foi possível remover essa fonte agora.')
    if storage_path.startswith('workspace_project_sources/'):
        try:
            path = project_sources.resolve_private_path(_workspace_source_root(), storage_path)
            if path.is_file():
                trash = Path(_workspace_source_root()) / 'workspace_project_sources_trash' / str(client_id)
                trash.mkdir(parents=True, exist_ok=True)
                path.replace(trash / f'{uuid4().hex}-{path.name}')
        except Exception:
            current_app.logger.warning('Fonte %s removida do banco, mas o arquivo não foi movido para a lixeira', source_id)
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/status')
@login_required
def update_project_status(project_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    project = _workspace_project(client_id, project_id)
    if not project:
        abort(404)
    status = 'ativo' if project.get('status') == 'arquivado' else 'arquivado'
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute('UPDATE cadu_ci_projetos SET status = %s, updated_at = NOW() WHERE id = %s AND id_cliente = %s',
                           (status, project_id, client_id))
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        abort(503, description='Não foi possível alterar o estado do projeto agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/api/projetos/<project_id>/consultar')
@login_required
def query_project_knowledge(project_id):
    """Search the existing indexed project chunks without leaving Workspace."""
    if not _workspace_api_csrf():
        return jsonify({'error': 'Atualize a página e tente novamente.'}), 403
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_project(client_id, project_id):
        abort(404)
    payload = request.get_json(silent=True) or {}
    query = ' '.join(str(payload.get('query') or '').split())[:400]
    if len(query) < 3:
        return jsonify({'error': 'Escreva ao menos três caracteres para consultar a base.'}), 400
    try:
        with get_db().cursor() as cursor:
            try:
                vector = project_knowledge.vector_literal(project_knowledge.query_embedding(query))
                cursor.execute(
                """WITH lexical AS (
                        SELECT id, ts_rank_cd(search_vector, plainto_tsquery('portuguese', %s)) AS score
                          FROM cadu_ci_chunks WHERE projeto_id=%s AND id_cliente=%s
                            AND search_vector @@ plainto_tsquery('portuguese', %s) ORDER BY score DESC LIMIT 18
                    ), semantic AS (
                        SELECT id, 1 - (embedding <=> %s::vector) AS score
                          FROM cadu_ci_chunks WHERE projeto_id=%s AND id_cliente=%s
                        ORDER BY embedding <=> %s::vector LIMIT 18
                    ), ranked AS (
                        SELECT id, SUM(1.0 / (60 + rank)) AS score FROM (
                            SELECT id, row_number() OVER (ORDER BY score DESC) AS rank FROM lexical
                            UNION ALL SELECT id, row_number() OVER (ORDER BY score DESC) AS rank FROM semantic
                        ) candidates GROUP BY id
                    ) SELECT c.titulo, LEFT(c.conteudo, 900) AS conteudo, r.score
                          FROM ranked r JOIN cadu_ci_chunks c ON c.id=r.id
                         ORDER BY r.score DESC, c.ordem ASC LIMIT 6""",
                    (query, project_id, client_id, query, vector, project_id, client_id, vector),
                )
            except project_knowledge.KnowledgeIndexError:
                cursor.execute(
                    """SELECT titulo, LEFT(conteudo, 900) AS conteudo,
                              ts_rank_cd(search_vector, plainto_tsquery('portuguese', %s)) AS score
                         FROM cadu_ci_chunks
                        WHERE projeto_id = %s AND id_cliente = %s
                          AND search_vector @@ plainto_tsquery('portuguese', %s)
                     ORDER BY score DESC, ordem ASC LIMIT 6""",
                    (query, project_id, client_id, query),
                )
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                results.append({
                    'source': item.get('titulo') or 'Fonte sem título',
                    'excerpt': item.get('conteudo') or '',
                })
            return jsonify({'query': query, 'result_count': len(results), 'results': results})
    except Exception:
        return jsonify({'error': 'Não foi possível consultar a base agora. Tente novamente.'}), 503


def _workspace_document_urls(document):
    """Return only Workspace-owned navigation and a share URL when enabled."""
    document_id = str(document.get('id') or '')
    payload = {
        'id': document_id,
        'title': document.get('title'),
        'type': document.get('type'),
        'status': document.get('status'),
        'editor_url': url_for('cadu_workspace.document_editor', document_id=document_id),
    }
    if document.get('share_enabled') and document.get('share_token'):
        payload['share_url'] = product_url('planner', '/docs/public/' + str(document['share_token']))
    return payload


@bp.post('/workspace/api/documentos')
@login_required
def create_workspace_document():
    """Save an explicit conversation artifact as an editable Smart Doc.

    This endpoint intentionally accepts optional project context: personal
    conversations remain useful, while a selected project makes its private
    files available to the document editor for later review.
    """
    if not _workspace_api_csrf():
        return jsonify({'error': 'Atualize a página e tente novamente.'}), 403
    client_id = int(session.get('cliente_id') or 0)
    payload = request.get_json(silent=True) or {}
    title = ' '.join(str(payload.get('title') or 'Texto do Cadu').split())[:255]
    content = str(payload.get('content') or '').strip()
    if len(content) < 20:
        return jsonify({'error': 'O texto precisa ter ao menos 20 caracteres.'}), 400
    if len(content) > 500000:
        return jsonify({'error': 'O texto excede o limite de 500.000 caracteres.'}), 400
    source_notes = []
    for source in (payload.get('sources') or [])[:8]:
        if not isinstance(source, dict):
            continue
        source_title = ' '.join(str(source.get('title') or '').split())[:180]
        source_url = str(source.get('url') or '').strip()
        if source_url:
            parsed = urlparse(source_url)
            source_url = source_url if parsed.scheme in {'http', 'https'} and parsed.netloc else ''
        if source_title or source_url:
            source_notes.append((source_title or 'Fonte do projeto', source_url))
    if source_notes:
        content += '\n\n## Fontes consultadas\n' + '\n'.join(
            '- %s%s' % (title, (' — ' + source_url) if source_url else '')
            for title, source_url in source_notes
        )
    project_id = str(payload.get('project_id') or '').strip() or None
    if project_id:
        _editable_workspace_project(client_id, project_id)
    try:
        from ..cadu_planner import docs
        document = docs.create_document(client_id, int(session['user_id']), {
            'title': title,
            'type': 'conversa',
            'html': docs.markdown_to_safe_html(content),
            'project_id': project_id,
        })
        return jsonify({'success': True, 'document': _workspace_document_urls(document)}), 201
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível salvar artefato de conversa')
        return jsonify({'error': 'Não foi possível salvar o texto agora.'}), 503


@bp.put('/workspace/api/documentos/<document_id>/publicar')
@login_required
def publish_workspace_document(document_id):
    """Publish only after the owner explicitly requests a public link."""
    if not _workspace_api_csrf():
        return jsonify({'error': 'Atualize a página e tente novamente.'}), 403
    try:
        from ..cadu_planner import docs
        client_id, actor_id = int(session.get('cliente_id') or 0), int(session['user_id'])
        document = docs.save_document(client_id, actor_id, document_id, {'status': 'published'})
        document = docs.share_document(client_id, actor_id, document_id, True)
        return jsonify({'success': True, 'document': _workspace_document_urls(document)})
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível publicar documento de conversa %s', document_id)
        return jsonify({'error': 'Não foi possível criar o link público agora.'}), 503


@bp.post('/workspace/api/artefatos/galeria')
@login_required
def publish_workspace_gallery():
    """Publish a user-selected conversation image set as a Smart Doc gallery.

    URLs are never fetched by this endpoint; they are only rendered in the
    sandboxed public document. This avoids server-side requests to user or
    provider controlled hosts while keeping the selected set shareable.
    """
    if not _workspace_api_csrf():
        return jsonify({'error': 'Atualize a página e tente novamente.'}), 403
    payload = request.get_json(silent=True) or {}
    images = []
    for value in (payload.get('images') or [])[:8]:
        source = str(value or '').strip()
        parsed = urlparse(source)
        if parsed.scheme == 'https' and parsed.netloc and source not in images:
            images.append(source)
    if not images:
        return jsonify({'error': 'Selecione ao menos uma imagem válida.'}), 400
    client_id, actor_id = int(session.get('cliente_id') or 0), int(session['user_id'])
    project_id = str(payload.get('project_id') or '').strip() or None
    if project_id:
        _editable_workspace_project(client_id, project_id)
    title = ' '.join(str(payload.get('title') or 'Seleção visual Cadu').split())[:255]
    figures = ''.join(
        '<figure><img src="%s" alt="Imagem %d da seleção"><figcaption>Imagem %d</figcaption></figure>'
        % (escape(source, quote=True), index + 1, index + 1)
        for index, source in enumerate(images)
    )
    html = '<section><p>Seleção visual criada no Cadu.</p><div class="cadu-public-gallery">%s</div></section>' % figures
    try:
        from ..cadu_planner import docs
        document = docs.create_document(client_id, actor_id, {
            'title': title, 'type': 'galeria', 'html': html, 'project_id': project_id,
        })
        document_id = document['id']
        document = docs.save_document(client_id, actor_id, document_id, {'status': 'published'})
        document = docs.share_document(client_id, actor_id, document_id, True)
        return jsonify({'success': True, 'document': _workspace_document_urls(document)})
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível publicar galeria de conversa')
        return jsonify({'error': 'Não foi possível criar o link da seleção agora.'}), 503


@bp.get('/workspace/app/marcas/<int:brand_id>')
@login_required
def brand_detail(brand_id):
    if request.path.startswith('/workspace/app/'):
        return redirect(url_for('cadu_workspace.clean_brand_detail', brand_id=brand_id), code=308)
    client_id = int(session.get('cliente_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    # Keep the view resilient while a legacy brand is still being enriched.
    # The normal repository path already supplies these fields; defaults avoid
    # a partially migrated record turning the entire detail page into a 500.
    brand.setdefault('assets', [])
    brand.setdefault('brand_profile', {})
    brand.setdefault('analysis_metadata', {})
    brand.setdefault('activity', [])
    brand.setdefault('readiness', {'score': 0, 'missing': ['diretrizes de identidade']})
    brand['review_pack'] = _brand_review_pack(brand)
    brand['visualVariant'] = _dock_visual_variant('brand', brand_id)
    can_manage_brand = session.get('user_type') in {'admin', 'superadmin'}
    studio_base = product_url('studio', '/studio/modelagem-criativos')
    if request.args.get('legacy') != '1':
        projects = _workspace_projects(client_id, status='todos')
        brands = _workspace_brands(client_id)
        linked_projects = _brand_linked_projects(client_id, brand_id)
        active_linked_project = linked_projects[0] if linked_projects else None
        profile = brand.get('brand_profile') or {}
        review_pack = brand.get('review_pack') or {}
        project_items = [{
            'id': f"ci:{item.get('id')}", 'kind': 'project', 'title': str(item.get('nome') or 'Projeto'),
            'name': str(item.get('nome') or 'Projeto'), 'projectRef': f"ci:{item.get('id')}",
            'previewUrl': str(item.get('brand_logo_url') or ''), 'visualInitials': str(item.get('thumbnail_initials') or 'P'),
            'visualColor': str(item.get('thumbnail_color') or item.get('cor') or '#176b5e'),
            'visualVariant': _dock_visual_variant('project', item.get('id')),
            'href': url_for('cadu_workspace.clean_project_detail', project_id=str(item.get('id'))),
        } for item in projects]
        brand_items = [{
            'id': str(item.get('id')), 'kind': 'brand', 'name': str(item.get('name') or 'Marca'),
            'title': str(item.get('name') or 'Marca'), 'logoUrl': str(item.get('display_logo') or ''),
            'visualInitials': str(item.get('display_initials') or 'M'),
            'visualColor': str(item.get('display_color') or item.get('primary_color') or '#176b5e'),
            'visualVariant': _dock_visual_variant('brand', item.get('id')),
            'href': url_for('cadu_workspace.clean_brand_detail', brand_id=int(item.get('id'))),
        } for item in brands]
        available_project_items = [{
            'id': str(item.get('id')), 'name': str(item.get('nome') or 'Projeto'),
            'description': str(item.get('descricao') or ''),
            'linkUrl': url_for('cadu_workspace.update_project_brands', project_id=str(item.get('id'))),
        } for item in projects if str(item.get('status') or 'ativo') != 'arquivado']
        brand_base = url_for('cadu_workspace.brand_detail', brand_id=brand_id).rstrip('/')
        conversation_args = {'prompt': f"Quero trabalhar a marca {brand.get('name') or 'marca'} em um projeto."}
        if active_linked_project:
            conversation_args['project'] = f"ci:{active_linked_project.get('id')}"
        brand_links = {
            'conversation': url_for('cadu_workspace.conversations', **conversation_args),
            'createImage': product_url('studio', f"/studio/modelagem-criativos/criar?creative_client_id={brand_id}" + (f"&project_id={active_linked_project.get('id')}" if active_linked_project else '')),
            'createVideo': product_url('studio', f"/studio/modelagem-criativos/video?creative_client_id={brand_id}" + (f"&project_id={active_linked_project.get('id')}" if active_linked_project else '')),
            'createPlan': product_url('planner', f"/novo?cliente_id={brand.get('crm_client_id') or ''}&cliente_name={quote(str(brand.get('name') or 'Marca'))}&brand_id={brand_id}&brand_name={quote(str(brand.get('name') or 'Marca'))}" + (f"&project_id={active_linked_project.get('id')}" if active_linked_project else '')),
            'system': url_for('cadu_workspace.brand_system', brand_id=brand_id),
            'generateHero': url_for('cadu_workspace.generate_brand_hero', brand_id=brand_id),
            'updateIdentity': url_for('cadu_workspace.update_brand_identity', brand_id=brand_id),
            'uploadAssets': url_for('cadu_workspace.upload_brand_assets', brand_id=brand_id),
            'audit': url_for('cadu_workspace.audit_brand', brand_id=brand_id),
            'auditStatus': url_for('cadu_workspace.brand_audit_status', brand_id=brand_id),
            'approve': url_for('cadu_workspace.approve_brand_reviews', brand_id=brand_id),
            'retry': url_for('cadu_workspace.retry_brand_audit', brand_id=brand_id),
            'setPrimaryBase': f'{brand_base}/ativos/__ASSET_ID__/principal',
            'promoteLogoBase': f'{brand_base}/ativos/__ASSET_ID__/logo',
            'deleteAssetBase': f'{brand_base}/ativos/__ASSET_ID__/apagar',
        }
        brand_data = {
            'id': str(brand.get('id')), 'name': str(brand.get('name') or 'Marca'), 'sector': str(brand.get('sector') or ''),
            'websiteUrl': str(brand.get('website_url') or ''), 'crmClientId': str(brand.get('crm_client_id') or ''),
            'logoUrl': str(brand.get('display_logo') or ''), 'initials': str(brand.get('display_initials') or 'M'),
            'primaryColor': str(brand.get('primary_color') or '#176b5e'), 'secondaryColor': str(brand.get('secondary_color') or '#dcece6'),
            'profile': {
                'brandSummary': str(profile.get('brand_summary') or profile.get('positioning') or ''),
                'toneOfVoice': str(profile.get('tone_of_voice') or brand.get('tone_of_voice') or ''),
                'targetAudience': str(profile.get('target_audience') or ''), 'positioning': str(profile.get('positioning') or ''),
                'brandValues': profile.get('brand_values') if isinstance(profile.get('brand_values'), list) else [],
                'colorPalette': profile.get('color_palette') if isinstance(profile.get('color_palette'), list) else [],
                'fonts': profile.get('fonts') if isinstance(profile.get('fonts'), list) else [],
            },
            'readiness': brand.get('readiness') or {'score': 0, 'missing': []}, 'reviewPack': review_pack,
            'analysisMetadata': {
                'pagesAnalyzed': int((brand.get('analysis_metadata') or {}).get('pages_analyzed') or 0),
                'assetsFound': int((brand.get('analysis_metadata') or {}).get('assets_found') or 0),
                'visualEvidenceCount': int((brand.get('analysis_metadata') or {}).get('visual_evidence_count') or 0),
                'sources': [str(item) for item in ((brand.get('analysis_metadata') or {}).get('sources') or []) if item],
            },
            'assets': [{
                'id': str(item.get('id')), 'role': str(item.get('role') or 'reference'), 'status': str(item.get('status') or 'registered'),
                'isPrimary': bool(item.get('is_primary')), 'displayUrl': str(item.get('display_url') or ''),
                'mimeType': str(item.get('mime_type') or ''), 'sourceKind': str(item.get('source_kind') or ''),
                'metadata': item.get('metadata') if isinstance(item.get('metadata'), dict) else {},
            } for item in brand.get('assets') or []],
            'linkedProjects': [{
                'id': str(item.get('id')), 'name': str(item.get('nome') or 'Projeto'), 'description': str(item.get('descricao') or ''),
                'sources': int(item.get('fontes_prontas') or 0), 'href': url_for('cadu_workspace.clean_project_detail', project_id=str(item.get('id'))),
                'logoUrl': str(item.get('brand_logo_url') or ''), 'initials': str(item.get('thumbnail_initials') or 'P'),
                'color': str(item.get('thumbnail_color') or item.get('cor') or '#176b5e'),
            } for item in linked_projects],
        }
        dock_items = _workspace_common_dock_items(client_id, int(session.get('user_id') or 0))
        return render_template(
            'cadu_workspace/brand_detail_react.html', brand_data=brand_data, brand_links=brand_links,
            brand_items=brand_items, project_items=project_items, available_project_items=available_project_items,
            dock_items=dock_items, can_manage_brand=can_manage_brand,
            usage_percent=round(float(credit_position(client_id).get('monthly_usage_percentage') or 0), 1),
        )
    return render_template(
        'cadu_workspace/brand_detail.html', brand=brand,
        can_manage_brand=can_manage_brand,
        linked_projects=_brand_linked_projects(client_id, brand_id),
        available_projects=_workspace_projects(client_id, status='ativos'),
        legacy_creatives_url=f'{studio_base}/trocar?client_id={brand_id}',
        legacy_uploads_url=f'{studio_base}/trocar?client_id={brand_id}&panel=uploads',
    )


@bp.get('/marcas/<int:brand_id>')
@login_required
def clean_brand_detail(brand_id):
    return brand_detail(brand_id)


@bp.post('/workspace/app/marcas/<int:brand_id>/identidade')
@login_required
def update_brand_identity(brand_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    existing_brand = _workspace_brand(client_id, brand_id)
    if not existing_brand:
        abort(404)
    data = _workspace_brand_form()
    # Autosave posts every field. Preserve the import marker until someone
    # actually changes the generated name, otherwise a tone/sector edit would
    # prevent the approved proposal from replacing the provisional name.
    if (existing_brand.get('brand_profile') or {}).get('name_autogenerated'):
        data['profile']['name_autogenerated'] = data['name'] == existing_brand.get('name')
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cx_clients
                      SET name = %s, sector = %s, website_url = %s,
                          primary_color = %s, secondary_color = %s,
                          tone_of_voice = %s,
                          brand_profile = COALESCE(brand_profile, '{}'::jsonb) || %s::jsonb,
                          updated_at = NOW()
                    WHERE id = %s AND crm_client_id = %s
                RETURNING id""",
                (data['name'], data['sector'], data['website_url'], data['primary_color'],
                 data['secondary_color'], data['profile']['tone_of_voice'],
                 json.dumps(data['profile']), brand_id, client_id),
            )
            if not cursor.fetchone():
                abort(404)
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível atualizar a marca %s', brand_id)
        abort(503, description='Não foi possível salvar a identidade agora. Tente novamente.')
    if request.accept_mimetypes.best == 'application/json':
        return jsonify({'ok': True, 'brand_id': brand_id, 'saved_at': _utc_timestamp()})
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/ativos')
@login_required
def upload_brand_assets(brand_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_brand(client_id, brand_id):
        abort(404)
    files = request.files.getlist('images')
    if not any(item and item.filename for item in files):
        abort(400, description='Escolha ao menos uma imagem de marca.')
    role = request.form.get('role') or 'reference'
    if role == 'logo' and len([item for item in files if item and item.filename]) != 1:
        abort(400, description='Envie somente um arquivo para o logo principal.')
    try:
        from ..creative_modeling_service import CreativeModelingService
        CreativeModelingService().upload_client_brand_assets(
            brand_id, files, role == 'logo', role,
        )
    except ValueError as exc:
        abort(400, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível enviar ativos para a marca %s', brand_id)
        abort(503, description='Não foi possível enviar os ativos agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/ativos/<int:asset_id>/principal')
@login_required
def set_primary_brand_asset(brand_id, asset_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_brand(client_id, brand_id):
        abort(404)
    try:
        from ..creative_modeling_service import CreativeModelingService
        CreativeModelingService().set_primary_brand_asset(brand_id, asset_id)
    except ValueError as exc:
        abort(400, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível definir o logo principal da marca %s', brand_id)
        abort(503, description='Não foi possível alterar o logo principal agora.')
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/ativos/<int:asset_id>/logo')
@login_required
def promote_brand_asset_to_logo(brand_id, asset_id):
    """Let the team choose any imported website visual as the official logo."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_brand(client_id, brand_id):
        abort(404)
    try:
        from ..creative_modeling_service import CreativeModelingService
        CreativeModelingService().promote_client_brand_asset_to_logo(brand_id, asset_id)
    except ValueError as exc:
        abort(400, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível definir o ativo %s como logo da marca %s', asset_id, brand_id)
        abort(503, description='Não foi possível definir este ativo como logo agora.')
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/ativos/<int:asset_id>/apagar')
@login_required
def delete_brand_asset(brand_id, asset_id):
    """Remove an asset while preserving the active Workspace tenant boundary."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_brand(client_id, brand_id):
        abort(404)
    try:
        from ..creative_modeling_service import CreativeModelingService
        CreativeModelingService().delete_brand_asset(brand_id, asset_id)
    except ValueError as exc:
        abort(400, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível apagar o ativo %s da marca %s', asset_id, brand_id)
        abort(503, description='Não foi possível apagar este ativo agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/ativos/referencias-recentes')
@login_required
def find_recent_brand_creatives(brand_id):
    """Import public campaign references into the current brand session."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    from ..creative_brand_analysis import search_recent_brand_creatives
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    from ..cadu_tool_billing import InsufficientToolCredits
    from ..creative_modeling_service import CreativeModelingService
    from ..services.integration_credentials import resolve_firecrawl_api_key
    user_id = int(session.get('user_id') or 0)
    credits = CaduCreditConnector()
    actor = CreditActor.from_values(client_id, user_id)
    run_id = uuid4().hex
    # Without a Firecrawl credential the lookup returns no web results and no
    # customer credit is reserved or charged.
    try:
        firecrawl_enabled = bool(resolve_firecrawl_api_key())
        if firecrawl_enabled:
            credits.authorize_firecrawl(actor, 'search', results=8)

        def charge_search(result_count):
            credits.charge_firecrawl(
                actor=actor, idempotency_key=f'workspace-brand:{brand_id}:recent-search:{run_id}',
                operation='search', results=result_count, app='Marca', stage='referencias_recentes',
                metadata={'brand_id': brand_id, 'run_id': run_id, 'query_brand': brand.get('name')},
            )

        candidates = search_recent_brand_creatives(
            brand.get('name'), limit=8, billing_callback=charge_search if firecrawl_enabled else None,
        )
    except HTTPException:
        raise
    except (CaduCreditUnavailable, InsufficientToolCredits) as exc:
        abort(409, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível buscar referências recentes da marca %s', brand_id)
        abort(503, description='Não foi possível buscar referências recentes agora. Tente novamente mais tarde.')
    if not candidates:
        abort(503, description='Não encontramos referências recentes utilizáveis agora. Tente novamente mais tarde.')
    try:
        imported = CreativeModelingService().import_website_brand_assets(brand_id, candidates)
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível importar referências recentes da marca %s', brand_id)
        abort(503, description='As referências foram encontradas, mas não puderam ser salvas agora. Tente novamente.')
    if request.accept_mimetypes.best == 'application/json':
        return jsonify(ok=True, imported=len(imported)), 201
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id, assets='recent'), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/hero/gerar')
@login_required
def generate_brand_hero(brand_id):
    """Create one low-resolution hero; insufficient credit deliberately stays quiet."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    user_id = int(session.get('user_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    if _brand_review_pack(brand).get('status') != 'approved':
        abort(409, description='Aprove a identidade da marca antes de criar o hero.')
    from ..cadu_credit_connector import CreditActor
    from ..creative_modeling_service import CreativeModelingService
    credits = CaduCreditConnector()
    # The action is intentionally silent when there is no usable balance.
    if credits.balance(client_id) <= 0:
        return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)
    actor = CreditActor.from_values(client_id, user_id)
    service = CreativeModelingService()
    result = None
    try:
        result = service.generate_client_brand_low_res_hero(brand_id, brand)
        credits.charge_provider(
            actor=actor, idempotency_key=f'workspace-brand:{brand_id}:hero:{uuid4().hex}',
            app='Hero da marca', stage='imagem_baixa_resolucao', provider_result=result,
            model=str(result.get('model') or ''),
            metadata={'brand_id': brand_id, 'resolution': '1K', 'quality': 'low'},
        )
    except Exception as exc:
        # Never leave a usable generated image behind when the matching debit
        # was rejected. A zero/insufficient balance remains deliberately quiet.
        if result:
            try:
                service.discard_client_brand_generated_hero(brand_id, result)
            except Exception:
                current_app.logger.exception('Não foi possível compensar o hero sem cobrança da marca %s', brand_id)
        from ..cadu_tool_billing import InsufficientToolCredits
        if isinstance(exc, InsufficientToolCredits):
            return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)
        current_app.logger.exception('Não foi possível gerar o hero da marca %s', brand_id)
        abort(503, description='Não foi possível gerar o hero agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id, hero='generated'), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/auditoria')
@login_required
def audit_brand(brand_id):
    """Queue a slow, reviewable brand audit without holding the browser open."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    credit_response = _brand_audit_credit_gate(client_id)
    if credit_response is not None:
        return credit_response
    website_url = _normalized_website_url(
        request.form.get('website_url') or brand.get('website_url') or '',
    )
    images = [item for item in request.files.getlist('images') if item and item.filename][:4]
    if not website_url and not images:
        abort(400, description='Informe o site ou envie uma imagem de referência.')
    image_payload = []
    connection = None
    try:
        for item in images:
            image_payload.append({
                'filename': item.filename,
                'content_type': item.mimetype,
                'content': item.read(),
            })
        job_id = uuid4().hex
        metadata = dict(brand.get('analysis_metadata') or {})
        metadata['review_pack'] = {
            'job_id': job_id,
            'status': 'queued',
            'stage': 'queued',
            'index': 0,
            'total': 4,
            'message': 'A auditoria entrou na fila.',
            'error': '',
            'created_at': _utc_timestamp(),
            'input': {'website_url': website_url, 'has_images': bool(image_payload),
                      'include_project_sources': request.form.get('include_project_sources') == 'true'},
            'analysis': {},
            'reviews': [],
        }
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cx_clients
                      SET analysis_metadata = %s::jsonb
                    WHERE id = %s AND crm_client_id = %s
                RETURNING id""",
                (json.dumps(metadata), brand_id, client_id),
            )
            if not cursor.fetchone():
                abort(404)
        connection.commit()
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        current_app.logger.exception('Não foi possível auditar a marca %s', brand_id)
        abort(503, description='Não foi possível iniciar a auditoria agora. Tente novamente.')
    _start_brand_review_job(client_id, int(session.get('user_id') or 0), brand_id, job_id, website_url, image_payload)
    if request.accept_mimetypes.best == 'application/json':
        return jsonify({
            'ok': True, 'job_id': job_id, 'status': 'queued',
            'status_url': url_for('cadu_workspace.brand_audit_status', brand_id=brand_id),
        }), 202
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id, audit='queued'), code=303)


@bp.get('/workspace/app/marcas/<int:brand_id>/auditoria/status')
@login_required
def brand_audit_status(brand_id):
    client_id = int(session.get('cliente_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    pack = _brand_review_pack(brand)
    if pack.get('job_id') and _brand_review_is_stale(pack):
        try:
            _save_brand_review_job(
                client_id, brand_id, pack['job_id'], status='failed', stage='failed',
                message='A auditoria foi interrompida antes de terminar.',
                error='A sessão de processamento expirou. Tente novamente para reiniciar a análise.',
            )
            pack.update({
                'status': 'failed', 'stage': 'failed',
                'message': 'A auditoria foi interrompida antes de terminar.',
                'error': 'A sessão de processamento expirou. Tente novamente para reiniciar a análise.',
            })
        except Exception:
            current_app.logger.exception('Não foi possível encerrar auditoria de marca expirada')
    return jsonify({
        'status': pack.get('status') or 'not_started', 'stage': pack.get('stage'),
        'index': pack.get('index', 0), 'total': pack.get('total', 4),
        'message': pack.get('message'), 'error': pack.get('error'),
        'review_count': len(pack.get('reviews') or []), 'created_at': pack.get('created_at'),
        'updated_at': pack.get('updated_at'),
    })


@bp.post('/workspace/app/marcas/<int:brand_id>/auditoria/repetir')
@login_required
def retry_brand_audit(brand_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    credit_response = _brand_audit_credit_gate(client_id)
    if credit_response is not None:
        return credit_response
    pack = _brand_review_pack(brand)
    website_url = str((brand.get('analysis_metadata') or {}).get('review_pack', {}).get('input', {}).get('website_url') or '').strip()
    if pack.get('status') != 'failed' or not website_url:
        abort(409, description='Para repetir uma auditoria com imagens, reenvie as referências no formulário.')
    job_id = uuid4().hex
    metadata = dict(brand.get('analysis_metadata') or {})
    checkpoint = pack.get('analysis') if isinstance(pack.get('analysis'), dict) else {}
    metadata['review_pack'] = {
        'job_id': job_id, 'status': 'queued', 'stage': 'queued', 'index': 0, 'total': 4,
        'message': 'Retomando a proposta salva.' if checkpoint else 'A auditoria entrou novamente na fila.', 'error': '',
        'created_at': _utc_timestamp(),
        'input': {'website_url': website_url, 'has_images': False}, 'analysis': checkpoint, 'reviews': [],
    }
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cx_clients SET analysis_metadata = %s::jsonb
                     WHERE id = %s AND crm_client_id = %s RETURNING id""",
                (json.dumps(metadata), brand_id, client_id),
            )
            if not cursor.fetchone():
                abort(404)
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível repetir a auditoria da marca %s', brand_id)
        abort(503, description='Não foi possível repetir a auditoria agora.')
    _start_brand_review_job(client_id, int(session.get('user_id') or 0), brand_id, job_id, website_url, [], proposal=checkpoint)
    if request.accept_mimetypes.best == 'application/json':
        return jsonify({'ok': True, 'job_id': job_id, 'status': 'queued',
                        'status_url': url_for('cadu_workspace.brand_audit_status', brand_id=brand_id)}), 202
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id, audit='queued'), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/auditoria/modulos/<module_id>/revisar')
@login_required
def refresh_brand_audit_module(brand_id, module_id):
    """Refresh one opinion from saved evidence; it never re-collects or applies identity."""
    if module_id not in {'evidencias', 'estrategia', 'direcao_criativa'}:
        abort(404)
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    user_id = int(session.get('user_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    pack = _brand_review_pack(brand)
    analysis = pack.get('analysis')
    if pack.get('status') != 'pending_approval' or not isinstance(analysis, dict):
        abort(409, description='Este parecer só pode ser refeito enquanto a proposta está em revisão.')
    credit_response = _brand_audit_credit_gate(client_id)
    if credit_response is not None:
        return credit_response
    job_id = uuid4().hex
    metadata = dict(brand.get('analysis_metadata') or {})
    next_pack = dict(pack)
    next_pack.update({
        'job_id': job_id, 'status': 'running', 'stage': module_id, 'index': 2,
        'total': 4, 'message': f'Refazendo o parecer de {module_id.replace("_", " ")}.',
        'error': '', 'created_at': _utc_timestamp(),
    })
    metadata['review_pack'] = next_pack
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cx_clients SET analysis_metadata = %s::jsonb
                              WHERE id = %s AND crm_client_id = %s RETURNING id""",
                           (json.dumps(metadata), brand_id, client_id))
            if not cursor.fetchone():
                abort(404)
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível refazer o parecer %s da marca %s', module_id, brand_id)
        abort(503, description='Não foi possível refazer este parecer agora.')

    app = current_app._get_current_object()
    def runner():
        with app.app_context():
            try:
                from ..creative_modeling_service import CreativeModelingService
                from ..cadu_credit_connector import CaduCreditConnector, CreditActor
                credits = CaduCreditConnector()
                actor = CreditActor.from_values(client_id, user_id)
                def bill(stage, provider_result, model):
                    credits.charge_provider(
                        actor=actor, idempotency_key=f'workspace-brand:{job_id}:{stage}',
                        app='Auditoria de marca', stage=stage, provider_result=provider_result, model=model,
                        metadata={'brand_id': brand_id, 'job_id': job_id, 'source': 'workspace', 'module': module_id},
                    )
                refreshed = CreativeModelingService().review_brand_module(analysis, module_id, billing_callback=bill)
                latest = _workspace_brand(client_id, brand_id) or {}
                latest_metadata = dict(latest.get('analysis_metadata') or {})
                latest_pack = dict(latest_metadata.get('review_pack') or {})
                if latest_pack.get('job_id') != job_id:
                    return
                reviews = [item for item in (latest_pack.get('reviews') or []) if item.get('id') != module_id]
                reviews.append(refreshed)
                order = {'evidencias': 0, 'estrategia': 1, 'direcao_criativa': 2}
                reviews.sort(key=lambda item: order.get(item.get('id'), 99))
                _save_brand_review_job(client_id, brand_id, job_id, status='pending_approval', stage='complete',
                                       index=4, total=4, message='Parecer atualizado. Revise a proposta antes de aplicar.',
                                       error='', reviews=reviews)
            except Exception as exc:
                current_app.logger.exception('Não foi possível refazer o parecer %s da marca %s', module_id, brand_id)
                _save_brand_review_job(client_id, brand_id, job_id, status='failed', stage='failed',
                                       message='O parecer não foi atualizado.', error=str(exc)[:360])
    threading.Thread(target=runner, daemon=True, name=f'brand-review-{module_id}-{job_id[:8]}').start()
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id, audit='queued'), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/revisoes/aprovar')
@login_required
def approve_brand_reviews(brand_id):
    """Promote a human-approved proposal to the brand context used by projects."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    pack = _brand_review_pack(brand)
    analysis = pack.get('analysis')
    if pack.get('status') != 'pending_approval' or not analysis:
        abort(409, description='Não há uma proposta de análise aguardando aprovação.')
    merged = _merge_brand_analysis(brand, analysis)
    # Once the reviewed proposal has supplied the definitive identity, that
    # value becomes user-owned context rather than a disposable URL guess.
    merged['profile']['name_autogenerated'] = False
    metadata = dict(merged['metadata'])
    review_pack = dict(metadata.get('review_pack') or pack)
    review_pack.update({
        'status': 'approved',
        'approved_at': _utc_timestamp(),
        'approved_by': int(session.get('user_id') or 0),
        # Keep the evidence and reviews for audit, but do not use the proposal
        # as a second source of truth after its values enter brand_profile.
        'analysis': analysis,
    })
    metadata['review_pack'] = review_pack
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cx_clients
                      SET name = CASE WHEN COALESCE(brand_profile->>'name_autogenerated', 'false') = 'true'
                                      THEN COALESCE(NULLIF(%s, ''), name) ELSE name END,
                          sector = COALESCE(NULLIF(sector, ''), %s),
                          website_url = COALESCE(%s, website_url),
                          logo_url = COALESCE(NULLIF(logo_url, ''), %s),
                          primary_color = COALESCE(NULLIF(primary_color, ''), %s),
                          secondary_color = COALESCE(NULLIF(secondary_color, ''), %s),
                          tone_of_voice = COALESCE(NULLIF(tone_of_voice, ''), %s),
                          brand_profile = %s::jsonb,
                          analysis_metadata = %s::jsonb,
                          updated_at = NOW()
                    WHERE id = %s AND crm_client_id = %s
                RETURNING id""",
                (analysis.get('name'), analysis.get('sector'), analysis.get('website_url'), analysis.get('logo_url'),
                 analysis.get('primary_color'), analysis.get('secondary_color'),
                 analysis.get('tone_of_voice'), json.dumps(merged['profile']),
                 json.dumps(metadata), brand_id, client_id),
            )
            if not cursor.fetchone():
                abort(404)
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível aprovar a revisão da marca %s', brand_id)
        abort(503, description='Não foi possível aprovar a análise agora. Tente novamente.')
    try:
        _fill_empty_project_identity_from_brand(client_id, brand_id, merged['profile'])
        # Projects receive compact, approved projections of the same evidence.
        _sync_approved_brand_to_projects(
            client_id, int(session.get('user_id') or 0), brand_id,
            {**brand, 'brand_profile': merged['profile'], 'analysis_metadata': metadata}, analysis,
        )
    except Exception:
        current_app.logger.exception('Contexto aprovado não sincronizado com projetos da marca %s', brand_id)
    try:
        _send_brand_approval_email(
            {**brand, 'name': analysis.get('name') or brand.get('name'), 'analysis_metadata': metadata},
            review_pack, client_id, brand_id,
        )
    except Exception:
        current_app.logger.exception('Resumo por e-mail não enviado após aprovação da marca %s', brand_id)
    # Seed low-resolution working visuals after the human decision.  A visual
    # starter must never block the approval itself: originals and the approved
    # identity remain the source of truth if this best-effort step is delayed.
    try:
        from ..creative_modeling_service import CreativeModelingService
        seed_brand = {
            **brand,
            'name': analysis.get('name') if (brand.get('brand_profile') or {}).get('name_autogenerated') else brand.get('name'),
            'sector': analysis.get('sector') or brand.get('sector'),
            'primary_color': analysis.get('primary_color') or brand.get('primary_color'),
            'secondary_color': analysis.get('secondary_color') or brand.get('secondary_color'),
        }
        CreativeModelingService().create_client_brand_seed_visuals(brand_id, seed_brand)
    except Exception:
        current_app.logger.exception('Não foi possível criar os visuais internos da marca %s', brand_id)
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id, review='approved'), code=303)


@bp.get('/workspace/app/marcas/<int:brand_id>/sistema')
@login_required
def brand_system(brand_id):
    """Advanced brand editor inside the tenant-scoped Workspace shell."""
    brand = _workspace_brand(int(session.get('cliente_id') or 0), brand_id)
    if not brand:
        abort(404)
    return render_template('cadu_workspace/brand_system_app.html', brand=brand)


@bp.get('/agencia', defaults={'section': 'agencia'})
@bp.get('/perfil', defaults={'section': 'perfil'})
@bp.get('/equipe', defaults={'section': 'equipe'})
@bp.get('/plano', defaults={'section': 'planos'})
@bp.get('/uso', defaults={'section': 'uso'})
@bp.get('/creditos', defaults={'section': 'creditos'})
@bp.get('/faturas', defaults={'section': 'faturamento'})
@bp.get("/workspace/app/<section>")
@login_required
def account_page(section):
    aliases = {
        "conta": "perfil", "perfil": "perfil", "agencia": "agencia", "organizacao": "agencia",
        "usuarios": "equipe", "equipe": "equipe", "planos": "planos", "uso": "uso", "creditos": "creditos",
        "financeiro": "faturamento", "faturamento": "faturamento",
    }
    section = aliases.get(section)
    if section is None:
        abort(404)
    canonical_paths = {
        'agencia': '/agencia',
        'perfil': '/perfil',
        'equipe': '/equipe',
        'planos': '/plano',
        'uso': '/uso',
        'creditos': '/creditos',
        'faturamento': '/faturas',
    }
    if request.path.startswith('/workspace/app/') or request.path != canonical_paths[section]:
        target = canonical_paths[section]
        if request.query_string:
            target = f'{target}?{request.query_string.decode("utf-8")}'
        return redirect(target, code=308)
    client_id = int(session.get("cliente_id") or 0)
    account = _php_account_data(client_id)
    # The agency identity belongs to the whole Account journey, not only to
    # the profile editor. These are canonical PHP records, never a copy.
    account.update(_workspace_settings_data(client_id, int(session.get("user_id") or 0)))
    if section == 'planos':
        try:
            from .. import db
            account['plan_options'] = [dict(row) for row in db.obter_plan_definitions(apenas_ativos=True)]
        except Exception:
            current_app.logger.warning('Não foi possível carregar as opções comerciais de planos', exc_info=True)
            account['plan_options'] = []
    projects = _workspace_projects(client_id)
    brands = _workspace_brands(client_id)
    account['agency_context'] = {
        'projects': [{'id': str(item.get('id')), 'name': str(item.get('nome') or 'Projeto'),
                      'brandName': str(item.get('thumbnail_label') or ''), 'status': str(item.get('status') or 'ativo'),
                      'sources': int(item.get('fontes_prontas') or 0),
                      'href': url_for('cadu_workspace.clean_project_detail', project_id=str(item.get('id')))} for item in projects],
        'brands': [{'id': str(item.get('id')), 'name': str(item.get('name') or 'Marca'),
                    'assetCount': int(item.get('asset_count') or 0),
                    'href': url_for('cadu_workspace.clean_brand_detail', brand_id=int(item.get('id')))} for item in brands],
    }
    if section == 'faturamento':
        account.update(_workspace_billing_data(client_id))
    try:
        dock_items = _workspace_common_dock_items(client_id, int(session.get('user_id') or 0))
    except Exception:
        current_app.logger.exception('Não foi possível carregar a dock do Workspace para a conta')
        dock_items = []
    return render_template(
        "cadu_workspace/account_react.html", section=section,
        account=account, dock_items=dock_items,
    )


def _redirect_account_alias(target):
    if request.query_string:
        target = f'{target}?{request.query_string.decode("utf-8")}'
    return redirect(target, code=308)


@bp.get('/conta')
@login_required
def account_alias_conta():
    return _redirect_account_alias('/perfil')


@bp.get('/planos')
@login_required
def account_alias_planos():
    return _redirect_account_alias('/plano')


@bp.get('/faturamento')
@login_required
def account_alias_faturamento():
    return _redirect_account_alias('/faturas')


@bp.get('/workspace/app/integracoes')
@bp.get('/integracoes')
@login_required
def integrations():
    if request.path.startswith('/workspace/app/'):
        return redirect(url_for('cadu_workspace.integrations', **request.args.to_dict(flat=True)), code=308)
    client_id = int(session.get('cliente_id') or 0)
    organization_id = int(session.get('organization_id') or client_id)
    return render_template(
        'cadu_workspace/integrations.html',
        integration_data=_workspace_integration_data(client_id, organization_id),
    )


@bp.post('/integracoes/google/sync')
@login_required
def google_workspace_sync():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    from ..services import google_workspace
    organization_id = int(session.get('organization_id') or session.get('cliente_id') or 0)
    try:
        results = []
        errors = []
        for operation in (
            google_workspace.sync_drive,
            google_workspace.sync_calendar_events,
            google_workspace.discover_meet_artifacts,
            google_workspace.sync_ads,
        ):
            try:
                results.append(operation(organization_id))
            except google_workspace.GoogleWorkspaceError as exc:
                errors.append(str(exc))
        if not results and errors:
            return jsonify({'success': False, 'error': errors[0]}), 400
        return jsonify({'success': True, 'results': results, 'errors': errors,
                        'synced': sum(int(item.get('synced') or 0) for item in results)})
    except google_workspace.GoogleWorkspaceError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.post('/integracoes/google/disconnect')
@login_required
def google_workspace_disconnect():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    from ..services import google_workspace
    organization_id = int(session.get('organization_id') or session.get('cliente_id') or 0)
    try:
        removed = google_workspace.disconnect(organization_id)
        return jsonify({'success': True, 'removed': removed})
    except google_workspace.GoogleWorkspaceError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.post('/integracoes/google/resources/<uuid:resource_id>/link')
@login_required
def google_workspace_link_resource(resource_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    from ..services import google_workspace
    payload = request.get_json(silent=True) or {}
    client_id = int(session.get('cliente_id') or 0)
    organization_id = int(session.get('organization_id') or client_id)
    try:
        result = google_workspace.link_resource(
            organization_id=organization_id,
            client_id=client_id,
            resource_id=str(resource_id),
            project_ref=str(payload.get('project_ref') or '').strip(),
            purpose=str(payload.get('purpose') or 'project_knowledge').strip(),
            user_id=int(session.get('user_id') or 0),
        )
        return jsonify({'success': True, **result})
    except google_workspace.GoogleWorkspaceError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.post('/integracoes/google/meet/artifacts/<uuid:artifact_id>/fetch')
@login_required
def google_workspace_fetch_meet_artifact(artifact_id):
    """Fetch transcript text only after an explicit user action."""
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    from ..services import google_workspace
    organization_id = int(session.get('organization_id') or session.get('cliente_id') or 0)
    try:
        result = google_workspace.fetch_meet_transcript_content(
            organization_id, str(artifact_id), limit=2000,
        )
        return jsonify({'success': True, **result})
    except google_workspace.GoogleWorkspaceError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


def _slack_config(name: str, default: str = '') -> str:
    return str(current_app.config.get(name) or os.getenv(name, '') or default).strip()


@bp.get('/integracoes/slack/connect')
@login_required
def slack_connect():
    from ..services import cadu_slack_connector
    client_id = _slack_config('SLACK_CLIENT_ID')
    redirect_uri = _slack_config('SLACK_REDIRECT_URI', product_url('workspace', '/integracoes/slack/callback'))
    if not client_id:
        return jsonify({'success': False, 'error': 'Configure SLACK_CLIENT_ID antes de conectar o Slack.'}), 400
    state = secrets.token_urlsafe(32)
    session['cadu_slack_oauth_state'] = state
    return redirect(cadu_slack_connector.authorization_url(
        client_id=client_id, redirect_uri=redirect_uri, state=state,
    ))


@bp.get('/integracoes/slack/callback')
@login_required
def slack_callback():
    from ..services import cadu_slack_connector
    expected = session.pop('cadu_slack_oauth_state', '')
    if not expected or not secrets.compare_digest(expected, str(request.args.get('state') or '')):
        abort(400, description='Estado OAuth do Slack inválido.')
    try:
        payload = cadu_slack_connector.exchange_code(
            code=str(request.args.get('code') or ''),
            client_id=_slack_config('SLACK_CLIENT_ID'),
            client_secret=_slack_config('SLACK_CLIENT_SECRET'),
            redirect_uri=_slack_config('SLACK_REDIRECT_URI', product_url('workspace', '/integracoes/slack/callback')),
        )
        signing_secret = _slack_config('SLACK_SIGNING_SECRET')
        if not signing_secret:
            raise cadu_slack_connector.SlackConnectorError('Configure SLACK_SIGNING_SECRET antes de conectar o Slack.')
        client_id = int(session.get('cliente_id') or 0)
        organization_id = int(session.get('organization_id') or client_id)
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_slack_connections
                    (id, organization_id, client_id, team_id, team_name,
                     encrypted_bot_token, encrypted_signing_secret, granted_scopes, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (organization_id) DO UPDATE SET
                    team_id=EXCLUDED.team_id, team_name=EXCLUDED.team_name,
                    encrypted_bot_token=EXCLUDED.encrypted_bot_token,
                    encrypted_signing_secret=EXCLUDED.encrypted_signing_secret,
                    granted_scopes=EXCLUDED.granted_scopes, status='connected', updated_at=NOW()""",
                (uuid4(), organization_id, client_id, str((payload.get('team') or {}).get('id') or ''),
                 str((payload.get('team') or {}).get('name') or ''),
                 cadu_slack_connector.encrypt_secret(str(payload.get('access_token') or '')),
                 cadu_slack_connector.encrypt_secret(signing_secret), str(payload.get('scope') or ''),
                 int(session.get('user_id') or 0)),
            )
        connection.commit()
        return redirect(url_for('cadu_workspace.integrations'))
    except (cadu_slack_connector.SlackConnectorError, KeyError, ValueError) as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@bp.post('/integracoes/slack/events')
def slack_events():
    """Acknowledge verified Slack events; indexing remains project-scoped."""
    from ..services import cadu_slack_connector
    body = request.get_data(cache=True)
    payload = request.get_json(silent=True) or {}
    if payload.get('type') == 'url_verification':
        # Slack sends this challenge before the installation is persisted.
        # Validate it with the app-level signing secret, then allow setup to
        # complete without requiring a pre-existing team row.
        signing_secret = _slack_config('SLACK_SIGNING_SECRET')
        if not signing_secret or not cadu_slack_connector.verify_signature(
            signing_secret=signing_secret,
            timestamp=str(request.headers.get('X-Slack-Request-Timestamp') or ''),
            body=body,
            signature=str(request.headers.get('X-Slack-Signature') or ''),
        ):
            return jsonify({'error': 'Assinatura Slack inválida.'}), 401
        return jsonify({'challenge': payload.get('challenge')})
    team_id = str(payload.get('team_id') or (payload.get('authorizations') or [{}])[0].get('team_id') or '')
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, encrypted_signing_secret FROM cadu_slack_connections
                WHERE team_id=%s AND status='connected'""",
            (team_id,),
        )
        connection = cursor.fetchone()
    if not connection:
        return jsonify({'error': 'Slack team não conectado.'}), 401
    try:
        secret = cadu_slack_connector.decrypt_secret(connection['encrypted_signing_secret'])
    except cadu_slack_connector.SlackConnectorError:
        return jsonify({'error': 'Segredo Slack indisponível.'}), 503
    if not cadu_slack_connector.verify_signature(
        signing_secret=secret,
        timestamp=str(request.headers.get('X-Slack-Request-Timestamp') or ''),
        body=body,
        signature=str(request.headers.get('X-Slack-Signature') or ''),
    ):
        return jsonify({'error': 'Assinatura Slack inválida.'}), 401
    event = cadu_slack_connector.normalize_event(payload)
    event_id = event['event_id'] or f"event:{sha256(body).hexdigest()}"
    connection_db = get_db()
    try:
        with connection_db.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_slack_events (connection_id, event_id, event_type, payload)
                VALUES (%s,%s,%s,%s) ON CONFLICT (connection_id, event_id) DO NOTHING""",
                (connection['id'], event_id, event['type'], json.dumps(event, ensure_ascii=False)),
            )
        connection_db.commit()
    except Exception:
        connection_db.rollback()
        raise
    return jsonify({'ok': True})


@bp.post('/workspace/app/perfil')
@login_required
def update_own_profile():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    name = ' '.join((request.form.get('name') or '').split())
    phone = ' '.join((request.form.get('phone') or '').split())
    avatar_badges = {
        'badge-comet.png', 'badge-ribbon.png', 'badge-orbit.png',
        'badge-prism.png', 'badge-sunburst.png', 'badge-sphere.png',
    }
    default_avatar_badges = (
        'badge-comet.png', 'badge-ribbon.png', 'badge-orbit.png',
        'badge-prism.png', 'badge-sunburst.png', 'badge-sphere.png',
    )
    avatar_badge = (request.form.get('avatar_badge') or '').strip()
    if not avatar_badge:
        avatar_badge = default_avatar_badges[int(session.get('user_id') or 0) % len(default_avatar_badges)]
    if not 2 <= len(name) <= 120:
        abort(400, description='Informe seu nome com 2 a 120 caracteres.')
    if len(phone) > 30 or (phone and not re.fullmatch(r'[0-9+() .-]+', phone)):
        abort(400, description='Informe um telefone válido.')
    if avatar_badge not in avatar_badges:
        abort(400, description='Escolha um selo de avatar válido.')
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE tbl_contato_cliente
                      SET nome_completo = %s, telefone = %s, cadu_avatar_badge = %s,
                          data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_contato_cliente = %s AND pk_id_tbl_cliente = %s
                RETURNING id_contato_cliente""",
                (name, phone or None, avatar_badge, int(session.get('user_id') or 0),
                 int(session.get('cliente_id') or 0)),
            )
            if not cursor.fetchone():
                abort(404)
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível atualizar o perfil do usuário')
        abort(503, description='Não foi possível salvar seu perfil agora.')
    session['user_name'] = name
    session['cadu_avatar_badge'] = avatar_badge
    return redirect(url_for('cadu_workspace.account_page', section='perfil', saved='1'), code=303)


@bp.post('/workspace/app/organizacao')
@login_required
def update_organization():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    fields = {
        'trade_name': ' '.join((request.form.get('trade_name') or '').split()),
        'legal_name': ' '.join((request.form.get('legal_name') or '').split()),
        'document': re.sub(r'\D', '', request.form.get('document') or ''),
        'postal_code': re.sub(r'\D', '', request.form.get('postal_code') or ''),
        'street': ' '.join((request.form.get('street') or '').split()),
        'number': ' '.join((request.form.get('number') or '').split()),
        'complement': ' '.join((request.form.get('complement') or '').split()),
        'district': ' '.join((request.form.get('district') or '').split()),
        'city': ' '.join((request.form.get('city') or '').split()),
        'state': (request.form.get('state') or '').strip().upper(),
    }
    if not 2 <= len(fields['trade_name']) <= 160:
        abort(400, description='Informe o nome da organização.')
    if fields['legal_name'] and len(fields['legal_name']) > 180:
        abort(400, description='A razão social é muito longa.')
    if fields['document'] and len(fields['document']) not in {11, 14}:
        abort(400, description='Informe um CPF ou CNPJ válido.')
    if fields['postal_code'] and len(fields['postal_code']) != 8:
        abort(400, description='Informe um CEP com oito dígitos.')
    for key in ('street', 'number', 'complement', 'district', 'city'):
        if len(fields[key]) > 180:
            abort(400, description='Revise os dados de endereço informados.')
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            state_id = None
            if fields['state']:
                cursor.execute(
                    'SELECT id_estado FROM tbl_estado WHERE UPPER(sigla) = %s LIMIT 1',
                    (fields['state'],),
                )
                state = cursor.fetchone()
                if not state:
                    abort(400, description='Selecione um estado válido.')
                state_id = state['id_estado']
            cursor.execute(
                """UPDATE tbl_cliente
                      SET nome_fantasia = %s, razao_social = %s, cnpj = %s,
                          cep = %s, logradouro = %s, numero = %s, complemento = %s,
                          bairro = %s, cidade = %s, pk_id_aux_estado = %s,
                          data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_cliente = %s
                RETURNING id_cliente""",
                (fields['trade_name'], fields['legal_name'] or None, fields['document'] or None,
                 fields['postal_code'] or None, fields['street'] or None, fields['number'] or None,
                 fields['complement'] or None, fields['district'] or None, fields['city'] or None,
                 state_id, int(session.get('cliente_id') or 0)),
            )
            if not cursor.fetchone():
                abort(404)
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível atualizar a organização')
        abort(503, description='Não foi possível salvar a organização agora.')
    return redirect(url_for('cadu_workspace.account_page', section='agencia', saved='1'), code=303)


@bp.post('/workspace/app/equipe/convites')
@login_required
def create_team_invite():
    """Create the established Cadu invite and dispatch it only after a user submits the form."""
    from .. import db
    from ..email_service import send_invite_email

    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    email = (request.form.get('email') or '').strip().lower()
    role = request.form.get('role') if request.form.get('role') in {'member', 'admin'} else 'member'
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        abort(400, description='Informe um e-mail válido para o convite.')
    client_id = int(session.get('cliente_id') or 0)
    try:
        pending_invite = db.verificar_convite_pendente(email, client_id)
    except Exception:
        current_app.logger.exception('Não foi possível validar convite de equipe')
        abort(503, description='Não foi possível validar o convite agora. Tente novamente.')
    if pending_invite:
        abort(409, description='Já existe um convite pendente para este e-mail.')
    try:
        invite_id = db.criar_invite(client_id, session.get('user_id'), email, role)
        invite = db.obter_invite_por_id(invite_id)
        plans = db.obter_planos_clientes({'cliente_id': client_id})
        company_name = (plans[0].get('nome_fantasia') if plans else '') or 'sua organização'
        result = send_invite_email(
            email, invite['invite_token'], company_name, session.get('user_name') or 'Equipe', invite['expires_at'],
            role_label='Administrador' if role == 'admin' else 'Membro',
        )
        if not result.get('success'):
            db.cancelar_invite(invite_id)
            current_app.logger.warning('Convite %s cancelado porque o envio falhou: %s', invite_id, result.get('error'))
            abort(502, description='O e-mail não pôde ser enviado. Confira o endereço e tente novamente.')
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível criar convite de equipe')
        abort(503, description='Não foi possível criar o convite agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


@bp.post('/workspace/app/equipe/convites/<int:invite_id>/reenviar')
@login_required
def resend_team_invite(invite_id):
    from .. import db
    from ..email_service import send_invite_email

    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    try:
        invite = db.obter_invite_por_id(invite_id)
        if not invite or int(invite.get('id_cliente') or 0) != client_id or invite.get('status') != 'pending':
            abort(404)
        if not db.reenviar_invite(invite_id):
            abort(409, description='Este convite não pode mais ser reenviado.')
        invite = db.obter_invite_por_id(invite_id)
        plans = db.obter_planos_clientes({'cliente_id': client_id})
        company_name = (plans[0].get('nome_fantasia') if plans else '') or 'sua organização'
        result = send_invite_email(
            invite['email'], invite['invite_token'], company_name, session.get('user_name') or 'Equipe', invite['expires_at'],
            role_label='Administrador' if invite.get('role') == 'admin' else 'Membro',
        )
        if not result.get('success'):
            current_app.logger.warning('Reenvio do convite %s falhou: %s', invite_id, result.get('error'))
            abort(502, description='O e-mail não pôde ser reenviado. Tente novamente em instantes.')
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível reenviar convite de equipe')
        abort(503, description='Não foi possível reenviar o convite agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


@bp.post('/workspace/app/equipe/convites/<int:invite_id>/cancelar')
@login_required
def cancel_team_invite(invite_id):
    from .. import db

    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    client_id = int(session.get('cliente_id') or 0)
    try:
        invite = db.obter_invite_por_id(invite_id)
        if not invite or int(invite.get('id_cliente') or 0) != client_id or invite.get('status') != 'pending':
            abort(404)
        if not db.cancelar_invite(invite_id):
            abort(409, description='Este convite não pode mais ser cancelado.')
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível cancelar convite de equipe')
        abort(503, description='Não foi possível cancelar o convite agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


@bp.post('/workspace/app/equipe/<int:contact_id>/status')
@login_required
def update_team_member_status(contact_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    if int(session.get('user_id') or 0) == contact_id:
        abort(409, description='Você não pode desativar o próprio acesso.')
    client_id = int(session.get('cliente_id') or 0)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id_contato_cliente, status, user_type
                     FROM tbl_contato_cliente
                    WHERE id_contato_cliente = %s AND pk_id_tbl_cliente = %s
                    FOR UPDATE""",
                (contact_id, client_id),
            )
            member = cursor.fetchone()
            if not member:
                abort(404)
            if member.get('status') and member.get('user_type') in {'admin', 'superadmin'}:
                cursor.execute(
                    """SELECT COUNT(*) AS total FROM tbl_contato_cliente
                        WHERE pk_id_tbl_cliente = %s AND status = TRUE
                          AND user_type IN ('admin', 'superadmin')""",
                    (client_id,),
                )
                if int(cursor.fetchone()['total'] or 0) <= 1:
                    abort(409, description='A organização precisa manter ao menos um administrador ativo.')
            cursor.execute(
                """UPDATE tbl_contato_cliente
                      SET status = NOT status, data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_contato_cliente = %s AND pk_id_tbl_cliente = %s
                RETURNING status""",
                (contact_id, client_id),
            )
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível alterar o acesso do usuário %s', contact_id)
        abort(503, description='Não foi possível alterar o acesso agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


@bp.post('/workspace/app/equipe/<int:contact_id>/papel')
@login_required
def update_team_member_role(contact_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    _workspace_team_admin()
    if int(session.get('user_id') or 0) == contact_id:
        abort(409, description='Outro administrador deve alterar o seu nível de acesso.')
    role = request.form.get('role') or 'client'
    if role not in {'client', 'admin', 'readonly'}:
        abort(400, description='Nível de acesso inválido.')
    client_id = int(session.get('cliente_id') or 0)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id_contato_cliente, status, user_type
                     FROM tbl_contato_cliente
                    WHERE id_contato_cliente = %s AND pk_id_tbl_cliente = %s
                    FOR UPDATE""",
                (contact_id, client_id),
            )
            member = cursor.fetchone()
            if not member:
                abort(404)
            if member.get('user_type') in {'admin', 'superadmin'} and role != 'admin' and member.get('status'):
                cursor.execute(
                    """SELECT COUNT(*) AS total FROM tbl_contato_cliente
                        WHERE pk_id_tbl_cliente = %s AND status = TRUE
                          AND user_type IN ('admin', 'superadmin')""",
                    (client_id,),
                )
                if int(cursor.fetchone()['total'] or 0) <= 1:
                    abort(409, description='A organização precisa manter ao menos um administrador ativo.')
            cursor.execute(
                """UPDATE tbl_contato_cliente
                      SET user_type = %s, data_modificacao = CURRENT_TIMESTAMP
                    WHERE id_contato_cliente = %s AND pk_id_tbl_cliente = %s
                RETURNING id_contato_cliente""",
                (role, contact_id, client_id),
            )
        connection.commit()
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        current_app.logger.exception('Não foi possível alterar o papel do usuário %s', contact_id)
        abort(503, description='Não foi possível alterar a permissão agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


@bp.get("/workspace/agentes")
def agents():
    return redirect(url_for("cadu_skills.agents"), code=302)


@bp.get("/workspace/minhas-skills")
@login_required
def my_skills():
    return render_template(
        "cadu_workspace/my_skills.html",
        customizations=list_customizations(client_id=int(session.get("cliente_id") or 0)),
    )


@bp.get("/robots.txt")
def robots():
    _workspace_host_only()
    body = "\n".join((
        "User-agent: *", "Allow: /workspace/", "Allow: /workspace/como-funciona",
        "Allow: /workspace/planos", "Allow: /workspace/ajuda", "Allow: /workspace/contato",
        "Disallow: /workspace/app", "Disallow: /workspace/minhas-skills",
        f"Sitemap: {product_url('workspace', '/sitemap.xml')}", "",
    ))
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    _workspace_host_only()
    paths = ("/", "/como-funciona", "/planos", "/ajuda", "/contato")
    urls = "".join(f"<url><loc>{product_url('workspace', path)}</loc></url>" for path in paths)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', mimetype="application/xml")


@bp.get("/llms.txt")
def llms():
    _workspace_host_only()
    lines = [
        "# Cadu Workspace", "",
        "> O ponto de partida público e autenticado para organizar o trabalho na família Cadu.", "",
        "## Páginas públicas", "",
        f"- [Visão geral]({product_url('workspace')})",
        f"- [Como funciona]({product_url('workspace', '/como-funciona')})",
        f"- [Planos]({product_url('workspace', '/planos')})",
        f"- [Ajuda]({product_url('workspace', '/ajuda')})",
        f"- [Contato]({product_url('workspace', '/contato')})", "",
        "## Conteúdo público relacionado", "",
        f"- [Agentes e capacidades]({product_url('skills', '/agentes')})",
        f"- [Skills públicas testáveis]({product_url('skills')})", "",
        "Áreas autenticadas", "",
        "Projetos, skills personalizadas, créditos, clientes, campanhas, contas, MCPs e relatórios são privados e não fazem parte do sitemap.", "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")
