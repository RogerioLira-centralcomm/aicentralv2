"""Transactional product e-mails with a safe, opt-in delivery boundary."""

from __future__ import annotations

from flask import current_app

from .brevo_service import get_brevo_product_service, product_email_brand


def _enabled() -> bool:
    return bool(current_app.config.get("CADU_PRODUCT_EMAILS_ENABLED", False))


def send_piece_ready(*, recipient_email: str, recipient_name: str, title: str, url: str, kind: str) -> dict:
    """Notify only the creator and never expose a public creative URL."""
    if not recipient_email or not _enabled():
        return {"success": True, "skipped": True}
    label = "vídeo" if kind == "video" else "peça"
    return get_brevo_product_service("studio").enviar_email_com_template(
        template_name="produto-atividade.html", template_folder="emails/externos",
        to_email=recipient_email, to_name=recipient_name or "Pessoa criadora",
        subject=f"Sua {label} está pronta para continuar no Studio",
        params={
            "BRAND": product_email_brand("studio"), "TITLE": title or f"Nova {label}",
            "DESCRIPTION": f"A {label} foi salva no Studio e está disponível no contexto da sua marca.",
            "CTA_LABEL": f"Ver {label}", "CTA_URL": url,
        },
    )


def send_studio_work_completed(*, recipient_email: str, recipient_name: str, title: str,
                               asset_url: str, studio_url: str, metrics: dict) -> dict:
    """Send the immutable first-finalization receipt for a Studio work chain."""
    if not recipient_email or not _enabled():
        return {"success": True, "skipped": True}
    data = metrics if isinstance(metrics, dict) else {}
    return get_brevo_product_service("studio").enviar_email_com_template(
        template_name="studio-trabalho-finalizado.html", template_folder="emails/externos",
        to_email=recipient_email, to_name=recipient_name or "Pessoa criadora",
        subject=f"Seu trabalho “{title or 'Studio'}” foi finalizado",
        params={
            "BRAND": product_email_brand("studio"), "TITLE": title or "Trabalho finalizado",
            "ASSET_URL": asset_url, "STUDIO_URL": studio_url,
            "GENERATION_COUNT": max(0, int(data.get("generation_count") or 0)),
            "EDIT_COUNT": max(0, int(data.get("edit_count") or 0)),
            "FORMAT_COUNT": max(0, int(data.get("format_count") or 0)),
            "HANDOFF_COUNT": max(0, int(data.get("handoff_count") or 0)),
            "ESTIMATED_MINUTES_SAVED": max(0, int(data.get("estimated_minutes_saved") or 0)),
        },
    )


def send_brand_audit_ready(*, recipient_email: str, recipient_name: str, brand_name: str,
                           summary: str, differentiators: list[str], url: str) -> dict:
    """Notify the requester only after a reviewable brand proposal is ready."""
    if not recipient_email or not _enabled():
        return {"success": True, "skipped": True}
    highlights = "; ".join(str(item).strip() for item in (differentiators or [])[:3] if str(item).strip())
    description = str(summary or '').strip()
    if highlights:
        description = f"{description}\n\nDiferenciais observados: {highlights}".strip()
    return get_brevo_product_service("workspace").enviar_email_com_template(
        template_name="produto-atividade.html", template_folder="emails/externos",
        to_email=recipient_email, to_name=recipient_name or "Pessoa criadora",
        subject=f"A leitura de {brand_name or 'sua marca'} está pronta para revisão",
        params={
            "BRAND": product_email_brand("workspace"),
            "TITLE": f"A proposta de {brand_name or 'marca'} está pronta",
            "DESCRIPTION": description or "Encontramos evidências para você revisar antes de aplicar à marca.",
            "CTA_LABEL": "Revisar marca", "CTA_URL": url,
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
