"""Central event connector for Cadu transactional e-mail delivery.

Product services decide when an event is meaningful; this module owns the
single delivery boundary, template rendering and product routing.
"""
from __future__ import annotations

from typing import Any, Iterable

from .brevo_service import get_brevo_product_service, product_email_brand


def send_cadu_event(*, product: str, event: str, template: str,
                    recipient: str | Iterable[str], recipient_name: str,
                    subject: str, params: dict[str, Any] | None = None,
                    internal: bool = False, cc: str | Iterable[str] | None = None) -> dict:
    """Send one named Cadu event through the centralized product connector."""
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
