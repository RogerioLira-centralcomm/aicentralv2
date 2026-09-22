"""Transactional product e-mails with a safe, opt-in delivery boundary."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import current_app

from .brevo_service import product_email_brand
from .cadu_email_connector import send_cadu_event


def _enabled() -> bool:
    return bool(current_app.config.get("CADU_PRODUCT_EMAILS_ENABLED", False))


def _decimal(value, default="0") -> Decimal:
    try:
        return max(Decimal("0"), Decimal(str(value if value not in (None, "") else default)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _number_pt(value) -> str:
    return f"{max(0, int(value or 0)):,}".replace(",", ".")


def _money_pt(value, prefix="R$", decimals=2) -> str:
    places = max(2, min(int(decimals or 2), 6))
    amount = _decimal(value).quantize(Decimal("1").scaleb(-places), rounding=ROUND_HALF_UP)
    base = f"{amount:,.{places}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{prefix} {base}"


def _duration_pt(minutes) -> str:
    total = max(0, int(minutes or 0))
    hours, rest = divmod(total, 60)
    if not hours:
        return f"{rest} minutos"
    return f"{hours}h {rest:02d}min" if rest else f"{hours}h"


def _active_credit_reference() -> tuple[Decimal, str]:
    """Resolve the unit token price from the current Cadu commercial plans."""
    try:
        from ..db import get_db

        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT plan_name, plan_type, monthly_price, price,
                          tokens_monthly_limit, tokens_limit
                     FROM cadu_plan_definitions
                    WHERE is_active = true
                      AND COALESCE(plan_type, '') IN ('pro', 'enterprise')
                      AND COALESCE(tokens_monthly_limit, tokens_limit, 0) > 0
                      AND COALESCE(monthly_price, price, 0) >= 0
                    ORDER BY COALESCE(monthly_price, price) /
                             NULLIF(COALESCE(tokens_monthly_limit, tokens_limit), 0)
                    LIMIT 1"""
            )
            row = cursor.fetchone() or {}
        tokens = max(1, int(row.get("tokens_monthly_limit") or row.get("tokens_limit") or 1))
        price = _decimal(row.get("monthly_price") or row.get("price")) / Decimal(tokens)
        return price, str(row.get("plan_name") or row.get("plan_type") or "plano comercial vigente")
    except Exception:
        current_app.logger.warning("Plano comercial de tokens indisponível; tentando pacotes legados", exc_info=True)
        try:
            from ..db import get_db

            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT name, price, credits
                         FROM cadu_credit_packages
                        WHERE is_active = true AND credits > 0 AND price >= 0
                        ORDER BY price / NULLIF(credits, 0), display_order, id
                        LIMIT 1"""
                )
                row = cursor.fetchone() or {}
            credits = max(1, int(row.get("credits") or 1))
            return _decimal(row.get("price")) / Decimal(credits), str(row.get("name") or "pacote legado vigente")
        except Exception:
            current_app.logger.warning("Não foi possível resolver nenhum preço de tokens", exc_info=True)
            return Decimal("0"), "preço indisponível"


def studio_completion_estimates(metrics: dict) -> dict:
    """Build transparent commercial estimates for the finalization receipt."""
    data = metrics if isinstance(metrics, dict) else {}
    generation = max(0, int(data.get("generation_count") or 0))
    edits = max(0, int(data.get("edit_count") or 0))
    formats = max(0, int(data.get("format_count") or 0))
    handoffs = max(0, int(data.get("handoff_count") or 0))
    manual_minutes = max(0, int(data.get("estimated_manual_minutes") or 0))
    if not manual_minutes:
        manual_minutes = generation * 45 + edits * 12 + formats * 8 + handoffs * 10

    salary = _decimal(current_app.config.get("STUDIO_DESIGNER_MONTHLY_SALARY_BRL", "3500"), "3500")
    monthly_hours = _decimal(current_app.config.get("STUDIO_DESIGNER_MONTHLY_HOURS", "220"), "220")
    clt_factor = _decimal(current_app.config.get("STUDIO_DESIGNER_CLT_FACTOR", "1.7"), "1.7")
    hourly_employer_cost = (salary / monthly_hours) * clt_factor if monthly_hours else Decimal("0")
    designer_cost = hourly_employer_cost * Decimal(manual_minutes) / Decimal("60")
    internal_cost_usd = _decimal(data.get("internal_cost_usd"))
    charged_credits = max(0, int(data.get("charged_credits") or data.get("credits") or 0))
    sale_unit = _decimal(data.get("sale_price_per_credit_brl"))
    sale_package_name = str(data.get("sale_package_name") or "").strip()
    if not sale_unit:
        sale_unit, resolved_package = _active_credit_reference()
        sale_package_name = sale_package_name or resolved_package
    return {
        "manual_minutes": manual_minutes,
        "manual_time_label": _duration_pt(manual_minutes),
        "designer_cost_brl": _money_pt(designer_cost),
        "designer_salary_brl": _money_pt(salary),
        "monthly_hours": int(monthly_hours),
        "clt_factor": str(clt_factor.normalize()).replace(".", ","),
        "charged_credits": _number_pt(charged_credits),
        "provider_tokens": _number_pt(data.get("provider_tokens") or 0),
        "internal_cost_usd": _money_pt(internal_cost_usd, "US$", decimals=4),
        "sale_unit_brl": _money_pt(sale_unit),
        "sale_value_brl": _money_pt(sale_unit * Decimal(charged_credits)),
        "sale_package_name": sale_package_name or "pacote vigente",
    }


def send_piece_ready(*, recipient_email: str, recipient_name: str, title: str, url: str, kind: str) -> dict:
    """Notify only the creator and never expose a public creative URL."""
    if not recipient_email or not _enabled():
        return {"success": True, "skipped": True}
    label = "vídeo" if kind == "video" else "peça"
    return send_cadu_event(product="studio", event="studio.piece_ready", template="produto-atividade.html",
        recipient=recipient_email, recipient_name=recipient_name or "Pessoa criadora",
        subject=f"Sua {label} está pronta para continuar no Studio",
        params={
            "BRAND": product_email_brand("studio"), "TITLE": title or f"Nova {label}",
            "DESCRIPTION": f"A {label} foi salva no Studio e está disponível no contexto da sua marca.",
            "CTA_LABEL": f"Ver {label}", "CTA_URL": url,
        },
    )


def send_studio_session_saved(*, recipient_email: str, recipient_name: str, title: str,
                              session_url: str, stage_image_url: str = "", edits: int = 0,
                              estimated_credits: int = 0, estimated_minutes: int = 0,
                              review_points: list[str] | None = None) -> dict:
    """Send one resumable-work receipt when an edit session is first saved.

    Autosaves do not call this function: the Studio route emits it only after
    creating the session, so routine editing never turns into e-mail noise.
    """
    if not recipient_email or not _enabled():
        return {"success": True, "skipped": True}
    points = [str(item).strip() for item in (review_points or []) if str(item).strip()][:4]
    return send_cadu_event(product="studio", event="studio.session_saved", template="studio-sessao-salva.html",
        recipient=recipient_email, recipient_name=recipient_name or "Pessoa criadora",
        subject=f"Sua mesa “{title or 'Studio'}” está salva para continuar",
        params={
            "BRAND": product_email_brand("studio"), "TITLE": title or "Mesa de edição salva",
            "SESSION_URL": session_url, "STAGE_IMAGE_URL": stage_image_url,
            "EDIT_COUNT": max(0, int(edits or 0)), "ESTIMATED_CREDITS": max(0, int(estimated_credits or 0)),
            "ESTIMATED_MINUTES": max(0, int(estimated_minutes or 0)), "REVIEW_POINTS": points,
        },
    )


def send_studio_work_completed(*, recipient_email: str, recipient_name: str, title: str,
                               asset_url: str, studio_url: str, metrics: dict,
                               public_url: str = "", session_url: str = "") -> dict:
    """Send the immutable first-finalization receipt for a Studio work chain."""
    if not recipient_email or not _enabled():
        return {"success": True, "skipped": True}
    data = metrics if isinstance(metrics, dict) else {}
    estimates = studio_completion_estimates(data)
    return send_cadu_event(product="studio", event="studio.work_completed", template="studio-trabalho-finalizado.html",
        recipient=recipient_email, recipient_name=recipient_name or "Pessoa criadora",
        subject=f"Seu trabalho “{title or 'Studio'}” foi finalizado",
        params={
            "BRAND": product_email_brand("studio"), "TITLE": title or "Trabalho finalizado",
            "ASSET_URL": asset_url, "PUBLIC_URL": public_url or asset_url,
            "STUDIO_URL": studio_url, "SESSION_URL": session_url or studio_url,
            "OUTPUT_TYPE": data.get("output_type") or data.get("media_type") or "Peça criativa",
            "EXTENSION": data.get("extension") or data.get("file_extension") or "—",
            "FORMAT_NAME": data.get("format_name") or data.get("format") or "—",
            "WIDTH": data.get("width") or data.get("width_px") or "—",
            "HEIGHT": data.get("height") or data.get("height_px") or "—",
            "DURATION": data.get("duration") or data.get("duration_label") or "—",
            "PROJECT_NAME": data.get("project_name") or data.get("project_title") or "Sem projeto vinculado",
            "GENERATION_COUNT": max(0, int(data.get("generation_count") or 0)),
            "EDIT_COUNT": max(0, int(data.get("edit_count") or 0)),
            "FORMAT_COUNT": max(0, int(data.get("format_count") or 0)),
            "HANDOFF_COUNT": max(0, int(data.get("handoff_count") or 0)),
            "ESTIMATED_MINUTES_SAVED": max(0, int(data.get("estimated_minutes_saved") or 0)),
            "ACTIVE_TIME": _duration_pt(max(1, round(int(data.get("active_seconds") or 0) / 60))),
            "ESTIMATED_MANUAL_TIME": estimates["manual_time_label"],
            "AI_CREDITS_USED": estimates["charged_credits"],
            "PROVIDER_TOKENS": estimates["provider_tokens"],
            "AI_COST_USD": estimates["internal_cost_usd"],
            "CREDIT_SALE_UNIT_BRL": estimates["sale_unit_brl"],
            "CREDIT_SALE_VALUE_BRL": estimates["sale_value_brl"],
            "CREDIT_SALE_PACKAGE": estimates["sale_package_name"],
            "DESIGNER_COST_BRL": estimates["designer_cost_brl"],
            "DESIGNER_SALARY_BRL": estimates["designer_salary_brl"],
            "DESIGNER_MONTHLY_HOURS": estimates["monthly_hours"],
            "DESIGNER_CLT_FACTOR": estimates["clt_factor"],
        },
    )


def send_brand_audit_ready(*, recipient_email: str, recipient_name: str, brand_name: str,
                           summary: str, differentiators: list[str], url: str, logo_url: str = '',
                           status: str = 'approved', coverage=None, costs=None, effort=None) -> dict:
    """Notify the requester only after a reviewable brand proposal is ready."""
    if not recipient_email or not _enabled():
        return {"success": True, "skipped": True}
    highlights = "; ".join(str(item).strip() for item in (differentiators or [])[:3] if str(item).strip())
    description = str(summary or '').strip()
    if highlights:
        description = f"{description}\n\nDiferenciais observados: {highlights}".strip()
    return send_cadu_event(product="workspace", event="workspace.brand_audit_ready", template="produto-atividade.html",
        recipient=recipient_email, recipient_name=recipient_name or "Pessoa criadora",
        subject=f"A leitura de {brand_name or 'sua marca'} está pronta para revisão",
        params={
            "BRAND": product_email_brand("workspace"),
            "TITLE": f"A proposta de {brand_name or 'marca'} está pronta",
            "DESCRIPTION": description or "Encontramos evidências para você revisar antes de aplicar à marca.",
            "CTA_LABEL": "Abrir auditoria", "CTA_URL": url,
            "BRAND_LOGO_URL": logo_url, "AUDIT_STATUS": status,
            "AUDIT_COVERAGE": coverage or {}, "AUDIT_COSTS": costs or {}, "AUDIT_EFFORT": effort or {},
        },
    )


WORKSPACE_ONBOARDING = (
    (0, "Boas-vindas ao Workspace", "Conheça o lugar onde seu time organiza o trabalho.", "Abrir Workspace", "/workspace/app"),
    (1, "Comece por um projeto", "Dê um nome ao trabalho que sua equipe vai conduzir.", "Ver projetos", "/workspace/app/projetos"),
    (3, "Organize sua marca", "Referências, identidades e decisões começam pela marca.", "Ver marcas", "/workspace/app/marcas"),
    (5, "Traga sua equipe", "Convide as pessoas que vão decidir e produzir junto.", "Ver equipe", "/workspace/app/equipe"),
    (7, "Planeje antes de produzir", "Use o Planner para transformar objetivo em direção de mídia.", "Abrir Planner", "/"),
    (10, "Sua primeira peça", "O Studio parte da marca e do projeto para criar com contexto.", "Abrir Studio", "/"),
    (14, "Transforme dados de campanha em uma leitura clara", "Reúna fontes, revise indicadores e compartilhe um report que sustenta a próxima decisão.", "Abrir Reports", "/"),
    (18, "Skills para decisões recorrentes", "Escolha uma capacidade especializada para o próximo passo.", "Abrir Skills", "/skills/"),
    (22, "Acompanhe seus créditos", "Veja o saldo compartilhado antes de iniciar uma execução.", "Ver créditos", "/workspace/app/creditos"),
    (28, "Seu contexto está pronto", "Projetos, marcas e equipe agora acompanham o trabalho entre produtos.", "Abrir Workspace", "/workspace/app"),
)
