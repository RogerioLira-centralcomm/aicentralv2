"""TypeSafe-assisted, reviewable improvement backlog for the Cadu agent."""

import json
import re
from uuid import uuid4
from flask import session

from ...cadu_family import repository
from ...services.integration_credentials import get_configuration, resolve_typesafe_api_key
from ...services.typesafe_service import system_one


def _int(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_state(telemetry, prior):
    """Only send aggregate operational counters, never prompts or transcripts."""
    summary = telemetry.get("summary") or {}
    project = telemetry.get("project_retrieval") or {}
    return {
        "window": "30 days",
        "turns": _int(summary.get("turns")),
        "failed_turns": _int(summary.get("failed")),
        "cancelled_turns": _int(summary.get("cancelled")),
        "avg_first_token_ms": _int(summary.get("avg_first_token_ms")),
        "avg_duration_ms": _int(summary.get("avg_duration_ms")),
        "invalid_html": _int(summary.get("invalid_html")),
        "truncated_html": _int(summary.get("truncated_html")),
        "project_questions_without_completed_evidence_last_7_days": _int(project.get("without_project_evidence")),
        "plugins": [
            {"id": str(item.get("plugin_id") or "unknown")[:80], "turns": _int(item.get("turns")),
             "failed": _int(item.get("failed")), "avg_duration_ms": _int(item.get("avg_duration_ms")),
             "avg_charged_credits": float(item.get("avg_charged_credits") or 0)}
            for item in (telemetry.get("plugin_metrics") or [])[:20]
        ],
        "alerts": [{"code": str(item.get("code") or "")[:80], "severity": str(item.get("severity") or "")[:16]}
                   for item in (telemetry.get("alerts") or [])[:20]],
        "recent_improvement_states": [{"status": str(row.get("status") or "")[:24]}
                                       for row in prior[:30]],
    }


def _assert_internal_client(client_id: int) -> None:
    """Ensure the route's tenant is the authenticated CentralComm organization."""
    from ...cadu_family import context as family_context
    actor = family_context.identity()
    if not session.get("is_centralcomm") or int(actor["organization_id"]) != int(client_id):
        raise ValueError("A análise de melhoria é restrita à conta interna.")


def analyze(client_id: int, user_id: int) -> dict:
    _assert_internal_client(client_id)
    if not resolve_typesafe_api_key():
        raise ValueError("Configure a integração TypeSafe para analisar a observabilidade.")
    telemetry = __import__(__package__ + ".observability", fromlist=["dashboard"]).dashboard(client_id)
    if not telemetry.get("available"):
        raise ValueError("A telemetria ainda não está disponível para análise.")
    prior = repository.rows("""SELECT status FROM cadu_agent_improvements
        WHERE client_id=%s ORDER BY created_at DESC LIMIT 30""", (client_id,))
    state = _safe_state(telemetry, prior)
    if state["turns"] < 5:
        raise ValueError("São necessários pelo menos 5 turns para gerar recomendações úteis.")

    try:
        configured_model = get_configuration("typesafe").get("default_model")
    except Exception:
        configured_model = None
    result = system_one(state, {
        "reliability": {"type": "noul", "instructions": "Do these operational metrics show a measurable reliability concern for the agent?",
                        "criteria": {"true": "Failures, invalid outputs, or missing completed evidence are material in this sample", "false": "The available reliability signals do not indicate a material concern"}},
        "latency": {"type": "noul", "instructions": "Do these operational metrics show a measurable latency concern worth engineering investigation?",
                    "criteria": {"true": "First-token or total duration metrics are materially slow", "false": "Latency metrics do not indicate a material concern"}},
        "cost": {"type": "noul", "instructions": "Do these operational metrics show a measurable cost-efficiency concern?",
                 "criteria": {"true": "Per-plugin cost signals justify checking cost per completed useful result", "false": "The data does not indicate a material cost concern"}},
    }, model=configured_model or None)
    answers = result.get("answers") or {}
    recommendations = []
    deterministic = {
        "reliability": state["failed_turns"] > 0 or state["invalid_html"] + state["truncated_html"] > 0 or state["project_questions_without_completed_evidence_last_7_days"] > 0,
        "latency": state["avg_first_token_ms"] > 5000 or state["avg_duration_ms"] > 30000,
        "cost": any(item["avg_charged_credits"] >= 10 for item in state["plugins"]),
    }
    for priority, signals_support in deterministic.items():
        answer = answers.get(priority) or {}
        probability = answer.get("noul")
        try:
            confidence = float(probability)
        except (TypeError, ValueError):
            continue
        # Noul is probability of true, not a separate confidence score. Keep a
        # human-review gate; thresholds must be calibrated against labeled cases.
        if not signals_support or confidence < 0.75:
            continue
        evidence = state
        title = {
            "reliability": "Investigar confiabilidade e evidência do agente",
            "latency": "Investigar latência do agente",
            "cost": "Investigar custo por execução",
        }.get(priority, "Revisar cobertura de observabilidade")
        rationale = {
            "reliability": f"Telemetria agregada: {state['failed_turns']} falhas, {state['invalid_html'] + state['truncated_html']} saídas HTML inválidas/truncadas e {state['project_questions_without_completed_evidence_last_7_days']} consultas de projeto sem evidência concluída.",
            "latency": f"Primeiro retorno médio de {state['avg_first_token_ms']} ms e duração média de {state['avg_duration_ms']} ms.",
            "cost": f"A telemetria mostra {state['turns']} turns e os custos médios por plugin; revisar eficiência antes de mudar comportamento.",
        }[priority]
        recommendation = {
            "reliability": "Reproduzir os casos com falha e conferir a rota, recuperação de evidências e validação da resposta. Propor uma alteração pequena, cobrir os casos afetados e comparar a taxa de falha antes/depois.",
            "latency": "Separar o tempo do provider das etapas e tools; localizar o maior contribuinte antes de propor otimização. Comparar p50/p95 antes/depois.",
            "cost": "Identificar plugins e rotas com maior custo médio, verificar tamanho de contexto e chamadas redundantes e medir custo por resultado concluído antes/depois.",
        }[priority]
        recommendations.append({"title": title, "rationale": rationale, "recommendation": recommendation,
                                "priority": "high" if priority == "reliability" else "medium",
                                "confidence": confidence, "evidence": evidence})

    persisted = []
    for item in recommendations:
        record_id = str(uuid4())
        repository.rows("""INSERT INTO cadu_agent_improvements
            (id,client_id,created_by,title,rationale,evidence,recommendation,priority,confidence)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) RETURNING id::text, status, created_at""",
            (record_id, client_id, user_id, item["title"], item["rationale"], json.dumps(item["evidence"]),
             item["recommendation"], item["priority"], item["confidence"]))
        persisted.append({**item, "id": record_id, "status": "identified"})
    return {"model": result.get("model"), "usage": result.get("usage") or {},
            "judgments": answers, "recommendations": persisted}


def list_items(client_id: int, limit=50) -> list[dict]:
    _assert_internal_client(client_id)
    return repository.rows("""SELECT id::text,title,rationale,evidence,recommendation,priority,confidence,status,
        applied_ref,applied_at,created_at,updated_at FROM cadu_agent_improvements
        WHERE client_id=%s ORDER BY CASE status WHEN 'identified' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END,
        created_at DESC LIMIT %s""", (client_id, min(100, max(1, int(limit or 50)))))


def update_item(client_id: int, user_id: int, item_id: str, status: str, applied_ref=None):
    _assert_internal_client(client_id)
    if status not in {"in_review", "applied", "dismissed"}:
        raise ValueError("Estado de melhoria inválido.")
    reference = str(applied_ref or "").strip()[:240]
    if status == "applied" and not reference:
        raise ValueError("Informe o commit ou PR que comprova a aplicação da melhoria.")
    if status == "applied" and not re.fullmatch(r"(?:[0-9a-fA-F]{7,40}|https://[^\s<>]+)", reference):
        raise ValueError("Informe um hash de commit ou uma URL HTTPS de PR.")
    rows = repository.rows("""UPDATE cadu_agent_improvements SET status=%s,
        applied_ref=CASE WHEN %s='applied' THEN %s ELSE NULL END,
        applied_by=CASE WHEN %s='applied' THEN %s ELSE NULL END,
        applied_at=CASE WHEN %s='applied' THEN NOW() ELSE NULL END, updated_at=NOW()
        WHERE id=%s AND client_id=%s
        RETURNING id::text,status,applied_ref,applied_at,updated_at""",
        (status, status, reference or None, status, user_id, status, item_id, client_id))
    if not rows:
        raise ValueError("Melhoria não encontrada.")
    return rows[0]
