"""Side-effect-free natural-language intent interpretation for every MCP surface."""

from dataclasses import replace
from html import escape

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


def _document_content(title: str, source: str) -> dict:
    paragraphs = [" ".join(item.split()) for item in str(source or "").split("\n\n") if item.strip()]
    html = "".join(f"<p>{escape(item)}</p>" for item in paragraphs)
    return {"title": title, "html": html or f"<p>{escape(str(source or '').strip())}</p>"}


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
        }, "additionalProperties": False},
        "title": {"type": "string", "minLength": 1, "maxLength": 180},
        "confirmed": {"type": "boolean", "enum": [True]},
    }, "additionalProperties": False},
)
def execute_intent(context: RequestContext, arguments: dict) -> dict:
    source = arguments["source"]["content"]
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
    fingerprint = {"intent_id": result.intent_id, "title": title,
                   "destination": result.destination, "source": source}
    artifact = operations.execute(
        arguments["request_id"], target, "intent.execute", fingerprint,
        lambda: artifact_service.create_draft(
            target, "document", _document_content(title, source), title=title,
            conversation_id=context.conversation_id,
        ),
    )
    return {
        "intent": result.to_dict(), "status": "completed", "artifact_id": str(artifact["id"]),
        "title": artifact.get("title") or title, "project_ref": artifact.get("project_ref"),
        "conversation_id": str(artifact.get("conversation_id") or context.conversation_id or "") or None,
        "current_version": int(artifact.get("current_version") or 1),
    }
