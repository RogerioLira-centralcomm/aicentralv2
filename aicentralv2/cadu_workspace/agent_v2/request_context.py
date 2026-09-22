"""Build the canonical context exclusively from server-authorized state."""

from flask import session

from ...cadu_family import context as family_context
from ...cadu_family import repository
from .contracts import ActiveObject, RequestContext, SURFACES


CAPABILITIES = ("workspace", "planner", "studio", "reports", "artifacts", "research")


def resolve(*, conversation_id=None, request_id=None, surface="conversations", active_object=None,
            project_ref=None, brand_ref=None) -> RequestContext:
    if surface not in SURFACES:
        raise ValueError("Superfície inválida.")
    actor = family_context.identity()
    selected = family_context.resolve()
    # A conversation keeps its bound project while moving between product
    # surfaces. Session selection is only the starting context for a new one.
    persisted = (repository.conversation_context(actor, selected["client_id"], str(conversation_id))
                 if conversation_id else None)
    saved = persisted or session.get("family_context") or {}
    resolved_project, resolved_brand = saved.get("project_ref"), saved.get("brand_ref")
    # A fresh turn may carry the selector value directly. This prevents a
    # race between the client-side selector and the session update endpoint.
    if not persisted:
        resolved_project = project_ref if isinstance(project_ref, str) else resolved_project
        resolved_brand = brand_ref if isinstance(brand_ref, str) else resolved_brand
    else:
        # Repair legacy/free threads whose persisted binding is empty while
        # the current turn carries a server-authorized context selection.
        # Never replace a non-empty conversation binding implicitly.
        if not resolved_project and isinstance(project_ref, str) and project_ref:
            resolved_project = project_ref
        if not resolved_brand and isinstance(brand_ref, str) and brand_ref:
            resolved_brand = brand_ref
    if resolved_project or resolved_brand:
        allowed = {item["ref"]: item for item in family_context.inventory(selected["client_id"])}
        if resolved_project and (resolved_project not in allowed or allowed[resolved_project]["kind"] != "project"):
            resolved_project = None
        if resolved_brand and (resolved_brand not in allowed or allowed[resolved_brand]["kind"] != "brand"):
            resolved_brand = None
        # A project with one explicit brand relationship carries that brand into
        # the conversation. Multiple brands remain unselected: the agent must
        # ask which one is relevant instead of guessing.
        if resolved_project and not resolved_brand:
            linked = {
                str(item.get("brand_ref") or "") for item in repository.project_brand_links(selected["client_id"])
                if str(item.get("project_ref") or "") == resolved_project
            }
            known = linked.intersection({ref for ref, item in allowed.items() if item["kind"] == "brand"})
            if len(known) == 1:
                resolved_brand = next(iter(known))
    current = None
    if isinstance(active_object, dict) and active_object.get("type") and active_object.get("id"):
        current = ActiveObject(str(active_object["type"])[:80], str(active_object["id"])[:200])
    return RequestContext(
        organization_id=int(actor["organization_id"]), client_id=int(selected["client_id"]),
        user_id=int(actor["id"]), conversation_id=str(conversation_id) if conversation_id else None,
        request_id=str(request_id) if request_id else None,
        surface=surface, project_ref=resolved_project, brand_ref=resolved_brand,
        active_object=current, capabilities=CAPABILITIES,
    )
