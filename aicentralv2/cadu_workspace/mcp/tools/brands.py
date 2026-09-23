"""Brand tools backed by the same reviewable Workspace workflows as the UI."""

from werkzeug.exceptions import HTTPException

from ... import brand_mcp_service as service
from ...agent_v2.contracts import RequestContext
from .. import operations
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


@register_tool(name="brands.inspect_site", capability="workspace", effect="read",
               description="Inspeciona com segurança o site oficial, valida um link de logo e encontra candidatos de logo sem aprová-los automaticamente.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object","properties":{
                   "website_url":{"type":"string","minLength":3,"maxLength":2000},
                   "logo_url":{"type":"string","maxLength":2000},
                   "brand_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def inspect_site(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.inspect_site(context, arguments.get("website_url", ""), arguments.get("logo_url", ""), arguments.get("brand_id")))


@register_tool(name="brands.list_assets", capability="workspace", effect="read",
               description="Lista imagens aprovadas da biblioteca da marca atual, incluindo IDs, prévias e qual é o logo principal.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object","properties":{"brand_id":{"type":"integer","minimum":1},
                   "limit":{"type":"integer","minimum":1,"maximum":100}},"additionalProperties":False})
def list_brand_assets(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.list_assets(context, arguments.get("brand_id"), arguments.get("limit", 50)))


@register_tool(name="brands.use_asset_as_logo", capability="workspace", effect="write",
               description="Define uma imagem aprovada da biblioteca da própria marca como logo principal, sem reenviar o arquivo.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","confirmed","asset_id"],"properties":{
                   "request_id":{"type":"string","minLength":36,"maxLength":36},
                   "confirmed":{"type":"boolean","enum":[True]},
                   "brand_id":{"type":"integer","minimum":1},
                   "asset_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def use_asset_as_logo(context: RequestContext, arguments: dict) -> dict:
    payload = {key: arguments.get(key) for key in ("brand_id", "asset_id")}
    return _domain(lambda: operations.execute(arguments["request_id"], context,
        "brands.use_asset_as_logo", payload,
        lambda: service.use_asset_as_logo(context, brand_id=arguments.get("brand_id"), asset_id=arguments["asset_id"])))


@register_tool(name="brands.create", capability="workspace", effect="write",
               description="Cria uma marca com nome, site oficial e segmento. Logo oficial e referências são opcionais; retorna ficha e uploads.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","confirmed","name","website_url","sector"],"properties":{"request_id":{"type":"string","minLength":36,"maxLength":36},"confirmed":{"type":"boolean","enum":[True]},"name":{"type":"string","minLength":2,"maxLength":150},"website_url":{"type":"string","minLength":3,"maxLength":2000},"sector":{"type":"string","minLength":2,"maxLength":80},"official_logo_url":{"type":"string","minLength":8,"maxLength":2000},"reference_urls":{"type":"array","maxItems":12,"items":{"type":"string","minLength":8,"maxLength":2000}}},"additionalProperties":False})
def create_brand(context: RequestContext, arguments: dict) -> dict:
    values = {key: value for key, value in arguments.items() if key != "confirmed"}
    return _domain(lambda: service.create_brand(context, **values))


_identity_change_properties = {
    "name":{"type":"string","minLength":2,"maxLength":150}, "sector":{"type":["string","null"],"maxLength":80},
    "website_url":{"type":["string","null"],"maxLength":2000},
    "primary_color":{"type":["string","null"],"pattern":"^#[0-9A-Fa-f]{6}$"},
    "secondary_color":{"type":["string","null"],"pattern":"^#[0-9A-Fa-f]{6}$"},
    **{field:{"type":"string","maxLength":4000} for field in service.BRAND_IDENTITY_TEXT_FIELDS},
    **{field:{"type":"array","items":{"type":"string","maxLength":300},"maxItems":12} for field in service.BRAND_IDENTITY_LIST_FIELDS},
}


@register_tool(name="brands.update_identity", capability="workspace", effect="write",
               description="Altera o site oficial (changes.website_url) ou outros campos explícitos da marca sem apagar os demais. Exige confirmação do usuário.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","confirmed","brand_id","changes"],"properties":{"request_id":{"type":"string","minLength":36,"maxLength":36},"confirmed":{"type":"boolean","enum":[True]},"brand_id":{"type":"integer","minimum":1},"changes":{"type":"object","minProperties":1,"properties":_identity_change_properties,"additionalProperties":False}},"additionalProperties":False})
def update_identity(context: RequestContext, arguments: dict) -> dict:
    values = {key: value for key, value in arguments.items() if key != "confirmed"}
    return _domain(lambda: service.update_identity(context, **values))


@register_tool(name="brands.prepare_logo_upload", capability="workspace", effect="draft",
               description="Cria uma autorização curta para enviar o logo principal de uma marca.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","brand_id"],"properties":{"request_id":{"type":"string","minLength":36,"maxLength":36},"brand_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def prepare_logo_upload(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.prepare_logo_upload(context, arguments["brand_id"]))


@register_tool(name="brands.prepare_asset_upload", capability="workspace", effect="draft",
               description="Prepara o envio de um ativo para a biblioteca da marca: logo, referência, peça criativa, fundo, apoio ou ícone.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","brand_id","role"],"properties":{
                   "request_id":{"type":"string","minLength":36,"maxLength":36},
                   "brand_id":{"type":"integer","minimum":1},
                   "role":{"type":"string","enum":sorted(service.BRAND_ASSET_ROLES)}},"additionalProperties":False})
def prepare_asset_upload(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.prepare_asset_upload(context, arguments["brand_id"], arguments["role"]))


@register_tool(name="brands.delete_asset", capability="workspace", effect="write",
               description="Remove um ativo específico da biblioteca da marca após confirmação. Não apaga a marca.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","confirmed","brand_id","asset_id"],"properties":{
                   "request_id":{"type":"string","minLength":36,"maxLength":36},
                   "confirmed":{"type":"boolean","enum":[True]},
                   "brand_id":{"type":"integer","minimum":1},"asset_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def delete_asset(context: RequestContext, arguments: dict) -> dict:
    payload = {"brand_id": arguments["brand_id"], "asset_id": arguments["asset_id"]}
    return _domain(lambda: operations.execute(arguments["request_id"], context, "brands.delete_asset", payload,
        lambda: service.delete_asset(context, **payload)))


@register_tool(name="brands.start_audit", capability="workspace", effect="write",
               description="Inicia análise completa ou profunda da marca após confirmar o custo. A auditoria pertence à marca e não altera o projeto atual; informe brand_id ou use brand_ref/contexto de marca, mesmo que project_ref aponte para outro projeto. Pode usar imagens aprovadas da biblioteca, incluindo o logo selecionado.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["request_id","confirmed","confirmed_cost"],"properties":{"request_id":{"type":"string","minLength":36,"maxLength":36},"confirmed":{"type":"boolean","enum":[True]},"confirmed_cost":{"type":"boolean","enum":[True]},"brand_id":{"type":"integer","minimum":1},"website_url":{"type":"string","maxLength":2000},"analysis_mode":{"type":"string","enum":["complete","deep"]},"social_links":{"type":"array","items":{"type":"string","maxLength":500},"maxItems":12},"additional_sources":{"type":"array","items":{"type":"string","maxLength":2000},"maxItems":12},"excluded_sources":{"type":"array","items":{"type":"string","maxLength":2000},"maxItems":12},"existing_asset_ids":{"type":"array","items":{"type":"integer","minimum":1},"maxItems":12}},"additionalProperties":False})
def start_audit(context: RequestContext, arguments: dict) -> dict:
    values = {key: value for key, value in arguments.items() if key != "confirmed"}
    return _domain(lambda: service.start_audit(context, **values))


@register_tool(name="brands.audit_status", capability="workspace", effect="read",
               description="Consulta o andamento e resultado operacional da auditoria de uma marca.", exposures=("internal", "customer_agent"),
               input_schema={"type":"object","required":["brand_id"],"properties":{"brand_id":{"type":"integer","minimum":1}},"additionalProperties":False})
def audit_status(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.audit_status(context, arguments["brand_id"]))
