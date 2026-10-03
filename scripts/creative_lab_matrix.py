#!/usr/bin/env python
"""Run Creative Lab scenarios across models, one generation at a time (same path as the /lab page).

    .venv/bin/python scripts/creative_lab_matrix.py --scenarios marca-so-texto --models qwen-image-3-pro
    .venv/bin/python scripts/creative_lab_matrix.py            # every scenario × every model
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CLIENT_ID = 174


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="*")
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--user-id", type=int, default=None)
    args = parser.parse_args()

    from run import app
    from aicentralv2.creative_lab import catalog, repository, runner, scenarios  # noqa: F401

    with app.test_request_context("/lab"):
        from flask import session
        session["user_id"] = args.user_id or 0
        session["cliente_id"] = CLIENT_ID
        models = args.models or list(catalog.manifests())
        for item in scenarios.scenarios(include_reserved=False):
            if args.scenarios and item["key"] not in args.scenarios:
                continue
            created = runner.run_scenario(CLIENT_ID, item["key"], models, args.user_id, start=False)
            print(f"\n== {item['key']} · experimento {created['experiment_id']} · {len(created['run_ids'])} a gerar", flush=True)
            for run_id in created["run_ids"]:
                runner.execute_run(CLIENT_ID, run_id)
                run = repository.get_run(CLIENT_ID, run_id)
                score = ((run.get("typesafe") or {}).get("scores") or {}).get("overall")
                failure = (run.get("typesafe") or {}).get("primary_failure")
                print(f"  {run['model_key']:<26} {run['status']:<9} {str(run['latency_ms'] or '-'):>6} ms "
                      f"US$ {run['actual_cost_usd'] if run['actual_cost_usd'] is not None else '-'} "
                      f"(est {run['estimated_cost_usd']}) nota {score} falha {failure} "
                      f"{(run.get('error') or {}).get('message', '')[:120]}", flush=True)


if __name__ == "__main__":
    main()
