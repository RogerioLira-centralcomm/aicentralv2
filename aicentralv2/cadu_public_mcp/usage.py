"""Metering and shared-credit admission for the public Cadu MCP."""

from __future__ import annotations

from time import monotonic
from uuid import uuid4

from psycopg.types.json import Json

from ..cadu_credit_connector import CaduCreditConnector, CreditActor
from ..db import get_db


PUBLIC_TOOL_COSTS = {
    "operations.get": 0,
    "media.creation_capabilities": 0,
    "media.start_studio_session": 0,
    "media.list_jobs": 1,
    "media.get_job": 1,
    "media.generate_image": 0,
    "media.edit_image": 0,
    "media.plan_video": 0,
    "account.get": 0,
    "account.list_team": 0,
    "credits.get_balance": 0,
    "credits.list_packages": 0,
    "credits.purchase_package": 0,
    "google.get_connector_status": 1,
    "google.list_project_resources": 1,
    "google.list_calendar_events": 1,
    "google.list_meet_records": 2,
    "google.link_resource_to_project": 2,
    "resources.search": 1,
    "resources.get": 1,
    "resources.capabilities": 1,
    "resources.start_image_edit": 0,
    "projects.list_sources": 1,
    "projects.search_knowledge": 2,
    "projects.get_source_chunks": 1,
    "projects.list_resources": 1,
    "projects.inspect_file_support": 1,
    "projects.classify_intake": 2,
    "projects.create_link_reference": 2,
    "projects.list_tasks": 1,
    "projects.create_task": 1,
    "projects.create_tasks": 1,
    "projects.create_initial_task_list": 1,
    "projects.update_task": 1,
    "brands.list": 1,
    "reports.list_project_reports": 1,
    "reports.get_report_metrics": 2,
    "reports.compare_report_to_plan": 3,
}


def tool_cost(tool_name: str) -> int:
    return max(0, int(PUBLIC_TOOL_COSTS.get(tool_name, 1)))


def new_request_id(value=None) -> str:
    raw = str(value or "").strip()
    return raw[:160] if raw else str(uuid4())


def authorize_credits(*, client_id: int, user_id: int, tool_name: str) -> int:
    if tool_cost(tool_name) == 0:
        return 0
    return CaduCreditConnector().authorize(
        CreditActor.from_values(client_id, user_id), tool_cost(tool_name)
    )


def charge_credits(*, client_id: int, user_id: int, tool_name: str, idempotency_key: str, metadata=None) -> dict | None:
    if tool_cost(tool_name) == 0:
        return None
    return CaduCreditConnector().charge_tokens(
        actor=CreditActor.from_values(client_id, user_id),
        idempotency_key=f"public-mcp:{idempotency_key}"[:160],
        app="public_mcp",
        stage=tool_name,
        charged_tokens=tool_cost(tool_name),
        model="cadu-public-mcp",
        metadata={"mcp_tool": tool_name, **(metadata or {})},
    )


def available() -> bool:
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.cadu_public_mcp_usage') AS table_name")
            return bool((cursor.fetchone() or {}).get("table_name"))
    except Exception:
        return False


def record(*, key_id: str, client_id: int, user_id: int, client_type: str,
           credential_type: str = "api_key",
           method: str, tool_name: str = "", request_id: str = "", status: str,
           credit_cost: int = 0, started_at: float | None = None,
           input_bytes: int = 0, output_bytes: int = 0, error_code: str = "") -> None:
    if not available():
        return
    duration_ms = max(0, int((monotonic() - started_at) * 1000)) if started_at else 0
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_public_mcp_usage
                    (key_id, credential_type, credential_id, client_id, user_id, client_type, method, tool_name,
                     request_id, status, credit_cost, duration_ms, input_bytes,
                     output_bytes, error_code, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (credential_type, credential_id, request_id, method, tool_name) DO UPDATE SET
                    status=EXCLUDED.status, credit_cost=EXCLUDED.credit_cost,
                    duration_ms=EXCLUDED.duration_ms, output_bytes=EXCLUDED.output_bytes,
                    error_code=EXCLUDED.error_code, updated_at=NOW()""",
                (key_id if credential_type == "api_key" else None, credential_type, key_id,
                 int(client_id), int(user_id), client_type, method, tool_name,
                 request_id[:160], status, int(credit_cost or 0), duration_ms,
                 int(input_bytes or 0), int(output_bytes or 0), error_code[:120] or None,
                 Json({})),
            )
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass


def summary(*, client_id: int, user_id: int) -> dict:
    fallback = {"total_calls": 0, "successful_calls": 0, "credits_used": 0, "average_duration_ms": 0, "by_client": [], "recent": []}
    if not available():
        fallback["available"] = False
        return fallback
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT COUNT(*) AS total_calls,
                          COUNT(*) FILTER (WHERE status='completed') AS successful_calls,
                          COALESCE(SUM(credit_cost) FILTER (WHERE status='completed'),0) AS credits_used,
                          COALESCE(ROUND(AVG(duration_ms))::int,0) AS average_duration_ms
                     FROM cadu_public_mcp_usage
                    WHERE client_id=%s AND user_id=%s""",
                (int(client_id), int(user_id)),
            )
            totals = dict(cursor.fetchone() or {})
            cursor.execute(
                """SELECT client_type, COUNT(*) AS calls,
                          COALESCE(SUM(credit_cost) FILTER (WHERE status='completed'),0) AS credits
                     FROM cadu_public_mcp_usage
                    WHERE client_id=%s AND user_id=%s
                 GROUP BY client_type ORDER BY calls DESC""",
                (int(client_id), int(user_id)),
            )
            by_client = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """SELECT client_type, method, tool_name, status, credit_cost,
                          duration_ms, error_code, created_at
                     FROM cadu_public_mcp_usage
                    WHERE client_id=%s AND user_id=%s
                 ORDER BY created_at DESC LIMIT 20""",
                (int(client_id), int(user_id)),
            )
            recent = [dict(row) for row in cursor.fetchall()]
        return {**fallback, **totals, "by_client": by_client, "recent": recent, "available": True}
    except Exception:
        return {**fallback, "available": False}
