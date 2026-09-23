"""Tenant-scoped operational views for the Cadu Harness."""

from ...cadu_family import repository


_SAFE_EVENT_FIELDS = {
    "status", "code", "conversation_id", "message_id", "message_terminal_state",
    "execution_mode", "runtime_id", "provider_config_version", "first_token_ms",
    "total_duration_ms", "name", "tool_name", "step_id", "artifact_id", "type",
    "context_diagnostics", "rollout", "budget",
}


def _safe_event(event: dict) -> dict:
    """Remove prose, prompts and provider output from the technical endpoint."""
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    safe_payload = {key: payload[key] for key in _SAFE_EVENT_FIELDS if key in payload}
    return {**event, "payload": safe_payload}


def dashboard(client_id: int, limit=60) -> dict:
    limit = min(200, max(1, int(limit or 60)))
    try:
        summary = repository.rows("""SELECT COUNT(*) AS turns,
             COUNT(*) FILTER (WHERE status='completed') AS completed,
             COUNT(*) FILTER (WHERE status='failed') AS failed,
             COUNT(*) FILTER (WHERE status='cancelled') AS cancelled,
             ROUND(AVG(first_token_ms))::int AS avg_first_token_ms,
             ROUND(AVG(total_duration_ms))::int AS avg_duration_ms,
             COALESCE(SUM(input_tokens),0) AS input_tokens,
             COALESCE(SUM(output_tokens),0) AS output_tokens,
             COALESCE(SUM(charged_credits),0) AS charged_credits
          FROM cadu_family_chat_runs
         WHERE client_id=%s AND runtime_version='v2' AND created_at >= NOW()-INTERVAL '30 days'""",
                                  (client_id,))[0]
        modes = repository.rows("""SELECT execution_mode, COUNT(*) AS turns,
             ROUND(AVG(total_duration_ms))::int AS avg_duration_ms,
             COUNT(*) FILTER (WHERE status='failed') AS failed
          FROM cadu_family_chat_runs WHERE client_id=%s AND runtime_version='v2'
           AND created_at >= NOW()-INTERVAL '30 days' GROUP BY execution_mode ORDER BY turns DESC""", (client_id,))
        runs = repository.rows("""SELECT run.id::text, run.conversation_id, run.status, run.execution_mode,
             run.runtime_id, run.provider_config_version,
             run.route, run.first_token_ms, run.total_duration_ms, run.provider_duration_ms,
             run.input_tokens, run.output_tokens, run.charged_credits, run.terminal_error_code,
             run.created_at, run.finished_at,
             (SELECT COUNT(*) FROM cadu_agent_tool_calls tool WHERE tool.run_id=run.id) AS tool_calls,
             (SELECT COUNT(*) FROM cadu_agent_turn_events event WHERE event.run_id=run.id) AS events
          FROM cadu_family_chat_runs run WHERE run.client_id=%s AND run.runtime_version='v2'
         ORDER BY run.created_at DESC LIMIT %s""", (client_id, limit))
        try:
            queue = repository.rows("""SELECT
                 COUNT(*) FILTER (WHERE status='queued') AS queued,
                 COUNT(*) FILTER (WHERE status='failed') AS failed,
                 COUNT(*) FILTER (WHERE status='running' AND started_at < NOW()-INTERVAL '10 minutes') AS stalled
              FROM cadu_project_resource_jobs WHERE client_id=%s""", (client_id,))[0]
        except Exception:
            repository.get_db().rollback()
            queue = {"queued": 0, "failed": 0, "stalled": 0}
        alerts = []
        turns, failures = int(summary.get("turns") or 0), int(summary.get("failed") or 0)
        if turns >= 5 and failures / turns >= .10:
            alerts.append({"severity": "high", "code": "turn_failure_rate",
                           "message": f"{round(failures / turns * 100)}% dos Turns falharam nos últimos 30 dias."})
        if int(queue.get("failed") or 0):
            alerts.append({"severity": "high", "code": "resource_jobs_failed",
                           "message": f"{queue['failed']} reconciliações de projeto exigem nova tentativa."})
        if int(queue.get("stalled") or 0):
            alerts.append({"severity": "medium", "code": "resource_jobs_stalled",
                           "message": f"{queue['stalled']} reconciliações estão em execução há mais de 10 minutos."})
        if int(summary.get("avg_first_token_ms") or 0) > 5000:
            alerts.append({"severity": "medium", "code": "first_token_slow",
                           "message": "O primeiro retorno médio ultrapassou 5 segundos."})
        return {"available": True, "summary": summary, "modes": modes, "runs": runs,
                "resource_queue": queue, "alerts": alerts}
    except Exception:
        try:
            repository.get_db().rollback()
        except Exception:
            pass
        return {"available": False, "summary": {}, "modes": [], "runs": [], "alerts": []}


def run_detail(client_id: int, run_id: str) -> dict:
    rows = repository.rows("""SELECT id::text, conversation_id, user_id, status, execution_mode,
        runtime_id, provider_config_version, route,
        first_token_ms, total_duration_ms, provider_duration_ms,
        input_tokens, output_tokens, charged_credits, terminal_error_code, created_at, finished_at
        FROM cadu_family_chat_runs WHERE id=%s AND client_id=%s AND runtime_version='v2'""", (run_id, client_id))
    if not rows:
        raise ValueError("Turn indisponível.")
    events = repository.rows("""SELECT sequence,event_type,item_type,payload,duration_ms,created_at
        FROM cadu_agent_turn_events WHERE run_id=%s ORDER BY sequence""", (run_id,))
    steps = repository.rows("""SELECT id::text,position,kind,name,status,requires_confirmation,
        error_code,started_at,finished_at FROM cadu_agent_run_steps
        WHERE run_id=%s ORDER BY position""", (run_id,))
    tools = repository.rows("""SELECT tool_name,status,duration_ms,error_code,created_at,finished_at
        FROM cadu_agent_tool_calls WHERE run_id=%s ORDER BY created_at""", (run_id,))
    admitted = next((event.get("payload") for event in events
                     if event.get("event_type") == "run.admitted" and isinstance(event.get("payload"), dict)), {})
    try:
        transcript = repository.rows("""SELECT COUNT(*) AS message_count,
            MIN(conversation_sequence) AS sequence_start,
            MAX(conversation_sequence) AS sequence_end
            FROM cadu_conversation_messages message WHERE conversation_id=%s
              AND EXISTS (SELECT 1 FROM cadu_conversations conversation
                           WHERE conversation.id=message.conversation_id AND conversation.id_cliente=%s)""",
                                     (rows[0]["conversation_id"], client_id))[0]
    except Exception:
        repository.get_db().rollback()
        transcript = {"message_count": 0, "sequence_start": None, "sequence_end": None}
    safe_run_keys = {
        "id", "conversation_id", "user_id", "status", "execution_mode", "runtime_id",
        "provider_config_version", "route", "first_token_ms", "total_duration_ms",
        "provider_duration_ms", "input_tokens", "output_tokens", "charged_credits",
        "terminal_error_code", "created_at", "finished_at",
    }
    safe_step_keys = {
        "id", "position", "kind", "name", "status", "requires_confirmation",
        "error_code", "started_at", "finished_at",
    }
    return {
        "run": {key: value for key, value in rows[0].items() if key in safe_run_keys},
        "events": [_safe_event(event) for event in events],
        "steps": [{key: value for key, value in step.items() if key in safe_step_keys} for step in steps],
        "tools": tools,
        "diagnostics": admitted.get("context_diagnostics") or {},
        "rollout": admitted.get("rollout") or {},
        "transcript": transcript,
    }
