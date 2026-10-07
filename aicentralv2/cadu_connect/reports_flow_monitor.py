"""Periodic Python availability checks for published Reports Funnel Flows."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import click
import requests
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.exceptions import BadRequest

from ..db import get_db
from .reports_flow import _host_allowed, _safe_path
from .reports_flow_lifecycle import is_measured
from .reports_link_tester import _fetch
from .reports_v1 import _rows

MAX_MONITORED_PAGES = 201
ALERT_TZ = ZoneInfo("America/Sao_Paulo")
ALERT_FROM_HOUR, ALERT_UNTIL_HOUR = 7, 23   # avisos só entre 7h e 23h (Brasília)
ALERT_REPEAT = timedelta(minutes=4, seconds=30)  # um aviso por ciclo de 5 min enquanto estiver fora
ALERT_FIXED_RECIPIENT = "apolo@centralcomm.media"
logger = logging.getLogger(__name__)


def in_alert_window(now=None):
    hour = (now or datetime.now(timezone.utc)).astimezone(ALERT_TZ).hour
    return ALERT_FROM_HOUR <= hour < ALERT_UNTIL_HOUR


def _alert_recipients(flow_id, client_id):
    rows = _rows("""SELECT u.email FROM cadu_reports_flow_registry f
        JOIN tbl_contato_cliente u ON u.id_contato_cliente=f.created_by
        WHERE f.id=%s AND f.client_id=%s AND u.status=TRUE""", (flow_id, client_id))
    emails = {row["email"].strip().lower() for row in rows if row.get("email")}
    emails.add(os.environ.get("REPORTS_MONITOR_ALERT_EMAIL", ALERT_FIXED_RECIPIENT).strip().lower())
    return sorted(emails)


def _send_monitor_email(flow, recipients, status, pages, down_since, recovered=False):
    """E-mail de marca do Reports; True só se todos os envios foram confirmados."""
    from ..services.cadu_email_connector import send_cadu_event
    base = os.environ.get("REPORTS_PUBLIC_BASE_URL", "").rstrip("/")
    failing = [page for page in pages if page["status"] != "online"]
    name = flow.get("name") or flow["allowed_host"]
    if recovered:
        title = f"Fluxo {name} voltou ao ar"
        description = "Todas as páginas monitoradas estão respondendo novamente."
    else:
        title = f"{len(failing)} de {len(pages)} páginas do fluxo {name} fora do ar"
        description = "A última verificação encontrou páginas sem resposta. Novo aviso em 5 minutos se continuar assim."
    since = down_since.astimezone(ALERT_TZ).strftime("%d/%m %H:%M") if down_since else "—"
    details = [{"label": "Site", "value": flow["allowed_host"]}, {"label": "Fora do ar desde", "value": since}]
    for page in failing[:8]:
        details.append({"label": page["path"], "value": page.get("detail") or "Sem resposta"})
    sent = True
    for email in recipients:
        result = send_cadu_event(
            product="connect", event="connect.reports_alert", template="produto-atividade.html",
            recipient=email, recipient_name="Equipe", subject=f"[Reports] {title}", client_id=flow["client_id"],
            params={"TITLE": title, "EYEBROW": "Monitor de páginas", "DESCRIPTION": description, "DETAILS": details,
                    "CTA_LABEL": "Abrir monitoramento" if base else "",
                    "CTA_URL": f"{base}/connect/app/flows/{flow['id']}/monitor" if base else ""})
        sent = sent and bool((result or {}).get("success"))
    return sent


def notify_transition(flow, status, pages, now=None):
    """Down: one e-mail per cycle between 7h and 23h. Back up: one recovery e-mail. Never raises."""
    now = now or datetime.now(timezone.utc)
    try:
        state = _rows("SELECT monitor_down_since,monitor_last_alert_at FROM cadu_reports_flow_registry WHERE id=%s AND client_id=%s",
                      (flow["id"], flow["client_id"]))[0]
        connection = get_db()
        if status == "online":
            if state["monitor_down_since"] is None:
                return
            if state["monitor_last_alert_at"] is not None:
                # An alert went out: the all-clear follows it, held until 7h when the site came back at night.
                if not in_alert_window(now) or not _send_monitor_email(
                        flow, _alert_recipients(flow["id"], flow["client_id"]), status, pages,
                        state["monitor_down_since"], recovered=True):
                    return
            with connection.cursor() as cursor:
                cursor.execute("UPDATE cadu_reports_flow_registry SET monitor_down_since=NULL,monitor_last_alert_at=NULL WHERE id=%s", (flow["id"],))
            connection.commit()
            return
        down_since = state["monitor_down_since"] or now
        last = state["monitor_last_alert_at"]
        due = in_alert_window(now) and (last is None or now - last >= ALERT_REPEAT)
        sent = due and _send_monitor_email(flow, _alert_recipients(flow["id"], flow["client_id"]), status, pages, down_since)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE cadu_reports_flow_registry SET monitor_down_since=%s,monitor_last_alert_at=%s WHERE id=%s",
                           (down_since, now if sent else last, flow["id"]))
        connection.commit()
    except Exception:
        logger.exception("Alerta de indisponibilidade do fluxo %s falhou", flow.get("id"))
        try:
            get_db().rollback()
        except Exception:
            pass


def _page_targets(flow):
    host = flow["allowed_host"]
    found = {("https", host, "/"): {"host": host, "path": "/", "label": "Página inicial"}}
    config = flow.get("config") if isinstance(flow.get("config"), dict) else {}
    for node in config.get("nodes", []):
        if not is_measured(node):
            continue
        path = node.get("path")
        page_host = node.get("host") or host
        if not isinstance(path, str) or not path.startswith("/") or not _host_allowed(page_host, host):
            continue
        path = _safe_path(path)
        found[("https", page_host, path)] = {"host": page_host, "path": path,
            "label": str(node.get("title") or path)[:120]}
    return list(found.values())[:MAX_MONITORED_PAGES]


def _check_page(target, allowed_host):
    """Request a known flow page without following redirects outside the client domain."""
    current = f"https://{target['host']}{target['path']}"
    started = time.monotonic()
    try:
        for _ in range(5):
            parsed = urlparse(current)
            if parsed.scheme != "https" or not _host_allowed(parsed.hostname or "", allowed_host):
                return {**target, "status": "offline", "http_status": None,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "detail": "Redirecionamento para domínio não autorizado."}
            code, headers, _ = _fetch(current, body=False)
            location = headers.get("Location") or headers.get("location")
            if code in (301, 302, 303, 307, 308) and location:
                current = urljoin(current, location)
                continue
            content_type = headers.get("Content-Type") or headers.get("content-type") or ""
            healthy = 200 <= code < 300 and "html" in content_type.lower()
            return {**target, "status": "online" if healthy else "offline",
                    "http_status": int(code), "duration_ms": round((time.monotonic() - started) * 1000),
                    "detail": "Página respondendo" if healthy else
                        ("Resposta não é uma página HTML" if 200 <= code < 300 else f"HTTP {code}"),
                    "checked_url": f"{parsed.scheme}://{parsed.netloc}{_safe_path(parsed.path or '/')}"}
        return {**target, "status": "degraded", "http_status": None,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "detail": "Redirecionamentos excederam o limite."}
    except (BadRequest, requests.RequestException, OSError, ValueError) as exc:
        return {**target, "status": "offline", "http_status": None,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "detail": str(exc.description if isinstance(exc, BadRequest) else "Falha de conexão")[:180]}


def run_check(flow):
    targets = _page_targets(flow)
    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_check_page, target, flow["allowed_host"]) for target in targets]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda page: (page["path"], page["host"]))
    online_count = sum(page["status"] == "online" for page in results)
    status = "online" if online_count == len(results) else "offline" if online_count == 0 else "degraded"
    return status, results, round((time.monotonic() - started) * 1000)


def check_flow(flow_id, client_id):
    flow = _rows("""SELECT f.id,f.client_id,f.name,f.config,f.tag_id,f.published_revision,t.allowed_host
        FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
        WHERE f.id=%s AND f.client_id=%s AND f.status='published'
            AND t.revoked_at IS NULL""", (flow_id, client_id))
    if not flow:
        return None
    flow = flow[0]
    status, pages, duration = run_check(flow)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO cadu_reports_flow_monitor_checks
                    (flow_id,client_id,status,duration_ms,pages)
                VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING id,checked_at""",
                (flow_id, client_id, status, duration,
                 json.dumps(pages, ensure_ascii=False)))
            check = cursor.fetchone()
            cursor.execute("""UPDATE cadu_reports_flow_registry SET monitor_status=%s,
                    monitor_checked_at=%s,monitor_next_check_at=CASE WHEN monitor_enabled
                        THEN NOW()+(CASE WHEN %s='online' THEN monitor_interval_minutes ELSE LEAST(monitor_interval_minutes,5) END*INTERVAL '1 minute') ELSE NULL END
                WHERE id=%s AND client_id=%s""",
                (status, check["checked_at"], status, flow_id, client_id))
            cursor.execute("""DELETE FROM cadu_reports_flow_monitor_checks
                WHERE flow_id=%s AND id NOT IN (SELECT id FROM cadu_reports_flow_monitor_checks
                    WHERE flow_id=%s ORDER BY checked_at DESC LIMIT 200)""", (flow_id, flow_id))
        connection.commit()
        notify_transition(flow, status, pages)
        return {"id": check["id"], "status": status, "checked_at": check["checked_at"],
                "duration_ms": duration, "pages": pages, "checked_pages": len(pages), "total_pages": len(_page_targets(flow)), "revision": flow.get("published_revision")}
    except Exception:
        connection.rollback()
        raise


def process_one():
    """Claim one due flow, run bounded HTTP checks, and persist its status."""
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""WITH due AS (
                    SELECT f.id FROM cadu_reports_flow_registry f
                    JOIN cadu_reports_site_tags t ON t.id=f.tag_id
                    WHERE f.monitor_enabled=TRUE AND f.status='published' AND t.revoked_at IS NULL
                      AND (monitor_next_check_at IS NULL OR monitor_next_check_at<=NOW())
                    ORDER BY monitor_next_check_at NULLS FIRST FOR UPDATE SKIP LOCKED LIMIT 1
                ) UPDATE cadu_reports_flow_registry f SET monitor_status='checking',
                    monitor_next_check_at=NOW()+(monitor_interval_minutes*INTERVAL '1 minute')
                FROM due WHERE f.id=due.id
                RETURNING f.id::text,f.client_id""")
            row = cursor.fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    if not row:
        return False
    try:
        check_flow(row["id"], row["client_id"])
    except Exception:
        current_app.logger.exception("Falha ao verificar disponibilidade do fluxo %s", row["id"])
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""UPDATE cadu_reports_flow_registry SET monitor_status='unknown',
                    monitor_checked_at=NOW(),monitor_next_check_at=NOW()+(monitor_interval_minutes*INTERVAL '1 minute')
                    WHERE id=%s""", (row["id"],))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return True


@click.command("reports-flow-monitor-once")
@with_appcontext
def worker_once_command():
    click.echo("Verificação concluída." if process_one() else "Nenhum fluxo aguardando verificação.")


@click.command("reports-flow-monitor-loop")
@click.option("--interval", type=click.IntRange(10, 300), default=30, show_default=True)
@with_appcontext
def worker_loop_command(interval):
    """Poll the Reports availability monitor from a supervised Python worker."""
    app = current_app._get_current_object()
    click.echo(f"Monitor de Fluxos ativo; consulta a cada {interval}s.")
    from .reports_alerts import PeriodicRunner
    alerts = PeriodicRunner()
    while True:
        try:
            with app.app_context():
                worked = process_one()
                alerts.tick()
            if not worked:
                time.sleep(interval)
        except KeyboardInterrupt:
            break
        except Exception:
            app.logger.exception("Ciclo do monitor de Fluxos falhou")
            time.sleep(interval)
