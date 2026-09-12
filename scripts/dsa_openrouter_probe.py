#!/usr/bin/env python
"""Probe do fluxo Ads: seed local sempre; OpenRouter se a chave existir.

Não persiste marca. Não gera imagem a menos que DSA_PROBE_IMAGE=1.
Depois do deploy: abra a mesa e o console Processo, ou rode com
DSA_PROBE_URL=https://ai.centralcomm.media e cookie de admin.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print_run(title, run):
    print(f"\n== {title} ==")
    print(f"run_id={run.get('run_id')} operation={run.get('operation')}")
    for step in run.get("steps") or []:
        usage = step.get("usage") or {}
        tokens = ""
        if usage:
            tokens = f" tok={usage.get('prompt_tokens')}/{usage.get('completion_tokens')}"
        line = (
            f"- {step.get('step')} [{step.get('status')}] "
            f"{step.get('model') or ''} {step.get('duration_ms')}ms{tokens}"
        )
        print(line.strip())
        if step.get("error"):
            print(f"  erro: {step['error']}")
        if step.get("notes"):
            print(f"  notas: {'; '.join(step['notes'])}")
        output = (step.get("output") or "").strip()
        if output:
            preview = output if len(output) <= 400 else output[:400] + "…"
            print(f"  saida: {preview}")


def _local_loop():
    from aicentralv2.creative_modeling_service import CreativeModelingService

    payload = CreativeModelingService().loop_brand_design_system("centralcomm")
    run = payload.get("run") or {}
    _print_run("loop local / preset CentralComm", run)
    info = payload.get("loop") or {}
    print(f"loop.action={info.get('action')} ready={info.get('ready')} label={info.get('label')}")
    return run


def _openrouter_compose():
    from aicentralv2.design_system_ads.materialize import ensure_brand_design_system
    from aicentralv2.design_system_ads.refine import compose_design_system
    from aicentralv2.design_system_ads.runlog import new_run, wrap_text_callable
    from aicentralv2.services.openrouter_service import chat_completion, resolve_api_key

    if not resolve_api_key():
        print("\n== compose OpenRouter ==\nSem OPENROUTER_API_KEY. Seed local no loop acima.")
        print("Depois do deploy, o console Processo na mesa mostra cada hop pago.")
        return None
    run = new_run("compose")
    system = ensure_brand_design_system(
        {"id": 0, "name": "Probe Ads", "primary_color": "#123456"}
    )
    composed, report = compose_design_system(
        system,
        text_callable=wrap_text_callable(chat_completion, run, step="compose"),
    )
    notes = list(getattr(report, "notes", None) or [])
    _print_run("compose OpenRouter (sem persistir)", run)
    print(f"headline={composed.ad_copy.get('headline')}")
    print(f"cta={composed.ad_copy.get('cta')}")
    if notes:
        print(f"report: {'; '.join(notes)}")
    return run


def _remote_probe(url):
    import urllib.request

    target = url.rstrip("/") + "/parametros/api/design-system/brand/centralcomm/loop"
    request = urllib.request.Request(target, method="POST", data=b"{}")
    cookie = os.getenv("DSA_PROBE_COOKIE", "")
    if cookie:
        request.add_header("Cookie", cookie)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"\n== probe remoto ==\nFalhou em {target}: {exc}")
        return None
    run = (payload.get("data") or {}).get("run") or {}
    _print_run(f"POST {target}", run)
    return run


def main():
    print("Probe Design System Ads")
    _local_loop()
    _openrouter_compose()
    remote = os.getenv("DSA_PROBE_URL", "").strip()
    if remote:
        _remote_probe(remote)
    if os.getenv("DSA_PROBE_IMAGE") == "1":
        print("\nGeração de imagem fica na mesa (console Processo), não neste script.")


if __name__ == "__main__":
    main()
