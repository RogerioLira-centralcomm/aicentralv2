"""Sequência de e-mails de adoção do Cadu: agenda, envio, descadastro e registro.

Regras (decisões do dono, 2026-10-11):
- 6 e-mails a cada 2 dias, começando 2 dias depois do onboarding concluído;
- ligada por ``CADU_EMAIL_SEQUENCE_ENABLED`` (padrão desligada);
- nunca envia a quem se descadastrou, fora de 8h–21h (Brasília) ou com falha repetida.

A decisão de "o que fazer agora" fica em funções puras (``decide_due``) para ser
testável sem banco; o acesso ao banco fica em funções finas.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from flask import current_app

logger = logging.getLogger(__name__)

SEQUENCE_KEY = "adocao_v1"
# Ordem aprovada no plano docs/plans/cadu-email-sequencia-e-painel.md (seção 5c).
SEQUENCE_STEPS = (
    "dicas-de-uso", "dicas-de-prompts", "planner-radar", "studio-criar", "planner-interativos",
    "plugins-agentes", "connect-reports",
)
# Sinal de que a pessoa já usa a ferramenta: o passo correspondente é pulado (sem envio).
USAGE_SIGNALS = {
    "planner-radar": ("cadu_radar_runs", "created_by", "Radar de Oportunidades", "created_at"),
    "studio-criar": ("cx_studio_assets", "owner_user_id", "Studio para criar anúncios e imagens", "created_at"),
    "plugins-agentes": ("cadu_public_mcp_usage", "user_id", "seu assistente de IA conectado ao Cadu", "created_at"),
}
# Atividade (para não lembrar quem já usa o Cadu): ferramentas acima + conversas no Workspace.
ACTIVITY_SIGNALS = {**USAGE_SIGNALS, "conversas": ("cadu_conversations", "id_contato_cliente", "Conversas", "updated_at")}
REENGAGEMENT_KEY = "reengajamento"
REENGAGEMENT_AFTER = timedelta(days=7)
INTERVAL = timedelta(days=2)
RETRY_DELAY = timedelta(hours=1)
LEASE = timedelta(minutes=30)
MAX_ATTEMPTS = 3
SEND_WINDOW = (8, 21)  # hora local de Brasília: envia a partir das 8h até antes das 21h
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
UNSUB_SALT = "cadu-email-unsubscribe"


def sequence_enabled() -> bool:
    return os.getenv("CADU_EMAIL_SEQUENCE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- descadastro

def _serializer():
    from itsdangerous import URLSafeSerializer
    return URLSafeSerializer(current_app.secret_key, salt=UNSUB_SALT)


def make_unsubscribe_token(contato_id: int) -> str:
    return _serializer().dumps({"c": int(contato_id)})


def read_unsubscribe_token(token: str) -> Optional[int]:
    try:
        data = _serializer().loads(str(token or ""))
        return int(data["c"])
    except Exception:
        return None


def unsubscribe_url(contato_id: int) -> str:
    from ..product_domains import product_url
    return product_url("workspace", f"/workspace/email/descadastrar/{make_unsubscribe_token(contato_id)}")


# --------------------------------------------------------------------------- decisão pura

def adjust_to_send_window(moment: datetime) -> datetime:
    """Move para 9h local do dia útil de envio se cair fora da janela (8h–21h Brasília)."""
    local = moment.astimezone(LOCAL_TZ)
    start, end = SEND_WINDOW
    if start <= local.hour < end:
        return moment
    day = local.date() if local.hour < start else local.date() + timedelta(days=1)
    return datetime(day.year, day.month, day.day, start + 1, 0, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def decide_due(row: dict, now: datetime) -> dict:
    """Ação para uma linha vencida: ``send``, ``cancel``, ``pause``, ``defer`` ou ``complete``."""
    if row.get("marketing_opt_out"):
        return {"action": "cancel", "reason": "descadastro"}
    if not row.get("email") or row.get("contact_active") is False:
        return {"action": "pause", "reason": "contato_inativo"}
    step = int(row.get("next_step") or 1)
    if step > len(SEQUENCE_STEPS):
        return {"action": "complete"}
    deferred = adjust_to_send_window(now)
    if deferred > now:
        return {"action": "defer", "until": deferred}
    return {"action": "send", "step": step, "model_key": SEQUENCE_STEPS[step - 1]}


def after_success(step: int, now: datetime) -> dict:
    if step >= len(SEQUENCE_STEPS):
        return {"status": "completed", "next_step": step + 1, "next_send_at": None}
    return {"status": "active", "next_step": step + 1, "next_send_at": adjust_to_send_window(now + INTERVAL)}


def after_failure(attempts: int, now: datetime) -> dict:
    if attempts >= MAX_ATTEMPTS:
        return {"status": "paused", "paused_reason": "falha_envio", "next_send_at": None}
    return {"status": "active", "next_send_at": now + RETRY_DELAY}


# --------------------------------------------------------------------------- banco

def _db():
    from ..db import get_db
    return get_db()


def enroll_contact(contato_id: int, *, sequence_key: str = SEQUENCE_KEY, start_at: Optional[datetime] = None) -> bool:
    """Inscreve (uma única vez) um contato; ``start_at`` padrão é agora + 2 dias."""
    when = adjust_to_send_window(start_at or (datetime.now(timezone.utc) + INTERVAL))
    conn = _db()
    with conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO cadu_email_sequence_state (contato_id, sequence_key, next_step, next_send_at, status)
               VALUES (%s, %s, 1, %s, 'active')
               ON CONFLICT (contato_id, sequence_key) DO NOTHING
               RETURNING id""",
            (contato_id, sequence_key, when),
        )
        created = cursor.fetchone() is not None
    conn.commit()
    return created


def set_opt_out(contato_id: int, source: str, *, opted_out: bool = True) -> None:
    conn = _db()
    with conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO cadu_email_preferences (contato_id, marketing_opt_out, opted_out_at, opt_out_source, updated_at)
               VALUES (%s, %s, CASE WHEN %s THEN NOW() END, CASE WHEN %s THEN %s END, NOW())
               ON CONFLICT (contato_id) DO UPDATE
                  SET marketing_opt_out = EXCLUDED.marketing_opt_out,
                      opted_out_at = EXCLUDED.opted_out_at,
                      opt_out_source = EXCLUDED.opt_out_source,
                      updated_at = NOW()""",
            (contato_id, opted_out, opted_out, opted_out, source),
        )
        if opted_out:
            cursor.execute(
                """UPDATE cadu_email_sequence_state SET status = 'cancelled', paused_reason = 'descadastro',
                          next_send_at = NULL, updated_at = NOW()
                    WHERE contato_id = %s AND status IN ('active', 'paused')""",
                (contato_id,),
            )
    conn.commit()


def log_email(*, contato_id, client_id, email: str, kind: str, event_type: str, subject: str, status: str,
              message_id: Optional[str] = None, error: Optional[str] = None,
              sequence_key: Optional[str] = None, step: Optional[int] = None) -> None:
    try:
        conn = _db()
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_email_log
                       (contato_id, id_cliente, recipient_email, kind, event_type, sequence_key, step,
                        subject, status, provider_message_id, provider_error)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (contato_id, client_id, email, kind, event_type, sequence_key, step, subject[:255], status,
                 message_id, (str(error)[:4000] if error else None)),
            )
        conn.commit()
    except Exception:
        logger.warning("Não foi possível registrar o envio no cadu_email_log.", exc_info=True)
        try:
            _db().rollback()
        except Exception:
            pass


_DUE_SQL = """
    SELECT s.id, s.contato_id, s.sequence_key, s.next_step, s.attempts,
           c.email, c.nome_completo, c.pk_id_tbl_cliente AS client_id,
           COALESCE(c.status, TRUE) AS contact_active,
           COALESCE(p.marketing_opt_out, FALSE) AS marketing_opt_out
      FROM cadu_email_sequence_state s
      JOIN tbl_contato_cliente c ON c.id_contato_cliente = s.contato_id
      LEFT JOIN cadu_email_preferences p ON p.contato_id = s.contato_id
     WHERE s.status = 'active' AND s.sequence_key = %s AND s.next_send_at <= NOW()
     ORDER BY s.next_send_at
     LIMIT %s
     FOR UPDATE OF s SKIP LOCKED"""


def _update_state(cursor, state_id: int, **fields) -> None:
    sets = ", ".join(f"{name} = %s" for name in fields)
    cursor.execute(f"UPDATE cadu_email_sequence_state SET {sets}, updated_at = NOW() WHERE id = %s",
                   (*fields.values(), state_id))


def last_usage(contato_id: int, *, keys=None, signals=None) -> dict:
    """Último uso de cada ferramenta com sinal conhecido. Tabela ausente ou erro: sem sinal (envia)."""
    found = {}
    conn = _db()
    for key, (table, column, _label, time_column) in (signals or USAGE_SIGNALS).items():
        if keys is not None and key not in keys:
            continue
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT to_regclass('public.{table}') IS NOT NULL AS ok")
                if not (cursor.fetchone() or {}).get("ok"):
                    continue
                cursor.execute(f"SELECT MAX({time_column}) AS at FROM {table} WHERE {column} = %s", (contato_id,))
                found[key] = (cursor.fetchone() or {}).get("at")
        except Exception:
            logger.warning("Sinal de uso %s indisponível.", table, exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
    return found


def send_sequence_step(row: dict, model_key: str, step: int) -> dict:
    """Renderiza e envia um passo; devolve o resultado da Brevo."""
    from .brevo_service import get_brevo_product_service
    from .cadu_growth_email_templates import GROWTH_EMAIL_MODELS, render_growth_email

    first_name = (str(row.get("nome_completo") or "").split() or [""])[0]
    unsub = unsubscribe_url(row["contato_id"])
    html = render_growth_email(model_key, first_name=first_name or None, unsubscribe_url=unsub)
    model = GROWTH_EMAIL_MODELS[model_key]
    return get_brevo_product_service(model["product"]).enviar_email(
        to_email=row["email"], to_name=row.get("nome_completo") or "",
        subject=model["subject"], html_content=html,
        headers={"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
        tags=[f"seq:{row['sequence_key']}", f"passo:{step}"],
    )


def process_due(limit: int = 50) -> dict:
    """Envia os passos vencidos. Seguro para rodar de tempos em tempos e em paralelo."""
    result = {"sent": 0, "failed": 0, "deferred": 0, "cancelled": 0, "paused": 0, "completed": 0}
    if not sequence_enabled():
        result["disabled"] = True
        return result
    conn = _db()
    now = datetime.now(timezone.utc)
    with conn.cursor() as cursor:
        cursor.execute(_DUE_SQL, (SEQUENCE_KEY, int(limit)))
        rows = [dict(r) for r in cursor.fetchall()]
        leased = []
        for row in rows:
            decision = decide_due(row, now)
            action = decision["action"]
            if action == "send":
                # Reserva (lease) antes de enviar: se o processo morrer entre o envio e o registro,
                # o passo só volta a vencer depois de 30 minutos, não imediatamente.
                _update_state(cursor, row["id"], next_send_at=now + LEASE)
                leased.append((row, decision))
            elif action == "defer":
                _update_state(cursor, row["id"], next_send_at=decision["until"])
                result["deferred"] += 1
            elif action == "cancel":
                _update_state(cursor, row["id"], status="cancelled", paused_reason=decision["reason"], next_send_at=None)
                result["cancelled"] += 1
            elif action == "pause":
                _update_state(cursor, row["id"], status="paused", paused_reason=decision["reason"], next_send_at=None)
                result["paused"] += 1
            else:
                _update_state(cursor, row["id"], status="completed", next_send_at=None)
                result["completed"] += 1
    conn.commit()

    for row, decision in leased:
        step, model_key = decision["step"], decision["model_key"]
        if model_key in USAGE_SIGNALS and last_usage(row["contato_id"], keys={model_key}).get(model_key):
            # Já usa a ferramenta: o e-mail que ensina a usá-la seria ruído. Pula e segue para o próximo.
            log_email(contato_id=row["contato_id"], client_id=row.get("client_id"), email=row["email"], kind="sequence",
                      event_type=f"seq.{model_key}", subject="Passo pulado: a pessoa já usa a ferramenta",
                      status="skipped", sequence_key=row["sequence_key"], step=step)
            with conn.cursor() as cursor:
                nxt = after_success(step, datetime.now(timezone.utc))
                if nxt["status"] == "active":
                    nxt["next_send_at"] = adjust_to_send_window(datetime.now(timezone.utc))
                _update_state(cursor, row["id"], attempts=0, **nxt)
            conn.commit()
            result["skipped"] = result.get("skipped", 0) + 1
            continue
        try:
            sent = send_sequence_step(row, model_key, step) or {}
        except Exception as exc:  # um envio com erro nunca trava os outros
            logger.exception("Passo %s da sequência falhou para o contato %s", step, row["contato_id"])
            sent = {"success": False, "error": str(exc)}
        ok = bool(sent.get("success"))
        from .cadu_growth_email_templates import GROWTH_EMAIL_MODELS
        log_email(contato_id=row["contato_id"], client_id=row.get("client_id"), email=row["email"], kind="sequence",
                  event_type=f"seq.{model_key}", subject=GROWTH_EMAIL_MODELS.get(model_key, {}).get("subject", model_key),
                  status="sent" if ok else "failed", message_id=sent.get("messageId"), error=sent.get("error"),
                  sequence_key=row["sequence_key"], step=step)
        now = datetime.now(timezone.utc)
        with conn.cursor() as cursor:
            if ok:
                _update_state(cursor, row["id"], attempts=0, paused_reason=None, **after_success(step, now))
                result["sent"] += 1
            else:
                attempts = int(row.get("attempts") or 0) + 1
                _update_state(cursor, row["id"], attempts=attempts, **after_failure(attempts, now))
                result["failed"] += 1
        conn.commit()
    return result


# --------------------------------------------------------------------------- reengajamento

def reengagement_body(unused: list[str]) -> str:
    """Texto do reengajamento a partir do que a pessoa ainda não usou."""
    intro = "A sua marca e o seu projeto continuam no Workspace, prontos para a próxima conversa, plano ou peça."
    if not unused:
        return intro + "\n\nSe quiser um ponto de partida, abra o projeto e peça ao Cadu **um resumo do que já foi decidido e do que falta**."
    items = "\n\n".join(f"**{label}**" for label in unused)
    return (f"{intro}\n\nAlgumas ferramentas que você ainda não experimentou e que partem desse mesmo contexto:\n\n{items}"
            "\n\nEscolha uma e teste com o projeto que já está lá.")


_REENGAGE_SQL = """
    SELECT * FROM (
    SELECT DISTINCT ON (o.contato_id) o.contato_id, c.email, c.nome_completo, c.pk_id_tbl_cliente AS client_id,
           o.completed_at
      FROM cadu_workspace_onboarding o
      JOIN tbl_contato_cliente c ON c.id_contato_cliente = o.contato_id
      LEFT JOIN cadu_email_preferences p ON p.contato_id = o.contato_id
     WHERE o.completed_at <= NOW() - INTERVAL '7 days'
       AND COALESCE(c.status, TRUE) AND NULLIF(c.email, '') IS NOT NULL
       AND NOT COALESCE(p.marketing_opt_out, FALSE)
       AND NOT EXISTS (SELECT 1 FROM cadu_email_log l WHERE l.contato_id = o.contato_id AND l.event_type = %s)
       AND NOT EXISTS (SELECT 1 FROM cadu_email_log l WHERE l.contato_id = o.contato_id AND l.kind = 'sequence'
                         AND l.status <> 'skipped' AND l.sent_at > NOW() - INTERVAL '48 hours')
       AND NOT EXISTS (SELECT 1 FROM cadu_email_log l WHERE l.contato_id = o.contato_id
                         AND l.first_clicked_at > NOW() - INTERVAL '7 days')
     ORDER BY o.contato_id, o.completed_at
    ) candidates
     ORDER BY completed_at
     LIMIT %s"""


def process_reengagement(limit: int = 20) -> dict:
    """Uma única vez por pessoa: 7 dias sem usar Radar, Studio ou o assistente conectado, nem clicar nos e-mails."""
    result = {"reengaged": 0, "active_users": 0}
    if not sequence_enabled():
        return result
    now = datetime.now(timezone.utc)
    if adjust_to_send_window(now) > now:
        return result  # fora do horário: tenta no próximo ciclo
    with _db().cursor() as cursor:
        cursor.execute(_REENGAGE_SQL, (REENGAGEMENT_KEY, int(limit)))
        candidates = [dict(r) for r in cursor.fetchall()]
    from .brevo_service import get_brevo_product_service
    from .cadu_growth_email_templates import GROWTH_EMAIL_MODELS, build_growth_email
    for row in candidates:
        usage = last_usage(row["contato_id"], signals=ACTIVITY_SIGNALS)
        if any(at and (now - at) < REENGAGEMENT_AFTER for at in usage.values()):
            result["active_users"] += 1
            continue  # usa o produto: não precisa de lembrete
        unused = [USAGE_SIGNALS[key][2] for key in USAGE_SIGNALS if not usage.get(key)]
        first = (str(row.get("nome_completo") or "").split() or [""])[0]
        unsub = unsubscribe_url(row["contato_id"])
        model = GROWTH_EMAIL_MODELS[REENGAGEMENT_KEY]
        try:
            cfg = build_growth_email(REENGAGEMENT_KEY, body=reengagement_body(unused), first_name=first or None,
                                     unsubscribe_url=unsub)
            html = _render_growth(cfg)
            sent = get_brevo_product_service(model["product"]).enviar_email(
                to_email=row["email"], to_name=row.get("nome_completo") or "", subject=model["subject"], html_content=html,
                headers={"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
                tags=["seq:reengajamento"]) or {}
        except Exception as exc:
            logger.exception("Reengajamento falhou para o contato %s", row["contato_id"])
            sent = {"success": False, "error": str(exc)}
        log_email(contato_id=row["contato_id"], client_id=row.get("client_id"), email=row["email"], kind="sequence",
                  event_type=REENGAGEMENT_KEY, subject=model["subject"], status="sent" if sent.get("success") else "failed",
                  message_id=sent.get("messageId"), error=sent.get("error"))
        result["reengaged"] += int(bool(sent.get("success")))
    return result


# --------------------------------------------------------------------------- resumo semanal do time

DIGEST_KEY = "resumo-semanal"
# (rótulo no singular, plural, tabela, coluna da conta, coluna de tempo)
DIGEST_METRICS = (
    ("conversa", "conversas", "cadu_conversations", "id_cliente", "created_at"),
    ("fonte enviada aos projetos", "fontes enviadas aos projetos", "cadu_ci_projeto_arquivos", "id_cliente", "created_at"),
    ("busca no Radar", "buscas no Radar", "cadu_radar_runs", "client_id", "created_at"),
)


def team_week(client_id: int) -> list[tuple[str, int]]:
    """Contagens da semana da conta; métrica sem tabela ou com erro fica de fora."""
    found = []
    conn = _db()
    for singular, plural, table, column, time_column in DIGEST_METRICS:
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT to_regclass('public.{table}') IS NOT NULL AS ok")
                if not (cursor.fetchone() or {}).get("ok"):
                    continue
                cursor.execute(f"""SELECT COUNT(*) AS n FROM {table}
                                    WHERE {column} = %s AND {time_column} >= NOW() - INTERVAL '7 days'""", (client_id,))
                count = int((cursor.fetchone() or {}).get("n") or 0)
            if count:
                found.append((singular if count == 1 else plural, count))
        except Exception:
            logger.warning("Métrica do resumo semanal indisponível: %s", table, exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
    return found


def digest_body(metrics: list[tuple[str, int]]) -> str:
    lines = "\n\n".join(f"**{count}** {label}" for label, count in metrics)
    return ("Um resumo do que o seu time fez no Cadu nos últimos 7 dias:\n\n" + lines +
            "\n\nAbra o Workspace para retomar de onde parou: os projetos guardam o contexto de cada trabalho.")


_DIGEST_SQL = """
    SELECT DISTINCT ON (c.id_contato_cliente) c.id_contato_cliente AS contato_id, c.email, c.nome_completo,
           c.pk_id_tbl_cliente AS client_id
      FROM cadu_workspace_onboarding o
      JOIN tbl_contato_cliente c ON c.pk_id_tbl_cliente = o.id_cliente
      LEFT JOIN cadu_email_preferences p ON p.contato_id = c.id_contato_cliente
     WHERE COALESCE(c.status, TRUE) AND NULLIF(c.email, '') IS NOT NULL
       AND NOT COALESCE(p.marketing_opt_out, FALSE)
       AND NOT EXISTS (SELECT 1 FROM cadu_email_log l WHERE l.contato_id = c.id_contato_cliente
                         AND l.event_type = %s AND l.sent_at > NOW() - INTERVAL '6 days')
     ORDER BY c.id_contato_cliente
     LIMIT %s"""


def process_weekly_digest(limit: int = 100) -> dict:
    """Segunda-feira, dentro da janela de envio: um resumo por pessoa, só se o time fez algo na semana."""
    result = {"digests": 0, "quiet_teams": 0}
    if not sequence_enabled():
        return result
    now = datetime.now(timezone.utc)
    if now.astimezone(LOCAL_TZ).weekday() != 0 or adjust_to_send_window(now) > now:
        return result
    with _db().cursor() as cursor:
        cursor.execute(_DIGEST_SQL, (DIGEST_KEY, int(limit)))
        recipients = [dict(r) for r in cursor.fetchall()]
    from .brevo_service import get_brevo_product_service
    from .cadu_growth_email_templates import GROWTH_EMAIL_MODELS, build_growth_email
    weeks: dict[int, list] = {}
    for row in recipients:
        client_id = int(row.get("client_id") or 0)
        if client_id not in weeks:
            weeks[client_id] = team_week(client_id)
        metrics = weeks[client_id]
        if not metrics:
            result["quiet_teams"] += 1
            continue  # semana sem atividade não vira e-mail vazio
        first = (str(row.get("nome_completo") or "").split() or [""])[0]
        unsub = unsubscribe_url(row["contato_id"])
        model = GROWTH_EMAIL_MODELS[DIGEST_KEY]
        try:
            cfg = build_growth_email(DIGEST_KEY, body=digest_body(metrics), first_name=first or None, unsubscribe_url=unsub)
            html = _render_growth(cfg)
            sent = get_brevo_product_service(model["product"]).enviar_email(
                to_email=row["email"], to_name=row.get("nome_completo") or "", subject=model["subject"], html_content=html,
                headers={"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
                tags=["seq:resumo-semanal"]) or {}
        except Exception as exc:
            logger.exception("Resumo semanal falhou para o contato %s", row["contato_id"])
            sent = {"success": False, "error": str(exc)}
        log_email(contato_id=row["contato_id"], client_id=client_id, email=row["email"], kind="sequence",
                  event_type=DIGEST_KEY, subject=model["subject"], status="sent" if sent.get("success") else "failed",
                  message_id=sent.get("messageId"), error=sent.get("error"))
        result["digests"] += int(bool(sent.get("success")))
    return result


def _render_growth(cfg: dict) -> str:
    from flask import has_request_context, render_template
    context = {k.lower(): v for k, v in cfg["params"].items()}
    if has_request_context():
        return render_template("emails/externos/cadu-growth.html", **context)
    with current_app.test_request_context("/"):  # worker: só app context
        return render_template("emails/externos/cadu-growth.html", **context)


# --------------------------------------------------------------------------- webhook da Brevo

_BREVO_STATUS = {
    "delivered": "delivered", "opened": "opened", "unique_opened": "opened", "proxy_open": "opened",
    "click": "clicked", "soft_bounce": "bounced", "hard_bounce": "bounced", "blocked": "bounced",
    "invalid_email": "bounced", "spam": "complained", "unsubscribed": "unsubscribed", "error": "failed",
}
_RANK = {"sent": 0, "delivered": 1, "opened": 2, "clicked": 3}


def apply_brevo_event(payload: dict) -> bool:
    """Atualiza o ledger a partir de um evento da Brevo; descadastro/spam cancela a sequência."""
    event = str(payload.get("event") or "").lower()
    message_id = str(payload.get("message-id") or payload.get("messageId") or "").strip()
    status = _BREVO_STATUS.get(event)
    if not status or not message_id:
        return False
    conn = _db()
    with conn.cursor() as cursor:
        cursor.execute(
            """UPDATE cadu_email_log SET
                   status = CASE WHEN %(rank)s > CASE status WHEN 'sent' THEN 0 WHEN 'delivered' THEN 1
                                  WHEN 'opened' THEN 2 WHEN 'clicked' THEN 3 ELSE 9 END
                                 OR %(status)s IN ('bounced', 'complained', 'unsubscribed', 'failed')
                            THEN %(status)s ELSE status END,
                   delivered_at = CASE WHEN %(status)s = 'delivered' THEN COALESCE(delivered_at, NOW()) ELSE delivered_at END,
                   first_opened_at = CASE WHEN %(status)s = 'opened' THEN COALESCE(first_opened_at, NOW()) ELSE first_opened_at END,
                   first_clicked_at = CASE WHEN %(status)s = 'clicked' THEN COALESCE(first_clicked_at, NOW()) ELSE first_clicked_at END,
                   open_count = open_count + CASE WHEN %(status)s = 'opened' THEN 1 ELSE 0 END,
                   click_count = click_count + CASE WHEN %(status)s = 'clicked' THEN 1 ELSE 0 END,
                   provider_error = CASE WHEN %(status)s IN ('bounced', 'complained', 'failed')
                                         THEN LEFT(COALESCE(%(reason)s, provider_error, ''), 4000) ELSE provider_error END,
                   last_event_at = NOW()
             WHERE provider_message_id = %(mid)s
         RETURNING contato_id""",
            {"rank": _RANK.get(status, 9), "status": status, "mid": message_id,
             "reason": str(payload.get("reason") or "")[:4000] or None},
        )
        rows = cursor.fetchall()
    conn.commit()
    if status in {"unsubscribed", "complained"}:
        for row in rows:
            if row.get("contato_id"):
                set_opt_out(int(row["contato_id"]), "brevo_webhook")
    return bool(rows)
