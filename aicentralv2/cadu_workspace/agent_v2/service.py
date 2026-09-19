"""Admission, execution and persistence for a complete Conversations V2 turn."""

import json
from dataclasses import asdict
from time import perf_counter
from uuid import UUID, uuid4

from flask import abort, current_app, has_app_context
from psycopg.types.json import Json

from ...cadu_credit_connector import CaduCreditConnector, CreditActor
from ...cadu_family import repository
from ...cadu_tool_billing import InsufficientToolCredits
from ..conversations.guardrails import history_context
from ..artifacts import create_draft
from . import provider
from .executor import prepare_execution
from .guardrails import normalize_response
from .request_context import resolve
from . import journal


def _event(kind, **values):
    return "data: " + json.dumps({"event": kind, **values}, ensure_ascii=False, default=str) + "\n\n"


def _journal(run_id, kind, payload=None, *, item_type="activity", duration_ms=None):
    try:
        return journal.record(run_id, kind, payload, item_type=item_type, duration_ms=duration_ms)
    except Exception:
        if has_app_context():
            current_app.logger.exception("Falha ao registrar evento do Turn %s", run_id)
        return {"event": kind, **(payload or {})}


def _complete_step(run_id, kind, output=None, error_code=None):
    try:
        journal.complete_step(run_id, kind, output, error_code)
    except Exception:
        if has_app_context():
            current_app.logger.exception("Falha ao salvar checkpoint %s do Turn %s", kind, run_id)


def _message(value):
    text = " ".join(str(value or "").split())
    if not 1 <= len(text) <= 20000:
        abort(400, description="Informe uma mensagem de até 20.000 caracteres.")
    return text


def _run_was_cancelled(run_id: str) -> bool:
    """Recheck durable state before persisting output from a stopped provider."""
    try:
        rows = repository.rows(
            "SELECT status FROM cadu_family_chat_runs WHERE id = %s AND runtime_version = 'v2'",
            (run_id,),
        )
        return bool(rows and rows[0].get("status") == "cancelled")
    except Exception:
        current_app.logger.exception("Falha ao consultar cancelamento do run V2 %s", run_id)
        return False


def prepare(data):
    message = _message(data.get("message"))
    try:
        run_id = str(UUID(str(data.get("request_id"))))
    except (TypeError, ValueError):
        abort(400, description="Identificador de envio inválido.")
    conversation_id = str(data.get("conversation_id") or uuid4())
    current = resolve(conversation_id=conversation_id,
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"))
    try:
        CaduCreditConnector().authorize(
            CreditActor.from_values(current.client_id, current.user_id),
            max(1, int(current_app.config.get("CADU_CHAT_ADMISSION_TOKENS", 8000) or 8000)),
        )
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))
    previous_messages = (repository.conversation_messages(
        current.user_id, current.client_id, conversation_id
    ) if data.get("conversation_id") else []) or []
    requested_mode = data.get("execution_mode") or data.get("depth") or data.get("mode") or ""
    execution = prepare_execution(message, current, history_context(previous_messages), requested_mode)
    runtime = provider.runtime_for(execution["execution_mode"])
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cadu_family_chat_runs WHERE id = %s", (run_id,))
            if cur.fetchone():
                abort(409, description="Este envio já foi recebido.")
            cur.execute("""SELECT id FROM cadu_conversations
                            WHERE id = %s AND id_contato_cliente = %s AND id_cliente = %s FOR UPDATE""",
                        (conversation_id, current.user_id, current.client_id))
            existing = cur.fetchone()
            if data.get("conversation_id") and not existing:
                abort(404)
            if not existing:
                cur.execute("""INSERT INTO cadu_conversations
                    (id, id_cliente, id_contato_cliente, titulo, status, total_mensagens, projeto_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 'ativa', 0, %s, NOW(), NOW())""",
                    (conversation_id, current.client_id, current.user_id, message[:120],
                     current.project_ref[3:] if current.project_ref and current.project_ref.startswith("ci:") else None))
                cur.execute("""INSERT INTO cadu_family_conversation_context
                    (conversation_id, user_id, organization_id, client_id, profile, project_ref, brand_ref)
                    VALUES (%s, %s, %s, %s, 'workspace', %s, %s)""",
                    (conversation_id, current.user_id, current.organization_id, current.client_id,
                     current.project_ref, current.brand_ref))
            cur.execute("""SELECT id FROM cadu_family_chat_runs
                            WHERE conversation_id = %s AND status = 'running'""", (conversation_id,))
            if cur.fetchone():
                abort(409, description="Aguarde a resposta atual ou interrompa a geração.")
            cur.execute("""SELECT provider_conversation_id FROM cadu_agent_provider_sessions
                             WHERE conversation_id=%s AND runtime_id=%s AND client_id=%s AND user_id=%s""",
                        (conversation_id, runtime["id"], current.client_id, current.user_id))
            provider_session = cur.fetchone()
            if provider_session:
                execution["provider_payload"]["conversation_id"] = provider_session["provider_conversation_id"]
            cur.execute("""INSERT INTO cadu_family_chat_runs
                (id, conversation_id, user_id, client_id, status, runtime_version, execution_mode,
                 runtime_id, provider_config_version, route, request_context, response_policy, context_chars, created_at)
                VALUES (%s, %s, %s, %s, 'running', 'v2', %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (run_id, conversation_id, current.user_id, current.client_id,
                 execution["execution_mode"], runtime["id"], runtime["config_version"],
                 Json(execution["route"]), Json(current.to_dict()), Json(execution["policy"]),
                 len(execution["provider_payload"]["inputs"]["evidence"])))
            cur.execute("""INSERT INTO cadu_conversation_messages
                (id, conversation_id, role, content, files, metadata, created_at)
                VALUES (%s, %s, 'user', %s, '[]'::jsonb, %s, NOW())""",
                (str(uuid4()), conversation_id, message, Json({"runtime": "v2"})))
            for call in execution["resolved_context"].tool_calls:
                cur.execute("""INSERT INTO cadu_agent_tool_calls
                    (id, run_id, tool_name, status, input_redacted, output_summary, error_code,
                     created_at, finished_at)
                    VALUES (%s, %s, %s, %s, '{}'::jsonb, %s, %s, NOW(), NOW())""",
                    (str(uuid4()), run_id, call["name"],
                     "completed" if call["status"] == "completed" else "failed",
                     Json({"available": call["status"] == "completed"}), call.get("code")))
                cur.execute("""UPDATE cadu_agent_tool_calls SET duration_ms=%s
                                WHERE run_id=%s AND tool_name=%s""",
                            (call.get("duration_ms"), run_id, call["name"]))
        conn.commit()
        journal.persist_plan(run_id, execution["plan"], execution["resolved_context"].tool_calls)
        _journal(run_id, "run.admitted", {"execution_mode": execution["execution_mode"],
                 "runtime_id": runtime["id"], "provider_config_version": runtime["config_version"],
                 "route": execution["route"], "budget": execution["budget"]})
    except Exception:
        conn.rollback()
        raise
    return {
        "run_id": run_id, "conversation_id": conversation_id, "message": message,
        "context": current, "runtime": runtime, **execution,
    }


def stream(run):
    run_started = perf_counter()
    execution_mode = run.get("execution_mode") or "analysis"
    provider_started = None
    first_token_ms = None
    answer_chunks, usage, provider_id, task_id = [], {}, None, None
    state, assistant_id = "failed", None
    _journal(run["run_id"], "run.started", {"conversation_id": run["conversation_id"],
             "execution_mode": execution_mode})
    yield _event("run.started", run_id=run["run_id"], conversation_id=run["conversation_id"], execution_mode=execution_mode)
    _journal(run["run_id"], "route.selected", {"route": run["route"], "policy": run["policy"]})
    yield _event("route.selected", route=run["route"], policy=run["policy"])
    for call in run["resolved_context"].tool_calls:
        _journal(run["run_id"], "tool.completed" if call["status"] == "completed" else "tool.unavailable",
                 call, item_type="activity", duration_ms=call.get("duration_ms"))
        yield _event("tool.completed" if call["status"] == "completed" else "tool.unavailable", **call)
    try:
        provider_started = perf_counter()
        for item in provider.events(run["provider_payload"], execution_mode):
            if first_token_ms is None and (item.get("answer") or item.get("event") in {"message", "agent_message"}):
                first_token_ms = round((perf_counter() - run_started) * 1000)
                _journal(run["run_id"], "provider.first_token", {"first_token_ms": first_token_ms},
                         duration_ms=first_token_ms)
            provider_id = item.get("conversation_id") or provider_id
            next_task_id = item.get("task_id")
            if next_task_id and next_task_id != task_id:
                task_id = next_task_id
                conn = repository.get_db()
                with conn.cursor() as cur:
                    cur.execute("UPDATE cadu_family_chat_runs SET task_id = %s WHERE id = %s AND status = 'running'",
                                (task_id, run["run_id"]))
                conn.commit()
            if item.get("event") in {"message", "agent_message"} and item.get("answer"):
                answer_chunks.append(str(item["answer"]))
            if item.get("event") == "message_end":
                usage = (item.get("metadata") or {}).get("usage") or {}
        if _run_was_cancelled(run["run_id"]):
            state = "cancelled"
        else:
            response = normalize_response("".join(answer_chunks), run["policy"])
            artifact = None
            if response.artifact_patch and run["route"].get("artifact_type"):
                artifact = create_draft(
                    run["context"], run["route"]["artifact_type"], response.artifact_patch,
                    title=response.answer[:120], conversation_id=run["conversation_id"],
                )
                _complete_step(run["run_id"], "artifact", {"artifact_id": str(artifact["id"])})
                _journal(run["run_id"], "artifact.created", {"artifact_id": str(artifact["id"]),
                         "type": run["route"]["artifact_type"]}, item_type="artifact")
                yield _event("artifact.created", artifact=artifact)
            _complete_step(run["run_id"], "generate", {"answer_chars": len(response.answer)})
            _journal(run["run_id"], "answer.completed", {"response": asdict(response)}, item_type="message")
            yield _event("answer.completed", response=asdict(response))
            state = "completed"
            conn = repository.get_db()
            with conn.cursor() as cur:
                assistant_id = str(uuid4())
                cur.execute("""INSERT INTO cadu_conversation_messages
                    (id, conversation_id, role, content, tokens_entrada, tokens_saida, metadata, created_at)
                    VALUES (%s, %s, 'assistant', %s, %s, %s, %s, NOW())""",
                    (assistant_id, run["conversation_id"], response.answer,
                     max(0, int(usage.get("prompt_tokens") or 0)),
                     max(0, int(usage.get("completion_tokens") or 0)),
                     Json({"runtime": "v2", "response": asdict(response),
                           "artifact_id": str(artifact["id"]) if artifact else None})))
                cur.execute("""UPDATE cadu_conversations
                    SET total_mensagens = (SELECT COUNT(*) FROM cadu_conversation_messages WHERE conversation_id = %s),
                        total_tokens_entrada = COALESCE(total_tokens_entrada, 0) + %s,
                        total_tokens_saida = COALESCE(total_tokens_saida, 0) + %s, updated_at = NOW()
                    WHERE id = %s""",
                    (run["conversation_id"], max(0, int(usage.get("prompt_tokens") or 0)),
                     max(0, int(usage.get("completion_tokens") or 0)), run["conversation_id"]))
            conn.commit()
            if provider_id:
                conn = repository.get_db()
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO cadu_agent_provider_sessions
                        (conversation_id,client_id,user_id,runtime_id,provider_conversation_id,created_at,updated_at)
                        VALUES (%s,%s,%s,%s,%s,NOW(),NOW())
                        ON CONFLICT (conversation_id,runtime_id) DO UPDATE SET
                            provider_conversation_id=EXCLUDED.provider_conversation_id,updated_at=NOW()
                        WHERE cadu_agent_provider_sessions.client_id=EXCLUDED.client_id
                          AND cadu_agent_provider_sessions.user_id=EXCLUDED.user_id""",
                        (run["conversation_id"], run["context"].client_id, run["context"].user_id,
                         run["runtime"]["id"], provider_id))
                conn.commit()
            if usage:
                try:
                    charge = CaduCreditConnector().charge_provider(
                        actor=CreditActor.from_values(run["context"].client_id, run["context"].user_id),
                        idempotency_key="chat-v2:" + run["run_id"], app="Cadu Chat", stage="conversa-v2",
                        provider_result={"usage": usage, "model": run["runtime"]["id"]},
                        metadata={"conversation_id": run["conversation_id"], "runtime_id": run["runtime"]["id"],
                                  "provider_conversation_id": provider_id or ""},
                    )
                    if charge:
                        conn = repository.get_db()
                        with conn.cursor() as cur:
                            cur.execute("""UPDATE cadu_family_chat_runs SET charged_credits=%s,
                                           estimated_cost_usd=%s WHERE id=%s""",
                                        (int(charge.get("tokens_cobrados") or charge.get("charged_tokens") or 0),
                                         charge.get("custo_interno") or charge.get("internal_cost_usd") or 0, run["run_id"]))
                        conn.commit()
                except Exception:
                    # The answer is already durable. Billing reconciliation uses
                    # the idempotency key and must not corrupt the customer turn.
                    current_app.logger.exception("Falha de cobrança no run V2 %s", run["run_id"])
    except Exception:
        if _run_was_cancelled(run["run_id"]):
            state = "cancelled"
        else:
            current_app.logger.exception("Falha no runtime Cadu Conversations V2; run=%s", run["run_id"])
            _complete_step(run["run_id"], "generate", error_code="provider_failed")
            _journal(run["run_id"], "run.failed", {"code": "provider_failed"}, item_type="error")
            yield _event("run.failed", message="A execução foi interrompida. Tente novamente.")
    finally:
        total_duration_ms = round((perf_counter() - run_started) * 1000)
        provider_duration_ms = round((perf_counter() - provider_started) * 1000) if provider_started else None
        conn = repository.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""UPDATE cadu_family_chat_runs
                               SET status = CASE WHEN status = 'cancelled' THEN status ELSE %s END,
                                   task_id = COALESCE(%s, task_id), finished_at = NOW(),
                                   first_token_ms=%s, total_duration_ms=%s, provider_duration_ms=%s,
                                   input_tokens=%s, output_tokens=%s,
                                   terminal_error_code=CASE WHEN %s='failed' THEN 'provider_failed' ELSE NULL END
                               WHERE id = %s""", (state, task_id, first_token_ms, total_duration_ms,
                                  provider_duration_ms, max(0, int(usage.get("prompt_tokens") or 0)),
                                  max(0, int(usage.get("completion_tokens") or 0)), state, run["run_id"]))
            conn.commit()
        except Exception:
            conn.rollback()
            current_app.logger.exception("Falha ao finalizar run V2 %s", run["run_id"])
    terminal_event = "run.completed" if state == "completed" else "run.cancelled" if state == "cancelled" else "run.failed"
    _journal(run["run_id"], terminal_event, {"status": state, "conversation_id": run["conversation_id"],
             "message_id": assistant_id, "total_duration_ms": round((perf_counter() - run_started) * 1000)})
    yield _event("run.completed", status=state, conversation_id=run["conversation_id"], message_id=assistant_id)
