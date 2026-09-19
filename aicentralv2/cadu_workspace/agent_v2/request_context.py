"""Build the canonical context exclusively from server-authorized state."""

from flask import session

from ...cadu_family import context as family_context
from ...cadu_family import repository
from .contracts import ActiveObject, RequestContext, SURFACES


CAPABILITIES = ("workspace", "planner", "studio", "reports", "artifacts")


def resolve(*, conversation_id=None, surface="conversations", active_object=None) -> RequestContext:
    if surface not in SURFACES:
        raise ValueError("Superfície inválida.")
    actor = family_context.identity()
    selected = family_context.resolve()
    # A conversation keeps its bound project while moving between product
    # surfaces. Session selection is only the starting context for a new one.
    saved = (repository.conversation_context(actor, selected["client_id"], str(conversation_id))
             if conversation_id else None) or session.get("family_context") or {}
    project_ref, brand_ref = saved.get("project_ref"), saved.get("brand_ref")
    if project_ref or brand_ref:
        allowed = {item["ref"]: item for item in family_context.inventory(selected["client_id"])}
        if project_ref and (project_ref not in allowed or allowed[project_ref]["kind"] != "project"):
            project_ref = None
        if brand_ref and (brand_ref not in allowed or allowed[brand_ref]["kind"] != "brand"):
            brand_ref = None
    current = None
    if isinstance(active_object, dict) and active_object.get("type") and active_object.get("id"):
        current = ActiveObject(str(active_object["type"])[:80], str(active_object["id"])[:200])
    return RequestContext(
        organization_id=int(actor["organization_id"]), client_id=int(selected["client_id"]),
        user_id=int(actor["id"]), conversation_id=str(conversation_id) if conversation_id else None,
        surface=surface, project_ref=project_ref, brand_ref=brand_ref,
        active_object=current, capabilities=CAPABILITIES,
    )
