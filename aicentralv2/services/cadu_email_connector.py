"""Central event connector for Cadu transactional e-mail delivery.

Product services decide when an event is meaningful; this module owns the
single delivery boundary, template rendering and product routing.
"""
from __future__ import annotations

from typing import Any, Iterable

from .brevo_service import get_brevo_product_service, product_email_brand

# Single source of truth for event names used by product services and the
# Workspace e-mail catalogue. ``planned`` events are documented but must not
# be presented as active delivery triggers until a caller is wired.
CADU_EMAIL_EVENTS: dict[str, dict[str, str]] = {
    "workspace.brand_audit_ready": {"product": "workspace", "status": "active"},
    "workspace.brand_approved": {"product": "workspace", "status": "active"},
    "workspace.project_created": {"product": "workspace", "status": "planned"},
    "workspace.source_received": {"product": "workspace", "status": "planned"},
    "workspace.source_indexed": {"product": "workspace", "status": "planned"},
    "workspace.source_attention": {"product": "workspace", "status": "planned"},
    "workspace.document_reviewed": {"product": "workspace", "status": "planned"},
    "workspace.conversation_important": {"product": "workspace", "status": "planned"},
    "planner.quote_request_internal": {"product": "planner", "status": "active"},
    "planner.new_user_internal": {"product": "planner", "status": "active"},
    "studio.piece_ready": {"product": "studio", "status": "active"},
    "studio.session_saved": {"product": "studio", "status": "active"},
    "studio.work_completed": {"product": "studio", "status": "active"},
}


def send_cadu_event(*, product: str, event: str, template: str,
                    recipient: str | Iterable[str], recipient_name: str,
                    subject: str, params: dict[str, Any] | None = None,
                    internal: bool = False, cc: str | Iterable[str] | None = None) -> dict:
    """Send one named Cadu event through the centralized product connector."""
    definition = CADU_EMAIL_EVENTS.get(event)
    if definition is None:
        raise ValueError(f"Evento de e-mail Cadu não catalogado: {event}")
    if definition["product"] != product:
        raise ValueError(f"Evento {event} pertence ao produto {definition['product']}, não {product}")
    if definition["status"] != "active":
        raise ValueError(f"Evento de e-mail Cadu ainda não está ativo: {event}")
    template_folder = "emails/internos" if internal else "emails/externos"
    payload = dict(params or {})
    payload.setdefault("BRAND", product_email_brand(product))
    payload.setdefault("CADU_EVENT", event)
    return get_brevo_product_service(product).enviar_email_com_template(
        template_name=template,
        template_folder=template_folder,
        to_email=recipient,
        to_name=recipient_name,
        subject=subject,
        params=payload,
        cc_email=cc,
    )
