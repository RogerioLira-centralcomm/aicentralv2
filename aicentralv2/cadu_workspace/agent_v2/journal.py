"""Durable ordered journal and checkpoints for Conversations V2."""

from uuid import uuid4

from psycopg.types.json import Json

from ...cadu_family import repository


def record(run_id: str, event_type: str, payload=None, *, item_type="activity", duration_ms=None) -> dict:
    connection = repository.get_db()
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM cadu_family_chat_runs WHERE id=%s FOR UPDATE", (run_id,))
        if not cursor.fetchone():
            raise ValueError("Turn indisponível.")
        cursor.execute("SELECT COALESCE(MAX(sequence),0)+1 AS sequence FROM cadu_agent_turn_events WHERE run_id=%s", (run_id,))
        sequence = int(cursor.fetchone()["sequence"])
        cursor.execute("""INSERT INTO cadu_agent_turn_events
            (run_id, sequence, event_type, item_type, payload, duration_ms)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (run_id, sequence, event_type, item_type, Json(payload or {}), duration_ms))
    connection.commit()
    return {"sequence": sequence, "event": event_type, **(payload or {})}


def persist_plan(run_id: str, plan: list[dict], tool_calls: list[dict]) -> None:
    calls = {item["name"]: item for item in tool_calls}
    connection = repository.get_db()
    with connection.cursor() as cursor:
        for position, step in enumerate(plan, 1):
            call = calls.get(step.get("name"))
            status = "completed" if call and call.get("status") == "completed" else "failed" if call else "pending"
            if step.get("kind") == "generate":
                status = "running"
            if step.get("kind") == "artifact":
                status = "waiting_confirmation" if step.get("requires_confirmation") else "pending"
            cursor.execute("""INSERT INTO cadu_agent_run_steps
                (id,run_id,position,kind,name,status,requires_confirmation,input_snapshot,
                 output_snapshot,error_code,started_at,finished_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        CASE WHEN %s IN ('running','completed','failed') THEN NOW() END,
                        CASE WHEN %s IN ('completed','failed') THEN NOW() END)
                ON CONFLICT (run_id,position) DO NOTHING""",
                (str(uuid4()), run_id, position, step.get("kind"), step.get("name") or step.get("action"), status,
                 bool(step.get("requires_confirmation")), Json(step), Json(call or {}),
                 call.get("code") if call else None, status, status))
    connection.commit()


def complete_step(run_id: str, kind: str, output=None, error_code=None) -> None:
    connection = repository.get_db()
    status = "failed" if error_code else "completed"
    with connection.cursor() as cursor:
        cursor.execute("""UPDATE cadu_agent_run_steps SET status=%s, output_snapshot=%s,
                                  error_code=%s, finished_at=NOW()
                            WHERE id=(SELECT id FROM cadu_agent_run_steps
                                      WHERE run_id=%s AND kind=%s AND status IN ('pending','running','waiting_confirmation')
                                      ORDER BY position LIMIT 1)""",
                       (status, Json(output or {}), error_code, run_id, kind))
        cursor.execute("""INSERT INTO cadu_agent_checkpoints (id,run_id,step_id,state)
                           SELECT %s,%s,id,%s FROM cadu_agent_run_steps
                            WHERE run_id=%s AND kind=%s ORDER BY position DESC LIMIT 1""",
                       (str(uuid4()), run_id, Json({"status": status, "output": output or {}}), run_id, kind))
    connection.commit()


def events(run_id: str, client_id: int, user_id: int) -> list[dict]:
    return repository.rows("""SELECT event.sequence, event.event_type, event.item_type, event.payload,
                                      event.duration_ms, event.created_at
                                 FROM cadu_agent_turn_events event
                                 JOIN cadu_family_chat_runs run ON run.id=event.run_id
                                WHERE event.run_id=%s AND run.client_id=%s AND run.user_id=%s
                             ORDER BY event.sequence""", (run_id, client_id, user_id))

