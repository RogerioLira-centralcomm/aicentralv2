"""Painel operacional do host que atende o CentralX.

O painel é deliberadamente somente de leitura. Domínios adicionais são definidos
em ``CENTRALX_MONITOR_DOMAINS`` (separados por vírgula) e verificados por DNS/TLS.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import current_app, jsonify, render_template, request

from .auth import admin_required, admin_required_api


def _percent(value: float, total: float) -> float:
    return round((value / total * 100) if total else 0, 1)


def _read_memory():
    """Lê memória em Linux sem tornar psutil uma dependência da aplicação."""
    values = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as meminfo:
            for line in meminfo:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return {"available": False}
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    return {
        "available": bool(total), "total": total, "used": max(total - available, 0),
        "percent": _percent(max(total - available, 0), total),
    }


def _uptime_seconds():
    try:
        with open("/proc/uptime", encoding="utf-8") as uptime:
            return int(float(uptime.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def _format_bytes(value: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{value} B"
        value /= 1024
    return "—"


def _format_uptime(seconds):
    if seconds is None:
        return "Não disponível"
    days, remaining = divmod(seconds, 86400)
    hours = remaining // 3600
    return f"{days}d {hours}h" if days else f"{hours}h"


def _domain_names():
    # Estes URLs são a fonte canônica dos produtos CentralComm. Assim, o
    # monitor acompanha Studio, Skills, Planner etc. sem depender de uma
    # variável manual em cada deploy.
    product_keys = (
        "CADU_URL", "CENTRALX_URL", "STUDIO_URL", "SKILLS_URL", "PLANNER_URL",
        "CONNECT_URL", "WORKSPACE_URL", "AUTH_URL",
    )
    raw_names = [str(current_app.config.get(key) or "") for key in product_keys]
    # Em desenvolvimento CENTRALX_URL pode cair em localhost. No painel ele
    # representa o host que está realmente recebendo a requisição.
    raw_names = [
        request.host.split(":", 1)[0] if urlparse(value).hostname in {"localhost", "127.0.0.1"} else value
        for value in raw_names
    ]
    configured = os.getenv("CENTRALX_MONITOR_DOMAINS", "")
    raw_names.extend(item.strip() for item in configured.split(",") if item.strip())
    if not raw_names:
        raw_names = [request.host.split(":", 1)[0]]
    names = []
    for raw in raw_names:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        hostname = parsed.hostname
        if hostname and hostname not in names:
            names.append(hostname)
    return names[:8]


def _check_domain(hostname):
    started = time.monotonic()
    result = {"domain": hostname, "status": "error", "detail": "DNS indisponível", "latency": None, "tls": None}
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        result["latency"] = round((time.monotonic() - started) * 1000)
        result["detail"] = f"DNS respondeu · {addresses[0][4][0]}"
    except socket.gaierror:
        return result
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=3) as connection:
            with context.wrap_socket(connection, server_hostname=hostname) as secure:
                certificate = secure.getpeercert()
        expires = certificate.get("notAfter")
        result.update({"status": "healthy", "detail": "HTTPS e certificado válidos", "tls": expires})
    except (OSError, ssl.SSLError):
        result.update({"status": "warning", "detail": "DNS respondeu; TLS não confirmou"})
    return result


def _snapshot():
    disk = shutil.disk_usage(os.getenv("CENTRALX_MONITOR_DISK_PATH", "/"))
    memory = _read_memory()
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0
    cpu_count = os.cpu_count() or 1
    domains = _domain_names()
    with ThreadPoolExecutor(max_workers=min(4, len(domains) or 1)) as executor:
        domain_status = list(executor.map(_check_domain, domains))
    alerts = []
    if memory.get("available") and memory["percent"] >= 85:
        alerts.append({"level": "critical", "title": "Memória acima do limite", "message": f"{memory['percent']}% da memória está em uso."})
    if _percent(disk.used, disk.total) >= 85:
        alerts.append({"level": "warning", "title": "Espaço em disco exige atenção", "message": f"{_percent(disk.used, disk.total)}% do volume principal está ocupado."})
    for domain in domain_status:
        if domain["status"] != "healthy":
            alerts.append({"level": domain["status"], "title": f"Verificar {domain['domain']}", "message": domain["detail"]})
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "server": {"status": "healthy", "name": socket.gethostname(), "platform": platform.system(), "uptime": _format_uptime(_uptime_seconds())},
        "resources": {
            "cpu": {"value": round(min(load / cpu_count * 100, 100), 1), "detail": f"Carga de 1 min: {load:.2f} em {cpu_count} vCPU"},
            "memory": {"value": memory.get("percent"), "detail": f"{_format_bytes(memory.get('used', 0))} de {_format_bytes(memory.get('total', 0))}" if memory.get("available") else "Métrica não disponível neste host"},
            "disk": {"value": _percent(disk.used, disk.total), "detail": f"{_format_bytes(disk.used)} de {_format_bytes(disk.total)}", "free": _format_bytes(disk.free)},
        },
        "domains": domain_status, "alerts": alerts,
    }


def register_server_monitor_routes(blueprint):
    @blueprint.route("/monitoramento")
    @admin_required
    def monitoramento_servidor():
        return render_template("parametros/monitoramento_servidor.html")

    @blueprint.route("/api/server-monitor")
    @admin_required_api
    def api_server_monitor():
        return jsonify({"success": True, "data": _snapshot()})
