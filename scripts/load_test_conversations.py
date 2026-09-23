#!/usr/bin/env python3
"""Guarded SSE load probe for Cadu Conversations V2.

Dry-run is the default. A real run requires both --execute and an exact
confirmation phrase so this script cannot generate provider traffic by typo.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import math
import os
import statistics
import sys
from threading import Barrier
from time import monotonic
from urllib.parse import urlparse
from uuid import uuid4

import requests


CONFIRMATION = "RODAR-CARGA-CADU-40"
DEFAULT_PATH = "/workspace/api/v2/conversations/messages"
TERMINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled"}


@dataclass
class Sample:
    worker: int
    status_code: int | None = None
    ttfb_ms: int | None = None
    first_token_ms: int | None = None
    total_ms: int | None = None
    terminal_event: str | None = None
    conversation_id: str | None = None
    run_id: str | None = None
    bytes_received: int = 0
    error: str | None = None


def percentile(values: list[int], percent: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percent * len(ordered)) - 1))
    return ordered[index]


def parse_sse(lines, sample: Sample) -> None:
    event = ""
    data: list[str] = []

    def consume() -> None:
        nonlocal event, data
        if not event and not data:
            return
        raw = "\n".join(data)
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            sample.conversation_id = str(payload.get("conversation_id") or sample.conversation_id or "") or None
            sample.run_id = str(payload.get("run_id") or sample.run_id or "") or None
            if event == "provider.first_token" and payload.get("first_token_ms") is not None:
                sample.first_token_ms = int(payload["first_token_ms"])
        if event in TERMINAL_EVENTS:
            sample.terminal_event = event
        event, data = "", []

    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line)
        sample.bytes_received += len(line.encode("utf-8")) + 1
        if not line:
            consume()
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    consume()


def run_one(args, worker: int, barrier: Barrier) -> Sample:
    sample = Sample(worker=worker)
    payload = {
        "message": args.prompt,
        "surface": "conversations",
        "execution_mode": args.execution_mode,
        "request_id": str(uuid4()),
    }
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "X-CSRF-Token": args.csrf,
        "Cookie": args.cookie,
        "User-Agent": "CaduLoadProbe/1.0",
    }
    barrier.wait()
    started = monotonic()
    try:
        with requests.post(
            args.url, headers=headers, json=payload, stream=True,
            timeout=(args.connect_timeout, args.read_timeout),
        ) as response:
            sample.status_code = response.status_code
            sample.ttfb_ms = round((monotonic() - started) * 1000)
            if response.status_code != 200:
                sample.error = f"http_{response.status_code}: {response.text[:240]}"
            else:
                parse_sse(response.iter_lines(decode_unicode=False), sample)
                if sample.terminal_event not in TERMINAL_EVENTS:
                    sample.error = "stream_without_terminal_event"
    except requests.RequestException as exc:
        sample.error = f"{type(exc).__name__}: {exc}"
    finally:
        sample.total_ms = round((monotonic() - started) * 1000)
    return sample


def summary(samples: list[Sample], wall_ms: int) -> dict:
    successful = [item for item in samples if not item.error and item.terminal_event == "run.completed"]
    ttfb = [item.ttfb_ms for item in samples if item.ttfb_ms is not None]
    first_token = [item.first_token_ms for item in samples if item.first_token_ms is not None]
    totals = [item.total_ms for item in samples if item.total_ms is not None]

    def distribution(values: list[int]) -> dict:
        return {
            "count": len(values), "min_ms": min(values) if values else None,
            "p50_ms": round(statistics.median(values)) if values else None,
            "p95_ms": percentile(values, 0.95), "p99_ms": percentile(values, 0.99),
            "max_ms": max(values) if values else None,
        }

    return {
        "connections": len(samples), "successful": len(successful),
        "failed": len(samples) - len(successful),
        "success_rate": round((len(successful) / len(samples)) * 100, 2) if samples else 0,
        "wall_time_ms": wall_ms,
        "completed_per_second": round(len(successful) / (wall_ms / 1000), 2) if wall_ms else 0,
        "ttfb": distribution(ttfb), "first_token": distribution(first_token),
        "total": distribution(totals),
        "terminal_events": {name: sum(item.terminal_event == name for item in samples)
                            for name in sorted(TERMINAL_EVENTS)},
        "http_statuses": {str(code): sum(item.status_code == code for item in samples)
                          for code in sorted({item.status_code for item in samples if item.status_code is not None})},
        "errors": [asdict(item) for item in samples if item.error],
    }


def arguments(argv=None):
    parser = argparse.ArgumentParser(description="Teste protegido de até 40 conexões SSE do Cadu.")
    parser.add_argument("--base-url", default=os.getenv("CADU_LOAD_BASE_URL", ""))
    parser.add_argument("--path", default=os.getenv("CADU_LOAD_PATH", DEFAULT_PATH))
    parser.add_argument("--connections", type=int, default=40)
    parser.add_argument("--prompt", default="Responda somente: Cadu disponível.")
    parser.add_argument("--execution-mode", choices=("fast", "analysis", "agentic"), default="fast")
    parser.add_argument("--connect-timeout", type=float, default=10)
    parser.add_argument("--read-timeout", type=float, default=180)
    parser.add_argument("--output", help="Arquivo JSON opcional para o relatório, sem credenciais.")
    parser.add_argument("--execute", action="store_true", help="Habilita tráfego real.")
    parser.add_argument("--confirm", default="", help=f"Confirmação obrigatória: {CONFIRMATION}")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = arguments(argv)
    if not 1 <= args.connections <= 40:
        raise SystemExit("--connections deve estar entre 1 e 40 nesta primeira etapa.")
    if not args.base_url:
        raise SystemExit("Defina CADU_LOAD_BASE_URL ou use --base-url.")
    parsed = urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("A URL base é inválida.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise SystemExit("Ambientes remotos exigem HTTPS.")
    args.cookie = os.getenv("CADU_LOAD_COOKIE", "")
    args.csrf = os.getenv("CADU_LOAD_CSRF", "")
    args.url = args.base_url.rstrip("/") + "/" + args.path.lstrip("/")

    plan = {
        "mode": "execute" if args.execute else "dry-run", "url": args.url,
        "connections": args.connections, "execution_mode": args.execution_mode,
        "prompt_chars": len(args.prompt), "connect_timeout": args.connect_timeout,
        "read_timeout": args.read_timeout,
    }
    if not args.execute:
        print(json.dumps({"plan": plan, "message": "Nenhuma conexão foi aberta."}, ensure_ascii=False, indent=2))
        return 0
    if args.confirm != CONFIRMATION:
        raise SystemExit(f"Execução bloqueada. Use --confirm {CONFIRMATION}")
    if not args.cookie or not args.csrf:
        raise SystemExit("Defina CADU_LOAD_COOKIE e CADU_LOAD_CSRF para a sessão de teste.")

    barrier = Barrier(args.connections)
    started = monotonic()
    with ThreadPoolExecutor(max_workers=args.connections, thread_name_prefix="cadu-load") as pool:
        futures = [pool.submit(run_one, args, worker, barrier) for worker in range(1, args.connections + 1)]
        samples = [future.result() for future in as_completed(futures)]
    report = {"plan": plan, "summary": summary(samples, round((monotonic() - started) * 1000)),
              "samples": [asdict(item) for item in sorted(samples, key=lambda item: item.worker)]}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    print(encoded)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as destination:
            destination.write(encoded + "\n")
    return 0 if report["summary"]["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
