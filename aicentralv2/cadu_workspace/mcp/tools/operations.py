"""Tenant-scoped execution receipts for external agents."""

from uuid import UUID

from ....db import get_db
from ...agent_v2.contracts import RequestContext
from ..registry import ToolInputError, register_tool


def _request_id(value) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise ToolInputError("request_id inválido.") from exc


@register_tool(
    name="operations.get",
    description=(
        "Consulta o recibo durável de uma ação pelo request_id. Use para retomar uma conversa, "
        "confirmar que uma escrita terminou ou evitar repetir uma operação."
    ),
    capability="workspace",
    effect="read",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["request_id"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "tool_name": {"type": "string", "minLength": 3, "maxLength": 120},
        },
        "additionalProperties": False,
    },
)
def get_operation(context: RequestContext, arguments: dict) -> dict:
    request_id = _request_id(arguments.get("request_id"))
    tool_name = str(arguments.get("tool_name") or "").strip()
    query = """SELECT request_id::text, tool_name, status, result, error_code,
                      started_at, finished_at, updated_at
                 FROM cadu_mcp_operations
                WHERE request_id=%s AND client_id=%s AND user_id=%s"""
    values = [request_id, context.client_id, context.user_id]
    if tool_name:
        query += " AND tool_name=%s"
        values.append(tool_name)
    query += " ORDER BY updated_at DESC"
    with get_db().cursor() as cursor:
        cursor.execute(query, tuple(values))
        rows = [dict(row) for row in cursor.fetchall()]
    if not rows:
        raise ToolInputError("Operação não encontrada para este usuário.")
    receipts = [{
        "operation_id": row["request_id"],
        "tool": row["tool_name"],
        "status": row["status"],
        "result": row.get("result") or {},
        "error": ({"code": row["error_code"]} if row.get("error_code") else None),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "updated_at": row.get("updated_at"),
    } for row in rows]
    return {"operation_id": request_id, "receipts": receipts,
            "status": receipts[0]["status"] if len(receipts) == 1 else "multiple"}
