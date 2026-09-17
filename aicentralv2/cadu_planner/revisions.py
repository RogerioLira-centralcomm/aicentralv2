"""Prompt contract for the Planner's transparent three-pass review process."""
from __future__ import annotations

from collections.abc import Mapping
import json
import re
from uuid import uuid4

from werkzeug.exceptions import BadRequest


REVIEW_PASSES = (
    ("Ler o contexto", "Verifique objetivo, público, período, investimento, KPIs, restrições e ativos de marca. Liste somente lacunas ou conflitos relevantes."),
    ("Reorganizar a recomendação", "Com base no contexto, corrija incoerências e melhore a lógica, a hierarquia e a continuidade da proposta."),
    ("Aplicar a versão revisada", "Entregue a versão final mais consistente. Esta é a única versão que será aplicada ao plano; não descreva o processo interno."),
)
MAX_REVIEW_DOCUMENT_CHARS = 40_000
BRIEFING_OUTPUT_TOKENS_PER_PASS = 800
DOCUMENT_OUTPUT_TOKENS_PER_PASS = 1_200

_TASKS = {
    "briefing": "Revise o briefing para que ele seja uma direção clara, verificável e pronta para orientar as escolhas de mídia.",
    "recommendation": "Revise a recomendação de mídia para que escolhas, distribuição e justificativas respondam ao briefing.",
    "document": "Revise o documento para que a narrativa seja fiel ao plano, clara para o cliente e pronta para compartilhamento.",
}


def build_review_prompt(task: str, context: Mapping[str, object]) -> str:
    """Build the internal Planner prompt without exposing implementation/model details.

    The caller sends the returned prompt to Cadu together with the scoped plan and
    brand data. The third pass is deliberately the applied result.
    """
    if task not in _TASKS:
        raise ValueError("Tipo de revisão do Planner inválido.")
    safe_context = {str(key): value for key, value in context.items() if value not in (None, "", [], {})}
    steps = "\n".join(f"{index}. {title}: {instruction}" for index, (title, instruction) in enumerate(REVIEW_PASSES, 1))
    return (
        "Você é o processo de revisão do Cadu Planner. "
        + _TASKS[task]
        + "\n\nExecute exatamente três passagens sequenciais sobre o mesmo contexto:\n"
        + steps
        + "\n\nRegras: preserve fatos fornecidos; não invente dados, preços, resultados ou disponibilidade; "
        "sinalize pressupostos de modo objetivo; respeite a voz e os ativos da marca presentes no contexto. "
        "Responda somente com a versão final da passagem 3, em português do Brasil.\n\n"
        f"Contexto do plano: {safe_context!r}"
    )


def build_review_pass_prompt(task: str, context: Mapping[str, object], previous: Mapping[str, object], pass_number: int) -> str:
    """Build one explicit pass of the loop while retaining the same source context."""
    if task not in _TASKS or pass_number not in (1, 2, 3):
        raise ValueError("Passagem de revisão do Planner inválida.")
    title, instruction = REVIEW_PASSES[pass_number - 1]
    source = {str(key): value for key, value in context.items() if value not in (None, "", [], {})}
    draft = {str(key): value for key, value in previous.items() if value not in (None, "", [], {})}
    return (
        "Você faz a passagem %d de 3 do processo de revisão do Cadu Planner.\n"
        "Tarefa: %s\n"
        "Etapa atual — %s: %s\n\n"
        "Não invente dados, preços, resultados ou disponibilidade. Preserve fatos do plano e use português do Brasil. "
        "Retorne APENAS JSON válido, sem markdown, com esta estrutura:\n"
        '{"advertiser_name":"","campaign_name":"","briefing":{"budget":"","period":"","geography":"","kpis":"","notes":""},"review_note":""}\n\n'
        "Contexto original do plano: %s\n\n"
        "Rascunho recebido da passagem anterior: %s"
    ) % (pass_number, _TASKS[task], title, instruction, source, draft)


def _json_object(value: str) -> dict:
    """Accept only the small schema used to update a Planner briefing."""
    raw = str(value or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.S | re.I)
    if fenced:
        raw = fenced.group(1)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BadRequest("O Cadu não devolveu uma revisão utilizável. Tente novamente.") from exc
    if not isinstance(parsed, dict):
        raise BadRequest("O Cadu não devolveu uma revisão utilizável. Tente novamente.")
    briefing = parsed.get("briefing")
    if not isinstance(briefing, dict):
        raise BadRequest("O Cadu não devolveu uma revisão utilizável. Tente novamente.")
    return {
        "advertiser_name": str(parsed.get("advertiser_name") or "").strip(),
        "campaign_name": str(parsed.get("campaign_name") or "").strip(),
        "briefing": {key: str(briefing.get(key) or "").strip()
                     for key in ("budget", "period", "geography", "kpis", "notes")},
        "review_note": str(parsed.get("review_note") or "").strip()[:500],
    }


def _estimate_tokens(source_chars: int, output_tokens_per_pass: int) -> int:
    """Conservative credit ceiling for three passes, before any provider call."""
    source_tokens = max(1, (max(0, source_chars) + 3) // 4)
    # Original context enters the first pass; subsequent passes carry the
    # bounded previous draft. Include a small instruction/JSON overhead.
    return source_tokens + (output_tokens_per_pass * 5) + 600


def briefing_estimate(client_id: int, actor_id: int, plan_id: str) -> int:
    from . import plans
    plan = plans.get_plan(client_id, actor_id, plan_id)
    source = repr({"title": plan.get("title"), "objective": plan.get("objective"),
                   "advertiser_name": plan.get("advertiser_name"), "campaign_name": plan.get("campaign_name"),
                   "briefing": plan.get("briefing") or {}, "items": plan.get("items") or []})
    return _estimate_tokens(len(source), BRIEFING_OUTPUT_TOKENS_PER_PASS)


def document_estimate(client_id: int, actor_id: int, doc_id: int) -> int:
    from . import docs
    document = docs.get_document(client_id, actor_id, doc_id)
    if not document.get("is_owner"):
        raise BadRequest("Somente o autor pode revisar este documento.")
    length = len(str(document.get("html") or ""))
    if not length:
        raise BadRequest("Escreva algum conteúdo antes de pedir uma revisão.")
    if length > MAX_REVIEW_DOCUMENT_CHARS:
        raise BadRequest(f"Para revisar, reduza o documento para até {MAX_REVIEW_DOCUMENT_CHARS:,} caracteres.")
    return _estimate_tokens(length, DOCUMENT_OUTPUT_TOKENS_PER_PASS)


def history(client_id: int, actor_id: int, *, plan_id: str | None = None, document_id: int | None = None) -> list[dict]:
    """Return compact, actor-scoped review history; old installs degrade safely."""
    if bool(plan_id) == bool(document_id):
        return []
    from ..cadu_family import repository
    available = repository.rows("SELECT to_regclass('public.cadu_planner_review_runs') IS NOT NULL AS available")
    if not available or not available[0].get("available"):
        return []
    target_column, target = ("plan_id", str(plan_id)) if plan_id else ("document_id", int(document_id))
    return repository.rows(
        f'''SELECT id, scope, passes, applied_pass, charged_tokens, review_note, created_at
              FROM cadu_planner_review_runs
             WHERE client_id = %s AND actor_id = %s AND {target_column} = %s
             ORDER BY created_at DESC LIMIT 12''',
        (client_id, actor_id, target),
    )


def _record_history(*, review_id: str, client_id: int, actor_id: int, scope: str, plan_id=None,
                    document_id=None, charged_tokens: int, note: str | None, source: Mapping[str, object], applied: Mapping[str, object]):
    from ..cadu_family import repository
    from ..db import get_db
    from psycopg.types.json import Json

    try:
        available = repository.rows("SELECT to_regclass('public.cadu_planner_review_runs') IS NOT NULL AS available")
        if not available or not available[0].get("available"):
            return
        with get_db() as conn, conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_planner_review_runs
                (id, client_id, actor_id, scope, plan_id, document_id, charged_tokens, review_note, source_snapshot, applied_snapshot)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (review_id, client_id, actor_id, scope, str(plan_id) if plan_id else None, document_id,
                 max(0, int(charged_tokens)), note or None, Json(dict(source)), Json(dict(applied))))
    except Exception:
        # A review already applied to the customer's material must not fail
        # merely because an older environment has not received the history DDL.
        return


def review_briefing(client_id: int, actor_id: int, plan_id: str) -> dict:
    """Run the three sequential passes and persist only the final briefing.

    Billing is attached to each actual provider response under an idempotency key.
    No provider/model name is returned to the Planner UI.
    """
    from ..cadu_tool_billing import ToolTokenLedger, charge_from_provider
    from ..training_studio.providers import TextProvider
    from . import plans

    plan = plans.get_plan(client_id, actor_id, plan_id)
    context = {
        "title": plan.get("title"), "objective": plan.get("objective"),
        "advertiser_name": plan.get("advertiser_name"), "campaign_name": plan.get("campaign_name"),
        "briefing": plan.get("briefing") or {},
        "selected_media": [{"kind": item.get("kind"), "name": (item.get("snapshot") or {}).get("name")}
                           for item in plan.get("items") or []],
    }
    ledger = ToolTokenLedger()
    # The estimate guards the account before starting three calls. The three
    # actual responses are charged once, only after a final version is applied.
    estimated_tokens = briefing_estimate(client_id, actor_id, plan_id)
    ledger.assert_available(client_id, estimated_tokens)
    provider, draft, responses = TextProvider(), {}, []
    review_id = str(uuid4())
    for pass_number in (1, 2, 3):
        response = provider.complete([
            {"role": "system", "content": "Você revisa planos de mídia com precisão e transparência."},
            {"role": "user", "content": build_review_pass_prompt("briefing", context, draft, pass_number)},
        ], max_tokens=800, temperature=0.15)
        draft = _json_object(response.get("content"))
        responses.append(response)
    # An omitted field is never an instruction to erase saved briefing context.
    final_payload = {
        "advertiser_name": draft["advertiser_name"] or plan.get("advertiser_name") or "",
        "campaign_name": draft["campaign_name"] or plan.get("campaign_name") or "",
        "briefing": {key: value or (plan.get("briefing") or {}).get(key, "")
                     for key, value in draft["briefing"].items()},
    }
    combined = {"usage": {"prompt_tokens": sum(int((item.get("usage") or {}).get("prompt_tokens") or 0) for item in responses),
                            "completion_tokens": sum(int((item.get("usage") or {}).get("completion_tokens") or 0) for item in responses)},
                "cost_usd": sum(float(item.get("cost_usd") or 0) for item in responses),
                "model": "planner-review"}
    updated = plans.update_briefing(client_id, actor_id, plan_id, final_payload, expected_updated_at=plan.get("updated_at"))
    charge = charge_from_provider(ledger=ledger, idempotency_key=f"planner-review:{review_id}",
                                  client_id=client_id, user_id=actor_id, tool="planner", stage="briefing_review",
                                  provider_result=combined, metadata={"plan_id": str(plan_id), "review_id": review_id, "passes": 3})
    charged_tokens = int((charge or {}).get("tokens_cobrados") or 0)
    _record_history(review_id=review_id, client_id=client_id, actor_id=actor_id, scope="briefing", plan_id=plan_id,
                    charged_tokens=charged_tokens, note=draft.get("review_note"), source=context, applied=final_payload)
    return {"plan": updated, "review": {"passes": 3, "applied_pass": 3, "charged_tokens": charged_tokens,
                                             "note": draft.get("review_note")}}


def _document_pass_prompt(document: Mapping[str, object], previous_html: str, pass_number: int, source_context: str = "") -> str:
    title, instruction = REVIEW_PASSES[pass_number - 1]
    return (
        "Você faz a passagem %d de 3 da revisão de um documento no Cadu Planner.\n"
        "Etapa atual — %s: %s\n"
        "Preserve fatos fornecidos; não invente preços, resultados ou disponibilidade. "
        "Melhore apenas clareza, estrutura e continuidade. Retorne SOMENTE HTML seguro de conteúdo, "
        "sem markdown, scripts, estilos, iframes ou tags html/body.\n\n"
        "Documento: %s\nTipo: %s\n\nFontes selecionadas do projeto:\n%s\n\nConteúdo recebido:\n%s"
    ) % (pass_number, title, instruction, document.get("title") or "Documento", document.get("type") or "documento", source_context or "Nenhuma fonte adicional selecionada.", previous_html)


def review_document(client_id: int, actor_id: int, doc_id: int, *, source_context: str = "") -> dict:
    """Apply the same three passes to a user-owned Planner document."""
    from ..cadu_tool_billing import ToolTokenLedger, charge_from_provider
    from ..training_studio.providers import TextProvider
    from . import docs

    document = docs.get_document(client_id, actor_id, doc_id)
    if not document.get("is_owner"):
        raise BadRequest("Somente o autor pode revisar este documento.")
    original = str(document.get("html") or "").strip()
    if not original:
        raise BadRequest("Escreva algum conteúdo antes de pedir uma revisão.")
    if len(original) > MAX_REVIEW_DOCUMENT_CHARS:
        raise BadRequest(f"Para revisar, reduza o documento para até {MAX_REVIEW_DOCUMENT_CHARS:,} caracteres.")
    ledger = ToolTokenLedger()
    estimated_tokens = document_estimate(client_id, actor_id, doc_id)
    ledger.assert_available(client_id, estimated_tokens)
    provider, draft, responses = TextProvider(), original, []
    review_id = str(uuid4())
    for pass_number in (1, 2, 3):
        response = provider.complete([
            {"role": "system", "content": "Você revisa documentos de planejamento de mídia com precisão e transparência."},
            {"role": "user", "content": _document_pass_prompt(document, draft, pass_number, source_context)},
        ], max_tokens=1200, temperature=0.15)
        draft = re.sub(r"^```(?:html)?\s*|\s*```$", "", str(response.get("content") or "").strip(), flags=re.I)
        if not draft:
            raise BadRequest("O Cadu não devolveu uma revisão utilizável. Tente novamente.")
        responses.append(response)
    combined = {"usage": {"prompt_tokens": sum(int((item.get("usage") or {}).get("prompt_tokens") or 0) for item in responses),
                            "completion_tokens": sum(int((item.get("usage") or {}).get("completion_tokens") or 0) for item in responses)},
                "cost_usd": sum(float(item.get("cost_usd") or 0) for item in responses),
                "model": "planner-review"}
    updated = docs.save_document(client_id, actor_id, doc_id, {
        "title": document.get("title"), "status": document.get("status"), "html": draft,
    }, expected_updated_at=document.get("updated_at"))
    charge = charge_from_provider(ledger=ledger, idempotency_key=f"planner-doc-review:{review_id}",
                                  client_id=client_id, user_id=actor_id, tool="planner", stage="document_review",
                                  provider_result=combined, metadata={"document_id": int(doc_id), "review_id": review_id, "passes": 3})
    charged_tokens = int((charge or {}).get("tokens_cobrados") or 0)
    _record_history(review_id=review_id, client_id=client_id, actor_id=actor_id, scope="document", document_id=doc_id,
                    charged_tokens=charged_tokens, note=None, source={"title": document.get("title"), "html": original, "sources": source_context[:12000]},
                    applied={"title": updated.get("title"), "html": updated.get("html")})
    return {"document": updated, "review": {"passes": 3, "applied_pass": 3, "charged_tokens": charged_tokens}}
