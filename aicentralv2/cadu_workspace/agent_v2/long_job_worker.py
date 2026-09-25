"""Supervised worker for resumable, incremental Cadu jobs."""

from __future__ import annotations

import json
import hashlib
import math
import re
import socket
import threading
from urllib.parse import urlsplit
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
from .market_intelligence import MAX_QUERIES, call as mi_call, profile_for, total_tokens as mi_tokens
from .guardrails import normalize_response
from .prompt_assembler import CORE
from ..mcp.registry import load_builtin_tools
from .context_resolver import public_web_query


PHASES = {
    "discover": "Defina o mapa de investigação e os tipos de fonte necessários. Não redija a entrega final.",
    "extract": "Extraia fatos, números, trechos úteis e limitações das evidências disponíveis.",
    "classify": "Agrupe as evidências por tema, confiabilidade, data e relação com o objetivo.",
    "summarize": "Produza notas sintéticas por tema, preservando divergências e lacunas.",
    "synthesize": "Relacione os achados e construa a tese que sustentará a entrega.",
    "compose": "Redija a entrega completa em texto organizado, com profundidade e sem metacomentários.",
    "review": "Revise integralmente a versão anterior: corrija lacunas, repetição, estrutura e precisão.",
    "plan": "Decomponha o objetivo em questões independentes de pesquisa. Use contexto privado somente para orientar a síntese, nunca o envie como consulta pública.",
    "gap_analysis": "Identifique quais questões ainda não têm evidência suficiente e proponha consultas públicas adicionais.",
    "followup_search": "Busque fontes adicionais para responder somente às lacunas identificadas.",
    "analyze": "Analise exclusivamente as evidências persistidas e o contexto autorizado fornecido.",
    "critic": "Desafie as conclusões como revisor independente; retorne apenas problemas concretos e correções recomendadas.",
    "evidence_check": "Verifique se cada afirmação factual importante possui suporte nas evidências citadas.",
}


def _mi_request_id(job: dict, unit: dict, stage: str) -> str:
    raw = f"{job['id']}:{unit['id']}:{stage}"
    return "mi-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def _candidate(job_id=None):
    rows = repository.rows("""SELECT id::text,client_id,user_id,conversation_id,project_ref,brand_ref,
        artifact_id::text,kind,title,objective,source_target,token_budget,tokens_used,mode,workflow_config
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
        client_id=int(job["client_id"]),
        user_id=int(job["user_id"]), conversation_id=str(job["conversation_id"]),
        surface="conversations", project_ref=job.get("project_ref"),
        brand_ref=job.get("brand_ref"),
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
    return mi_tokens(usage)


def _merge_usage(total: dict, current: dict) -> dict:
    for key in ("prompt_tokens", "completion_tokens", "input_tokens", "output_tokens", "total_tokens", "cost"):
        try:
            value = float((current or {}).get(key) or 0)
        except (TypeError, ValueError):
            continue
        if value:
            total[key] = total.get(key, 0) + value
    return total


def _mi_profile(job: dict) -> dict:
    config = job.get("workflow_config") if isinstance(job.get("workflow_config"), dict) else {}
    return profile_for(job.get("mode") or config.get("mode") or "deep", config)


def _mi_call(job: dict, unit: dict, role: str, system: str, prompt: str, *, json_output=False,
             max_tokens=1800, call_index=0) -> dict:
    usage_state = long_jobs.model_call_usage(job["id"])
    config = _mi_profile(job)
    if role == "structured_extractor":
        if int(usage_state.get("extractor_calls") or 0) >= int(job.get("max_extractor_calls") or config["max_extractor_calls"]):
            raise RuntimeError("O limite de chamadas de extração deste trabalho foi atingido.")
    elif int(usage_state.get("agent_calls") or 0) >= int(job.get("max_agent_calls") or config["max_agent_calls"]):
        raise RuntimeError("O limite de chamadas de análise deste trabalho foi atingido.")
    used_tokens = max(int(job.get("tokens_used") or 0), int(usage_state.get("tokens") or 0))
    remaining_tokens = max(0, int(job.get("token_budget") or 0) - used_tokens)
    input_estimate = max(1, (len(system) + len(prompt)) // 3)
    output_limit = min(int(max_tokens), remaining_tokens - input_estimate)
    if output_limit < 128:
        raise RuntimeError("O orçamento de tokens do trabalho foi atingido.")
    CaduCreditConnector().authorize(
        CreditActor.from_values(int(job["client_id"]), int(job["user_id"])),
        min(8_000, max(1_000, input_estimate + output_limit)),
    )
    result = mi_call(role, system, prompt, json_output=json_output, max_tokens=output_limit,
                     model=(config.get("model_roles") or {}).get(role, ""))
    long_jobs.record_model_call(
        job["id"], unit["id"], role=role, provider=result["provider"], model=result["model"],
        usage=result["usage"], idempotency_key=f"{unit['id']}:{unit['attempts']}:{call_index}:{role}",
    )
    return result


def _mi_private_context(context: RequestContext, *, include_project=True) -> dict:
    """Resolve only authorized, bounded context; it never goes to public search."""
    registry = load_builtin_tools()
    result = {}
    if context.brand_ref:
        try:
            brand = registry.execute("brands.get_context", {}, context)
            if isinstance(brand, dict):
                result["brand"] = {key: brand.get(key) for key in
                    ("name", "sector", "website_url", "identity", "market", "campaigns") if brand.get(key)}
        except Exception:
            result["brand_context_status"] = "unavailable"
    if include_project and context.project_ref:
        try:
            project = registry.execute("workspace.get_project_context", {"query": "contexto e objetivo do projeto"}, context)
            if isinstance(project, dict):
                # Preserve the project packet for synthesis, but exclude it from search planning.
                result["project"] = project
        except Exception:
            result["project_context_status"] = "unavailable"
    return result


def _mi_public_seed(job: dict, private_context: dict) -> str:
    """Create a public-only search seed from user intent and approved brand facts."""
    brand = private_context.get("brand") if isinstance(private_context.get("brand"), dict) else {}
    pieces = [" ".join(str(job.get("objective") or "").split())[:400]]
    # Brand name, official sector and registered competitors are approved public identifiers.
    for value in (brand.get("name"), brand.get("sector")):
        if value:
            pieces.append(str(value)[:100])
    market = brand.get("market") if isinstance(brand.get("market"), dict) else {}
    competitors = market.get("competitors") or []
    if isinstance(competitors, str):
        competitors = re.split(r"[,;\n]+", competitors)
    for item in competitors[:8]:
        value = item.get("name") if isinstance(item, dict) else item
        if value:
            pieces.append(str(value)[:80])
    seed = " ".join(pieces)
    cleaned = public_web_query(seed, project_selected=bool(job.get("project_ref")), min_terms=1)
    # public_web_query intentionally allowlists query terms; re-add only the approved brand identifier.
    brand_name = " ".join(str(brand.get("name") or "").split())
    if brand_name and brand_name.casefold() not in cleaned.casefold():
        cleaned = f"{brand_name} {cleaned}".strip()
    return cleaned[:400]


def _mi_evidence_payload(job_id: str, limit=42_000) -> tuple[str, list[dict]]:
    rows = repository.rows("""SELECT id::text,title,url,excerpt,metadata,relevance,status
        FROM cadu_agent_long_job_sources WHERE job_id=%s
        ORDER BY relevance DESC NULLS LAST,discovered_at LIMIT 150""", (job_id,))
    serialized = []
    parts, size = [], 0
    for index, row in enumerate(rows, 1):
        metadata = row.get("metadata") or {}
        item = {"source_no": index, "source_id": row["id"], "title": row.get("title") or "Sem título",
                "url": row.get("url") or "", "published_at": metadata.get("published_at") or "",
                "status": row.get("status"), "relevance": row.get("relevance")}
        serialized.append(item)
        if row.get("status") == "extracted" and row.get("excerpt") and len(parts) < 15:
            excerpt = json.dumps({"source_no": index, "source_id": row["id"],
                                  "excerpt": str(row["excerpt"])[:420]}, ensure_ascii=False)
            if size + len(excerpt) <= limit // 4:
                parts.append(excerpt)
                size += len(excerpt)
    id_to_source = {str(item["source_id"]): item for item in serialized}
    fragments = repository.rows("""SELECT heading,content FROM cadu_agent_long_job_fragments
        WHERE job_id=%s AND kind='evidence' AND heading LIKE 'evidence_batch_%%' ORDER BY ordinal""", (job_id,))
    claim_count = 0
    for fragment in fragments:
        try:
            claims = (json.loads(fragment.get("content") or "{}") or {}).get("claims") or []
        except (TypeError, ValueError):
            claims = []
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            source = id_to_source.get(str(claim.get("source_id") or ""))
            if not source or source["status"] != "extracted":
                continue
            item = {"source_no": source["source_no"], "source_id": source["source_id"],
                    "title": source["title"], "url": source["url"],
                    "published_at": source["published_at"], "claim": str(claim.get("claim") or "")[:500],
                    "entity": str(claim.get("entity") or "")[:100], "topic": str(claim.get("topic") or "")[:100],
                    "quote": str(claim.get("quote") or "")[:500], "confidence": claim.get("confidence")}
            encoded = json.dumps(item, ensure_ascii=False)
            if size + len(encoded) > limit:
                continue
            parts.append(encoded)
            size += len(encoded)
            claim_count += 1
    if not claim_count:
        for item in (source for source in serialized if source["status"] == "extracted"):
            row = next((source for source in rows if str(source["id"]) == str(item["source_id"])), {})
            metadata = row.get("metadata") or {}
            content = str(metadata.get("content") or row.get("excerpt") or "").strip()
            if not content:
                continue
            encoded = json.dumps({**item, "content": content[:1500]}, ensure_ascii=False)
            if size + len(encoded) <= limit:
                parts.append(encoded)
                size += len(encoded)
    return "\n".join(parts), serialized


def _mi_run_search(job: dict, unit: dict, context: RequestContext, private_context: dict, *, followup=False) -> tuple[str, dict, list[str]]:
    config = _mi_profile(job)
    public_seed = _mi_public_seed(job, private_context)
    if followup:
        gap = next((row["content"] for row in repository.rows(
            "SELECT content FROM cadu_agent_long_job_fragments WHERE job_id=%s AND heading='gap_analysis' ORDER BY ordinal DESC LIMIT 1",
            (job["id"],))), "")
        try:
            gap_data = json.loads(gap)
        except (TypeError, ValueError):
            gap_data = {}
        if gap_data.get("sufficient") or not gap_data.get("gaps"):
            return json.dumps({"status": "skipped", "reason": "Não foram identificadas lacunas relevantes."}, ensure_ascii=False), {}, []
        raw_gaps = gap_data.get("gaps") or []
        if not isinstance(raw_gaps, list):
            raw_gaps = [raw_gaps]
        safe_gaps = [public_web_query(str(item)[:500], project_selected=True, min_terms=1)
                     for item in raw_gaps[:12]]
        safe_gaps = [item for item in safe_gaps if item]
        prompt = (f"Objetivo público aprovado: {public_seed}\n"
                  f"Lacunas públicas filtradas: {json.dumps(safe_gaps, ensure_ascii=False)}\n"
                  "Crie consultas adicionais somente com esses termos públicos.")
    else:
        prompt = (f"Contexto público aprovado: {public_seed}\n"
                  "Gere até 5 consultas complementares para pesquisa de mercado atual usando apenas este contexto público.")
    system = ('Gere consultas web concisas em JSON: {"queries":["..."]}. Use somente termos presentes no contexto público '
              'aprovado ou termos gerais de mercado. Não inclua URLs, dados pessoais ou detalhes privados. '
              + ("Respeite esta preferência de fontes: " + str(config.get("source_preferences"))[:1500]
                 if config.get("source_preferences") else ""))
    prior_searches = repository.rows("""SELECT content FROM cadu_agent_long_job_fragments
        WHERE job_id=%s AND heading IN ('discover','followup_search') ORDER BY ordinal""", (job["id"],))
    already_used = 0
    for prior in prior_searches:
        try:
            already_used += len((json.loads(prior["content"]) or {}).get("queries") or [])
        except (TypeError, ValueError):
            pass
    query_limit = min(5, max(0, int(config["max_queries"]) - already_used))
    if query_limit <= 0:
        return json.dumps({"status": "skipped", "reason": "Limite de consultas atingido."}, ensure_ascii=False), {}, []
    queries_result = _mi_call(job, unit, "query_generator", system, prompt, json_output=True,
                              max_tokens=900, call_index=0)
    queries = (queries_result.get("json") or {}).get("queries") or []
    queries = [" ".join(str(query).split())[:400] for query in queries if len(str(query).strip()) >= 4]
    if not queries:
        queries = [public_seed]
    queries = list(dict.fromkeys(queries))[:min(query_limit, MAX_QUERIES)]
    profile = str(job.get("mode") or "deep")
    remaining = max(0, int(job.get("source_target") or 0) - len(long_jobs.snapshot(job["id"], context)["sources"]))
    if remaining <= 0:
        return "O limite de fontes já foi atingido.", queries_result["usage"], []
    usage_total = dict(queries_result["usage"])
    added_ids = []
    per_query_limit = min(12, max(3, math.ceil(remaining / max(1, len(queries)))))
    for index, query in enumerate(queries, 1):
        # Search only the sanitized seed and generated public query; never attach project notes.
        safe_query = public_web_query(f"{public_seed} {query}", project_selected=bool(job.get("project_ref")), min_terms=1)
        brand_name = str((private_context.get("brand") or {}).get("name") or "").strip()
        if brand_name and brand_name.casefold() not in safe_query.casefold():
            safe_query = f"{brand_name} {safe_query}".strip()
        if len(safe_query) < 3:
            continue
        result = web_search.search(context, {
            "query": safe_query[:400], "depth": "fast" if profile == "quick" else "agentic",
            "limit": per_query_limit, "include_content": False,
            "recency": "month" if profile == "quick" else "year",
            "include_domains": config.get("include_domains") or [],
            "exclude_domains": config.get("exclude_domains") or [],
            "request_id": _mi_request_id(job, unit, f"search:{index}"),
        })
        saved = long_jobs.add_sources(job["id"], context, result.get("sources") or [])
        added_ids.extend(item["id"] for item in saved)
        if len(long_jobs.snapshot(job["id"], context)["sources"]) >= int(job.get("source_target") or 0):
            break
    if not added_ids and not long_jobs.snapshot(job["id"], context)["sources"]:
        raise RuntimeError("A busca não encontrou fontes públicas para esta análise.")
    return json.dumps({"queries": queries, "new_sources": len(added_ids),
                       "total_sources": len(long_jobs.snapshot(job["id"], context)["sources"])}, ensure_ascii=False), usage_total, added_ids


def _mi_extract(job: dict, unit: dict, context: RequestContext) -> tuple[str, dict, list[str]]:
    snapshot = long_jobs.snapshot(job["id"], context)
    pending = [item for item in snapshot["sources"] if item.get("status") == "discovered"]
    if str(job.get("mode") or "") == "quick":
        social_hosts = ("facebook.com", "instagram.com", "tiktok.com", "youtube.com", "x.com")
        pending.sort(key=lambda item: (
            any((urlsplit(item.get("url") or "").hostname or "").endswith(host) for host in social_hosts),
            (urlsplit(item.get("url") or "").path or "").lower().endswith(".pdf"),
            -(float(item.get("relevance") or 0)),
        ))
        pending = pending[:6]
    usage_sum = {}
    source_ids = []
    for batch_index in range(0, len(pending), 8):
        batch = pending[batch_index:batch_index + 8]
        try:
            read_result = web_search.read(context, {
                "urls": [item["url"] for item in batch],
                "request_id": _mi_request_id(job, unit, f"read:{batch_index // 8}"),
            })
        except web_search.WebSearchUnavailable:
            read_result = {"sources": []}
        read_urls = {item.get("url") for item in read_result.get("sources") or []}
        unavailable_ids = [item["id"] for item in batch if item["url"] not in read_urls]
        if unavailable_ids:
            connection = repository.get_db()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""UPDATE cadu_agent_long_job_sources SET status='unavailable'
                        WHERE job_id=%s AND id=ANY(%s::uuid[]) AND status='discovered'""",
                        (job["id"], unavailable_ids))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        persisted = long_jobs.add_sources(job["id"], context, read_result.get("sources") or [])
        source_ids.extend(item["id"] for item in persisted)
        current = {item.get("url"): item for item in read_result.get("sources") or []}
        normalized = [{**item, "content": (current.get(item["url"]) or {}).get("content") or ""} for item in persisted]
        for source_batch in range(0, len(normalized), 4):
            sources = normalized[source_batch:source_batch + 4]
            packed = [{"id": item["id"], "title": item["title"], "url": item["url"],
                       "content": item["content"][:5000]} for item in sources if item.get("content")]
            if not packed:
                continue
            result = _mi_call(job, unit, "structured_extractor",
                ('Extraia evidências rastreáveis. JSON estrito: {"claims":[{"claim":"...","date":"...",'
                 '"entity":"...","topic":"...","quote":"...","source_id":"...","confidence":"low|medium|high"}]} '
                 'Não infira fatos fora do conteúdo e use somente source_id recebido.'),
                json.dumps({"objective": job["objective"], "sources": packed}, ensure_ascii=False),
                json_output=True, max_tokens=2200, call_index=100 + batch_index + source_batch)
            _merge_usage(usage_sum, result["usage"])
            valid_ids = {item["id"] for item in packed}
            claims = (result.get("json") or {}).get("claims") or []
            claims = [claim for claim in claims if isinstance(claim, dict) and claim.get("source_id") in valid_ids]
            if claims:
                fragment = json.dumps({"claims": claims}, ensure_ascii=False, indent=2)
                long_jobs.append_fragment(job["id"], context, fragment, unit_id=unit["id"], kind="evidence",
                                          heading=f"evidence_batch_{batch_index + source_batch}",
                                          source_ids=list(valid_ids))
    return f"Extração concluída para {len(source_ids)} fontes; evidências persistidas com seus IDs de origem.", usage_sum, list(dict.fromkeys(source_ids))


def _mi_generate_stage(job: dict, unit: dict, context: RequestContext, private_context: dict) -> tuple[str, dict, list[str]]:
    kind = unit["kind"]
    quick = str(job.get("mode") or "") == "quick"
    if quick and kind == "compose":
        analysis = repository.rows("""SELECT content FROM cadu_agent_long_job_fragments
            WHERE job_id=%s AND heading='analyze' ORDER BY ordinal DESC LIMIT 1""", (job["id"],))
        if not analysis:
            raise RuntimeError("A análise necessária para montar o Quick Scan não está disponível.")
        source_ids = [str(item["id"]) for item in long_jobs.snapshot(job["id"], context)["sources"]]
        return str(analysis[0]["content"]), {}, source_ids
    evidence_text, sources = _mi_evidence_payload(job["id"], limit=14_000 if quick else 42_000)
    if kind in {"classify", "analyze", "critic", "evidence_check", "compose", "review"} and not any(
        item["status"] == "extracted" for item in sources
    ):
        return "Não há conteúdo de fonte legível para sustentar conclusões nesta etapa.", {}, []
    prior = _prior_text(job["id"], limit=2_000 if quick else 18_000)
    config = _mi_profile(job)
    role = {"classify": "fast_classifier", "gap_analysis": "research_reasoner", "analyze": "research_reasoner",
            "critic": "critic", "evidence_check": "structured_extractor", "compose": "editorial_writer",
            "review": "critic", "plan": "research_reasoner"}.get(kind, "research_reasoner")
    custom = "\nINSTRUÇÃO METODOLÓGICA DO CLIENTE:\n" + str(config.get("methodology") or "") if config.get("methodology") else ""
    taxonomy = "\nTAXONOMIA DO CLIENTE:\n" + str(config.get("taxonomy") or "") if config.get("taxonomy") else ""
    scoring = "\nCRITÉRIOS DE PONTUAÇÃO DO CLIENTE:\n" + str(config.get("scoring") or "") if config.get("scoring") else ""
    review_policy = "\nREGRAS DE REVISÃO DO CLIENTE:\n" + str(config.get("review_policy") or "") if config.get("review_policy") else ""
    artifact_template = "\nMODELO DE ARTEFATO DO CLIENTE:\n" + str(config.get("artifact_template") or "") if config.get("artifact_template") else ""
    private_json = json.dumps(private_context, ensure_ascii=False, default=str)[:4000 if quick else 9000]
    policy = {
        "plan": "Decomponha em perguntas, critérios de evidência e tipos de fonte; devolva JSON.",
        "classify": "Resuma as evidências em até seis tópicos curtos: concorrentes, tendências, sinais, campanhas, riscos e oportunidades. Cite os source_id úteis como [S:<source_id>].",
        "gap_analysis": "Compare questões planejadas com evidências disponíveis. Declare se há lacunas e crie queries públicas concisas. Devolva JSON.",
        "analyze": "Construa conclusões apenas do corpus. Para cada conclusão, cite source_id(s), confiança e implicação. Diferencie fato e interpretação.",
        "critic": "Revise criticamente as conclusões, procurando fontes fracas, generalizações, contradições, datas inválidas e alternativas. Não reescreva o relatório.",
        "evidence_check": "Valide cada claim factual contra o corpus. Retorne JSON com claims aceitos/rejeitados e source_id válido.",
        "compose": "Escreva relatório claro em Markdown: resumo executivo, contexto, movimentos, matriz de concorrentes, tendências, oportunidades, riscos e recomendações. Use somente conclusões aceitas por evidence_check quando disponível. Cite evidências como [S:<source_id>]. Não invente números, fontes ou datas.",
        "review": "Revise texto final contra a análise e evidências. Corrija apenas erros e lacunas demonstráveis; mantenha referências válidas.",
    }.get(kind, PHASES.get(kind, "Produza somente a saída desta etapa."))
    if quick and kind == "analyze":
        policy = ("Produza um Quick Scan conciso em Markdown, com resumo executivo, sinais, oportunidades, riscos, "
                  "lacunas e próximos passos. Diferencie fatos de hipóteses e cite cada afirmação factual como "
                  "[S:<source_id>]. Limite a resposta a cerca de 900 palavras; não invente dados.")
    json_stage = kind in {"plan", "gap_analysis", "evidence_check"}
    prompt = json.dumps({"objective": job["objective"], "approved_context_for_synthesis_only": private_json,
                         "profile": config, "previous_work": prior, "evidence_corpus": evidence_text,
                         "task": policy + custom + taxonomy + scoring + review_policy + artifact_template}, ensure_ascii=False)
    system = ("Você é o analista do plugin Market Intelligence. Use somente corpus e contexto autorizado. "
              "Não trate ausência de evidência como evidência de ausência. Separe fatos, interpretações e hipóteses. "
              "Não envie nem repita contexto privado em consultas externas. "
              + ("Retorne JSON válido sem texto fora do objeto." if json_stage else "Preserve IDs de fonte como tokens de citação."))
    result = _mi_call(job, unit, role, system, prompt, json_output=json_stage,
                      max_tokens=(1200 if kind == "classify" else 1800 if quick and kind == "analyze"
                                  else 4200 if kind in {"analyze", "compose", "review"} else 2600),
                      call_index=0)
    structured = result.get("json") or {}
    if json_stage and result.get("parse_error"):
        if kind == "plan":
            structured = {"questions": [str(job["objective"])[:400]], "status": "fallback_after_invalid_json"}
        elif kind == "gap_analysis":
            structured = {"gaps": ["Cobertura de evidências ainda não verificada."], "sufficient": False,
                          "status": "fallback_after_invalid_json"}
        else:
            structured = {"claims": [], "status": "unverified", "reason": "A checagem estruturada falhou."}
    content = json.dumps(structured, ensure_ascii=False, indent=2) if json_stage else result["text"]
    if kind == "gap_analysis":
        if not structured.get("queries") and not structured.get("gaps"):
            content = json.dumps({"gaps": [], "queries": [], "sufficient": True}, ensure_ascii=False)
    if kind == "evidence_check":
        allowed = {str(item["source_id"]) for item in sources if item["status"] == "extracted"}
        checked = structured.get("claims") or []
        checked = [claim for claim in checked if isinstance(claim, dict)
                   and bool(claim.get("source_ids"))
                   and set(map(str, claim.get("source_ids") or [])) <= allowed]
        content = json.dumps({"claims": checked, "source_count": len(allowed),
                              "status": structured.get("status") or "verified"}, ensure_ascii=False, indent=2)
    return content, result["usage"], [item["source_id"] for item in sources]


def _market_stage(job: dict, unit: dict, context: RequestContext) -> tuple[str, dict, list[str]]:
    kind = unit["kind"]
    needs_synthesis_context = kind in {
        "plan", "gap_analysis", "analyze", "critic", "evidence_check", "compose", "review",
    }
    private_context = _mi_private_context(context, include_project=needs_synthesis_context) if kind in {
        "discover", "followup_search", "plan", "gap_analysis", "analyze", "critic",
        "evidence_check", "compose", "review",
    } else {}
    if kind == "discover":
        content, usage, source_ids = _mi_run_search(job, unit, context, private_context)
    elif kind == "followup_search":
        content, usage, source_ids = _mi_run_search(job, unit, context, private_context, followup=True)
    elif kind == "extract":
        content, usage, source_ids = _mi_extract(job, unit, context)
    elif kind == "render":
        content, usage, source_ids = _mi_report(job, context)
    else:
        content, usage, source_ids = _mi_generate_stage(job, unit, context, private_context)
    long_jobs.append_fragment(job["id"], context, content, unit_id=unit["id"],
                              kind="evidence" if kind in {"classify", "gap_analysis", "evidence_check"} else "section",
                              heading=kind, source_ids=source_ids)
    return content, usage, source_ids


def _mi_report(job: dict, context: RequestContext) -> tuple[str, dict, list[str]]:
    fragments = long_jobs.snapshot(job["id"], context)["fragments"]
    final = next((item for item in reversed(fragments) if item.get("heading") == "review"), None)
    final = final or next((item for item in reversed(fragments) if item.get("heading") == "compose"), None)
    final = final or next((item for item in reversed(fragments) if item.get("heading") == "analyze"), None)
    report = str((final or {}).get("content") or "").strip()
    _, sources = _mi_evidence_payload(job["id"], limit=20_000)
    index = {str(item["source_id"]): item["source_no"] for item in sources}
    verified_ids = {str(item["source_id"]) for item in sources if item["status"] == "extracted"}
    verified_numbers = {index[source_id] for source_id in verified_ids}
    used_ids = [source_id.lower() for source_id in re.findall(r"\[S:([0-9a-f-]{36})\]", report, re.I)]
    used_numbers = {int(value) for value in re.findall(r"\[S(\d+)\]", report, re.I)}
    incomplete_citation = any(
        not re.fullmatch(r"[0-9a-f-]{36}", marker, re.I)
        for marker in re.findall(r"\[S:([^\]\n]*)(?:\]|$)", report, re.I)
    )
    report = re.sub(
        r"\[S:([0-9a-f-]{36})\]",
        lambda match: f"[S{index[match.group(1).lower()]}]" if match.group(1).lower() in verified_ids
        else "[fonte não verificada]",
        report, flags=re.I,
    )
    report = re.sub(r"\[S:[0-9a-f-]{8,36}(?:\])?", "[referência incompleta]", report, flags=re.I)
    rows = repository.rows("""SELECT id::text,title,url,metadata,status FROM cadu_agent_long_job_sources
        WHERE job_id=%s ORDER BY relevance DESC NULLS LAST,discovered_at LIMIT 150""", (job["id"],))
    source_by_id = {str(row["id"]): row for row in rows}
    claims = []
    evidence_fragments = repository.rows("""SELECT content FROM cadu_agent_long_job_fragments
        WHERE job_id=%s AND kind='evidence' AND heading LIKE 'evidence_batch_%%' ORDER BY ordinal""", (job["id"],))
    for fragment in evidence_fragments:
        try:
            batch_claims = (json.loads(fragment.get("content") or "{}") or {}).get("claims") or []
        except (TypeError, ValueError):
            batch_claims = []
        for claim in batch_claims:
            if isinstance(claim, dict) and str(claim.get("source_id") or "") in verified_ids:
                claims.append(claim)
    if (set(used_ids) - verified_ids or used_numbers - verified_numbers or incomplete_citation
            or (report and not used_ids and not used_numbers)):
        # An unsupported citation taints the surrounding prose, not only its marker.
        # Keep the delivery useful by rebuilding it from persisted, readable evidence.
        verified_lines = []
        for claim in claims[:30]:
            source_id = str(claim["source_id"])
            statement = " ".join(str(claim.get("claim") or "").split()).strip()
            if statement:
                verified_lines.append(f"- {statement} [S{index[source_id]}]")
        report = (f"# {job['title']}\n\n"
                  "## Achados com fonte lida\n\n"
                  + ("\n".join(verified_lines) if verified_lines else "Nenhum achado verificável foi extraído das páginas lidas.")
                  + "\n\n## Limites desta análise\n\n"
                  "A pesquisa encontrou fontes cujo conteúdo não pôde ser lido. "
                  "Elas aparecem no índice abaixo, mas não sustentam os achados deste documento.")
        used_ids = [str(claim["source_id"]) for claim in claims[:30]]
    evidence_lines = []
    for claim in claims[:100]:
        source = source_by_id[str(claim.get("source_id"))]
        source_no = index.get(str(source["id"]), "?")
        clean = lambda value: " ".join(str(value or "").replace("|", "\\|").split())[:350]
        evidence_lines.append(f"| {clean(claim.get('topic'))} | {clean(claim.get('entity'))} | {clean(claim.get('claim'))} | [S{source_no}] | {clean(claim.get('confidence'))} |")
    if evidence_lines:
        report += ("\n\n## Base de evidências\n\n| Tema | Entidade | Afirmação extraída | Fonte | Confiança |\n"
                   "|---|---|---|---|---|\n" + "\n".join(evidence_lines))
    bibliography = []
    for row in rows:
        source_no = index.get(str(row["id"]))
        if source_no is None:
            continue
        metadata = row.get("metadata") or {}
        published = str(metadata.get("published_at") or "")
        state = "conteúdo lido" if row.get("status") == "extracted" else "conteúdo indisponível"
        bibliography.append(f"- [S{source_no}] [{row.get('title') or 'Fonte'}]({row.get('url')})"
                            + (f" — publicada em {published}" if published else "") + f" — {state}")
    report += "\n\n## Fontes e leituras\n\n" + ("\n".join(bibliography) if bibliography else "Nenhuma fonte foi localizada.")
    read_count = sum(row.get("status") == "extracted" for row in rows)
    profile = _mi_profile(job)
    rounds = len([item for item in repository.rows("""SELECT id FROM cadu_agent_long_job_units
        WHERE job_id=%s AND kind IN ('discover','followup_search') AND status='completed'""", (job["id"],))])
    calls = long_jobs.model_call_usage(job["id"])
    gap_row = next((item for item in reversed(fragments) if item.get("heading") == "gap_analysis"), None)
    gap_summary = ""
    if gap_row:
        try:
            gaps = json.loads(gap_row.get("content") or "{}").get("gaps") or []
            if gaps:
                gap_summary = "\nLacunas remanescentes: " + "; ".join(str(item)[:180] for item in gaps[:8])
        except (TypeError, ValueError):
            pass
    report += (f"\n\n## Estado da pesquisa\n\nModalidade: {profile['label']}. Rodadas concluídas: {rounds}. "
               f"Fontes localizadas: {len(rows)}; conteúdo lido: {read_count}. "
               f"Chamadas de modelo: {int(calls.get('agent_calls') or 0) + int(calls.get('extractor_calls') or 0)}."
               + gap_summary)
    report += f"\n\n> Foram encontradas {len(rows)} fontes, {read_count} foram lidas e {len(set(used_ids) & verified_ids)} referências verificadas aparecem no relatório."
    return report, {}, [str(row["id"]) for row in rows]


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
        if job.get("kind") == "market_intelligence":
            content, usage, source_ids = _market_stage(job, unit, context)
            kind = "revision" if unit["kind"] == "review" else "section"
            fragment = long_jobs.append_fragment(job["id"], context, content, unit_id=unit["id"],
                                                 kind=kind, heading=f"{unit['kind']}_render_input",
                                                 source_ids=source_ids)
            output = {"fragment_id": fragment["id"], "ordinal": fragment["ordinal"]}
            if unit["kind"] in {"compose", "review", "render"}:
                artifact = _save_artifact(job, context, content, unit["kind"])
                output.update({"artifact_id": str(artifact["id"]), "version": artifact["current_version"]})
        elif unit["kind"] == "render":
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
                idempotency_key=(
                    _mi_request_id(job, unit, f"provider-charge:{unit['attempts']}")
                    if job.get("kind") == "market_intelligence"
                    else f"long-job:{job['id']}:{unit['id']}:{unit['attempts']}"
                ),
                app="Cadu Chat", stage=f"trabalho-longo:{unit['kind']}",
                provider_result={"usage": usage,
                                 "model": "market-intelligence-role-policy" if job.get("kind") == "market_intelligence" else "cadu-operator",
                                 "provider": "openrouter" if job.get("kind") == "market_intelligence" else "dify"},
                metadata={"conversation_id": job["conversation_id"], "long_job_id": job["id"],
                          "unit_id": unit["id"], "mode": job.get("mode") or "",
                          "model_calls": long_jobs.model_call_usage(job["id"]) if job.get("kind") == "market_intelligence" else {}},
            )
        except Exception:
            current_app.logger.exception("Cobrança pendente para etapa %s do trabalho %s", unit["id"], job["id"])
        completion = long_jobs.complete_unit(
            job["id"], unit["id"], context, output=output, token_usage=_tokens(usage),
            checkpoint={"position": unit["position"], "kind": unit["kind"], **output},
        )
        if job.get("kind") == "market_intelligence" and unit["kind"] == "gap_analysis":
            try:
                gap = json.loads(content)
            except (TypeError, ValueError):
                gap = {}
            if gap.get("sufficient") or not gap.get("gaps"):
                long_jobs.skip_later_research(job["id"], unit["id"], context)
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
