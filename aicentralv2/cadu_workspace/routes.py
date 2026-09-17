"""Área autenticada de conta e administração do workspace.centralcomm.media."""

from pathlib import Path
import calendar
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import json
import re
import threading
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4
import secrets

from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException

from flask import Blueprint, Response, abort, current_app, g, jsonify, redirect, render_template, request, send_file, session, url_for

from ..auth import login_required
from ..cadu_family import repository as family_repository
from ..cadu_connect.repository import accounts_for_workspace_context
from ..cadu_skills.repository import CaduCreditUnavailable, charge_project_rag, credit_position, list_customizations
from ..db import get_db
from ..product_domains import product_url
from ..smart_planner.logos import public_logo
from . import project_sources


bp = Blueprint("cadu_workspace", __name__)
# The advanced brand editor has a Workspace-owned API prefix.  Its handlers
# are registered during app setup, alongside this product blueprint.
brand_api_bp = Blueprint("workspace_brand_api", __name__, url_prefix="/workspace")


@bp.before_request
def prepare_shared_cadu_chat():
    if session.get("user_id"):
        session.setdefault("family_csrf", secrets.token_urlsafe(32))


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
    granted = int(credit.get("monthly_limit") or credit.get("monthly") or 0)
    used = int(credit.get("monthly_used") or max(0, granted - int(credit.get("available") or 0)))
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
                          tokens_amount AS credits, status AS payment_status,
                          NULL::varchar AS reference, purchased_at
                     FROM cadu_credits_extras
                    WHERE id_cliente = %s
                 ORDER BY purchased_at DESC NULLS LAST, id DESC LIMIT 20""",
                (client_id,),
            )
            purchases = [dict(row) for row in cursor.fetchall()]
    except Exception:
        purchases = []
    insights = _workspace_account_insights(plan, position, people)
    return {"people": people, "invites": invites, "plan": plan, "credit": credit,
            "position": position, "movements": movements, "purchases": purchases,
            "insights": insights}


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
    return {
        'accounts': accounts,
        'connected_count': sum(str(item.get('status') or '').lower() in {'active', 'connected', 'ready'}
                               for item in accounts),
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
            {'name': 'Meta Business Suite', 'icon': 'fa-brands fa-meta'},
            {'name': 'Slack', 'icon': 'fa-brands fa-slack'},
            {'name': 'Notion', 'icon': 'fa-solid fa-note-sticky'},
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


def _workspace_team_admin() -> None:
    if session.get('user_type') not in {'admin', 'superadmin'}:
        abort(403, description='Somente administradores podem gerenciar acessos da organização.')


def _workspace_brand_form() -> dict:
    """Normalize the small, durable identity contract owned by Workspace."""
    website_url = (request.form.get('website_url') or '').strip()[:2000]
    if website_url and not re.match(r'^https?://', website_url, re.I):
        website_url = 'https://' + website_url.lstrip('/')
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
            'name_autogenerated': name_autogenerated,
        },
    }


def _cadu_area(config_key: str, path: str) -> str:
    return str(current_app.config.get(config_key) or product_url("cadu", path))


def _workspace_brands(client_id: int, query: str = "") -> list[dict]:
    """Read brand records owned by the active Workspace organization."""
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT c.id, c.name, c.sector, c.tone_of_voice, c.website_url, c.primary_color,
                          c.secondary_color, c.logo_url, c.logo_upload_path, c.brand_profile,
                          c.analysis_metadata, c.created_at AS updated_at,
                          COUNT(a.id) FILTER (WHERE a.status = 'approved') AS asset_count,
                          COUNT(a.id) FILTER (WHERE a.role = 'logo' AND a.is_primary) AS has_logo
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
                brand['display_logo'] = public_logo(brand.get('logo_upload_path') or brand.get('logo_url'))
                seed_visuals = brand['brand_profile'].get('seed_visuals') or {}
                brand['visual_thumbnail'] = public_logo(seed_visuals.get('thumbnail')) if isinstance(seed_visuals, dict) else ''
                brand['display_initials'] = ''.join(
                    word[0] for word in re.findall(r"[\wÀ-ÿ]+", name)[:2]
                ).upper() or 'M'
                brand['display_color'] = brand.get('primary_color') or '#176b5e'
            return brands
    except Exception:
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


def _brand_review_pack(brand: dict) -> dict:
    """Normalize the pending/approved analysis contract stored with a brand."""
    metadata = brand.get('analysis_metadata') or {}
    pack = metadata.get('review_pack') if isinstance(metadata, dict) else {}
    if not isinstance(pack, dict):
        return {}
    reviews = [item for item in pack.get('reviews', []) if isinstance(item, dict)]
    return {
        'status': str(pack.get('status') or 'pending_approval'),
        'job_id': pack.get('job_id'),
        'stage': str(pack.get('stage') or ''),
        'index': int(pack.get('index') or 0),
        'total': int(pack.get('total') or 4),
        'message': str(pack.get('message') or ''),
        'error': str(pack.get('error') or ''),
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
        'target_audience', 'products_services', 'differentiators', 'proof_points',
        'ad_segments', 'creative_guidelines', 'campaign_opportunities',
        'visual_motifs', 'mandatory_elements', 'forbidden_elements', 'fonts',
        'confidence', 'sources',
    }
    return {key: value for key, value in analysis.items() if key in allowed}


def _ensure_brand_audit_credit(client_id: int) -> None:
    """Avoid starting a paid provider workflow when the client has no balance."""
    try:
        from ..cadu_tool_billing import ToolTokenLedger
        available = ToolTokenLedger().available(client_id)
    except Exception:
        current_app.logger.exception('Não foi possível consultar créditos para auditoria de marca')
        abort(503, description='Não foi possível consultar os créditos da organização agora.')
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
            current['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            metadata['review_pack'] = current
            cursor.execute(
                """UPDATE cx_clients SET analysis_metadata = %s::jsonb, updated_at = NOW()
                     WHERE id = %s AND crm_client_id = %s""",
                (json.dumps(metadata), brand_id, client_id),
            )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise


def _start_brand_review_job(client_id: int, user_id: int, brand_id: int, job_id: str, website_url: str, images: list[dict], proposal=None):
    """Run slow model work outside the browser request, retaining visible progress."""
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
                from ..cadu_tool_billing import ToolTokenLedger, charge_from_provider
                service = CreativeModelingService()
                ledger = ToolTokenLedger()

                def bill(stage, provider_result, model):
                    """One durable, idempotent ledger movement per provider call."""
                    charge_from_provider(
                        ledger=ledger, idempotency_key=f'workspace-brand:{job_id}:{stage}',
                        client_id=client_id, user_id=user_id, tool='Auditoria de marca', stage=stage,
                        provider_result=provider_result, model=model,
                        metadata={'brand_id': brand_id, 'job_id': job_id, 'source': 'workspace'},
                    )

                analysis_metadata = {}
                if isinstance(proposal, dict) and proposal:
                    # A prior attempt already paid for and saved the evidence
                    # extraction. Resume from that durable checkpoint.
                    proposal = _brand_analysis_proposal(proposal)
                    _save_brand_review_job(client_id, brand_id, job_id,
                        status='running', stage='evidence_reused', index=1, total=4,
                        message='Retomando a proposta já extraída.')
                else:
                    analysis = service.analyze_brand(website_url, restored_images, billing_callback=bill)
                    if not isinstance(analysis, dict) or not analysis.get('analysis_metadata'):
                        raise ValueError('A análise não retornou evidências suficientes.')
                    proposal = _brand_analysis_proposal(analysis)
                    analysis_metadata = analysis.get('analysis_metadata') or {}
                    _save_brand_review_job(client_id, brand_id, job_id,
                        status='running', stage='evidence_complete', index=1, total=4,
                        message='Evidências organizadas. Iniciando os pareceres.',
                        analysis=proposal, analysis_metadata=analysis_metadata)

                def progress(review_id, title, position, total):
                    _save_brand_review_job(client_id, brand_id, job_id,
                        status='running', stage=review_id, index=position + 1, total=total + 1,
                        message=f'{title}: preparando parecer.')

                reviews = service.review_brand_analysis(proposal, progress=progress, billing_callback=bill)
                if not isinstance(reviews, list) or len(reviews) != 3:
                    raise ValueError('As três revisões da marca não foram concluídas.')
                _save_brand_review_job(client_id, brand_id, job_id,
                    status='pending_approval', stage='complete', index=4, total=4,
                    message='Três pareceres estão prontos para decisão.', error='',
                    analysis=proposal, reviews=reviews,
                    analysis_metadata=analysis_metadata)
            except Exception as exc:
                current_app.logger.exception('Não foi possível auditar a marca %s', brand_id)
                _save_brand_review_job(client_id, brand_id, job_id,
                    status='failed', stage='failed', message='A análise precisa ser tentada novamente.',
                    error=str(exc)[:360])

    threading.Thread(target=runner, daemon=True, name=f'brand-review-{job_id[:12]}').start()


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


def _workspace_projects(client_id: int, query: str = "", status: str = "ativos") -> list[dict]:
    """Project dossiers retained from Cadu, always isolated by organization."""
    status = status if status in {'ativos', 'arquivados', 'todos'} else 'ativos'
    status_clause = "p.status = 'ativo'" if status == 'ativos' else "p.status = 'arquivado'" if status == 'arquivados' else "p.status <> 'deletado'"
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
                (client_id, '%' + query[:100] + '%', '%' + query[:100] + '%'),
            )
            return _attach_project_identity(client_id, [dict(row) for row in cursor.fetchall()])
    except Exception:
        # Older Cadu databases may still be missing narrative/RAG migrations.
        # Keep the dossier visible and let its missing capabilities read as empty.
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
                    (client_id, '%' + query[:100] + '%', '%' + query[:100] + '%'),
                )
                records = [dict(row) for row in cursor.fetchall()]
                for record in records:
                    record.update({'tom_de_voz': '', 'publico': '', 'posicionamento': ''})
                return _attach_project_identity(client_id, records)
        except Exception:
            return []


def _attach_project_identity(client_id: int, projects: list[dict]) -> list[dict]:
    """Add the linked brand mark while keeping older dossiers presentable."""
    if not projects:
        return projects
    try:
        brands_by_ref = {f"studio:{brand['id']}": brand for brand in _workspace_brands(client_id)}
        links_by_project: dict[str, list[dict]] = {}
        for link in family_repository.project_brand_links(client_id):
            brand = brands_by_ref.get(str(link.get('brand_ref') or ''))
            if brand:
                links_by_project.setdefault(str(link.get('project_ref') or ''), []).append(brand)
    except Exception:
        links_by_project = {}

    for project in projects:
        name = str(project.get('nome') or '').strip()
        brand = next(iter(links_by_project.get(f"ci:{project.get('id')}", [])), {})
        project['thumbnail_url'] = public_logo(brand.get('logo_upload_path') or brand.get('logo_url')) if brand else ''
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
    return {'workspace_sidebar_projects': _workspace_sidebar_projects(client_id)}


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
    if project.get('smartdocs') or project.get('images'):
        score += 10
    else:
        missing.append('referências produzidas')
    if project.get('brands'):
        score += 10
    else:
        missing.append('uma marca vinculada')
    if score >= 80:
        label = 'Pronto para orientar o trabalho'
    elif score >= 45:
        label = 'Contexto em construção'
    else:
        label = 'Comece estruturando o contexto'
    return {'score': score, 'label': label, 'missing': missing[:3]}


def _project_recent_activity(project: dict) -> list[dict]:
    """A chronological, factual timeline assembled from the dossier records."""
    activity = []
    if project.get('updated_at'):
        activity.append({'title': 'Projeto atualizado', 'detail': project.get('nome'), 'at': project['updated_at']})
    for item in project.get('files', [])[:4]:
        activity.append({'title': 'Fonte adicionada', 'detail': item.get('nome_arquivo') or 'Arquivo', 'at': item.get('created_at')})
    for item in project.get('conversations', [])[:3]:
        activity.append({'title': 'Conversa atualizada', 'detail': item.get('titulo') or 'Conversa sem título', 'at': item.get('updated_at')})
    for item in project.get('smartdocs', [])[:3]:
        activity.append({'title': 'SmartDoc atualizado', 'detail': item.get('titulo') or 'Documento sem título', 'at': item.get('updated_at')})
    for item in project.get('images', [])[:3]:
        activity.append({'title': 'Referência visual adicionada', 'detail': item.get('title') or 'Imagem sem título', 'at': item.get('created_at')})
    return sorted(activity, key=lambda item: str(item.get('at') or ''), reverse=True)[:8]


def _chunk_project_note(content: str, limit: int = 1800) -> list[str]:
    """Compatibility wrapper kept for tests and callers of the first native slice."""
    return project_sources.chunks(content, limit)


def _persist_project_source(client_id: int, project_id: str, title: str, content: str,
                            mime: str, size: int, storage_path: str, source: str) -> int:
    source_chunks = project_sources.chunks(content)
    if not source_chunks:
        raise ValueError('A fonte não contém texto indexável.')
    word_count = len(re.findall(r'\b\w+\b', content, flags=re.UNICODE))
    tokens = max(1, round(len(content) / 4))
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            charged_tokens = charge_project_rag(
                cursor, client_id=client_id, user_id=int(session.get('user_id') or 0), project_id=project_id,
                tokens=tokens, stage='indexacao', idempotency_key='workspace-rag-index:' + uuid4().hex,
            )
            cursor.execute(
                """INSERT INTO cadu_ci_projeto_arquivos
                       (projeto_id, id_cliente, criado_por, nome_arquivo, mime, tamanho,
                        storage_path, doc_form, indexing_status, word_count, tokens, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s,
                            'text_model', 'completed', %s, %s, NOW(), NOW())
                 RETURNING id""",
                (project_id, client_id, session.get('user_id'), title, mime, size,
                 storage_path, word_count, charged_tokens),
            )
            file_id = cursor.fetchone()['id']
            for order, chunk in enumerate(source_chunks):
                cursor.execute(
                    """INSERT INTO cadu_ci_chunks
                           (projeto_id, id_cliente, arquivo_id, ordem, titulo, conteudo,
                            metadata, embedding, embedding_norm, dim, modelo, tokens, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, '[]'::jsonb,
                                0, 0, 'workspace-text', %s, NOW())""",
                    (project_id, client_id, file_id, order, title, chunk,
                     json.dumps({'source': source, 'arquivo_id': file_id}),
                     max(1, round(len(chunk) / 4))),
                )
            cursor.execute(
                """UPDATE cadu_ci_projetos
                      SET total_arquivos = COALESCE(total_arquivos, 0) + 1, updated_at = NOW()
                    WHERE id = %s AND id_cliente = %s""",
                (project_id, client_id),
            )
        connection.commit()
        return int(file_id)
    except Exception:
        connection.rollback()
        raise


def _project_source(client_id: int, project_id: str, source_id: int) -> Optional[dict]:
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, nome_arquivo, mime, tamanho, storage_path, indexing_status,
                          word_count, tokens, erro_msg, created_at, updated_at
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
    project['brand_guidance'] = [_project_brand_guidance(brand) for brand in project['brands']]
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, nome_arquivo, mime, tamanho, storage_path, doc_form, indexing_status,
                          word_count, tokens, erro_msg, created_at
                     FROM cadu_ci_projeto_arquivos
                    WHERE projeto_id = %s AND id_cliente = %s ORDER BY created_at DESC""",
                (project_id, client_id),
            )
            project['files'] = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """SELECT id, titulo, total_mensagens, updated_at FROM cadu_conversations
                    WHERE projeto_id = %s AND id_cliente = %s ORDER BY updated_at DESC LIMIT 8""",
                (project_id, client_id),
            )
            project['conversations'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        project['files'] = []
        project['conversations'] = []
    # SmartDocs and visual references were part of the original dossier.  They
    # live in optional legacy tables, so each lookup degrades independently.
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, titulo, tipo, status, updated_at
                     FROM cadu_artifacts
                    WHERE projeto_id = %s AND id_cliente = %s
                 ORDER BY updated_at DESC LIMIT 12""",
                (project_id, client_id),
            )
            project['smartdocs'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        project['smartdocs'] = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, title, source, mime, file_path, created_at
                     FROM cadu_docs_client_images
                    WHERE projeto_id = %s AND id_cliente = %s AND ativo = true
                 ORDER BY created_at DESC LIMIT 12""",
                (project_id, client_id),
            )
            project['images'] = [dict(row) for row in cursor.fetchall()]
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
    project['context_health'] = _project_context_health(project)
    project['activity'] = _project_recent_activity(project)
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
        description="O ambiente Cadu que reúne conta, projetos, contexto, créditos e acesso aos produtos da organização.",
        hero=secrets.choice(WORKSPACE_PUBLIC_HEROES),
    )


PUBLIC_PAGES = {
    "como-funciona": {
        "title": "Como funciona",
        "description": "Entenda como o Cadu Workspace preserva o contexto entre projetos, pessoas e produtos.",
        "lead": "Um ponto de partida para o time organizar o trabalho antes de planejar, criar ou conectar dados.",
    },
    "planos": {
        "title": "Planos",
        "description": "Conheça a estrutura de planos e créditos do ecossistema Cadu.",
        "lead": "A mesma conta atende todo o time no Cadu. Capacidade, créditos e número de pessoas variam por plano.",
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
    {"image": "public-people-v2.jpg", "tone": "light"},
    {"image": "public-people-v3.jpg", "tone": "dark"},
)
WORKSPACE_APP_HEROES = (
    {"image": "app-team-v1.jpg", "tone": "dark"},
    {"image": "app-team-v2.jpg", "tone": "dark"},
    {"image": "app-team-v3.jpg", "tone": "dark"},
)


@bp.get("/entrada/<product>")
def product_entry(product):
    product = str(product or "").lower()
    item = PRODUCT_ENTRIES.get(product)
    if not item:
        abort(404)
    entry = dict(zip(("name", "eyebrow", "title", "description"), item))
    entry["icon_family"] = "workspace" if product == "cadu" else product
    # A página pública do Cadu também mora no Workspace: o domínio cadu.* é a
    # aplicação PHP autenticada e não deve receber links para uma rota Flask.
    entry_host = "workspace" if product == "cadu" else product
    return render_template("cadu_workspace/product_entry.html", product=product, entry=entry, canonical=product_url(entry_host, f"/entrada/{product}"))


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
    projects = _workspace_projects(client_id)
    brands = _workspace_brands(client_id)
    customizations = list_customizations(client_id=client_id)
    sections = (
        ("Usuários e equipe", "Pessoas, convites e permissões da organização.", url_for("cadu_workspace.account_page", section="equipe"), "Workspace"),
        ("Planos", "Plano contratado, limites e recursos habilitados.", url_for("cadu_workspace.account_page", section="planos"), "Workspace"),
        ("Créditos", "Saldo, consumo e histórico compartilhado entre produtos.", url_for("cadu_workspace.account_page", section="creditos"), "Workspace"),
        ("Financeiro", "Faturas, pagamentos e dados de cobrança.", url_for("cadu_workspace.account_page", section="faturamento"), "Conta"),
        ("Integrações", "Conexões autorizadas para os produtos da organização.", url_for("cadu_workspace.integrations"), "Workspace"),
        ("Ajuda", "Orientação de uso e canais de atendimento.", url_for("cadu_workspace.public_page", page="ajuda"), "Suporte"),
    )
    return render_template(
        "cadu_workspace/index.html", sections=sections, projects=projects, brands=brands,
        customizations=customizations, credit=credit_position(client_id), hero=secrets.choice(WORKSPACE_APP_HEROES),
        data_health=_workspace_data_health(),
    )


@bp.get("/workspace/app")
@login_required
def legacy_dashboard_url():
    """Preserve favoritos antigos e exponha a entrada curta do produto."""
    return redirect(url_for("cadu_workspace.dashboard"), code=308)


@bp.get('/workspace/app/conversas')
@login_required
def conversations():
    """Dedicated Cadu surface; message delivery remains in the shared guarded API."""
    return render_template('cadu_workspace/conversations.html')


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
    return render_template('cadu_workspace/brands.html', brands=records, query=query, filter_name=filter_name)


@bp.get('/marcas')
@login_required
def clean_brands():
    return brands()


@bp.get('/docs')
@login_required
def documents():
    client_id = int(session.get('cliente_id') or 0)
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id, titulo, tipo, status, updated_at FROM cadu_artifacts WHERE id_cliente = %s ORDER BY updated_at DESC LIMIT 60", (client_id,))
            records = [dict(row) for row in cursor.fetchall()]
    except Exception:
        records = []
    return render_template('cadu_workspace/documents.html', documents=records)


@bp.post('/workspace/app/marcas')
@login_required
def create_brand():
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    data = _workspace_brand_form()
    if data['website_url'] and urlparse(data['website_url']).scheme not in {'http', 'https'}:
        abort(400, description='Informe um site iniciado por http:// ou https://.')
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
    return render_template('cadu_workspace/projects.html', projects=_workspace_projects(client_id, query, status), query=query,
                           status=status if status in {'ativos', 'arquivados', 'todos'} else 'ativos')


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
        return redirect(url_for('cadu_workspace.clean_project_detail', project_id=project_id), code=308)
    client_id = int(session.get('cliente_id') or 0)
    project = _workspace_project(client_id, project_id)
    if not project:
        abort(404)
    _remember_workspace_project(project_id)
    return render_template('cadu_workspace/project_detail.html', project=project, brands=_workspace_brands(client_id),
                           rag_credit=credit_position(client_id),
                           can_manage_brand=session.get('user_type') in {'admin', 'superadmin'})


@bp.get('/projetos/<project_id>')
@login_required
def clean_project_detail(project_id):
    return project_detail(project_id)


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
    wanted = {next((value for value in request.form.getlist('brand_ids') if value in valid_ids), '')}
    wanted.discard('')
    project_ref = f'ci:{project_id}'
    try:
        existing = {str(item.get('brand_ref') or '') for item in family_repository.project_brand_links(client_id)
                    if item.get('project_ref') == project_ref and str(item.get('brand_ref') or '').startswith('studio:')}
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
    website_url = (request.form.get('website_url') or '').strip()[:2000]
    if len(name) < 2:
        abort(400, description='Informe o nome da marca.')
    if not re.match(r'^https?://', website_url, re.I):
        abort(400, description='Informe o site oficial iniciado por http:// ou https://.')
    job_id = uuid4().hex
    metadata = {'review_pack': {
        'job_id': job_id, 'status': 'queued', 'stage': 'queued', 'index': 0, 'total': 4,
        'message': 'A importação entrou na fila.', 'error': '',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'input': {'website_url': website_url, 'has_images': False}, 'analysis': {}, 'reviews': [],
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
    _start_brand_review_job(client_id, int(session.get('user_id') or 0), brand_id, job_id, website_url, [])
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
    try:
        _persist_project_source(
            client_id, project_id, title, content, 'text/markdown',
            len(content.encode('utf-8')), f'workspace://project-notes/{uuid4()}', 'workspace_note',
        )
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
    source = project_sources.validate_upload(uploaded)
    source_key = uuid4().hex
    target = project_sources.private_path(
        _workspace_source_root(), client_id, project_id, source['suffix'], source_key,
    )
    target.write_bytes(source['data'])
    storage_path = target.relative_to(Path(_workspace_source_root())).as_posix()
    try:
        _persist_project_source(
            client_id, project_id, source['name'], source['text'], source['mime'],
            len(source['data']), storage_path, 'workspace_upload',
        )
    except CaduCreditUnavailable as exc:
        target.unlink(missing_ok=True)
        abort(409, description=str(exc))
    except Exception:
        target.unlink(missing_ok=True)
        current_app.logger.exception('Não foi possível registrar arquivo no projeto %s', project_id)
        abort(503, description='Não foi possível adicionar o arquivo agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/fontes/urls')
@login_required
def import_project_url(project_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    try:
        source = project_sources.extract_public_url(request.form.get('url'))
        _persist_project_source(
            client_id, project_id, source['name'], source['text'], source['mime'],
            0, f"workspace-url:{source['url']}", 'workspace_url',
        )
    except HTTPException:
        raise
    except CaduCreditUnavailable as exc:
        abort(409, description=str(exc))
    except ValueError as exc:
        abort(400, description=str(exc))
    except Exception:
        current_app.logger.exception('Não foi possível importar URL no projeto %s', project_id)
        abort(503, description='Não foi possível importar essa página agora. Tente novamente.')
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
    files = [{
        'id': item.get('id'), 'name': item.get('nome_arquivo'),
        'status': item.get('indexing_status'), 'words': item.get('word_count') or 0,
        'error': item.get('erro_msg') or '',
    } for item in project.get('files', [])]
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
    if storage_path.startswith('workspace://'):
        abort(409, description='Notas já ficam disponíveis imediatamente e não precisam de reprocessamento.')
    try:
        if storage_path.startswith('workspace-url:'):
            extracted = project_sources.extract_public_url(storage_path.removeprefix('workspace-url:'))
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
        source_chunks = project_sources.chunks(content)
        if not source_chunks:
            abort(400, description='A fonte não contém texto indexável.')
        connection = get_db()
        with connection.cursor() as cursor:
            charged_tokens = charge_project_rag(
                cursor, client_id=client_id, user_id=int(session.get('user_id') or 0), project_id=project_id,
                tokens=max(1, round(len(content) / 4)), stage='reindexacao',
                idempotency_key='workspace-rag-reindex:' + uuid4().hex,
            )
            cursor.execute(
                'DELETE FROM cadu_ci_chunks WHERE arquivo_id = %s AND projeto_id = %s AND id_cliente = %s',
                (source_id, project_id, client_id),
            )
            for order, chunk in enumerate(source_chunks):
                cursor.execute(
                    """INSERT INTO cadu_ci_chunks
                           (projeto_id, id_cliente, arquivo_id, ordem, titulo, conteudo,
                            metadata, embedding, embedding_norm, dim, modelo, tokens, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, '[]'::jsonb,
                                0, 0, 'workspace-text', %s, NOW())""",
                    (project_id, client_id, source_id, order, source.get('nome_arquivo'), chunk,
                     json.dumps({'source': 'workspace_reprocessed', 'arquivo_id': source_id}),
                     max(1, round(len(chunk) / 4))),
                )
            cursor.execute(
                """UPDATE cadu_ci_projeto_arquivos
                      SET indexing_status = 'completed', erro_msg = NULL, word_count = %s,
                          tokens = %s, updated_at = NOW()
                    WHERE id = %s AND projeto_id = %s AND id_cliente = %s""",
                (len(re.findall(r'\b\w+\b', content, flags=re.UNICODE)),
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
            cursor.execute(
                """SELECT titulo, LEFT(conteudo, 900) AS conteudo,
                          ts_rank_cd(to_tsvector('portuguese', conteudo), plainto_tsquery('portuguese', %s)) AS score
                     FROM cadu_ci_chunks
                    WHERE projeto_id = %s AND id_cliente = %s
                      AND to_tsvector('portuguese', conteudo) @@ plainto_tsquery('portuguese', %s)
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


@bp.post('/workspace/api/projetos/<project_id>/documentos')
@login_required
def create_project_document(project_id):
    """Persist a user-approved Cadu result in the project that owns its context.

    This is deliberately a Workspace action, not a Dify database tool: the
    browser session binds both the user and project, so a model cannot write a
    plan into another client's project by changing an identifier in a prompt.
    """
    if not _workspace_api_csrf():
        return jsonify({'error': 'Atualize a página e tente novamente.'}), 403
    client_id = int(session.get('cliente_id') or 0)
    _editable_workspace_project(client_id, project_id)
    payload = request.get_json(silent=True) or {}
    title = ' '.join(str(payload.get('title') or 'Plano Cadu').split())[:255]
    content = str(payload.get('content') or '').strip()
    if len(content) < 20:
        return jsonify({'error': 'O plano precisa ter ao menos 20 caracteres.'}), 400
    if len(content) > 500000:
        return jsonify({'error': 'O plano excede o limite de 500.000 caracteres.'}), 400
    try:
        from ..cadu_planner import docs
        document = docs.create_document(
            client_id, int(session['user_id']),
            {'title': title, 'type': 'plano', 'html': docs.markdown_to_safe_html(content), 'project_id': project_id},
        )
        return jsonify({'success': True, 'document': {
            key: document.get(key) for key in ('id', 'title', 'type', 'status', 'updated_at')
        }}), 201
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível salvar documento no projeto %s', project_id)
        return jsonify({'error': 'Não foi possível salvar o plano no projeto agora.'}), 503


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
    can_manage_brand = session.get('user_type') in {'admin', 'superadmin'}
    studio_base = product_url('studio', '/studio/modelagem-criativos')
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
    if data['website_url'] and urlparse(data['website_url']).scheme not in {'http', 'https'}:
        abort(400, description='Informe um site iniciado por http:// ou https://.')
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
        return jsonify({'ok': True, 'brand_id': brand_id, 'saved_at': datetime.utcnow().isoformat() + 'Z'})
    return redirect(url_for('cadu_workspace.brand_detail', brand_id=brand_id), code=303)


@bp.post('/workspace/app/marcas/<int:brand_id>/ativos')
@login_required
def upload_brand_assets(brand_id):
    if not _workspace_api_csrf():
        abort(403, description='Atualize a página e tente novamente.')
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_brand(client_id, brand_id):
        abort(404)
    files = request.files.getlist('images')
    if not any(item and item.filename for item in files):
        abort(400, description='Escolha ao menos uma imagem de marca.')
    role = request.form.get('role') or 'reference'
    try:
        from ..creative_modeling_service import CreativeModelingService
        CreativeModelingService().upload_client_brand_assets(
            brand_id, files, request.form.get('primary_logo') == 'true', role,
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
    website_url = (request.form.get('website_url') or brand.get('website_url') or '').strip()[:2000]
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
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'input': {'website_url': website_url, 'has_images': bool(image_payload)},
            'analysis': {},
            'reviews': [],
        }
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cx_clients
                      SET analysis_metadata = %s::jsonb,
                          updated_at = NOW()
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
        'review_count': len(pack.get('reviews') or []), 'updated_at': pack.get('updated_at'),
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
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'input': {'website_url': website_url, 'has_images': False}, 'analysis': checkpoint, 'reviews': [],
    }
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cx_clients SET analysis_metadata = %s::jsonb, updated_at = NOW()
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
        'approved_at': datetime.utcnow().isoformat() + 'Z',
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


@bp.get("/workspace/app/<section>")
@login_required
def account_page(section):
    aliases = {
        "conta": "perfil", "perfil": "perfil", "organizacao": "organizacao",
        "usuarios": "equipe", "equipe": "equipe", "planos": "planos", "creditos": "creditos",
        "financeiro": "faturamento", "faturamento": "faturamento",
    }
    section = aliases.get(section)
    if section is None:
        abort(404)
    client_id = int(session.get("cliente_id") or 0)
    account = _php_account_data(client_id)
    if section in {"perfil", "organizacao"}:
        account.update(_workspace_settings_data(client_id, int(session.get("user_id") or 0)))
    if section == 'faturamento':
        account.update(_workspace_billing_data(client_id))
    return render_template(
        "cadu_workspace/account.html", section=section,
        account=account,
    )


@bp.get('/workspace/app/integracoes')
@login_required
def integrations():
    client_id = int(session.get('cliente_id') or 0)
    organization_id = int(session.get('organization_id') or client_id)
    return render_template(
        'cadu_workspace/integrations.html',
        integration_data=_workspace_integration_data(client_id, organization_id),
    )


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
    return redirect(url_for('cadu_workspace.account_page', section='organizacao', saved='1'), code=303)


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
        result = send_invite_email(email, invite['invite_token'], company_name,
                                   session.get('user_name') or 'Equipe', invite['expires_at'])
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
        result = send_invite_email(invite['email'], invite['invite_token'], company_name,
                                   session.get('user_name') or 'Equipe', invite['expires_at'])
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
