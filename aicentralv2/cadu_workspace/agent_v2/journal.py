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
            if step.get("requires_confirmation"):
                status = "waiting_confirmation"
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


def state(run_id: str, client_id: int, user_id: int) -> dict:
    runs = repository.rows("""SELECT id::text,status,execution_mode,runtime_id,provider_config_version,
                                      route,created_at,finished_at
                                 FROM cadu_family_chat_runs
                                WHERE id=%s AND client_id=%s AND user_id=%s AND runtime_version='v2'""",
                           (run_id, client_id, user_id))
    if not runs:
        raise ValueError("Turn indisponível.")
    steps = repository.rows("""SELECT id::text,position,kind,name,status,requires_confirmation,
                                       input_snapshot,output_snapshot,error_code,decided_by,decided_at,decision_note
                                  FROM cadu_agent_run_steps WHERE run_id=%s ORDER BY position""", (run_id,))
    checkpoints = repository.rows("""SELECT id::text,step_id::text,state,created_at
                                        FROM cadu_agent_checkpoints WHERE run_id=%s ORDER BY created_at""", (run_id,))
    return {"run": runs[0], "steps": steps, "checkpoints": checkpoints}


def waiting_actions(run_id: str, client_id: int, user_id: int) -> list[dict]:
    rows = repository.rows("""SELECT step.id::text,step.name,step.input_snapshot
                                 FROM cadu_agent_run_steps step
                                 JOIN cadu_family_chat_runs run ON run.id=step.run_id
                                WHERE step.run_id=%s AND run.client_id=%s AND run.user_id=%s
                                  AND step.kind='action' AND step.status='waiting_confirmation'
                             ORDER BY step.position""", (run_id, client_id, user_id))
    actions = []
    for row in rows:
        snapshot = row.get("input_snapshot") or {}
        actions.append({
            "step_id": row["id"], "name": row.get("name"),
            "summary": snapshot.get("summary") or "Confirmar ação",
            "effect": snapshot.get("effect") or "write",
            "arguments": snapshot.get("arguments") or {},
            "cost_estimate": snapshot.get("cost_estimate"),
        })
    return actions


def start_direct_link_action(run_id: str, client_id: int, user_id: int) -> dict | None:
    """Claim an explicitly authorized project-link write before producing its receipt."""
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_agent_run_steps step
                                  SET status='running', started_at=NOW()
                                 FROM cadu_family_chat_runs run
                                WHERE step.run_id=%s AND run.id=step.run_id
                                  AND run.client_id=%s AND run.user_id=%s
                                  AND step.kind='action' AND step.name='projects.create_link_reference'
                                  AND step.requires_confirmation=false AND step.status='pending'
                             RETURNING step.id::text,step.kind,step.name,step.status,step.input_snapshot""",
                           (run_id, client_id, user_id))
            step = cursor.fetchone()
        connection.commit()
        return dict(step) if step else None
    except Exception:
        connection.rollback()
        raise


def propose_action(run_id: str, name: str, arguments: dict, summary: str) -> dict:
    """Seal a validated provider proposal as a user-confirmable server action."""
    step_id, request_id = str(uuid4()), str(uuid4())
    snapshot = {"kind": "action", "name": name, "requires_confirmation": True,
                "request_id": request_id, "arguments": arguments, "effect": "write",
                "summary": str(summary or "Confirmar ação")[:500]}
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COALESCE(MAX(position),0)+1 AS position FROM cadu_agent_run_steps WHERE run_id=%s",
                           (run_id,))
            position = int(cursor.fetchone()["position"])
            cursor.execute("""INSERT INTO cadu_agent_run_steps
                (id,run_id,position,kind,name,status,requires_confirmation,input_snapshot)
                VALUES (%s,%s,%s,'action',%s,'waiting_confirmation',true,%s)""",
                (step_id, run_id, position, name, Json(snapshot)))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"step_id": step_id, "name": name, "summary": snapshot["summary"],
            "effect": "write", "arguments": arguments}


def decide_step(run_id: str, step_id: str, client_id: int, user_id: int, approved: bool, note="") -> dict:
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT id FROM cadu_family_chat_runs
                                WHERE id=%s AND client_id=%s AND user_id=%s AND runtime_version='v2'
                                FOR UPDATE""", (run_id, client_id, user_id))
            if not cursor.fetchone():
                raise ValueError("Turn indisponível.")
            cursor.execute("""UPDATE cadu_agent_run_steps step
                                   SET status=CASE WHEN %s AND step.kind='action' THEN 'running'
                                                   WHEN %s THEN 'completed' ELSE 'cancelled' END,
                                      decided_by=%s,
                                      decided_at=NOW(),decision_note=%s,
                                      started_at=CASE WHEN %s AND step.kind='action' THEN NOW() ELSE step.started_at END,
                                      finished_at=CASE WHEN %s AND step.kind='action' THEN NULL ELSE NOW() END
                                 FROM cadu_family_chat_runs run
                                WHERE step.id=%s AND step.run_id=%s AND run.id=step.run_id
                                  AND run.client_id=%s AND run.user_id=%s
                                  AND step.requires_confirmation=true AND step.status='waiting_confirmation'
                            RETURNING step.id::text,step.kind,step.name,step.status,step.input_snapshot""",
                           (approved, approved, user_id, str(note or "")[:1000], approved, approved,
                            step_id, run_id, client_id, user_id))
            step = cursor.fetchone()
            if not step:
                raise ValueError("Etapa indisponível ou já decidida.")
            cursor.execute("""INSERT INTO cadu_agent_checkpoints (id,run_id,step_id,state)
                               VALUES (%s,%s,%s,%s)""",
                           (str(uuid4()), run_id, step_id, Json({"status": step["status"], "approved": approved,
                                                                 "note": str(note or "")[:1000]})))
            cursor.execute("SELECT COALESCE(MAX(sequence),0)+1 AS sequence FROM cadu_agent_turn_events WHERE run_id=%s",
                           (run_id,))
            sequence = int(cursor.fetchone()["sequence"])
            cursor.execute("""INSERT INTO cadu_agent_turn_events
                (run_id,sequence,event_type,item_type,payload)
                VALUES (%s,%s,%s,'action',%s)""",
                (run_id, sequence, "confirmation.approved" if approved else "confirmation.rejected",
                 Json({"step_id": step_id, "step": step.get("name"), "note": str(note or "")[:1000]})))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return dict(step)


def finish_action(run_id: str, step_id: str, client_id: int, user_id: int, receipt=None, error_code=None) -> dict:
    """Persist an approved action's terminal state and public receipt atomically."""
    connection = repository.get_db()
    status = "failed" if error_code else "completed"
    payload = {"step_id": step_id, "status": status, "receipt": receipt or {}}
    try:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_agent_run_steps step
                                  SET status=%s,output_snapshot=%s,error_code=%s,finished_at=NOW()
                                 FROM cadu_family_chat_runs run
                                WHERE step.id=%s AND step.run_id=%s AND run.id=step.run_id
                                  AND run.client_id=%s AND run.user_id=%s AND step.kind='action'
                                  AND step.status='running'
                            RETURNING step.id::text,step.kind,step.name,step.status,step.output_snapshot,step.error_code""",
                           (status, Json(receipt or {}), error_code, step_id, run_id, client_id, user_id))
            step = cursor.fetchone()
            if not step:
                raise ValueError("Ação indisponível ou já finalizada.")
            cursor.execute("""INSERT INTO cadu_agent_checkpoints (id,run_id,step_id,state)
                               VALUES (%s,%s,%s,%s)""",
                           (str(uuid4()), run_id, step_id, Json(payload)))
            cursor.execute("SELECT COALESCE(MAX(sequence),0)+1 AS sequence FROM cadu_agent_turn_events WHERE run_id=%s",
                           (run_id,))
            sequence = int(cursor.fetchone()["sequence"])
            cursor.execute("""INSERT INTO cadu_agent_turn_events
                (run_id,sequence,event_type,item_type,payload)
                VALUES (%s,%s,%s,%s,%s)""",
                (run_id, sequence, "action.failed" if error_code else "action.completed",
                 "error" if error_code else "action", Json(payload)))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return dict(step)
