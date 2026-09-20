"""Execute server-authored, user-approved action steps through the MCP registry."""

from ..mcp.registry import ToolError, ToolInputError, load_builtin_tools

ALLOWED_ACTION_TOOLS = frozenset({"planner.link_test", "workspace.create_project"})


def execute(step: dict, context) -> dict:
    if step.get("kind") != "action" or step.get("status") != "running":
        raise ToolInputError("A etapa não está pronta para execução.")
    snapshot = step.get("input_snapshot") or {}
    if not isinstance(snapshot, dict) or snapshot.get("name") != step.get("name"):
        raise ToolInputError("A proposta de ação não corresponde à etapa aprovada.")
    if step.get("name") not in ALLOWED_ACTION_TOOLS:
        raise ToolInputError("Esta ação ainda não pode ser executada automaticamente.")
    arguments = snapshot.get("arguments")
    request_id = snapshot.get("request_id")
    if not isinstance(arguments, dict) or not request_id:
        raise ToolInputError("A proposta aprovada está incompleta.")
    sealed = {**arguments, "request_id": request_id, "confirmed": True}
    result = load_builtin_tools().execute(step["name"], sealed, context, "internal")
    if not isinstance(result, dict):
        raise ToolError("A ação não devolveu um receipt válido.")
    return {"tool": step["name"], "request_id": request_id, "result": result}
