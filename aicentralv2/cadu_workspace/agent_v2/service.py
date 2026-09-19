"""Admission, execution and persistence for a complete Conversations V2 turn."""

import json
from dataclasses import asdict
from uuid import UUID, uuid4

from flask import abort, current_app
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


def _event(kind, **values):
    return "data: " + json.dumps({"event": kind, **values}, ensure_ascii=False, default=str) + "\n\n"


def _message(value):
    text = " ".join(str(value or "").split())
    if not 1 <= len(text) <= 20000:
        abort(400, description="Informe uma mensagem de até 20.000 caracteres.")
    return text


def prepare(data):
    provider.settings()  # Fail before recording a turn when V2 is not configured.
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
    execution = prepare_execution(message, current, history_context(previous_messages))
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
            cur.execute("""INSERT INTO cadu_family_chat_runs
                (id, conversation_id, user_id, client_id, status, runtime_version, route,
                 request_context, response_policy, context_chars, created_at)
                VALUES (%s, %s, %s, %s, 'running', 'v2', %s, %s, %s, %s, NOW())""",
                (run_id, conversation_id, current.user_id, current.client_id,
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
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "run_id": run_id, "conversation_id": conversation_id, "message": message,
        "context": current, **execution,
    }


def stream(run):
    answer_chunks, usage, provider_id, task_id = [], {}, None, None
    state, assistant_id = "failed", None
    yield _event("run.started", run_id=run["run_id"], conversation_id=run["conversation_id"])
    yield _event("route.selected", route=run["route"], policy=run["policy"])
    for call in run["resolved_context"].tool_calls:
        yield _event("tool.completed" if call["status"] == "completed" else "tool.unavailable", **call)
    try:
        for item in provider.events(run["provider_payload"]):
            provider_id = item.get("conversation_id") or provider_id
            task_id = item.get("task_id") or task_id
            if item.get("event") in {"message", "agent_message"} and item.get("answer"):
                answer_chunks.append(str(item["answer"]))
            if item.get("event") == "message_end":
                usage = (item.get("metadata") or {}).get("usage") or {}
        response = normalize_response("".join(answer_chunks), run["policy"])
        artifact = None
        if response.artifact_patch and run["route"].get("artifact_type"):
            artifact = create_draft(
                run["context"], run["route"]["artifact_type"], response.artifact_patch,
                title=response.answer[:120], conversation_id=run["conversation_id"],
            )
            yield _event("artifact.created", artifact=artifact)
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
        if usage:
            try:
                CaduCreditConnector().charge_provider(
                    actor=CreditActor.from_values(run["context"].client_id, run["context"].user_id),
                    idempotency_key="chat-v2:" + run["run_id"], app="Cadu Chat", stage="conversa-v2",
                    provider_result={"usage": usage, "model": "dify-v2"},
                    metadata={"conversation_id": run["conversation_id"], "provider_conversation_id": provider_id or ""},
                )
            except Exception:
                # The answer is already durable. Billing reconciliation uses
                # the idempotency key and must not corrupt the customer turn.
                current_app.logger.exception("Falha de cobrança no run V2 %s", run["run_id"])
    except Exception:
        current_app.logger.exception("Falha no runtime Cadu Conversations V2; run=%s", run["run_id"])
        yield _event("run.failed", message="A execução foi interrompida. Tente novamente.")
    finally:
        conn = repository.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""UPDATE cadu_family_chat_runs
                               SET status = %s, task_id = COALESCE(%s, task_id), finished_at = NOW()
                               WHERE id = %s""", (state, task_id, run["run_id"]))
            conn.commit()
        except Exception:
            conn.rollback()
            current_app.logger.exception("Falha ao finalizar run V2 %s", run["run_id"])
    yield _event("run.completed", status=state, conversation_id=run["conversation_id"], message_id=assistant_id)
