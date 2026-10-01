"""Periodic Python availability checks for published Reports Funnel Flows."""
from __future__ import annotations

import json
import time
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
    flow = _rows("""SELECT f.id,f.client_id,f.config,f.tag_id,f.published_revision,t.allowed_host
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
                        THEN NOW()+(monitor_interval_minutes*INTERVAL '1 minute') ELSE NULL END
                WHERE id=%s AND client_id=%s""",
                (status, check["checked_at"], flow_id, client_id))
            cursor.execute("""DELETE FROM cadu_reports_flow_monitor_checks
                WHERE flow_id=%s AND id NOT IN (SELECT id FROM cadu_reports_flow_monitor_checks
                    WHERE flow_id=%s ORDER BY checked_at DESC LIMIT 200)""", (flow_id, flow_id))
        connection.commit()
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
