"""E-mails dos eventos do Workspace, com regras para não virar ruído.

- projeto criado: avisa o resto do time (nunca quem criou; contas de uma pessoa não recebem);
- fonte recebida: avisa o dono do projeto quando um colega adiciona algo;
- fonte lida: só quando a leitura de um link demorou (a pessoa provavelmente saiu da tela);
- documento revisado: só quando a revisão levou mais de 45 s;
- trabalho longo concluído: sempre (por definição a pessoa não ficou esperando).

Cada aviso tem um intervalo mínimo por pessoa e por assunto (``_recently_sent``),
roda fora da requisição (``fire``) e nunca derruba o fluxo que o chamou.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Iterable, Optional

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

SLOW_SOURCE_SECONDS = 120
SLOW_REVIEW_SECONDS = 45
MAX_TEAM_RECIPIENTS = 25


def fire(fn, /, **kwargs) -> None:
    """Executa ``fn`` em segundo plano com app context; a requisição não espera a Brevo."""
    if not has_app_context():
        return
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            try:
                fn(**kwargs)
            except Exception:  # noqa: BLE001 — aviso é cortesia
                logger.warning("Aviso do Workspace %s não enviado.", getattr(fn, "__name__", fn), exc_info=True)

    threading.Thread(target=run, daemon=True, name="cadu-workspace-mail").start()


def _db():
    from ..db import get_db
    return get_db()


def _recently_sent(recipient: str, event: str, *, subject: Optional[str] = None, hours: int = 1) -> bool:
    try:
        with _db().cursor() as cursor:
            cursor.execute(
                f"""SELECT 1 FROM cadu_workspace_email_events
                     WHERE LOWER(recipient_email) = LOWER(%s) AND event_type = %s
                       AND created_at > NOW() - INTERVAL '{int(hours)} hours'
                       {"AND subject = %s" if subject else ""}
                     LIMIT 1""",
                (recipient, event, subject) if subject else (recipient, event),
            )
            return cursor.fetchone() is not None
    except Exception:
        logger.warning("Não foi possível conferir o intervalo do aviso %s.", event, exc_info=True)
        try:
            _db().rollback()
        except Exception:
            pass
        return True  # na dúvida, não envia de novo


def _contact(contato_id) -> dict:
    from .. import db
    return dict(db.obter_contato_por_id(int(contato_id)) or {}) if contato_id else {}


def _first(name: str) -> str:
    return (str(name or "").split() or ["alguém do time"])[0]


def _send(event: str, *, recipient: dict, subject: str, title: str, description: str, cta_label: str, cta_url: str,
          client_id=None, throttle_hours: int = 1, throttle_subject: bool = True) -> dict:
    from .brevo_service import product_email_brand
    from .cadu_email_connector import send_cadu_event
    from .cadu_product_emails import _enabled

    email = str(recipient.get("email") or "").strip()
    if not email or not _enabled() or recipient.get("status") is False:
        return {"success": True, "skipped": True}

    def deliver():
        return send_cadu_event(product="workspace", event=event, template="produto-atividade.html",
                               recipient=email, recipient_name=recipient.get("nome_completo") or "Pessoa do time",
                               subject=subject, client_id=client_id,
                               params={"BRAND": product_email_brand("workspace"), "TITLE": title,
                                       "DESCRIPTION": description, "CTA_LABEL": cta_label, "CTA_URL": cta_url})

    if throttle_hours <= 0:
        return deliver()
    # Vários uploads chegam em requisições paralelas: sem trava, todos passariam pela checagem antes do
    # primeiro registro. A trava no banco (vale entre processos) serializa "conferir + enviar + registrar".
    key = f"{email.lower()}|{event}|{subject if throttle_subject else ''}"
    conn = _db()
    locked = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(hashtext(%s))", (key,))
        locked = True
        if _recently_sent(email, event, subject=subject if throttle_subject else None, hours=throttle_hours):
            return {"success": True, "skipped": True, "reason": "throttled"}
        return deliver()
    finally:
        if locked:
            try:
                with _db().cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", (key,))
                _db().commit()
            except Exception:  # conexão fechada pelo registro: a trava de sessão já foi liberada
                pass


def _project(client_id: int, project_id: str) -> dict:
    with _db().cursor() as cursor:
        cursor.execute("SELECT id::text AS id, nome, criado_por FROM cadu_ci_projetos WHERE id::text = %s AND id_cliente = %s",
                       (str(project_id), client_id))
        return dict(cursor.fetchone() or {})


def _project_url(project_id: str) -> str:
    from ..product_domains import product_url
    return product_url("workspace", f"/projetos/{project_id}")


# --------------------------------------------------------------------------- eventos

def notify_project_created(*, client_id: int, creator_id: int, project_id: str, name: str) -> int:
    with _db().cursor() as cursor:
        cursor.execute("""SELECT id_contato_cliente, nome_completo, email, status FROM tbl_contato_cliente
                           WHERE pk_id_tbl_cliente = %s AND status = TRUE AND id_contato_cliente <> %s
                           ORDER BY id_contato_cliente LIMIT %s""", (client_id, creator_id, MAX_TEAM_RECIPIENTS))
        team = [dict(r) for r in cursor.fetchall()]
    if not team:
        return 0  # conta de uma pessoa: quem criou já sabe
    creator = _first(_contact(creator_id).get("nome_completo"))
    sent = 0
    for member in team:
        result = _send("workspace.project_created", recipient=member, client_id=client_id,
                       subject=f"{creator} criou o projeto {name}"[:150],
                       title=f"Novo projeto no time: {name}",
                       description=(f"{creator} criou o projeto “{name}” no Workspace. Fontes, conversas e decisões "
                                    "desse trabalho vão ficar reunidas lá, para todo o time consultar."),
                       cta_label="Abrir o projeto", cta_url=_project_url(project_id),
                       throttle_hours=1, throttle_subject=False)
        sent += int(bool(result.get("success")) and not result.get("skipped"))
    return sent


def notify_source_received(*, client_id: int, project_id: str, actor_id: int, source_names: Iterable[str]) -> bool:
    names = [str(n) for n in source_names if str(n or "").strip()]
    project = _project(client_id, project_id)
    owner_id = project.get("criado_por")
    if not names or not owner_id or int(owner_id) == int(actor_id or 0):
        return False  # quem adicionou é o próprio dono
    actor = _first(_contact(actor_id).get("nome_completo"))
    listed = ", ".join(f"“{n[:60]}”" for n in names[:3]) + (f" e mais {len(names) - 3}" if len(names) > 3 else "")
    title = project.get("nome") or "seu projeto"
    result = _send("workspace.source_received", recipient=_contact(owner_id), client_id=client_id,
                   subject=f"Novas fontes em {title}"[:150],
                   title=f"{actor} adicionou {'uma fonte' if len(names) == 1 else f'{len(names)} fontes'} em {title}",
                   description=(f"{actor} enviou {listed} para o projeto. O conteúdo passa a ser consultado nas conversas "
                                "e planos desse projeto."),
                   cta_label="Ver as fontes", cta_url=_project_url(project_id), throttle_hours=2)
    return bool(result.get("success")) and not result.get("skipped")


def notify_source_indexed(*, client_id: int, project_id: str, user_id: int, source_name: str,
                          started_at: Optional[datetime]) -> bool:
    if not started_at:
        return False
    started = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - started).total_seconds() < SLOW_SOURCE_SECONDS:
        return False  # foi rápido: a pessoa viu na tela
    result = _send("workspace.source_indexed", recipient=_contact(user_id), client_id=client_id,
                   subject="O link que você enviou já está no projeto",
                   title=f"“{(source_name or 'O link')[:90]}” já pode ser consultado",
                   description="O Cadu terminou de ler o link e o conteúdo já está disponível nas conversas e planos do projeto.",
                   cta_label="Abrir o projeto", cta_url=_project_url(project_id), throttle_hours=1, throttle_subject=False)
    return bool(result.get("success")) and not result.get("skipped")


def notify_document_reviewed(*, client_id: int, user_id: int, document_id: str, title: str, elapsed_seconds: float) -> bool:
    if elapsed_seconds < SLOW_REVIEW_SECONDS:
        return False
    from ..product_domains import product_url
    result = _send("workspace.document_reviewed", recipient=_contact(user_id), client_id=client_id,
                   subject=f"Revisão pronta: {title or 'documento'}"[:150],
                   title=f"A revisão de “{(title or 'seu documento')[:90]}” terminou",
                   description="O Cadu fez as três passagens de revisão. Abra o documento para comparar e aceitar as mudanças.",
                   cta_label="Abrir o documento", cta_url=product_url("workspace", f"/docs/{document_id}"), throttle_hours=0)
    return bool(result.get("success")) and not result.get("skipped")


def notify_conversation_important(*, client_id: int, user_id: int, title: str, project_ref: Optional[str]) -> bool:
    from ..product_domains import product_url
    url = (_project_url(project_ref[3:]) if project_ref and project_ref.startswith("ci:")
           else product_url("workspace", "/chat"))
    result = _send("workspace.conversation_important", recipient=_contact(user_id), client_id=client_id,
                   subject=f"Pronto: {title or 'o trabalho que você pediu'}"[:150],
                   title=f"Terminamos “{(title or 'o trabalho longo')[:90]}”",
                   description=("O trabalho longo que você pediu ao Cadu foi concluído. O resultado está na conversa, "
                                "com o documento pronto para revisar e editar."),
                   cta_label="Ver o resultado", cta_url=url, throttle_hours=0)
    return bool(result.get("success")) and not result.get("skipped")
