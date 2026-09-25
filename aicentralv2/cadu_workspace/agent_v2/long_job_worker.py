"""Supervised worker for resumable, incremental Cadu jobs."""

from __future__ import annotations

import json
import socket
import threading
from uuid import uuid4

import click
from flask import current_app
from flask.cli import with_appcontext
from psycopg.types.json import Json

from ...cadu_credit_connector import CaduCreditConnector, CreditActor
from ...cadu_family import repository
from ...cadu_planner import docs
from ..artifacts import create_draft, get_artifact, patch_artifact
from .. import web_search
from . import long_jobs, provider
from .contracts import RequestContext
from .guardrails import normalize_response
from .prompt_assembler import CORE


PHASES = {
    "discover": "Defina o mapa de investigação e os tipos de fonte necessários. Não redija a entrega final.",
    "extract": "Extraia fatos, números, trechos úteis e limitações das evidências disponíveis.",
    "classify": "Agrupe as evidências por tema, confiabilidade, data e relação com o objetivo.",
    "summarize": "Produza notas sintéticas por tema, preservando divergências e lacunas.",
    "synthesize": "Relacione os achados e construa a tese que sustentará a entrega.",
    "compose": "Redija a entrega completa em texto organizado, com profundidade e sem metacomentários.",
    "review": "Revise integralmente a versão anterior: corrija lacunas, repetição, estrutura e precisão.",
}


def _candidate(job_id=None):
    rows = repository.rows("""SELECT id::text,organization_id,client_id,user_id,conversation_id,project_ref,
        artifact_id::text,kind,title,objective,source_target,token_budget,tokens_used
        FROM cadu_agent_long_jobs job
        WHERE job.status IN ('queued','running','waiting') AND job.tokens_used < job.token_budget
          AND (%s::uuid IS NULL OR job.id=%s)
          AND EXISTS (SELECT 1 FROM cadu_agent_long_job_units unit WHERE unit.job_id=job.id
              AND unit.attempts < unit.max_attempts
              AND (unit.status='queued' OR (unit.status='running' AND unit.lease_expires_at<NOW())))
        ORDER BY job.updated_at,job.created_at LIMIT 1""", (job_id, job_id))
    return dict(rows[0]) if rows else None


def _context(job: dict) -> RequestContext:
    return RequestContext(
        organization_id=int(job["organization_id"]), client_id=int(job["client_id"]),
        user_id=int(job["user_id"]), conversation_id=str(job["conversation_id"]),
        surface="conversations", project_ref=job.get("project_ref"),
        capabilities=("workspace", "planner", "studio", "reports", "artifacts", "research"),
    )


def _prior_text(job_id: str, limit=45_000) -> str:
    rows = repository.rows("""SELECT kind,heading,content FROM cadu_agent_long_job_fragments
        WHERE job_id=%s ORDER BY ordinal""", (job_id,))
    text = "\n\n".join(
        f"[{row['kind']}] {row.get('heading') or ''}\n{row.get('content') or ''}" for row in rows
    )
    return text[-limit:]


def _source_evidence(job_id: str, limit=55_000) -> str:
    """Return bounded, extracted source material for downstream research phases."""
    rows = repository.rows("""SELECT title,url,excerpt,metadata FROM cadu_agent_long_job_sources
        WHERE job_id=%s AND status='extracted'
        ORDER BY relevance DESC NULLS LAST, extracted_at, created_at""", (job_id,))
    parts, size = [], 0
    for row in rows:
        metadata = row.get("metadata") or {}
        content = str(metadata.get("content") or row.get("excerpt") or "").strip()
        if not content:
            continue
        header = f"FONTE: {row.get('title') or 'Sem título'}\nURL: {row.get('url') or ''}\n"
        remaining = limit - size - len(header)
        if remaining <= 0:
            break
        part = header + content[:remaining]
        parts.append(part)
        size += len(part)
        if size >= limit:
            break
    return "\n\n".join(parts)


def _payload(job: dict, unit: dict, context: RequestContext) -> dict:
    previous = _prior_text(job["id"], limit=32_000)
    source_evidence = "" if unit["kind"] == "discover" else _source_evidence(job["id"])
    instruction = PHASES[unit["kind"]]
    request = (
        f"OBJETIVO DO TRABALHO:\n{job['objective']}\n\n"
        f"ETAPA ATUAL: {unit['kind']}\n{instruction}\n\n"
        f"MATERIAL PRODUZIDO NAS ETAPAS ANTERIORES:\n{previous or 'Nenhum fragmento anterior.'}\n\n"
        f"FONTES EXTRAÍDAS (use e preserve as URLs ao sustentar afirmações):\n"
        f"{source_evidence or 'Nenhuma fonte extraída nesta execução.'}"
    )
    inputs = {
        "core": CORE + "\n\nVocê está executando uma etapa interna de um trabalho longo. Entregue somente o conteúdo útil desta etapa.",
        "user_request": json.dumps({"role": "user", "text": request}, ensure_ascii=False),
        "task": json.dumps({"action": f"long_job_{unit['kind']}", "response_mode": "analysis", "execution_mode": "agentic"}),
        "current_context": json.dumps(context.to_dict(), ensure_ascii=False, default=str),
        "evidence": json.dumps({"previous_fragments": previous, "sources": source_evidence}, ensure_ascii=False),
        "response_policy": json.dumps({"max_questions": 0, "max_next_steps": 0, "artifact_in_chat": False}),
        "output_contract": json.dumps({"text": {"content": "string"}, "ui": {"confidence": "low|medium|high"}}),
    }
    inputs.update({"skill_context": inputs["core"], "projeto_context": inputs["evidence"],
                   "files_context": "", "user_memory_context": "", "user_profile_context": inputs["current_context"],
                   "is_first_message": "false"})
    return {"query": request, "user": f"user-{context.user_id}", "inputs": inputs,
            "files": unit.get("input_snapshot", {}).get("files") or [], "response_mode": "streaming"}


def _generate(job: dict, unit: dict, context: RequestContext) -> tuple[str, dict]:
    chunks, usage = [], {}
    for event in provider.events(_payload(job, unit, context), "agentic"):
        if event.get("event") in {"message", "agent_message"} and event.get("answer"):
            chunks.append(str(event["answer"]))
        if event.get("event") == "message_end":
            usage = (event.get("metadata") or {}).get("usage") or {}
    response = normalize_response("".join(chunks), {"max_questions": 0, "max_next_steps": 0, "artifact_in_chat": False})
    content = str(response.answer or "").strip()
    if not content:
        raise RuntimeError("O agente não produziu conteúdo para esta etapa.")
    return content, usage


def _discover(job: dict, unit: dict, context: RequestContext) -> tuple[str, dict, list[str]]:
    result = web_search.search(context, {
        "query": job["objective"], "depth": "agentic", "limit": int(job.get("source_target") or 5),
        "include_content": True, "request_id": f"long-job:{job['id']}:{unit['id']}",
    })
    sources = long_jobs.add_sources(job["id"], context, result.get("sources") or [])
    if not sources:
        raise RuntimeError("A pesquisa não encontrou fontes públicas utilizáveis.")
    lines = [f"- {source['title']} — {source['url']}\n  {source.get('excerpt') or ''}" for source in sources]
    return "Fontes descobertas e preparadas para extração:\n\n" + "\n".join(lines), {}, [source["id"] for source in sources]


def _tokens(usage: dict) -> int:
    return max(0, int(usage.get("total_tokens") or 0))


def _save_artifact(job: dict, context: RequestContext, content: str, phase: str) -> dict:
    artifact_id = str(job.get("artifact_id") or "")
    payload = {"title": job["title"], "html": docs.markdown_to_safe_html(content)}
    if artifact_id:
        current = get_artifact(context, artifact_id)
        return patch_artifact(context, artifact_id, payload, expected_version=current["current_version"],
                              title=job["title"], change_summary=f"Trabalho longo · {phase}")
    artifact = create_draft(context, "document", payload, title=job["title"], conversation_id=job["conversation_id"])
    connection = repository.get_db()
    with connection.cursor() as cursor:
        cursor.execute("UPDATE cadu_agent_long_jobs SET artifact_id=%s,updated_at=NOW() WHERE id=%s",
                       (str(artifact["id"]), job["id"]))
    connection.commit()
    job["artifact_id"] = str(artifact["id"])
    return artifact


def _persist_completion(job: dict, context: RequestContext, artifact: dict) -> None:
    answer = "Concluí o trabalho e preparei o documento para revisão e edição."
    response = {
        "answer": answer, "confidence": "high", "assumptions": [], "questions": [], "actions": [],
        "artifact_patch": {"type": "document", "title": artifact.get("title") or job["title"]},
        "citations": [], "blocks": [],
    }
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT 1 FROM cadu_conversation_messages
                WHERE conversation_id=%s AND metadata->>'long_job_id'=%s LIMIT 1""",
                (job["conversation_id"], job["id"]))
            if cursor.fetchone():
                connection.commit()
                return
            cursor.execute("""INSERT INTO cadu_conversation_messages
                (id,conversation_id,role,content,tokens_entrada,tokens_saida,metadata,created_at)
                VALUES (%s,%s,'assistant',%s,0,%s,%s,NOW())""",
                (str(uuid4()), job["conversation_id"], answer, int(job.get("tokens_used") or 0),
                 Json({"runtime": "v2-long-job", "long_job_id": job["id"], "response": response,
                       "artifact_id": str(artifact["id"])})))
            cursor.execute("""UPDATE cadu_conversations SET
                total_mensagens=(SELECT COUNT(*) FROM cadu_conversation_messages WHERE conversation_id=%s),
                total_tokens_saida=COALESCE(total_tokens_saida,0)+%s,updated_at=NOW() WHERE id=%s""",
                (job["conversation_id"], int(job.get("tokens_used") or 0), job["conversation_id"]))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def process_one(worker_id="", job_id=None) -> bool:
    job = _candidate(job_id)
    if not job:
        return False
    context = _context(job)
    worker_id = worker_id or f"{socket.gethostname()}:{uuid4().hex[:8]}"
    unit = long_jobs.claim_next_unit(job["id"], context, worker_id, lease_seconds=900)
    if not unit:
        return False
    try:
        if unit["kind"] == "render":
            fragments = long_jobs.snapshot(job["id"], context)["fragments"]
            candidates = [item for item in fragments if item["kind"] in {"revision", "section", "final"}]
            if not candidates:
                raise RuntimeError("Não há conteúdo composto para renderizar.")
            content, usage = candidates[-1]["content"], {}
            artifact = _save_artifact(job, context, content, "render")
            output = {"artifact_id": str(artifact["id"]), "version": artifact["current_version"]}
        else:
            CaduCreditConnector().authorize(CreditActor.from_values(context.client_id, context.user_id),
                                            min(8_000, max(1_000, int(job["token_budget"]) - int(job["tokens_used"]))))
            if unit["kind"] == "discover":
                content, usage, source_ids = _discover(job, unit, context)
            else:
                content, usage = _generate(job, unit, context)
                source_ids = []
            kind = "revision" if unit["kind"] == "review" else "section"
            fragment = long_jobs.append_fragment(job["id"], context, content, unit_id=unit["id"],
                                                 kind=kind, heading=unit["kind"].capitalize(), source_ids=source_ids)
            output = {"fragment_id": fragment["id"], "ordinal": fragment["ordinal"]}
            if unit["kind"] in {"compose", "review"}:
                artifact = _save_artifact(job, context, content, unit["kind"])
                output.update({"artifact_id": str(artifact["id"]), "version": artifact["current_version"]})
            try:
                CaduCreditConnector().charge_provider(
                    actor=CreditActor.from_values(context.client_id, context.user_id),
                    idempotency_key=f"long-job:{job['id']}:{unit['id']}:{unit['attempts']}",
                    app="Cadu Chat", stage=f"trabalho-longo:{unit['kind']}",
                    provider_result={"usage": usage, "model": "cadu-operator"},
                    metadata={"conversation_id": job["conversation_id"], "long_job_id": job["id"], "unit_id": unit["id"]},
                )
            except Exception:
                current_app.logger.exception("Cobrança pendente para etapa %s do trabalho %s", unit["id"], job["id"])
        completion = long_jobs.complete_unit(
            job["id"], unit["id"], context, output=output, token_usage=_tokens(usage),
            checkpoint={"position": unit["position"], "kind": unit["kind"], **output},
        )
        if completion["job_status"] == "completed" and output.get("artifact_id"):
            job["tokens_used"] = completion["tokens_used"]
            _persist_completion(job, context, get_artifact(context, output["artifact_id"]))
    except Exception as exc:
        long_jobs.complete_unit(job["id"], unit["id"], context, error_code=type(exc).__name__,
                                checkpoint={"position": unit["position"], "kind": unit["kind"], "error": str(exc)[:500]})
        raise
    return True


def dispatch(job_id: str) -> None:
    """Best-effort immediate execution; the supervised worker remains the recovery path."""
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            worker = f"web:{socket.gethostname()}:{uuid4().hex[:8]}"
            while True:
                try:
                    if not process_one(worker, job_id=str(job_id)):
                        return
                except Exception:
                    app.logger.exception("Trabalho longo %s interrompido; o supervisor poderá retomá-lo.", job_id)
                    return

    threading.Thread(target=run, daemon=True, name=f"cadu-long-job-{str(job_id)[:12]}").start()


@click.command("long-job-worker-once")
@with_appcontext
def worker_command():
    """Process one resumable unit from the durable Cadu queue."""
    click.echo("Etapa processada." if process_one() else "Fila vazia.")
