"""Brand tools backed by the same reviewable Workspace workflows as the UI."""

from werkzeug.exceptions import HTTPException

from ... import brand_mcp_service as service
from ...agent_v2.contracts import RequestContext
from ..registry import ToolError, register_tool


def _domain(callable_):
    try:
        return callable_()
    except HTTPException as exc:
        error = ToolError(exc.description)
        error.code = "brand_workflow_error"
        raise error from exc


@register_tool(name="brands.list", capability="workspace", effect="read",
               description="Lista marcas da organização atual.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","properties":{"query":{"type":"string","maxLength":100},"limit":{"type":"integer","minimum":1,"maximum":50}},"additionalProperties":False})
def list_brands(context: RequestContext, arguments: dict) -> dict:
    return {"brands": service.list_brands(context, arguments.get("query", ""), arguments.get("limit", 30))}


@register_tool(name="brands.get_context", capability="workspace", effect="read",
               description="Obtém o contexto aprovado da marca para conversas, projetos e artefatos, com cores, logo e fontes.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["brand_id"],"properties":{"brand_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def get_brand_context(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.brand_context(context, arguments["brand_id"]))


@register_tool(name="brands.create", capability="workspace", effect="write",
               description="Cria uma marca com nome e site oficial após confirmação do usuário.", exposures=("internal",),
               input_schema={"type":"object","required":["request_id","confirmed","name","website_url"],"properties":{"request_id":{"type":"string","minLength":36,"maxLength":36},"confirmed":{"type":"boolean","enum":[True]},"name":{"type":"string","minLength":2,"maxLength":150},"website_url":{"type":"string","minLength":3,"maxLength":2000},"sector":{"type":"string","maxLength":80}},"additionalProperties":False})
def create_brand(context: RequestContext, arguments: dict) -> dict:
    values = {key: value for key, value in arguments.items() if key != "confirmed"}
    return _domain(lambda: service.create_brand(context, **values))


@register_tool(name="brands.prepare_logo_upload", capability="workspace", effect="draft",
               description="Cria uma autorização curta para enviar o logo principal de uma marca.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","brand_id"],"properties":{"request_id":{"type":"string","minLength":36,"maxLength":36},"brand_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def prepare_logo_upload(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.prepare_logo_upload(context, arguments["brand_id"]))


@register_tool(name="brands.start_audit", capability="workspace", effect="write",
               description="Inicia a auditoria paga de uma marca após confirmação explícita do usuário administrador.", exposures=("internal",),
               input_schema={"type":"object","required":["request_id","confirmed","confirmed_cost","brand_id"],"properties":{"request_id":{"type":"string","minLength":36,"maxLength":36},"confirmed":{"type":"boolean","enum":[True]},"confirmed_cost":{"type":"boolean","enum":[True]},"brand_id":{"type":"integer","minimum":1},"website_url":{"type":"string","maxLength":2000},"analysis_mode":{"type":"string","enum":["complete","deep"]},"social_links":{"type":"array","items":{"type":"string","maxLength":500},"maxItems":12}},"additionalProperties":False})
def start_audit(context: RequestContext, arguments: dict) -> dict:
    values = {key: value for key, value in arguments.items() if key != "confirmed"}
    return _domain(lambda: service.start_audit(context, **values))


@register_tool(name="brands.audit_status", capability="workspace", effect="read",
               description="Consulta o andamento e resultado operacional da auditoria de uma marca.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["brand_id"],"properties":{"brand_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def audit_status(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.audit_status(context, arguments["brand_id"]))
