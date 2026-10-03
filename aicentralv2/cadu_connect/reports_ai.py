"""Reports' single door to paid AI and scraping: every call is authorised and debited through the Cadu credit connector.

The debited account is the Reports client the person is working in (`selected['client_id']`, the same one used for
every other Reports query), never a client the person only sees through a shared link. Callers use these helpers
instead of `chat_completion`, `system_one` or `_firecrawl_scrape` directly, so a new AI feature cannot run for free.
"""
import logging
import uuid

from flask import abort, g, has_request_context, session

from ..cadu_credit_connector import CaduCreditConnector, CreditActor
from ..cadu_tool_billing import InsufficientToolCredits

APP = 'Cadu Reports'
logger = logging.getLogger(__name__)


def actor_for(selected=None):
    """Who pays: the Reports client in use and the signed-in user. Guests (shared access) and viewers cannot spend credits."""
    if selected is None:
        if not has_request_context():
            raise ValueError('Esta ação de IA precisa de um cliente e um usuário para cobrar os créditos.')
        from . import reports_access
        selected = g.get('reports_selected') or reports_access.resolve()
    if selected.get('access_scope') == 'shared' or selected.get('role') == 'viewer':
        abort(403, description='Seu acesso não permite usar IA neste cliente.')
    user_id = selected.get('user_id') or (session.get('user_id') if has_request_context() else None)
    return CreditActor.from_values(selected['client_id'], user_id)


NO_PRICE = 'Este cliente não tem preço de tokens configurado no plano; a IA fica indisponível até o plano ser ajustado.'


def _authorize(actor, estimate=1):
    """Refuses before the paid call when there is no balance or no token price (a call that cannot be debited must not run)."""
    credits = CaduCreditConnector()
    try:
        credits.ensure_priced(actor.client_id)
        credits.authorize(actor, estimate)
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))
    except ValueError:
        abort(409, description=NO_PRICE)


def _charge(label, call):
    """The answer is already in hand: a billing failure is logged for reconciliation, never lost silently or shown as an AI error."""
    try:
        return call()
    except Exception:
        logger.error('Falha ao debitar créditos de IA do Reports (%s)', label, exc_info=True)
        return None


def chat(stage, messages, *, call=None, selected=None, actor=None, metadata=None, **options):
    """`chat_completion` with a balance check before and a debit after, on the client's credits."""
    if call is None:
        from ..services.openrouter_service import chat_completion as call
    actor = actor or actor_for(selected)
    _authorize(actor)
    response = call(messages, **options)
    run_id = str(uuid.uuid4())
    _charge(f'{stage} cliente {actor.client_id}', lambda: CaduCreditConnector().charge_provider(
        actor=actor, idempotency_key=f'reports-ai:{stage}:{run_id}', app=APP, stage=stage,
        provider_result=response, metadata={**(metadata or {}), 'billing_run_id': run_id, 'billing_class': 'text_agent'}))
    return response


def typesafe(stage, state, questions, *, call=None, selected=None, actor=None, metadata=None, **options):
    """`system_one` (TypeSafe) with the same balance check and debit; tokens come from the response usage."""
    if call is None:
        from ..services.typesafe_service import system_one as call
    actor = actor or actor_for(selected)
    _authorize(actor)
    result = call(state, questions, **options)
    run_id = str(uuid.uuid4())
    _charge(f'{stage} cliente {actor.client_id}', lambda: CaduCreditConnector().charge_provider(
        actor=actor, idempotency_key=f'reports-ai:{stage}:{run_id}', app=APP, stage=stage,
        provider_result={'usage': result.get('usage'), 'model': result.get('model')},
        metadata={**(metadata or {}), 'billing_run_id': run_id, 'billing_class': 'typesafe'}))
    return result


def firecrawl_scrape(stage, url, *, call=None, selected=None, actor=None, metadata=None, **options):
    """Hosted page capture (Firecrawl scrape: one credit per page), billed to the client's credits."""
    if call is None:
        from ..crm_v3_web_scout import _firecrawl_scrape as call
    actor = actor or actor_for(selected)
    credits = CaduCreditConnector()
    try:
        credits.authorize_firecrawl(actor, 'scrape', pages=1)
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))
    except ValueError:
        abort(409, description=NO_PRICE)
    data = call(url, **options)
    run_id = str(uuid.uuid4())
    _charge(f'{stage} cliente {actor.client_id}', lambda: credits.charge_firecrawl(
        actor=actor, idempotency_key=f'reports-ai:{stage}:{run_id}', operation='scrape', pages=1, app=APP, stage=stage,
        metadata={**(metadata or {}), 'billing_run_id': run_id, 'url_host': str(url).split('/')[2] if '//' in str(url) else ''}))
    return data
