"""Biblioteca privada de áudio e exportação de clipes do estúdio."""
from __future__ import annotations

import hashlib
from array import array
import logging
import json
import math
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from flask import abort, current_app, jsonify, render_template, request, session, send_file, url_for

from .http import studio_http as _http
from .studio_auth import studio_or_admin_required_api
from .studio_csrf import studio_csrf_required
from .storage import media_root
from .transcode import ffmpeg_available
from ..creative_modeling_storage import ClientLogoStorage

logger = logging.getLogger(__name__)

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio-export")
_SLOTS = threading.BoundedSemaphore(2)
_MAX_UPLOAD = 25 * 1024 * 1024
_ID = re.compile(r"^[a-f0-9]{32}$")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_PALETTE_ANALYST_MODEL = "openai/gpt-5-nano"


def _logo_identity_suggestion(brand_context, text_callable):
    """Extract a reviewable palette and type direction from an official logo.

    The model is deliberately not asked to name a proprietary typeface from
    pixels. It can only return an observable type classification; the team
    later assigns the approved font family in Marcas.
    """
    brand = brand_context if isinstance(brand_context, dict) else {}
    assets = brand.get("assets") if isinstance(brand.get("assets"), dict) else {}
    logo_url = str(brand.get("logo_url") or next(iter(assets.get("logo") or []), "")).strip()
    if not logo_url:
        raise ValueError("Adicione uma logo antes de definir as cores da marca.")
    response = text_callable(
        [
            {
                "role": "system",
                "content": (
                    "Extract a conservative visual identity proposal from the supplied official brand logo. "
                    "Return JSON only in the form {\"colors\":[\"#RRGGBB\",...],\"fonts\":[{\"role\":\"display|body\",\"classification\":\"short observable description\",\"confidence\":0.0}]}. "
                    "Return one to five distinct, visible logo colors. If the logo is monochrome or has only two colors, return only those colors. Ignore transparency, "
                    "near-white canvas backgrounds and generic shadows. Do not invent colors. "
                    "For typography, describe only what is visibly supported (such as geometric sans, humanist sans, high-contrast serif). "
                    "Never guess, name or claim a proprietary/licensed font family."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Official brand logo. Extract its visible colors and a cautious typographic direction."},
                    {"type": "image_url", "image_url": {"url": logo_url}},
                ],
            },
        ],
        model=_PALETTE_ANALYST_MODEL,
        max_tokens=220,
        response_format={"type": "json_object"},
        reasoning={"effort": "low"},
    )
    raw = response.get("message", {}).get("content") if isinstance(response, dict) else {}
    if isinstance(raw, str):
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        try:
            raw = json.loads(clean)
        except json.JSONDecodeError as exc:
            raise ValueError("Não foi possível identificar as cores da logo.") from exc
    values = raw.get("colors") if isinstance(raw, dict) else []
    colors = []
    for value in values[:6] if isinstance(values, list) else []:
        color = str(value or "").strip().upper()
        if _HEX_COLOR.fullmatch(color) and color not in colors:
            colors.append(color)
    if not colors:
        raise ValueError("Não foi possível identificar uma cor confiável nesta logo.")
    fonts = []
    values = raw.get("fonts") if isinstance(raw, dict) else []
    for item in values[:3] if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        classification = str(item.get("classification") or "").strip()[:100]
        role = str(item.get("role") or "body").strip().lower()
        if not classification or role not in {"display", "body", "accent", "legal", "ui"}:
            continue
        try:
            confidence = max(0.0, min(float(item.get("confidence", 0.55)), 1.0))
        except (TypeError, ValueError):
            confidence = 0.55
        fonts.append({"family": "", "classification": classification, "role": role, "source": "logo_analysis", "confidence": confidence})
    return {"colors": colors[:5], "fonts": fonts}, response


def _logo_palette_suggestion(brand_context, text_callable):
    """Backward-compatible palette helper used by existing Studio callers."""
    identity, response = _logo_identity_suggestion(brand_context, text_callable)
    return identity["colors"], response


def _api_root():
    studio_host = urlparse(str(current_app.config.get("STUDIO_URL") or "")).hostname
    return "/studio/api" if studio_host and request.host.split(":", 1)[0].lower() == studio_host.lower() else "/parametros/api"


def number(raw, default, low, high):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value)) if math.isfinite(value) else default


def normalize_edit(raw):
    from .studio_layers import normalize_layers
    data = raw if isinstance(raw, dict) else {}
    return {
        "layers": normalize_layers(data.get("layers")),
        "output_ratio": data.get("output_ratio") if data.get("output_ratio") in {"16:9","9:16","1:1","4:5","3:4","4:3","21:9"} else "",
        "start": number(data.get("start"), 0, 0, 300),
        "end": number(data.get("end"), 0, 0, 300),
        "speed": number(data.get("speed"), 1, .25, 4),
        "original_volume": number(data.get("original_volume"), 1, 0, 1),
        "sound_id": str(data.get("sound_id") or "")[:32],
        "sound_volume": number(data.get("sound_volume"), .35, 0, 1),
        "sound_offset": number(data.get("sound_offset"), 0, 0, 600),
        "fade_in": number(data.get("fade_in"), 0, 0, 10),
        "fade_out": number(data.get("fade_out"), 0, 0, 10),
        "loop": data.get("loop") is True,
        "video_fade_in": number(data.get("video_fade_in"), 0, 0, 10),
        "video_fade_out": number(data.get("video_fade_out"), 0, 0, 10),
        "grayscale": data.get("grayscale") is True,
        "flip": data.get("flip") is True,
    }


def probe(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,mp3,wav,ogg,flac,aac,matroska,webm", "-show_entries", "format=duration:stream=codec_type",
        "-of", "json", str(path),
    ], capture_output=True, text=True, check=True, timeout=20)
    data = json.loads(result.stdout)
    duration = number(data.get("format", {}).get("duration"), 0, 0, 36000)
    return duration, {row.get("codec_type") for row in data.get("streams", [])}


def waveform_levels(path):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '1000', '-f', 's16le', '-'], capture_output=True, check=True, timeout=30)
    samples = array('h')
    samples.frombytes(result.stdout)
    if not samples:
        return {'overview':[],'medium':[],'detail':[]}
    def peaks(count):
        step=max(1,(len(samples)+count-1)//count)
        values=[max(abs(value) for value in samples[i:i+step])/32768 for i in range(0,len(samples),step)][:count]
        scale=max(values) or 1
        return [round(value/scale,3) for value in values]
    return {'overview':peaks(96),'medium':peaks(384),'detail':peaks(1536)}


def waveform(path):
    return waveform_levels(path)['overview']


def _write(path, data):
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False))
    temporary.replace(path)


def _scope(client):
    if not str(client or "").isdigit() or int(client) <= 0:
        raise ValueError("Escolha uma marca para abrir a biblioteca de sons.")
    # Same authentication boundary as the existing admin-only studio; files are brand scoped.
    key = hashlib.sha256(f"client:{int(client)}".encode()).hexdigest()[:32]
    root = media_root() / "studio" / key
    root.mkdir(parents=True, exist_ok=True)
    return root


def _assert_project_brand_access(project_id, client_id):
    """Bind every project-led creation write to the signed-in tenant.

    ``client_id`` is deliberately treated as untrusted input on Studio APIs.
    The project/brand link is the durable permission fact for a Studio account;
    an administrator without a tenant session keeps the legacy back-office
    access path.
    """
    project_key = str(project_id or "").strip()
    if not project_key:
        raise ValueError('Selecione um projeto antes de criar uma imagem.')
    try:
        account_id = int(session.get('cliente_id') or 0)
        brand_id = int(client_id)
    except (TypeError, ValueError):
        raise ValueError('Projeto não encontrado nesta marca.')
    if not account_id:
        return
    from .project_contexts import linked_project_contexts
    allowed = {
        str(item.get('id')): int(item.get('client_id'))
        for item in linked_project_contexts(account_id)
        if item.get('id') is not None and item.get('client_id') is not None
    }
    if allowed.get(project_key) != brand_id:
        raise ValueError('Projeto não encontrado nesta marca.')


def _studio_reference_masks():
    """Return the shared low-resolution composition references for Studio V2."""
    references = [
        {
            'id': f'feed-mask-{index:02d}',
            'label': f'Feed · composição {index:02d}',
            'role': 'composition',
            'group': 'feed-4x5',
            'concept': 'composition-mask',
            'format': '4:5',
            'width': 1080,
            'height': 1350,
            'url': url_for(
                'static',
                filename=f'images/cadu/studio/references/feed/feed-mask-{index:02d}.webp',
            ),
        }
        for index in range(1, 11)
    ]
    references.extend(
        {
            'id': f'square-mask-{index:02d}',
            'label': f'300×300 · composição {index:02d}',
            'role': 'composition',
            'group': 'display-300x300',
            'concept': concept,
            'format': '1:1',
            'width': 300,
            'height': 300,
            'url': url_for(
                'static',
                filename=f'images/cadu/studio/references/square-300x300/square-mask-{index:02d}.webp',
            ),
        }
        for index, concept in enumerate((
            'product-hero',
            'institutional-full-bleed',
            'photo-text-split',
            'editorial-footer',
            'service-contact',
            'headline-overlay',
        ), start=1)
    )
    references.append(
        {
            'id': 'iab-300x250-mask-01',
            'label': '300×250 · composição 01',
            'role': 'composition',
            'group': 'iab-300x250',
            'concept': 'institutional-lifestyle',
            'format': '6:5',
            'width': 300,
            'height': 250,
            'url': url_for(
                'static',
                filename='images/cadu/studio/references/iab-300x250/iab-300x250-mask-01.webp',
            ),
        }
    )
    return references


def _record(root, ident, kind):
    if not _ID.fullmatch(str(ident or "")):
        raise ValueError("Arquivo inválido.")
    path = root / f"{kind}-{ident}.json"
    if not path.is_file():
        raise ValueError("Arquivo não encontrado nesta marca.")
    return path, json.loads(path.read_text())


def register_studio_routes(blueprint):
    from .studio_media import register
    register(blueprint)
    blueprint.add_url_rule('/api/format-lab/studio/agent/plan', view_func=studio_agent_plan, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/prompt/optimize', view_func=studio_prompt_optimize, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/create/directions', view_func=studio_create_directions, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/create/image', view_func=studio_create_image, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/csrf', view_func=studio_csrf, methods=['GET'])
    blueprint.add_url_rule('/api/format-lab/studio/agent/narration', view_func=studio_agent_narration, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/projects', view_func=studio_projects, methods=['GET', 'POST'])
    blueprint.add_url_rule('/api/format-lab/studio/library-sessions', view_func=studio_library_sessions, methods=['GET'])
    blueprint.add_url_rule('/api/format-lab/studio/reference-uploads', view_func=studio_reference_uploads, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/brand-palette/suggest', view_func=studio_brand_palette_suggest, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/brand-palette', view_func=studio_brand_palette, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/personal-assets', view_func=studio_personal_assets, methods=['DELETE'])
    blueprint.add_url_rule('/api/format-lab/studio/project-contexts', view_func=studio_project_contexts, methods=['GET'])
    blueprint.add_url_rule('/api/format-lab/studio/projects/<ident>', view_func=studio_project, methods=['GET', 'POST'])
    blueprint.add_url_rule('/api/format-lab/studio/projects/<ident>/creation-history', view_func=studio_project_creation_history, methods=['GET'])
    blueprint.add_url_rule('/api/format-lab/studio/projects/<ident>/directions/<direction_id>/select', view_func=studio_project_select_direction, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/projects/<ident>/items', view_func=studio_project_items, methods=['POST', 'DELETE'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions', view_func=studio_sessions, methods=['GET', 'POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>', view_func=studio_session, methods=['GET', 'PATCH'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/accept', view_func=studio_session_accept, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/attach-project', view_func=studio_session_attach_project, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/handoff', view_func=studio_session_handoff, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/continue', view_func=studio_session_continue, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/finalize', view_func=studio_session_finalize, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/leave', view_func=studio_session_leave, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/discard', view_func=studio_session_discard, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/restore', view_func=studio_session_restore, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sessions/<ident>/share', view_func=studio_session_share, methods=['POST'])
    blueprint.add_url_rule('/mesa/<token>', view_func=studio_public_canvas, methods=['GET'])
    blueprint.add_url_rule('/api/format-lab/studio/capabilities', view_func=capabilities)
    blueprint.add_url_rule('/api/format-lab/studio/sounds', view_func=sounds, methods=['GET', 'POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sounds/<ident>', view_func=sound_content)
    blueprint.add_url_rule('/api/format-lab/studio/exports', view_func=export_clip, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/exports/<ident>', view_func=export_status)
    blueprint.add_url_rule('/api/format-lab/studio/exports/<ident>/content', view_func=export_content)


@studio_or_admin_required_api
def studio_csrf():
    """Return the current Studio token without exposing it in cacheable HTML."""
    from .studio_csrf import get_or_create_token
    return jsonify({'success': True, 'data': {'token': get_or_create_token()}}), 200, {
        'Cache-Control': 'no-store, private',
    }


@studio_or_admin_required_api
@studio_csrf_required
def studio_agent_plan():
    from ..cadu_credit_connector import CaduCreditConnector
    from ..services.cadu_ai_connector import CaduAIConnector
    from .studio_agent import plan_request
    execute, json_body, ok, service = _http()

    def run():
        data = json_body()
        client_id = data.get('client_id')
        _scope(client_id)
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para usar o agente do Studio.')
        modeling = service()
        payer = modeling._credits_crm_id(client_id) or int(client_id)
        payload_fingerprint = json.dumps({
            'client_id': int(client_id),
            'message': data.get('message'),
            'context': data.get('context'),
        }, ensure_ascii=False, sort_keys=True, default=str)
        request_key = str(data.get('request_id') or hashlib.sha256(
            payload_fingerprint.encode('utf-8')
        ).hexdigest())[:160]
        connector = CaduAIConnector(CaduCreditConnector(modeling.credit_ledger))

        def metered_plan(messages, **options):
            return connector.complete(
                messages,
                client_id=payer,
                user_id=user_id,
                idempotency_key=f'studio:agent-plan:{request_key}',
                app='Cadu Studio',
                stage='video_agent_plan',
                estimated_tokens=900,
                metadata={
                    'studio_client_id': int(client_id),
                    'request_id': request_key,
                    'billing_class': 'agent',
                },
                **options,
            )

        return ok(plan_request(
            data.get('message'), data.get('context'), text_callable=metered_plan
        ))

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_prompt_optimize():
    """Compile a user request for the image model without changing literals."""
    from ..services.openrouter_service import chat_completion
    from .studio_prompt import optimize_prompt
    execute, json_body, ok, service = _http()

    def run():
        data = json_body()
        quick_mode = not data.get('client_id')
        modeling = service()
        client_id = _quick_creative_client(modeling) if quick_mode else data.get('client_id')
        if not session.get('user_id'):
            raise ValueError('Entre novamente para otimizar o pedido.')
        _scope(client_id)
        from ..cadu_credit_connector import CaduCreditConnector, CreditActor
        payer = modeling._credits_crm_id(client_id) or int(client_id)
        CaduCreditConnector(modeling.credit_ledger).authorize(
            CreditActor.from_values(payer, session.get('user_id')), 1100
        )
        provider_calls = []

        def metered_prompt(*args, **kwargs):
            response = chat_completion(*args, **kwargs)
            provider_calls.append(response)
            return response

        result = optimize_prompt(
            data.get('prompt'), mode=data.get('mode'), context=data.get('context'),
            text_callable=metered_prompt,
        )
        if provider_calls:
            request_key = str(data.get('request_id') or hashlib.sha256(
                f"{data.get('studio_session_id')}:{data.get('mode')}:{data.get('prompt')}".encode('utf-8')
            ).hexdigest())[:160]
            charged = modeling._charge_studio_call(
                client_id=client_id, user_id=session.get('user_id'),
                idempotency_key=f"studio:prompt-optimize:{request_key}",
                stage="prompt_optimization", provider_result=provider_calls[-1],
                fallback_cost=modeling._estimate("prompt"), media=False,
                metadata={
                    "studio_session_id": str(data.get('studio_session_id') or ''),
                    "studio_root_session_id": str(
                        data.get('studio_root_session_id') or data.get('studio_session_id') or ''
                    ),
                },
            ) or {}
            result['charged_credits'] = int(charged.get('tokens_cobrados') or 0)
        return ok(result)

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_create_directions():
    from ..services.openrouter_service import chat_completion
    from . import studio_create
    execute, json_body, ok, service = _http()

    def run():
        data = json_body()
        quick_mode = data.get('quick_mode') is True
        # A quick creation has no creative brand or project, but it is still
        # billable.  Its tenant must therefore come from the authenticated
        # session, never from an arbitrary browser-provided client id.
        modeling = service()
        client_id = _quick_creative_client(modeling) if quick_mode else data.get('client_id')
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para gerar direções.')
        if quick_mode and not client_id:
            raise ValueError('Não foi possível identificar a conta de créditos desta sessão. Atualize a página e tente novamente.')
        _scope(client_id)
        count = max(1, min(int(data.get('count') or 1), 5))
        project_id = str(data.get('project_id') or '')
        if not quick_mode:
            _assert_project_brand_access(project_id, client_id)
        if not quick_mode:
            from ..creative_format_lab.brand_context import build_brand_context, select_brand_logo
            project_context = data.get('context') if isinstance(data.get('context'), dict) else {}
            project_context['brand_context'] = select_brand_logo(
                build_brand_context(modeling.get_client(client_id)), data.get('selected_logo_id'),
            )
            project_context['project_id'] = project_id
            data['context'] = project_context
        # The balance gate occurs before the provider receives the request.
        # Use the same image contract as the director: selected references plus
        # the official logo, limited to three visual inputs.
        estimate_context = studio_create.clean_context(data.get('context'), count)
        reference_count = len(estimate_context.get('references') or [])
        studio_create.assert_available(client_id, user_id, count, reference_count)
        history = _creation_history()
        run_id = history.start(project_id, client_id, user_id, data.get('prompt'), data.get('context'), count) if history and project_id else None
        try:
            if history and project_id:
                history.add_references(project_id, client_id, user_id, data.get('references'))
            result, provider = studio_create.create(data, chat_completion)
            charged, remaining = studio_create.charge(
                provider, int(client_id), int(user_id), result['count'], project_id, run_id,
                reference_count=reference_count,
                studio_session_id=data.get('studio_session_id'),
                studio_root_session_id=data.get('studio_root_session_id'),
            )
        except Exception as error:
            if history and project_id:
                history.fail(run_id, project_id, client_id, str(error))
            raise
        if history and project_id:
            try:
                history.complete(run_id, project_id, client_id, user_id, result, charged)
            except Exception:
                # A successful provider call and a durable credit charge must
                # not be presented as a failed creative generation. The run is
                # kept pending so it can be reconciled without a second debit.
                logger.exception('Studio direction history completion failed for %s', run_id)
                result['history_sync_pending'] = True
        result.update({'charged_credits': charged, 'remaining_credits': remaining})
        # Provider/model details are internal billing and audit metadata, not
        # part of the Studio's user-facing contract.
        result.pop('provider', None)
        result.pop('model', None)
        return ok(result)

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_create_image():
    from . import studio_create
    execute, json_body, ok, service = _http()

    def run():
        data = json_body()
        direction_approved = data.get('direction_approved')
        direction_approved = direction_approved is True or direction_approved == 1 or str(direction_approved).lower() in {'1', 'true'}
        if data.get('studio_v2') is True and not direction_approved:
            raise ValueError('Revise e aprove a direção antes de gerar a imagem.')
        quick_mode = data.get('quick_mode') is True
        modeling = service()
        client_id = _quick_creative_client(modeling) if quick_mode else data.get('client_id')
        user_id = session.get('user_id')
        if not client_id:
            raise ValueError('Não foi possível identificar a conta de créditos desta sessão.')
        if not user_id:
            raise ValueError('Entre novamente para gerar a imagem.')
        _scope(client_id)
        project_id = str(data.get('project_id') or '')
        if not quick_mode:
            _assert_project_brand_access(project_id, client_id)
            # Rehydrate identity server-side. The browser only carries display
            # metadata and must never decide whether a brand asset is usable.
            from ..creative_format_lab.brand_context import build_brand_context, select_brand_logo
            data['brand_context'] = select_brand_logo(
                build_brand_context(modeling.get_client(client_id)), data.get('selected_logo_id'),
            )
        request_id = studio_create.image_request_id(data)
        data['request_id'] = request_id
        request_hash = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        studio_phase = 'history_claim'
        try:
            history = _creation_history()
        except Exception:
            if not quick_mode:
                raise
            logger.exception('Studio quick image history unavailable')
            history = None
        claim = None
        if history:
            try:
                claim = history.claim_image(request_id, request_hash, client_id, user_id, project_id, data.get('prompt'))
            except Exception:
                # A quick creation is still a valid personal generation when
                # the optional timeline table is temporarily unavailable. Do
                # not turn a successful provider call into a generic 500 just
                # because the shelf cannot be synchronized. Project-bound
                # generations remain strict because their project item is part
                # of the requested contract.
                if not quick_mode:
                    logger.exception('Studio image history claim failed')
                    raise
                logger.exception('Studio quick image history claim unavailable')
                try:
                    history.connection.rollback()
                except Exception:
                    logger.exception('Studio quick image history rollback failed')
                history = None
            if claim:
                if claim['state'] == 'pending':
                    raise ValueError('Esta geração já está em andamento. Aguarde alguns segundos e tente novamente.')
                if claim['state'] == 'completed':
                    result = dict(claim.get('result') or {})
                    result['replayed'] = True
                else:
                    result = None
            else:
                result = None
        else:
            result = None

        if result is None:
            try:
                studio_phase = 'image_provider'
                result = studio_create.create_image(data, modeling, int(client_id), int(user_id))
            except Exception as error:
                if not getattr(error, 'studio_phase', ''):
                    setattr(error, 'studio_phase', studio_phase)
                logger.exception(
                    'Studio image failed request_id=%s phase=%s client_id=%s user_id=%s error_type=%s',
                    request_id, getattr(error, 'studio_phase', studio_phase), client_id,
                    user_id, type(error).__name__,
                )
                if history:
                    try:
                        history.fail_image(request_id, client_id, str(error))
                    except Exception:
                        # Never replace the original provider/storage/billing
                        # exception with a secondary history-sync failure.
                        logger.exception('Studio image failure could not be recorded for %s', request_id)
                raise

        if project_id and not quick_mode and not result.get('project_item_id'):
            try:
                if history:
                    result['project_item_id'] = history.add_item(
                        project_id, client_id, user_id, 'image',
                        str(data.get('title') or 'Imagem criada no Studio'),
                        result['image_url'], {
                            'prompt': str(data.get('prompt') or '')[:4000],
                            'model': result.get('model'),
                            'masked': result.get('masked', False),
                            'request_id': str(data.get('request_id') or ''),
                        },
                    )
                    result.pop('history_sync_pending', None)
            except Exception:
                logger.exception('Studio image project history sync failed for %s', project_id)
                result['history_sync_pending'] = True
        if quick_mode and history and claim:
            result['asset_id'] = f"personal:{claim['id']}"
        result.setdefault('title', str(data.get('title') or 'Criação rápida'))
        result.setdefault('aspect_ratio', str(data.get('aspect_ratio') or ''))
        result['visibility'] = 'personal' if quick_mode or not project_id else 'project'
        result['owner_only'] = result['visibility'] == 'personal'
        if history:
            try:
                studio_phase = 'history_complete'
                history.complete_image(request_id, client_id, result)
            except Exception:
                # The paid image is already persisted at this point. A history
                # sync failure must not turn a successful generation into a
                # generic 500 or force the user to pay for a retry.
                logger.exception('Studio image history completion failed for %s', request_id)
                result['history_sync_pending'] = True
        result.pop('model', None)
        return ok(result)

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_brand_palette_suggest():
    """Suggest colors from the selected official logo before the user saves them."""
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    from ..creative_format_lab.brand_context import build_brand_context, select_brand_logo
    from ..services.openrouter_service import chat_completion
    execute, json_body, ok, service = _http()

    def run():
        data = json_body()
        client_id = data.get('client_id')
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para definir as cores da marca.')
        _scope(client_id)
        _assert_project_brand_access(data.get('project_id'), client_id)
        modeling = service()
        brand_context = select_brand_logo(
            build_brand_context(modeling.get_client(client_id)), data.get('selected_logo_id'),
        )
        existing = [str(color or '').strip().upper() for color in brand_context.get('palette', [])]
        existing = [color for color in existing if _HEX_COLOR.fullmatch(color)]
        existing_fonts = brand_context.get('fonts') if isinstance(brand_context.get('fonts'), list) else []
        has_typography = any(
            isinstance(font, dict) and (str(font.get('family') or '').strip() or str(font.get('classification') or '').strip())
            for font in existing_fonts
        )
        if existing and has_typography:
            return ok({'colors': existing[:5], 'fonts': existing_fonts[:4], 'brand_context': brand_context, 'suggested': False})
        payer = modeling._credits_crm_id(client_id) or int(client_id)
        CaduCreditConnector(modeling.credit_ledger).authorize(
            CreditActor.from_values(payer, user_id), 1200
        )
        identity, provider = _logo_identity_suggestion(brand_context, chat_completion)
        # Existing approved colors are evidence, not a provider suggestion.
        # When only typography is missing, retain them exactly and ask the
        # visual read only for the missing type direction.
        colors = existing[:5] or identity['colors']
        logo_url = str(brand_context.get('logo_url') or '').strip()
        request_key = str(data.get('request_id') or hashlib.sha256(
            f"{client_id}:{brand_context.get('selected_logo_id') or logo_url}".encode('utf-8')
        ).hexdigest())[:160]
        charged = modeling._charge_studio_call(
            client_id=client_id,
            user_id=user_id,
            idempotency_key=f"studio:brand-palette:{request_key}",
            stage='brand_identity_extraction',
            provider_result=provider,
            fallback_cost=modeling._estimate('prompt'),
            media=False,
            metadata={
                'project_id': str(data.get('project_id') or ''),
                'selected_logo_id': str(brand_context.get('selected_logo_id') or ''),
            },
        ) or {}
        return ok({
            'colors': colors,
            'fonts': identity['fonts'],
            'brand_context': brand_context,
            'suggested': True,
            'charged_credits': int(charged.get('tokens_cobrados') or 0),
        })

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_brand_palette():
    """Persist an explicit palette before a brand-led Studio generation.

    This is intentionally a narrow write.  The creation desk can fill the one
    missing piece required for a faithful image without being allowed to
    overwrite the rest of the brand dossier.
    """
    execute, json_body, ok, service = _http()

    def run():
        data = json_body()
        client_id = data.get('client_id')
        _scope(client_id)
        _assert_project_brand_access(data.get('project_id'), client_id)
        raw_colors = data.get('colors') if isinstance(data.get('colors'), list) else []
        colors = []
        for value in raw_colors[:6]:
            color = str(value or '').strip().upper()
            if not _HEX_COLOR.fullmatch(color):
                raise ValueError('Escolha cores no formato hexadecimal #RRGGBB.')
            if color not in colors:
                colors.append(color)
        if not colors:
            raise ValueError('Escolha ao menos uma cor oficial da marca.')
        modeling = service()
        client = modeling.get_client(client_id)
        profile = dict(client.get('brand_profile') or {})
        profile['color_palette'] = [
            {'hex': color, 'name': f'Cor {index + 1}', 'role': 'primary' if index == 0 else 'accent' if index == 1 else 'support', 'source': 'manual', 'confidence': 1.0}
            for index, color in enumerate(colors)
        ]
        raw_fonts = data.get('fonts') if isinstance(data.get('fonts'), list) else []
        fonts = []
        for index, item in enumerate(raw_fonts[:4]):
            source = item if isinstance(item, dict) else {'family': item}
            family = str(source.get('family') or '').strip()[:100]
            classification = str(source.get('classification') or '').strip()[:100]
            role = str(source.get('role') or ('display' if index == 0 else 'body')).strip().lower()
            if not family and not classification:
                continue
            if role not in {'display', 'body', 'accent', 'legal', 'ui'}:
                role = 'body'
            fonts.append({'family': family, 'classification': classification, 'role': role, 'weight': str(source.get('weight') or '').strip()[:32], 'style': str(source.get('style') or '').strip()[:32], 'source': 'manual', 'confidence': 1.0})
        if fonts:
            profile['fonts'] = fonts
        writer = getattr(modeling.repository, 'update_client_brand_profile', None)
        if not callable(writer):
            raise ValueError('Não foi possível salvar a paleta desta marca.')
        writer(int(client_id), profile)
        from ..creative_format_lab.brand_context import build_brand_context, select_brand_logo
        return ok({
            'brand_context': select_brand_logo(
                build_brand_context(modeling.get_client(client_id)), data.get('selected_logo_id'),
            ),
        })

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_agent_narration():
    from ..services.openrouter_service import chat_completion
    from .studio_agent import suggest_narration
    execute, json_body, ok, _ = _http()
    def run():
        data = json_body()
        _scope(data.get('client_id'))
        return ok(suggest_narration(data.get('creative'), data.get('duration'), text_callable=chat_completion))
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_projects():
    from . import studio_projects as repository
    execute, json_body, ok, _ = _http()
    def run():
        store = _project_store(repository)
        if request.method == 'GET':
            client_id = request.args.get('client_id')
            root = _scope(client_id)
            if hasattr(store, 'import_legacy'):
                store.import_legacy(root, client_id)
            return ok({'items': store.listing(client_id, int(request.args.get('offset', 0)))})
        data = json_body()
        client_id = data.get('client_id')
        _scope(client_id)
        return ok(store.save(client_id, data.get('document')))
    return execute(run)


@studio_or_admin_required_api
def studio_library_sessions():
    execute, _, ok, service = _http()

    def selected_client():
        """Resolve a requested Studio project only inside the signed-in account."""
        project_id = str(request.args.get('project_id') or '').strip()
        if not project_id:
            return _quick_creative_client(service())
        try:
            uuid.UUID(project_id)
            account_id = int(session.get('cliente_id') or 0)
        except (TypeError, ValueError) as error:
            raise ValueError('Projeto inválido.') from error
        if not account_id:
            raise ValueError('Não foi possível identificar a sua conta.')

        from ..db import get_db
        from .project_contexts import linked_project_contexts
        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT client_id,document FROM cx_studio_projects WHERE id=%s LIMIT 1",
                (project_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise ValueError('Projeto não encontrado nesta marca.')
        document = row.get('document') if isinstance(row, dict) else row['document']
        document = document if isinstance(document, dict) else {}
        external_id = str(document.get('external_project_id') or '')
        allowed = {
            str(item.get('id')): int(item.get('client_id'))
            for item in linked_project_contexts(account_id)
        }
        client_id = int(row['client_id'])
        if not external_id or allowed.get(external_id) != client_id:
            raise ValueError('Projeto não encontrado nesta marca.')
        requested_client = str(request.args.get('client_id') or '').strip()
        if requested_client and requested_client != str(client_id):
            raise ValueError('A marca não corresponde ao projeto selecionado.')
        return client_id

    def run():
        # Quick creation has no project. In Edit, the selected project is the
        # source of truth for its brand-scoped shelf and reference context.
        client_id = selected_client()
        _scope(client_id)
        history = _creation_history()
        user_id = session.get('user_id')
        personal_assets = history.personal_assets(client_id, user_id) if history and user_id else []
        storage = ClientLogoStorage()
        personal_assets = [asset for asset in personal_assets if not str(asset.get('image_url') or '').startswith('/static/') or storage.absolute_public_path(asset.get('image_url')) is not None]
        return ok({
            'client_id': client_id,
            'items': history.library_sessions(client_id) if history else [],
            'personal_assets': personal_assets,
            'reference_masks': _studio_reference_masks(),
        })
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_reference_uploads():
    """Persist user uploads as private, reusable Studio reference assets."""
    execute, _, ok, service = _http()

    def run():
        project_id = str(request.form.get('project_id') or '').strip() or None
        client_id = request.form.get('client_id') if project_id else _quick_creative_client(service())
        user_id = session.get('user_id')
        _scope(client_id)
        if not user_id:
            raise ValueError('Entre novamente para salvar suas referências.')
        files = [item for item in request.files.getlist('files') if item and item.filename]
        if not files:
            raise ValueError('Selecione ao menos uma imagem.')
        if len(files) > 3:
            raise ValueError('Use no máximo três referências por envio.')
        history = _creation_history()
        if not history:
            raise ValueError('A biblioteca persistente do Studio não está disponível nesta sessão.')
        if project_id:
            try:
                uuid.UUID(project_id)
            except ValueError as error:
                raise ValueError('Projeto inválido.') from error
            with history.connection.cursor() as cursor:
                cursor.execute('SELECT id FROM cx_studio_projects WHERE id=%s AND client_id=%s', (project_id, int(client_id)))
                if not cursor.fetchone():
                    raise ValueError('Projeto não encontrado nesta marca.')
        from ..creative_modeling_storage import CreativeAssetStorage, public_studio_asset_url
        storage = CreativeAssetStorage()
        saved = []
        saved_paths = []
        try:
            for file_storage in files:
                item = storage.save_reference(file_storage)
                asset_path = item.get('asset_path')
                saved_paths.append(asset_path)
                asset_id = history.save_reference_asset(
                    client_id, user_id, project_id, item.get('original_name'),
                    asset_path, asset_path,
                    {'role': 'reference', 'original_name': item.get('original_name'), 'sha256': item.get('sha256')},
                )
                public_url = public_studio_asset_url(asset_path)
                saved.append({
                    'id': f'reference:{asset_id}', 'asset_id': asset_id,
                    # Keep the database path relative, but give the browser and
                    # both AI stages the same fetchable public URL immediately.
                    'url': public_url, 'image_url': public_url,
                    'thumb_url': public_url,
                    'label': item.get('original_name') or 'Referência visual',
                    'role': 'reference', 'visibility': 'personal',
                })
            history.connection.commit()
        except Exception:
            history.connection.rollback()
            for asset_path in saved_paths:
                storage.delete(asset_path)
            raise
        return ok({'items': saved})

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_personal_assets():
    execute, json_body, ok, service = _http()
    def run():
        data = json_body()
        client_id = _quick_creative_client(service())
        _scope(client_id)
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para organizar sua biblioteca.')
        history = _creation_history()
        return ok({'removed': history.trash_personal_assets(client_id, user_id, data.get('ids')) if history else 0})
    return execute(run)


@studio_or_admin_required_api
def studio_project_contexts():
    """Expose Studio's project-to-brand contexts from the shared database."""
    from .project_contexts import linked_project_contexts
    try:
        account_id = int(session.get('cliente_id') or 0)
    except (TypeError, ValueError):
        account_id = 0
    if not account_id:
        return jsonify({'success': False, 'error': 'Não foi possível identificar a sua conta.'}), 400
    from psycopg.types.json import Json
    from ..db import get_db
    modeling = _http()[3]()
    items = []
    db = get_db()
    with db.cursor() as cursor:
        for project in linked_project_contexts(account_id):
            external_id = str(project['id'])
            client_id = int(project['client_id'])
            cursor.execute("SELECT id::text AS id FROM cx_studio_projects WHERE client_id=%s AND document->>'external_project_id'=%s LIMIT 1", (client_id, external_id))
            row = cursor.fetchone()
            studio_id = str(row['id']) if row else str(uuid.uuid4())
            if not row:
                cursor.execute("INSERT INTO cx_studio_projects (id, client_id, name, revision, document) VALUES (%s,%s,%s,1,%s)", (studio_id, client_id, str(project.get('nome') or 'Projeto sem nome')[:120], Json({'external_project_id': external_id, 'brief': str(project.get('descricao') or project.get('instrucoes') or ''), 'brand_name': str(project.get('brand_name') or '')})))
            brand_context = {}
            try:
                from ..creative_format_lab.brand_context import build_brand_context
                brand_context = build_brand_context(modeling.get_client(client_id))
            except Exception:
                logger.exception('Studio project brand context unavailable for %s', external_id)
            items.append({'id': studio_id, 'external_project_id': external_id, 'name': str(project.get('nome') or 'Projeto sem nome'), 'brief': str(project.get('descricao') or project.get('instrucoes') or ''), 'client_id': str(client_id), 'brand_name': str(project.get('brand_name') or brand_context.get('name') or 'Marca vinculada'), 'brand_count': int(project.get('brand_count') or 1), 'brand_context': brand_context})
    db.commit()
    return jsonify({'success': True, 'data': {'items': items}})


@studio_or_admin_required_api
@studio_csrf_required
def studio_project(ident):
    from flask import jsonify
    from . import studio_projects as repository
    execute, json_body, ok, _ = _http()
    def run():
        if not _ID.fullmatch(ident):
            # PostgreSQL projects use UUIDs; local legacy projects use a compact hex id.
            try:
                uuid.UUID(ident)
            except ValueError:
                raise ValueError('Projeto inválido.')
        store = _project_store(repository)
        if request.method == 'GET':
            revision = request.args.get('revision')
            client_id = request.args.get('client_id')
            _scope(client_id)
            return ok(store.read(client_id, ident, int(revision) if revision else None))
        data = json_body()
        try:
            client_id = data.get('client_id')
            _scope(client_id)
            return ok(store.save(client_id, data.get('document'), ident, data.get('expected_revision')))
        except repository.RevisionConflict as error:
            return jsonify(success=False, error=str(error), code='revision_conflict'), 409
    return execute(run)


@studio_or_admin_required_api
def studio_project_creation_history(ident):
    execute, _, ok, service = _http()
    def run():
        try:
            uuid.UUID(ident)
        except ValueError:
            raise ValueError('Projeto inválido.')
        client_id = request.args.get('client_id') or session.get('cliente_id')
        _scope(client_id)
        history = _creation_history()
        if not history:
            return ok({'runs': [], 'items': [], 'reference_masks': _studio_reference_masks()})
        result = history.history(ident, client_id, request.args.get('limit', 30))
        try:
            from ..creative_format_lab.brand_context import build_brand_context
            brand = build_brand_context(service().get_client(client_id))
            assets = brand.get('assets') if isinstance(brand, dict) else {}
            brand_items = []
            for role, urls in (('logo', assets.get('logo', [])), ('reference', assets.get('references', []))):
                for index, asset_url in enumerate(urls or []):
                    if asset_url:
                        brand_items.append({'id': f'brand:{role}:{index}', 'kind': 'reference', 'title': f'{brand.get("name") or "Marca"} · {role}', 'asset_url': asset_url, 'source_type': 'brand_asset', 'metadata': {'role': role, 'brand_name': brand.get('name', '')}})
            result['items'] = brand_items + result.get('items', [])
            result['brand_context'] = brand
        except Exception:
            logger.exception('Studio project brand assets unavailable for %s', ident)
        result['reference_masks'] = _studio_reference_masks()
        return ok(result)
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_project_select_direction(ident, direction_id):
    execute, json_body, ok, _ = _http()
    def run():
        try:
            uuid.UUID(ident)
            uuid.UUID(direction_id)
        except ValueError:
            raise ValueError('Direção inválida.')
        data = json_body()
        client_id = data.get('client_id')
        _scope(client_id)
        history = _creation_history()
        if not history:
            return ok({'id': direction_id})
        return ok({'id': history.select_direction(direction_id, ident, client_id)})
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_project_items(ident):
    execute, json_body, ok, _ = _http()
    def run():
        try:
            uuid.UUID(ident)
        except ValueError:
            raise ValueError('Projeto inválido.')
        data = json_body()
        client_id = data.get('client_id')
        _scope(client_id)
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para vincular o ativo.')
        history = _creation_history()
        if not history:
            return ok({'id': ''})
        if request.method == 'DELETE':
            removed = history.remove_item(ident, client_id, data.get('asset_url'))
            return ok({'removed': removed})
        item_id = history.add_item(ident, client_id, user_id, data.get('kind'), data.get('title'), data.get('asset_url'), data.get('metadata'))
        return ok({'id': item_id})
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_sessions():
    """Create or list persistent work sessions for the authenticated Studio."""
    from flask import jsonify
    from .studio_sessions import SessionConflict
    execute, json_body, ok, _ = _http()

    def run():
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para abrir suas sessões.')
        if request.method == 'GET':
            client_id = request.args.get('client_id')
            store = _session_store(client_id)
            return ok({'items': store.listing(
                client_id, user_id, request.args.get('project_id'), request.args.get('status'),
                request.args.get('limit', 100), request.args.get('scope') == 'all',
            )})
        data = json_body()
        client_id = data.get('client_id') or session.get('cliente_id')
        store = _session_store(client_id)
        try:
            created = store.create(client_id, user_id, data)
            # A mesa de edição fica aberta por padrão. O primeiro salvamento
            # recebe um único recibo resumível; autosaves posteriores não
            # disparam e-mail nem interrompem a criação.
            if str(data.get('studio_type') or '').lower() == 'edit':
                editor = ((data.get('metadata') or {}).get('editor') or {})
                stage = editor.get('current_asset') if isinstance(editor.get('current_asset'), dict) else {}
                stage_url = str(stage.get('url') or '')
                recipient = str(session.get('user_email') or '').strip().lower()
                if recipient and stage_url and hasattr(store, 'queue_session_receipt'):
                    try:
                        versions = editor.get('versions') if isinstance(editor.get('versions'), list) else []
                        director = editor.get('director') if isinstance(editor.get('director'), dict) else {}
                        review_points = [
                            f"Formato em edição: {editor.get('format') or 'original'}.",
                            f"{len(versions)} versão(ões) disponível(is) para revisão.",
                        ]
                        if director.get('objective'):
                            review_points.append(f"Direção: {str(director['objective'])[:180]}")
                        from urllib.parse import urlencode, urljoin
                        query = urlencode({'session_id': created.get('id'), 'client_id': client_id, 'project_id': data.get('project_id') or ''})
                        store.queue_session_receipt(client_id, user_id, created['id'], {
                            'recipient_email': recipient, 'recipient_name': str(session.get('user_name') or ''),
                            'email_payload': {'title': str(created.get('title') or 'Mesa de edição'), 'stage_image_url': urljoin(request.url_root, stage_url), 'session_url': f"{request.url_root.rstrip('/')}/studio/imagem?{query}", 'edits': max(0, len(versions) - 1), 'estimated_credits': int(((editor.get('estimate') or {}).get('estimated_tokens') or 0)), 'estimated_minutes': 0, 'review_points': review_points},
                        })
                    except Exception:
                        logger.exception('Studio session receipt could not be queued')
            return ok(created)
        except SessionConflict as error:
            return jsonify(success=False, error=str(error), code='revision_conflict'), 409

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_session(ident):
    from flask import jsonify
    from .studio_sessions import SessionConflict
    execute, json_body, ok, _ = _http()

    def run():
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para abrir esta sessão.')
        data = json_body() if request.method == 'PATCH' else request.args
        client_id = data.get('client_id') or session.get('cliente_id')
        store = _session_store(client_id)
        if request.method == 'GET':
            return ok(store.read(client_id, user_id, ident))
        try:
            return ok(store.save(client_id, user_id, ident, data))
        except SessionConflict as error:
            return jsonify(success=False, error=str(error), code='revision_conflict'), 409

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_attach_project(ident):
    """Make a personal Studio conversation part of an existing client project."""
    execute, json_body, ok, _ = _http()

    def run():
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para vincular esta sessão.')
        data = json_body()
        client_id = data.get('client_id') or session.get('cliente_id')
        return ok(_session_store(client_id).attach_project(
            client_id, user_id, ident, data.get('project_id'),
        ))

    return execute(run)


def _session_action(ident, action):
    execute, json_body, ok, _ = _http()

    def run():
        data = json_body()
        client_id = data.get('client_id') or session.get('cliente_id')
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para alterar esta sessão.')
        store = _session_store(client_id)
        if action == 'accept':
            result = store.accept(client_id, user_id, ident, data)
        elif action == 'handoff':
            result = store.handoff(client_id, user_id, ident, data)
        elif action == 'continue':
            result = store.continue_session(client_id, user_id, ident, data)
        elif action == 'finalize':
            # The recipient comes from the authenticated identity, never from
            # an arbitrary address supplied by the browser.
            data['recipient_email'] = str(session.get('user_email') or '').strip().lower()
            data['recipient_name'] = str(session.get('user_name') or '').strip()
            result = store.finalize(client_id, user_id, ident, data)
            if current_app.config.get('STUDIO_PROJECTS_POSTGRES', False):
                try:
                    from .jobs import wake_worker
                    wake_worker()
                except Exception:
                    logger.exception('Studio finalization queued, but the media worker was not awakened')
        elif action in {'discard', 'restore'}:
            result = store.discard(client_id, user_id, ident, str(data.get('asset_id') or ''), restore=action == 'restore')
        else:
            raise ValueError('Ação de sessão inválida.')
        return ok(result)

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_accept(ident):
    return _session_action(ident, 'accept')


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_handoff(ident):
    return _session_action(ident, 'handoff')


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_continue(ident):
    return _session_action(ident, 'continue')


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_finalize(ident):
    return _session_action(ident, 'finalize')


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_leave(ident):
    """Atomically persist the latest editor snapshot and finalize only edited work."""
    from flask import jsonify
    from .studio_sessions import SessionConflict
    execute, json_body, ok, _ = _http()

    def run():
        data = json_body()
        client_id = data.get('client_id') or session.get('cliente_id')
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para salvar esta sessão.')
        store = _session_store(client_id)
        try:
            saved = store.save(client_id, user_id, ident, data.get('save') or {})
        except SessionConflict:
            fresh = store.read(client_id, user_id, ident)
            retry = dict(data.get('save') or {})
            retry['expected_revision'] = fresh.get('revision')
            saved = store.save(client_id, user_id, ident, retry)
        if not data.get('has_edits') or saved.get('status') == 'finalized':
            return ok({'session': saved, 'finalized': False})
        final_payload = dict(data.get('finalize') or {})
        final_payload['recipient_email'] = str(session.get('user_email') or '').strip().lower()
        final_payload['recipient_name'] = str(session.get('user_name') or '').strip()
        try:
            result = store.finalize(client_id, user_id, ident, final_payload)
        except ValueError:
            logger.info('Studio leave saved session %s before its generated asset was ready to finalize', ident)
            return ok({'session': saved, 'finalized': False})
        if current_app.config.get('STUDIO_PROJECTS_POSTGRES', False):
            try:
                from .jobs import wake_worker
                wake_worker()
            except Exception:
                logger.exception('Studio leave queued delivery, but the worker was not awakened')
        return ok({**result, 'finalized': True})

    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_discard(ident):
    return _session_action(ident, 'discard')


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_restore(ident):
    return _session_action(ident, 'restore')


@studio_or_admin_required_api
@studio_csrf_required
def studio_session_share(ident):
    """Enable, revoke or rotate a read-only review link for a Studio session."""
    execute, json_body, ok, _ = _http()

    def run():
        user_id = session.get('user_id')
        if not user_id:
            raise ValueError('Entre novamente para compartilhar esta sessão.')
        data = json_body()
        client_id = data.get('client_id') or session.get('cliente_id')
        result = _session_store(client_id).share(client_id, user_id, ident, data)
        share = (result.get('metadata') or {}).get('share') or {}
        token = str(share.get('token') or '')
        result['share_url'] = f'/studio/mesa/{token}' if share.get('enabled') and token else ''
        return ok(result)

    return execute(run)


def studio_public_canvas(token):
    """Client-approved, anonymous canvas. Prompts and control data stay private."""
    from .studio_sessions import PostgresSessionRepository, find_local_public_canvas
    token = str(token or '').strip()
    if current_app.testing:
        canvas = find_local_public_canvas(media_root() / 'studio', token)
    else:
        from .. import db
        from .schema import ensure_schema
        connection = db.get_db()
        ensure_schema(connection)
        canvas = PostgresSessionRepository(connection).public_canvas(token)
    if not canvas:
        abort(404)
    response = render_template('cadu_studio/public_canvas.html', canvas=canvas)
    return response, 200, {'Cache-Control': 'private, no-store'}


def _session_store(client_id):
    """Use PostgreSQL for every non-test Studio session.

    A persisted conversation is part of the Studio work record.  The old
    feature flag could silently direct a production request to a server-local
    SQLite file, leaving personal sessions unavailable to the shared Studio
    timeline and operational support.
    """
    from .studio_sessions import LocalSessionRepository, PostgresSessionRepository
    if current_app.testing:
        return LocalSessionRepository(_scope(client_id))
    from .. import db
    from .schema import ensure_schema
    connection = db.get_db()
    ensure_schema(connection)
    return PostgresSessionRepository(connection)


def _project_store(repository):
    """Use Postgres in the application; retain the file store only for test isolation."""
    from flask import current_app
    if current_app.testing or not current_app.config.get('STUDIO_PROJECTS_POSTGRES', False):
        class LocalStore:
            def listing(self, client_id, offset): return repository.listing(_scope(client_id), offset)
            def read(self, client_id, ident, revision=None): return repository.read(_scope(client_id), ident, revision)
            def save(self, client_id, document, project_id=None, expected_revision=0): return repository.save(_scope(client_id), document, project_id, expected_revision)
        return LocalStore()
    from .. import db
    connection = db.get_db()
    # The media schema is idempotent and carries the studio-project tables too.
    from .schema import ensure_schema
    ensure_schema(connection)
    return repository.PostgresProjectRepository(connection)


def _creation_history():
    """The shared database is the source of truth for a project timeline.

    The isolated SQLite test mode intentionally keeps the UI usable without
    writing an unrelated local history database.
    """
    if current_app.testing or not current_app.config.get('STUDIO_PROJECTS_POSTGRES', False):
        return None
    from .. import db
    from .schema import ensure_schema
    from .studio_history import StudioCreationHistory
    connection = db.get_db()
    ensure_schema(connection)
    return StudioCreationHistory(connection)


def _quick_creative_client(modeling=None):
    """Map the authenticated CRM tenant to the Studio's canonical client id."""
    crm_client_id = session.get('cliente_id')
    if not crm_client_id:
        raise ValueError('Não foi possível identificar a conta de créditos desta sessão.')
    if modeling is None:
        from ..creative_modeling_service import CreativeModelingService
        modeling = CreativeModelingService()
    return int(modeling.repository.resolve_client_id(crm_client_id, 'crm'))


@studio_or_admin_required_api
def capabilities():
    from flask import jsonify
    from . import settings
    from .planner import AUDIO_MODES, MOTION_PRESETS
    return jsonify(success=True, data={
        "model": settings.MODEL,
        "skills": {
            "single_image": {
                "id": "seedance-2-5-image-to-video",
                "label": "Seedance 2.5 · imagem para vídeo",
                "resolution": "720p",
                "duration_min": 4,
                "duration_max": 30,
                "native_audio": True,
                "aspect_ratio": "source_image",
                "supports_seed": False,
            }
        },
        "durations": [value for value in settings.DURATIONS if value <= settings.MAX_DURATION],
        "ratios": [*settings.SEEDANCE_RATIOS, "4:5"],
        "qualities": {"draft": settings.DRAFT_RESOLUTION, "production": settings.PRODUCTION_RESOLUTION},
        "audio_modes": AUDIO_MODES,
        "motion_presets": MOTION_PRESETS,
        "seed": {"min": 0, "max": 2147483647},
    })


@studio_or_admin_required_api
@studio_csrf_required
def sounds():
    execute, _, ok, _ = _http()
    def run():
        client = request.args.get('client_id') if request.method == 'GET' else request.form.get('client_id')
        root = _scope(client)
        if request.method == 'GET':
            rows = sorted((json.loads(p.read_text()) for p in root.glob('sound-*.json')), key=lambda row: row.get('created_at', 0), reverse=True)
            from .studio_media import public_sounds
            return ok({"items": rows + public_sounds()[1]})
        if not ffmpeg_available():
            raise ValueError('O processamento de áudio não está disponível no servidor.')
        upload = request.files.get('file')
        if not upload:
            raise ValueError('Escolha um arquivo de áudio.')
        payload = upload.stream.read(_MAX_UPLOAD + 1)
        if not payload or len(payload) > _MAX_UPLOAD:
            raise ValueError('Envie um áudio de até 25 MB.')
        ident = uuid.uuid4().hex
        source = root / f'{ident}.upload'
        dest = root / f'{ident}.m4a'
        source.write_bytes(payload)
        try:
            duration, streams = probe(source)
            if 'audio' not in streams or 'video' in streams or not 0 < duration <= 600:
                raise ValueError('Envie somente áudio, com duração de até 10 minutos.')
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,mp3,wav,ogg,flac,aac,matroska,webm', '-i', str(source), '-vn', '-map_metadata', '-1',
                            '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2', str(dest)],
                           check=True, timeout=90, capture_output=True)
        except Exception as error:
            dest.unlink(missing_ok=True)
            raise ValueError('Não foi possível processar o áudio. Use MP3, WAV, M4A ou OGG de até 10 minutos.') from error
        finally:
            source.unlink(missing_ok=True)
        try:
            levels = waveform_levels(dest);peaks=levels['overview']
        except (subprocess.SubprocessError, OSError):
            levels={'overview':[],'medium':[],'detail':[]};peaks=[]
        row = {'waveform': peaks, 'waveform_levels': levels, 'id': ident, 'name': str(upload.filename or 'Áudio').replace('\\', '/').split('/')[-1][:120],
               'duration': round(duration, 2), 'category': request.form.get('category') if request.form.get('category') in {'music', 'effect', 'ambient', 'voice'} else 'music',
               'url': f'{_api_root()}/format-lab/studio/sounds/{ident}?client_id={int(client)}',
               'created_at': time.time()}
        _write(root / f'sound-{ident}.json', row)
        return ok(row)
    return execute(run)


@studio_or_admin_required_api
def sound_content(ident):
    execute, _, _, _ = _http()
    def run():
        root = _scope(request.args.get('client_id'))
        _record(root, ident, 'sound')
        return send_file(root / f'{ident}.m4a', mimetype='audio/mp4', conditional=True)
    return execute(run)


def render_clip(source, dest, edit, sound=None):
    duration, streams = probe(source)
    if 'video' not in streams:
        raise ValueError('O arquivo selecionado não é um vídeo.')
    start = edit['start']
    end = edit['end'] or duration
    end = min(end, duration)
    length = end - start
    if length < .1 or length > 300:
        raise ValueError('Escolha um intervalo de corte válido, de até 5 minutos.')
    speed = edit['speed']
    output_length = length / speed
    command = ['ffmpeg', '-y', '-v', 'error', '-ss', str(start), '-i', str(source)]
    if sound:
        if edit['loop']:
            command += ['-stream_loop', '-1']
        command += ['-ss', str(edit['sound_offset']), '-i', str(sound)]
    filters = []
    labels = []
    if 'audio' in streams and edit['original_volume'] > 0:
        filters += [f"[0:a]asetpts=PTS-STARTPTS,{_atempo(speed)},volume={edit['original_volume']},apad[original]"]
        labels += ['[original]']
    if sound:
        filters += [f"[1:a]asetpts=PTS-STARTPTS,volume={edit['sound_volume']},apad,atrim=duration={output_length},"
                    f"afade=t=in:d={min(edit['fade_in'], output_length)},"
                    f"afade=t=out:st={max(0, output_length-edit['fade_out'])}:d={min(edit['fade_out'], output_length)}[sound]"]
        labels += ['[sound]']
    command += ['-t', str(output_length)]
    if labels:
        filters += [''.join(labels) + f'amix=inputs={len(labels)}:normalize=0,alimiter=limit=0.95[audio]']
        command += ['-filter_complex', ';'.join(filters), '-map', '0:v:0', '-map', '[audio]', '-c:a', 'aac']
    else:
        command += ['-map', '0:v:0', '-an']
    visual = []
    if edit.get('output_ratio'):
        from .studio_composition import output_dimensions
        width,height=output_dimensions({'ratio':edit['output_ratio'],'resolution':720})
        visual.append(f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1')
    if speed != 1:
        visual.append(f'setpts=(PTS-STARTPTS)/{speed}')
    if edit['grayscale']:
        visual.append('hue=s=0')
    if edit['flip']:
        visual.append('hflip')
    if edit['video_fade_in']:
        visual.append(f"fade=t=in:d={min(edit['video_fade_in'], output_length)}")
    if edit['video_fade_out']:
        visual.append(f"fade=t=out:st={max(0, output_length-edit['video_fade_out'])}:d={min(edit['video_fade_out'], output_length)}")
    if visual:
        command += ['-vf', ','.join(visual)]
    command += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-movflags', '+faststart', str(dest)]
    subprocess.run(command, check=True, capture_output=True, timeout=240)


def _atempo(speed):
    value = float(speed or 1)
    parts = []
    while value < .5:
        parts.append('atempo=0.5')
        value /= .5
    while value > 2:
        parts.append('atempo=2.0')
        value /= 2
    parts.append(f'atempo={value}')
    return ','.join(parts)


def _render_job(root, ident, source, edit, sound, release_slot=True):
    path = root / f'export-{ident}.json'
    envelope = json.loads(path.read_text()) if path.exists() else {}
    _write(path, {**envelope, 'id':ident, 'status':'rendering'})
    try:
        work = envelope.get('work') or {}
        if work.get('composition'):
            from .studio_composition import render_composition
            render_composition(work['composition'], work['sources'], work['sounds'], root / f'{ident}.mp4')
        elif edit.get('layers'):
            from .studio_layers import render_layers
            intermediate = root / f'{ident}-base.mp4'
            try:
                render_clip(source, intermediate, edit, sound)
                render_layers(intermediate, root / f'{ident}.mp4', edit['layers'])
            finally:
                intermediate.unlink(missing_ok=True)
        else:
            render_clip(source, root / f'{ident}.mp4', edit, sound)
        from .studio_delivery import finish_delivery
        delivery_result=finish_delivery(root,ident,envelope)
        _write(path, {**envelope, **delivery_result, 'id': ident, 'status': 'ready', 'created_at': time.time()})
    except Exception:
        logger.exception("Studio export failed: %s", ident)
        (root / f'{ident}.mp4').unlink(missing_ok=True)
        _write(path, {**envelope, 'id': ident, 'status': 'failed', 'error': 'Não foi possível exportar. Verifique o intervalo de corte e tente novamente.', 'created_at': time.time()})
    finally:
        if release_slot:
            _SLOTS.release()


@studio_or_admin_required_api
@studio_csrf_required
def export_clip():
    execute, json_body, ok, service = _http()
    def run():
        data = json_body()
        root = _scope(data.get('client_id'))
        from .studio_media import resolve_clip, public_sounds
        source = resolve_clip(root, data.get('client_id'), data.get('clip_id'), service())
        edit = normalize_edit(data.get('edit'))
        sound = None
        if edit['sound_id']:
            public_root, catalog = public_sounds()
            public = next((r for r in catalog if r['id'] == edit['sound_id']), None)
            if public:
                sound = public_root / public['filename']
            else:
                _record(root, edit['sound_id'], 'sound')
                sound = root / f"{edit['sound_id']}.m4a"
        if not ffmpeg_available():
            raise ValueError('A exportação não está disponível no servidor.')
        ident = str(data.get('request_id') or '')
        if not _ID.fullmatch(ident):
            raise ValueError('Identificador da exportação inválido.')
        path = root / f'export-{ident}.json'
        # Exclusive creation makes retries idempotent, including across web workers.
        try:
            with path.open('x') as handle:
                from .studio_delivery import reserve_delivery
                delivery=reserve_delivery(root,data,service(),edit.get('output_ratio'))
                json.dump({'delivery':delivery,'id': ident, 'status': 'queued', 'created_at': time.time(), 'user_id': session.get('user_id'), 'work': {'source':str(source), 'sound':str(sound) if sound else '', 'edit':edit}}, handle)
        except FileExistsError:
            return ok(export_public(json.loads(path.read_text())))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        from .jobs import worker_mode, wake_worker
        if worker_mode() in {'process', 'supervised'}:
            wake_worker()
            return ok({'id':ident, 'status':'queued'})
        if not _SLOTS.acquire(blocking=False):
            path.unlink(missing_ok=True)
            raise ValueError('Há exportações em andamento. Tente novamente em instantes.')
        try:
            _POOL.submit(_render_job, root, ident, Path(source), edit, sound)
        except Exception:
            _SLOTS.release()
            path.unlink(missing_ok=True)
            raise
        return ok({'id': ident, 'status': 'rendering'})
    return execute(run)


@studio_or_admin_required_api
def export_status(ident):
    execute, _, ok, _ = _http()
    def run():
        _, row = _record(_scope(request.args.get('client_id')), ident, 'export')
        if row['status'] == 'rendering' and not row.get('work') and time.time() - row['created_at'] > 600:
            row.update(status='failed', error='A exportação foi interrompida. Tente novamente.')
        return ok(export_public(row))
    return execute(run)


@studio_or_admin_required_api
def export_content(ident):
    execute, _, _, _ = _http()
    def run():
        root = _scope(request.args.get('client_id'))
        _, row = _record(root, ident, 'export')
        if row['status'] != 'ready':
            raise ValueError('A exportação ainda não está pronta.')
        kind=request.args.get('format') or row.get('format','mp4')
        if kind not in {'mp4','gif','html'} or not (root/f'{ident}.{kind}').is_file():raise ValueError('Formato indisponível nesta exportação.')
        name=row.get('filename','cadu_studio.mp4')
        if kind!=row.get('format','mp4'):name=str(Path(name).with_suffix('.'+kind))
        return send_file(root / f'{ident}.{kind}', mimetype={'mp4':'video/mp4','gif':'image/gif','html':'text/html'}[kind], as_attachment=request.args.get('inline')!='1', download_name=name, conditional=True)
    return execute(run)


def export_public(row):
    return {key:row[key] for key in ('id','status','created_at','error','filename','format','download_url','public_url') if key in row}
