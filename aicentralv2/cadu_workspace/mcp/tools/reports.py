"""Read-only tools for manually imported and human-reviewed Reports data."""

from ....cadu_family import repository
from ....cadu_planner import plans
from ...agent_v2.contracts import RequestContext
from ..registry import ToolInputError, register_tool


def _reports(context: RequestContext, report_id=None):
    where = "AND w.id = %s" if report_id is not None else ""
    params = [context.organization_id, context.client_id]
    if report_id is not None:
        params.append(report_id)
    if context.project_ref:
        where += " AND w.project_ref = %s"
        params.append(context.project_ref)
    return repository.rows(f"""SELECT w.id, w.project_ref, w.campaign_name, w.document,
                                      w.revision, w.updated_at
                                 FROM cadu_connect_report_workspaces w
                                WHERE w.organization_id = %s AND w.client_id = %s {where}
                             ORDER BY w.updated_at DESC LIMIT 50""", tuple(params))


@register_tool(
    name="reports.list_project_reports", capability="reports", requires_project=True,
    description="Lista relatórios importados e autorizados do projeto atual.",
    exposures=("internal", "customer_agent"),
)
def list_project_reports(context: RequestContext, arguments: dict) -> dict:
    return {"reports": [{key: row.get(key) for key in ("id", "project_ref", "campaign_name", "revision", "updated_at")}
                        for row in _reports(context)]}


@register_tool(
    name="reports.get_recent_project_metrics", capability="reports", requires_project=True,
    description="Lê métricas revisadas dos relatórios mais recentes do projeto, identificando cada campanha e período.",
    exposures=("internal", "customer_agent"),
)
def get_recent_project_metrics(context: RequestContext, arguments: dict) -> dict:
    reports = _reports(context)
    recent = []
    for row in reports[:3]:
        reviewed = get_report_metrics(context, {"report_id": row["id"]})
        recent.append({
            "report": {key: reviewed["report"].get(key) for key in
                       ("id", "project_ref", "campaign_name", "revision", "updated_at")},
            "reviewed_sources": reviewed["reviewed_sources"][:8],
            "additional_reviewed_sources": max(0, len(reviewed["reviewed_sources"]) - 8),
        })
    return {
        "available_reports": len(reports),
        "recent_reports": recent,
        "note": "Até oito fontes revisadas de cada um dos três relatórios mais recentes; não representa dados em tempo real.",
    }


@register_tool(
    name="reports.get_report_metrics", capability="reports",
    description="Obtém o relatório e somente as métricas revisadas por uma pessoa.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object", "required": ["report_id"],
        "properties": {"report_id": {"type": ["integer", "string"]}}, "additionalProperties": False,
    },
)
def get_report_metrics(context: RequestContext, arguments: dict) -> dict:
    try:
        report_id = int(arguments.get("report_id"))
    except (TypeError, ValueError):
        raise ToolInputError("Informe o relatório que deve ser consultado.")
    found = _reports(context, report_id)
    if not found:
        raise ToolInputError("Relatório indisponível neste contexto.")
    metrics = repository.rows("""SELECT DISTINCT ON (s.id)
             s.id AS source_id, s.original_name, s.supplier, s.period_start, s.period_end,
             r.metrics, r.note, r.report_revision, r.created_at
        FROM cadu_connect_report_sources s
        JOIN cadu_connect_report_source_reviews r ON r.source_id = s.id
       WHERE s.report_id = %s AND s.status = 'reviewed'
    ORDER BY s.id, r.report_revision DESC, r.created_at DESC""", (report_id,))
    report = found[0]
    return {
        "report": {key: report.get(key) for key in ("id", "project_ref", "campaign_name", "document", "revision", "updated_at")},
        "reviewed_sources": metrics,
        "metric_policy": "Somente métricas revisadas são tratadas como evidência factual.",
    }


@register_tool(
    name="reports.compare_report_to_plan", capability="reports", requires_project=True,
    description="Reúne um relatório revisado e um plano autorizado para comparação; solicita seleção quando um lado está ausente.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {"report_id": {"type": ["integer", "string"]}, "plan_id": {"type": "string"}},
        "additionalProperties": False,
    },
)
def compare_report_to_plan(context: RequestContext, arguments: dict) -> dict:
    report_id, plan_id = arguments.get("report_id"), str(arguments.get("plan_id") or "").strip()
    report = None
    if report_id not in (None, ""):
        report = get_report_metrics(context, {"report_id": report_id})
    available_plans = plans.list_plans(context.client_id, context.user_id)
    plan = plans.get_plan(context.client_id, context.user_id, plan_id) if plan_id else None
    if not report:
        return {"status": "needs_report", "reports": list_project_reports(context, {})["reports"],
                "plan": plan, "instruction": "Peça ao usuário para selecionar um relatório."}
    if not plan:
        return {"status": "needs_plan", "report": report,
                "plans": [{key: row.get(key) for key in ("id", "title", "objective", "status")} for row in available_plans[:20]],
                "instruction": "Peça ao usuário para selecionar o plano correto; não escolha apenas por nome."}
    return {"status": "ready", "report": report,
            "plan": {key: plan.get(key) for key in ("id", "title", "objective", "briefing", "items", "allocations", "readiness")}}
