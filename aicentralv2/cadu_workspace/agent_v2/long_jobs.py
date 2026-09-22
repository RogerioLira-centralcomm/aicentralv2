"""Contracts and persistence primitives for resumable multi-call agent work."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from uuid import uuid4
import re
from urllib.parse import urlsplit, urlunsplit

from psycopg.types.json import Json

from ...cadu_family import repository
from .contracts import RequestContext


KINDS = {"deep_research", "long_document", "multi_source_analysis", "artifact_revision"}
UNIT_KINDS = {"discover", "extract", "classify", "summarize", "synthesize", "compose", "review", "render"}


def spec_for_message(message: str) -> LongJobSpec | None:
    """Route only explicit substantial deliverables; ordinary chat remains synchronous."""
    text = " ".join(str(message or "").lower().split())
    if not text or re.search(r"\bn[aã]o\s+(?:crie|abra|gere)\s+(?:um\s+)?artefato\b", text):
        return None
    word_match = re.search(r"(?:cerca de|aproximadamente|mínimo de|ao menos)?\s*([1-9][\d.]{2,5})\s+palavras", text)
    word_count = int(word_match.group(1).replace(".", "")) if word_match else 0
    source_match = re.search(r"(?:até|de|com|menos)\s+(\d{1,2})\s+fontes", text)
    asks_research = any(term in text for term in ("pesquise", "pesquisa", "fontes", "internet", "web"))
    asks_artifact = "artefato" in text or "documento editável" in text or "documento editavel" in text
    explicit_long = any(term in text for term in (
        "pesquisa profunda", "relatório completo", "relatorio completo", "guia completo",
        "documento completo", "documento extenso", "análise aprofundada", "analise aprofundada", "trabalho longo",
    ))
    substantial_research = asks_research and asks_artifact and bool(source_match) and int(source_match.group(1)) >= 5
    if word_count < 1200 and not explicit_long and not substantial_research:
        return None
    source_target = min(40, max(5, int(source_match.group(1)))) if source_match else (12 if asks_research else 0)
    title = "Pesquisa aprofundada" if asks_research else "Documento em elaboração"
    return LongJobSpec(
        kind="deep_research" if asks_research else "long_document", title=title,
        objective=str(message or "").strip(), source_target=source_target,
        max_agent_calls=12 if asks_research else 5,
        max_extractor_calls=min(80, max(source_target, source_target * 2)),
        token_budget=120_000 if asks_research else 60_000,
    ).validated()


@dataclass(frozen=True)
class LongJobSpec:
    kind: str
    title: str
    objective: str
    source_target: int = 5
    max_agent_calls: int = 8
    max_extractor_calls: int = 40
    token_budget: int = 40_000

    def validated(self) -> "LongJobSpec":
        if self.kind not in KINDS:
            raise ValueError("Tipo de trabalho longo inválido.")
        title = " ".join(str(self.title or "").split())[:180]
        objective = " ".join(str(self.objective or "").split())[:20_000]
        if not title or not objective:
            raise ValueError("Título e objetivo são obrigatórios.")
        if not 0 <= int(self.source_target) <= 40:
            raise ValueError("A pesquisa aceita entre 0 e 40 fontes.")
        if not 1 <= int(self.max_agent_calls) <= 40:
            raise ValueError("Limite de chamadas de agente inválido.")
        if not 0 <= int(self.max_extractor_calls) <= 80:
            raise ValueError("Limite de extratores inválido.")
        if not 1_000 <= int(self.token_budget) <= 1_000_000:
            raise ValueError("Orçamento de tokens inválido.")
        return LongJobSpec(self.kind, title, objective, int(self.source_target), int(self.max_agent_calls),
                           int(self.max_extractor_calls), int(self.token_budget))


def default_units(spec: LongJobSpec) -> list[dict]:
    spec = spec.validated()
    kinds = (["discover", "extract", "classify", "summarize", "synthesize", "compose", "review", "render"]
             if spec.source_target else ["compose", "review", "render"])
    return [{"position": index, "kind": kind, "status": "queued"} for index, kind in enumerate(kinds, 1)]


def create(context: RequestContext, conversation_id: str, spec: LongJobSpec, *, run_id=None,
           artifact_id=None, idempotency_key="") -> dict:
    spec = spec.validated()
    job_id = str(uuid4())
    units = default_units(spec)
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO cadu_agent_long_jobs
                (id,run_id,conversation_id,artifact_id,organization_id,client_id,user_id,project_ref,
                 kind,title,objective,source_target,max_agent_calls,max_extractor_calls,token_budget,idempotency_key)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (client_id,user_id,idempotency_key)
                DO UPDATE SET updated_at=NOW() RETURNING id::text,status,created_at""",
                (job_id, run_id, conversation_id, artifact_id, context.organization_id, context.client_id,
                 context.user_id, context.project_ref, spec.kind, spec.title, spec.objective,
                 spec.source_target, spec.max_agent_calls, spec.max_extractor_calls, spec.token_budget,
                 idempotency_key or None))
            job = dict(cursor.fetchone())
            if job["id"] == job_id:
                for unit in units:
                    cursor.execute("""INSERT INTO cadu_agent_long_job_units
                        (id,job_id,position,kind,status,input_snapshot) VALUES (%s,%s,%s,%s,'queued',%s)""",
                        (str(uuid4()), job_id, unit["position"], unit["kind"], Json({"objective": spec.objective})))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {**job, "spec": asdict(spec), "units": units}


def fragment_hash(content: str) -> str:
    return sha256(str(content or "").encode("utf-8")).hexdigest()


def add_sources(job_id: str, context: RequestContext, sources: list[dict]) -> list[dict]:
    connection = repository.get_db()
    saved = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT id,status,source_target FROM cadu_agent_long_jobs
                WHERE id=%s AND organization_id=%s AND client_id=%s AND user_id=%s FOR UPDATE""",
                (job_id, context.organization_id, context.client_id, context.user_id))
            job = cursor.fetchone()
            if not job or job["status"] in {"cancelled", "failed", "completed", "budget_exhausted"}:
                raise ValueError("O trabalho não aceita novas fontes.")
            for item in (sources or [])[:int(job["source_target"] or 0)]:
                url = str(item.get("url") or "").strip()
                try:
                    parsed = urlsplit(url)
                except ValueError:
                    continue
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    continue
                canonical = urlunsplit(("https", parsed.hostname.lower(), parsed.path.rstrip("/") or "/", parsed.query, ""))
                source_id = str(uuid4())
                content = str(item.get("content") or "")[:60_000]
                cursor.execute("""INSERT INTO cadu_agent_long_job_sources
                    (id,job_id,url,canonical_url,title,source_type,status,relevance,content_hash,excerpt,metadata,extracted_at)
                    VALUES (%s,%s,%s,%s,%s,'web',%s,%s,%s,%s,%s,CASE WHEN %s THEN NOW() END)
                    ON CONFLICT (job_id,canonical_url) DO UPDATE SET title=EXCLUDED.title,status=EXCLUDED.status,
                    relevance=EXCLUDED.relevance,content_hash=EXCLUDED.content_hash,excerpt=EXCLUDED.excerpt,
                    metadata=EXCLUDED.metadata,extracted_at=EXCLUDED.extracted_at
                    RETURNING id::text,url,title,status,excerpt,metadata""",
                    (source_id, job_id, url[:4000], canonical[:4000], str(item.get("title") or parsed.hostname)[:500],
                     "extracted" if content else "discovered", item.get("score"), fragment_hash(content) if content else None,
                     str(item.get("excerpt") or item.get("content_excerpt") or content[:520])[:2000],
                     Json({"content": content, "published_at": item.get("published_at"), "favicon": item.get("favicon")}),
                     bool(content)))
                saved.append(dict(cursor.fetchone()))
        connection.commit()
        return saved
    except Exception:
        connection.rollback()
        raise


def append_fragment(job_id: str, context: RequestContext, content: str, *, unit_id=None,
                    kind="section", heading="", source_ids=None, supersedes_id=None) -> dict:
    """Append an immutable text fragment, deduplicating retries by content hash."""
    content = str(content or "").strip()
    if not content:
        raise ValueError("O fragmento não pode ser vazio.")
    if kind not in {"note", "evidence", "section", "revision", "final"}:
        raise ValueError("Tipo de fragmento inválido.")
    digest = fragment_hash(content)
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT id,status FROM cadu_agent_long_jobs
                WHERE id=%s AND organization_id=%s AND client_id=%s AND user_id=%s FOR UPDATE""",
                (job_id, context.organization_id, context.client_id, context.user_id))
            job = cursor.fetchone()
            if not job:
                raise ValueError("Trabalho longo indisponível.")
            if job["status"] in {"cancelled", "failed", "budget_exhausted", "completed"}:
                raise ValueError("O trabalho não aceita novos fragmentos.")
            cursor.execute("""SELECT id::text,ordinal,kind,heading,content,source_ids,created_at
                FROM cadu_agent_long_job_fragments WHERE job_id=%s AND content_hash=%s""", (job_id, digest))
            existing = cursor.fetchone()
            if existing:
                connection.commit()
                return dict(existing)
            cursor.execute("""SELECT COALESCE(MAX(ordinal),0)+1 AS ordinal
                FROM cadu_agent_long_job_fragments WHERE job_id=%s""", (job_id,))
            ordinal = int(cursor.fetchone()["ordinal"])
            fragment_id = str(uuid4())
            cursor.execute("""INSERT INTO cadu_agent_long_job_fragments
                (id,job_id,unit_id,ordinal,kind,heading,content,source_ids,content_hash,supersedes_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id::text,ordinal,kind,heading,content,source_ids,created_at""",
                (fragment_id, job_id, unit_id, ordinal, kind, str(heading or "")[:300], content,
                 list(source_ids or []), digest, supersedes_id))
            fragment = dict(cursor.fetchone())
            cursor.execute("UPDATE cadu_agent_long_jobs SET updated_at=NOW() WHERE id=%s", (job_id,))
        connection.commit()
        return fragment
    except Exception:
        connection.rollback()
        raise


def claim_next_unit(job_id: str, context: RequestContext, worker_id: str, *, lease_seconds=120) -> dict | None:
    """Claim one resumable unit. Expired leases can safely be reclaimed by another worker."""
    worker_id = str(worker_id or "").strip()[:180]
    if not worker_id:
        raise ValueError("Identificador do worker é obrigatório.")
    lease_seconds = max(30, min(int(lease_seconds), 900))
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT id,status,token_budget,tokens_used FROM cadu_agent_long_jobs
                WHERE id=%s AND organization_id=%s AND client_id=%s AND user_id=%s FOR UPDATE""",
                (job_id, context.organization_id, context.client_id, context.user_id))
            job = cursor.fetchone()
            if not job:
                raise ValueError("Trabalho longo indisponível.")
            if job["status"] in {"completed", "failed", "cancelled", "budget_exhausted", "paused"}:
                connection.commit()
                return None
            if int(job["tokens_used"] or 0) >= int(job["token_budget"] or 0):
                cursor.execute("""UPDATE cadu_agent_long_jobs SET status='budget_exhausted',
                    finished_at=NOW(),updated_at=NOW(),lease_owner=NULL,lease_expires_at=NULL WHERE id=%s""", (job_id,))
                connection.commit()
                return None
            cursor.execute("""SELECT id::text,position,kind,input_snapshot,attempts,max_attempts
                FROM cadu_agent_long_job_units
                WHERE job_id=%s AND attempts < max_attempts
                  AND (status='queued' OR (status='running' AND lease_expires_at < NOW()))
                ORDER BY position FOR UPDATE SKIP LOCKED LIMIT 1""", (job_id,))
            unit = cursor.fetchone()
            if not unit:
                connection.commit()
                return None
            cursor.execute("""UPDATE cadu_agent_long_job_units SET status='running',attempts=attempts+1,
                lease_owner=%s,lease_expires_at=NOW()+(%s*INTERVAL '1 second'),
                started_at=COALESCE(started_at,NOW()),updated_at=NOW() WHERE id=%s
                RETURNING id::text,position,kind,status,input_snapshot,attempts,max_attempts,lease_expires_at""",
                (worker_id, lease_seconds, unit["id"]))
            claimed = dict(cursor.fetchone())
            cursor.execute("""UPDATE cadu_agent_long_jobs SET status='running',lease_owner=%s,
                lease_expires_at=NOW()+(%s*INTERVAL '1 second'),started_at=COALESCE(started_at,NOW()),updated_at=NOW()
                WHERE id=%s""", (worker_id, lease_seconds, job_id))
        connection.commit()
        return claimed
    except Exception:
        connection.rollback()
        raise


def complete_unit(job_id: str, unit_id: str, context: RequestContext, *, output=None,
                  token_usage=0, error_code=None, checkpoint=None) -> dict:
    """Commit unit output and budget usage atomically so a restart never loses progress."""
    token_usage = max(0, int(token_usage or 0))
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT id,status,token_budget,tokens_used FROM cadu_agent_long_jobs
                WHERE id=%s AND organization_id=%s AND client_id=%s AND user_id=%s FOR UPDATE""",
                (job_id, context.organization_id, context.client_id, context.user_id))
            job = cursor.fetchone()
            if not job:
                raise ValueError("Trabalho longo indisponível.")
            if job["status"] == "cancelled":
                cursor.execute("""UPDATE cadu_agent_long_job_units SET status='cancelled',token_usage=token_usage+%s,
                    lease_owner=NULL,lease_expires_at=NULL,updated_at=NOW(),finished_at=NOW()
                    WHERE id=%s AND job_id=%s AND status='running' RETURNING id::text,position,kind,status,
                    token_usage,error_code,output_snapshot,attempts,max_attempts""", (token_usage, unit_id, job_id))
                unit = cursor.fetchone()
                if not unit:
                    raise ValueError("Etapa não está em execução ou já foi concluída.")
                tokens_used = int(job["tokens_used"] or 0) + token_usage
                cursor.execute("UPDATE cadu_agent_long_jobs SET tokens_used=%s,updated_at=NOW() WHERE id=%s",
                               (tokens_used, job_id))
                connection.commit()
                return {"unit": dict(unit), "job_status": "cancelled", "tokens_used": tokens_used,
                        "token_budget": int(job["token_budget"] or 0)}
            cursor.execute("""UPDATE cadu_agent_long_job_units SET status=%s,output_snapshot=%s,
                token_usage=token_usage+%s,error_code=%s,lease_owner=NULL,lease_expires_at=NULL,
                updated_at=NOW(),finished_at=NOW() WHERE id=%s AND job_id=%s AND status='running'
                RETURNING id::text,position,kind,status,token_usage,error_code,output_snapshot,attempts,max_attempts""",
                ("failed" if error_code else "completed", Json(output or {}), token_usage,
                 str(error_code or "")[:100] or None, unit_id, job_id))
            unit = cursor.fetchone()
            if not unit:
                raise ValueError("Etapa não está em execução ou já foi concluída.")
            tokens_used = int(job["tokens_used"] or 0) + token_usage
            cursor.execute("""SELECT COUNT(*) AS pending FROM cadu_agent_long_job_units
                WHERE job_id=%s AND status NOT IN ('completed','skipped','cancelled')""", (job_id,))
            pending = int(cursor.fetchone()["pending"])
            if tokens_used >= int(job["token_budget"] or 0):
                status = "budget_exhausted"
            elif error_code and int(unit["attempts"]) < int(unit["max_attempts"]):
                status = "waiting"
                cursor.execute("""UPDATE cadu_agent_long_job_units SET status='queued',finished_at=NULL
                    WHERE id=%s""", (unit_id,))
            elif error_code:
                status = "failed"
            elif pending == 0:
                status = "completed"
            else:
                status = "running"
            finished = status in {"completed", "failed", "budget_exhausted"}
            cursor.execute("""UPDATE cadu_agent_long_jobs SET status=%s,tokens_used=%s,
                checkpoint=COALESCE(%s,checkpoint),lease_owner=NULL,lease_expires_at=NULL,updated_at=NOW(),
                finished_at=CASE WHEN %s THEN NOW() ELSE finished_at END WHERE id=%s""",
                (status, tokens_used, Json(checkpoint) if checkpoint is not None else None, finished, job_id))
        connection.commit()
        return {"unit": dict(unit), "job_status": status, "tokens_used": tokens_used,
                "token_budget": int(job["token_budget"] or 0)}
    except Exception:
        connection.rollback()
        raise


def cancel(job_id: str, context: RequestContext) -> bool:
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_agent_long_jobs SET status='cancelled',finished_at=NOW(),updated_at=NOW(),
                lease_owner=NULL,lease_expires_at=NULL WHERE id=%s AND organization_id=%s AND client_id=%s
                AND user_id=%s AND status IN ('queued','running','waiting','paused')""",
                (job_id, context.organization_id, context.client_id, context.user_id))
            changed = cursor.rowcount == 1
            cursor.execute("""UPDATE cadu_agent_long_job_units SET status='cancelled',finished_at=NOW(),updated_at=NOW(),
                lease_owner=NULL,lease_expires_at=NULL WHERE job_id=%s AND status IN ('queued','waiting')""", (job_id,))
        connection.commit()
        return changed
    except Exception:
        connection.rollback()
        raise


def snapshot(job_id: str, context: RequestContext) -> dict:
    jobs = repository.rows("""SELECT id::text,run_id::text,conversation_id,artifact_id::text,kind,status,title,
        objective,source_target,max_agent_calls,max_extractor_calls,token_budget,tokens_used,checkpoint,
        result_summary,created_at,started_at,updated_at,finished_at
        FROM cadu_agent_long_jobs WHERE id=%s AND organization_id=%s AND client_id=%s AND user_id=%s""",
        (job_id, context.organization_id, context.client_id, context.user_id))
    if not jobs:
        raise ValueError("Trabalho longo indisponível.")
    units = repository.rows("""SELECT id::text,parent_id::text,position,kind,status,attempts,max_attempts,
        token_usage,error_code,output_snapshot,started_at,finished_at FROM cadu_agent_long_job_units
        WHERE job_id=%s ORDER BY position""", (job_id,))
    sources = repository.rows("""SELECT id::text,url,title,source_type,status,relevance,excerpt,metadata
        FROM cadu_agent_long_job_sources WHERE job_id=%s ORDER BY relevance DESC NULLS LAST,discovered_at""", (job_id,))
    fragments = repository.rows("""SELECT id::text,unit_id::text,ordinal,kind,heading,content,source_ids,
        supersedes_id::text,created_at FROM cadu_agent_long_job_fragments WHERE job_id=%s ORDER BY ordinal""", (job_id,))
    return {"job": jobs[0], "units": units, "sources": sources, "fragments": fragments}
