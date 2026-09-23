"""Durable idempotency boundary for MCP commands and synchronous jobs."""

from hashlib import sha256
import json
from time import monotonic
from uuid import UUID

from psycopg.types.json import Json

from ...db import get_db
from ..agent_v2.contracts import RequestContext
from .registry import ToolInputError


def _uuid(value) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise ToolInputError("Identificador da operação inválido.") from exc


def _enrich_operation(connection, operation_id: str, context: RequestContext,
                      tool_name: str, started_clock: float, terminal_state: str) -> None:
    """Best-effort metadata for installations where the new columns exist."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_mcp_operations
                   SET duration_ms=%s,terminal_state=%s,conversation_id=%s,tool_call_id=%s
                 WHERE request_id=%s AND client_id=%s AND user_id=%s AND tool_name=%s""",
                (max(0, int((monotonic() - started_clock) * 1000)), terminal_state,
                 context.conversation_id, operation_id, operation_id,
                 context.client_id, context.user_id, tool_name))
        connection.commit()
    except Exception:
        # These columns belong to the optional MCP context migration. Their
        # absence must not change the result of the canonical operation.
        connection.rollback()


def execute(request_id, context: RequestContext, tool_name: str, arguments: dict, operation):
    started_clock = monotonic()
    operation_id = _uuid(request_id)
    normalized = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    fingerprint = sha256(normalized.encode()).hexdigest()
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                           (f"cadu-mcp:{context.client_id}:{context.user_id}:{tool_name}:{operation_id}",))
            cursor.execute("""SELECT input_hash,status,result,
                                       (status='running' AND started_at < NOW()-INTERVAL '10 minutes') AS stale
                                  FROM cadu_mcp_operations
                                WHERE request_id=%s AND client_id=%s AND user_id=%s AND tool_name=%s""",
                           (operation_id, context.client_id, context.user_id, tool_name))
            existing = cursor.fetchone()
            if existing and existing["input_hash"] != fingerprint:
                raise ToolInputError("Este request_id já foi usado com parâmetros diferentes.")
            if existing and existing["status"] == "completed":
                connection.commit()
                return existing.get("result") or {}
            if existing and existing["status"] == "running" and not existing.get("stale"):
                raise ToolInputError("Esta operação ainda está em andamento.")
            cursor.execute("""INSERT INTO cadu_mcp_operations
                (request_id,client_id,user_id,tool_name,input_hash,status,started_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,'running',NOW(),NOW())
                ON CONFLICT (request_id,client_id,user_id,tool_name) DO UPDATE SET
                    status='running',error_code=NULL,started_at=NOW(),updated_at=NOW()""",
                (operation_id, context.client_id, context.user_id, tool_name, fingerprint))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    try:
        result = operation()
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_mcp_operations SET status='completed',result=%s,
                                      finished_at=NOW(),updated_at=NOW()
                                WHERE request_id=%s AND client_id=%s AND user_id=%s AND tool_name=%s""",
                           (Json(result or {}), operation_id, context.client_id, context.user_id, tool_name))
        connection.commit()
        _enrich_operation(connection, operation_id, context, tool_name, started_clock, "completed")
        return result
    except Exception as exc:
        connection.rollback()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""UPDATE cadu_mcp_operations SET status='failed',error_code=%s,
                                          finished_at=NOW(),updated_at=NOW()
                                    WHERE request_id=%s AND client_id=%s AND user_id=%s AND tool_name=%s""",
                               (type(exc).__name__[:80], operation_id, context.client_id, context.user_id, tool_name))
            connection.commit()
            _enrich_operation(connection, operation_id, context, tool_name, started_clock, "failed")
        except Exception:
            connection.rollback()
        raise
