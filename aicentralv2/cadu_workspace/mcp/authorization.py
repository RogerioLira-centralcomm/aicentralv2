"""Short-lived, scoped delegation for Cadu agents using the internal MCP."""

import secrets
from dataclasses import dataclass

from flask import current_app, request, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..agent_v2.contracts import ActiveObject, RequestContext
from ..agent_v2.request_context import resolve


SALT = "cadu-workspace-mcp-v2"
MAX_AGE_SECONDS = 300


class MCPUnauthorized(RuntimeError):
    pass


@dataclass(frozen=True)
class MCPPrincipal:
    context: RequestContext
    exposure: str = "internal"


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt=SALT)


def issue(context: RequestContext, exposure: str = "internal") -> str:
    if exposure not in {"internal", "customer_agent"}:
        raise ValueError("Perfil de exposição inválido.")
    return _serializer().dumps({"context": context.to_dict(), "exposure": exposure})


def _delegated(token: str) -> MCPPrincipal:
    try:
        value = _serializer().loads(token, max_age=MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise MCPUnauthorized("A delegação do agente expirou.") from exc
    except BadSignature as exc:
        raise MCPUnauthorized("Delegação do agente inválida.") from exc
    if not isinstance(value, dict):
        raise MCPUnauthorized("Delegação do agente inválida.")
    exposure = str(value.get("exposure") or "internal")
    value = value.get("context")
    if exposure not in {"internal", "customer_agent"} or not isinstance(value, dict):
        raise MCPUnauthorized("Perfil de delegação inválido.")
    active = value.get("active_object")
    active_object = ActiveObject(str(active["type"]), str(active["id"])) if isinstance(active, dict) else None
    try:
        context = RequestContext(
            organization_id=int(value["organization_id"]), client_id=int(value["client_id"]),
            user_id=int(value["user_id"]), conversation_id=value.get("conversation_id"),
            request_id=value.get("request_id"),
            surface=str(value["surface"]), project_ref=value.get("project_ref"),
            brand_ref=value.get("brand_ref"), active_object=active_object,
            capabilities=tuple(value.get("capabilities") or ()),
        )
        return MCPPrincipal(context=context, exposure=exposure)
    except (KeyError, TypeError, ValueError) as exc:
        raise MCPUnauthorized("A delegação do agente está incompleta.") from exc


def authorize(params: dict) -> MCPPrincipal:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return _delegated(header[7:].strip())
    if not session.get("user_id"):
        raise MCPUnauthorized("Autenticação necessária.")
    expected, supplied = session.get("family_csrf"), request.headers.get("X-CSRF-Token", "")
    if not expected or not secrets.compare_digest(expected, supplied):
        raise MCPUnauthorized("Sessão expirada. Atualize a página.")
    return MCPPrincipal(context=resolve(
        conversation_id=params.get("conversation_id"),
        surface=str(params.get("surface") or "conversations"),
        active_object=params.get("active_object"),
        project_ref=params.get("project_ref"),
        brand_ref=params.get("brand_ref"),
    ))
