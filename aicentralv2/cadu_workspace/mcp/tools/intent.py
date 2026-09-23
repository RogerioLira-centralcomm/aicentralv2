"""Side-effect-free natural-language intent interpretation for every MCP surface."""

from dataclasses import replace
from html import escape

from ....cadu_family import repository
from ...intent_engine import interpret
from ...agent_v2.contracts import RequestContext
from ...artifacts import service as artifact_service
from .. import operations
from ..registry import ToolInputError, register_tool


@register_tool(
    name="intent.interpret", capability="workspace", effect="read",
    description=(
        "Interpreta pedidos naturais em português do Brasil, como 'joga isso no projeto', "
        "'faz um doc disso' ou 'não salva ainda'. Não executa alterações. Em MCP público, "
        "envie source.content quando 'isso' se referir a uma resposta criada pelo host."
    ),
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request"], "properties": {
        "request": {"type": "string", "minLength": 1, "maxLength": 20000},
        "source": {"type": ["object", "null"], "properties": {
            "type": {"type": "string", "enum": ["inline_content", "cadu_message", "artifact"]},
            "content": {"type": "string", "maxLength": 100000},
            "id": {"type": "string", "maxLength": 180},
        }, "additionalProperties": False},
        "pending_action": {"type": "boolean"},
    }, "additionalProperties": False},
)
def interpret_intent(context: RequestContext, arguments: dict) -> dict:
    source = arguments.get("source") if isinstance(arguments.get("source"), dict) else {}
    result = interpret(
        arguments["request"], has_project=bool(context.project_ref),
        has_source=bool(source.get("content") or source.get("id")),
        pending_action=bool(arguments.get("pending_action")),
        surface="public_mcp",
    ).to_dict()
    result["context"] = {
        "conversation_id": context.conversation_id, "project_ref": context.project_ref,
        "brand_ref": context.brand_ref,
    }
    result["next_step"] = (
        "provide_missing_fields" if result["missing"] else
        "call_proposed_tool" if result["proposed_tool"] else "respond"
    )
    return result


def _document_content(title: str, source: str, provenance: dict | None = None) -> dict:
    paragraphs = [" ".join(item.split()) for item in str(source or "").split("\n\n") if item.strip()]
    html = "".join(f"<p>{escape(item)}</p>" for item in paragraphs)
    content = {"title": title, "html": html or f"<p>{escape(str(source or '').strip())}</p>"}
    if provenance:
        content["_provenance"] = provenance
    return content


def _verified_provenance(context: RequestContext, source_input: dict, content: str) -> dict:
    source_type = str(source_input.get("type") or "inline_content")
    source_id = str(source_input.get("id") or "").strip()
    provenance = {
        "conversation_id": str(context.conversation_id or "") or None,
        "source_type": source_type,
        "source_id": source_id or None,
    }
    if source_type == "cadu_message":
        if not source_id or not context.conversation_id:
            raise ToolInputError("Uma mensagem de origem exige source.id e conversation_id válidos.")
        rows = repository.rows("""SELECT 1 FROM cadu_conversation_messages m
            JOIN cadu_conversations c ON c.id=m.conversation_id
            WHERE m.id=%s AND m.conversation_id=%s AND m.content=%s
              AND c.id_cliente=%s AND c.id_contato_cliente=%s LIMIT 1""",
            (source_id, context.conversation_id, content, context.client_id, context.user_id))
        if not rows:
            raise ToolInputError("A mensagem de origem não pertence a esta conversa ou seu conteúdo diverge.")
    elif source_type == "artifact":
        if not source_id:
            raise ToolInputError("Um artefato de origem exige source.id.")
        artifact_service.get_artifact(context, source_id)
    return {key: value for key, value in provenance.items() if value is not None}


@register_tool(
    name="intent.execute", capability="artifacts", effect="write",
    description=(
        "Executa com idempotência somente intenções naturais de criar documento ou salvá-lo no projeto. "
        "Exige o conteúdo de origem explícito; não tenta adivinhar respostas privadas do host."
    ),
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "request", "source", "confirmed"],
                  "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "request": {"type": "string", "minLength": 1, "maxLength": 20000},
        "source": {"type": "object", "required": ["content"], "properties": {
            "content": {"type": "string", "minLength": 1, "maxLength": 100000},
            "type": {"type": "string", "enum": ["inline_content", "cadu_message", "artifact"]},
            "id": {"type": "string", "maxLength": 180},
        }, "additionalProperties": False},
        "title": {"type": "string", "minLength": 1, "maxLength": 180},
        "confirmed": {"type": "boolean", "enum": [True]},
    }, "additionalProperties": False},
)
def execute_intent(context: RequestContext, arguments: dict) -> dict:
    source_input = arguments["source"]
    source = source_input["content"]
    result = interpret(arguments["request"], has_project=bool(context.project_ref),
                       has_source=True, surface="mcp")
    if result.intent not in {"create_artifact", "persist_content"}:
        raise ToolInputError("O pedido não descreve uma criação ou persistência de documento suportada.")
    if result.missing:
        raise ToolInputError("Falta contexto para executar: " + ", ".join(result.missing) + ".")
    if result.intent == "persist_content" and not context.project_ref:
        raise ToolInputError("Selecione um projeto antes de salvar o documento.")
    title = " ".join(str(arguments.get("title") or "").split())[:180]
    if not title:
        title = " ".join(source.split())[:90].rstrip(".,;:") or "Documento da conversa"
    target = context if result.intent == "persist_content" else replace(context, project_ref=None)
    provenance = _verified_provenance(context, source_input, source)
    fingerprint = {"intent_id": result.intent_id, "title": title,
                   "destination": result.destination, "source": source,
                   "source_type": provenance.get("source_type"), "source_id": provenance.get("source_id")}
    artifact = operations.execute(
        arguments["request_id"], target, "intent.execute", fingerprint,
        lambda: artifact_service.create_draft(
            target, "document", _document_content(title, source, provenance), title=title,
            conversation_id=context.conversation_id,
        ),
    )
    return {
        "intent": result.to_dict(), "status": "completed", "artifact_id": str(artifact["id"]),
        "title": artifact.get("title") or title, "project_ref": artifact.get("project_ref"),
        "conversation_id": str(artifact.get("conversation_id") or context.conversation_id or "") or None,
        "current_version": int(artifact.get("current_version") or 1),
    }
