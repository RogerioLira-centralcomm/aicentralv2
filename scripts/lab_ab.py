"""A/B of Studio generation changes on Lab scenarios, before anything changes in the Studio.

Runs the Studio pipeline through the Lab bridge for the given Lab runs (their experiment = briefing, brand, format and
mockup), once per arm, and prints one JSON line per piece: delivered score, versions, the reviewer's components of the
first version, cost and time. Nothing is written to the database; images go to --out.

Each arm is a set of LabModeling overrides, e.g.

    .venv/bin/python scripts/lab_ab.py --runs 240,238,236 \
        --arm 'A={"typeset_social": false}' --arm 'B={"typeset_social": true}' --attempts 3

``--attempts 3`` is the Studio's behaviour (up to three versions while the reviewer rejects); ``--attempts 1`` compares
what a single call delivers. Rule of the house: a change only goes to the Studio when the Lab shows the gain.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import json
import os
import sys
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aicentralv2 import create_app  # noqa: E402

CAPTURE: dict[int, list[dict]] = {}


def _capture_components():
    from aicentralv2.creative_lab import evaluation
    original = evaluation._summarize
    if getattr(original, "_lab_ab", False):
        return

    def summarize(answers):
        scores = original(answers)
        CAPTURE.setdefault(threading.get_ident(), []).append(
            {key: (value.get("choice") if isinstance(value, dict) else value) for key, value in scores.items()})
        return scores

    summarize._lab_ab = True
    evaluation._summarize = summarize


def _brand_snapshot(client_id: int, brand_id: int) -> dict:
    """The brand's snapshot; its logo stays a public URL (the Studio downloads it, SVG included)."""
    from aicentralv2.creative_lab import brands
    snap = brands.brand_snapshot(client_id, brand_id)
    return snap


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", required=True, help="Lab run ids, comma separated (their experiments are reused)")
    parser.add_argument("--arm", action="append", required=True, help='NAME={"attribute": value, ...}')
    parser.add_argument("--model", default="gpt-image-2.5-sunburst--openai")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--client", type=int, default=174)
    parser.add_argument("--out", default="output/lab-ab")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    arms = []
    for item in args.arm:
        name, _, overrides = item.partition("=")
        arms.append((name, json.loads(overrides or "{}")))
    os.makedirs(args.out, exist_ok=True)
    app = create_app()

    def one(run_id, arm, direction, spec, snap, plan, by_ref, user_id):
        CAPTURE[threading.get_ident()] = []
        with app.app_context():
            from aicentralv2.creative_lab import files, studio_bridge
            started = time.monotonic()
            result = studio_bridge.run_create(model_key=args.model, spec=spec, snapshot=snap, plan=plan, by_ref=by_ref,
                                              direction=direction, files_module=files, client_id=args.client,
                                              user_id=user_id)
            with open(f"{args.out}/{run_id}-{arm}.png", "wb") as handle:
                handle.write(base64.b64decode(result["b64"]))
            review = result.get("review") or {}
            return {"run": run_id, "arm": arm, "score": review.get("score"), "approved": review.get("approved"),
                    "reason": review.get("final_reason") or review.get("reason") or "",
                    "versions": [item.get("score") for item in review.get("attempts") or []],
                    "first": CAPTURE.get(threading.get_ident(), [{}])[0] if CAPTURE.get(threading.get_ident()) else {},
                    "calls": result["calls"], "cost": result["cost_usd"],
                    "provider_s": round(result["latency_ms"] / 1000, 1), "wall_s": round(time.monotonic() - started, 1)}

    def safe(*job):
        try:
            return one(*job)
        except Exception as exc:
            return {"run": job[0], "arm": job[1], "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                    "where": traceback.format_exc().strip().splitlines()[-3][:200]}

    rows = []
    with app.app_context():
        from aicentralv2.creative_lab import repository, studio_bridge
        _capture_components()
        base = studio_bridge.LabModeling
        for name, overrides in arms:
            # One class per arm, set before the director runs (it reads the arm's settings) and never swapped mid-batch.
            # "_spec" (optional) replaces briefing fields of every scenario for this arm (e.g. a v5 instruction).
            spec_fields = overrides.pop("_spec", {}) if isinstance(overrides, dict) else {}
            # "_brand" (optional): run the scenario for another brand of the client — its profile read from the
            # brand record (read only), its official logo loaded in memory, and none of the scenario's own images.
            brand_id = overrides.pop("_brand", None) if isinstance(overrides, dict) else None
            studio_bridge.LabModeling = type("Modeling" + name, (base,), {"review_attempts": args.attempts,
                                                                         "refine_target": None, **overrides})
            jobs = []
            for run_id in [int(item) for item in args.runs.split(",")]:
                run = repository.get_run(args.client, run_id)
                exp = repository.get_experiment(args.client, run["experiment_id"])
                spec, snap, plan = dict(exp["spec"]), exp["brand_snapshot"] or {}, run["adaptation_plan"]
                if brand_id:
                    snap, plan = _brand_snapshot(args.client, int(brand_id)), {**plan, "sent": [], "converted_to_text": []}
                    spec["brand_payload"] = __import__("aicentralv2.creative_lab.brands", fromlist=["x"]).payload_fields(snap)
                    spec["references"] = []
                for key, value in spec_fields.get(str(run_id), spec_fields.get("*", {})).items():
                    spec[key] = {**(spec.get(key) or {}), **value} if isinstance(value, dict) and isinstance(spec.get(key), dict) else value
                by_ref = {ref["ref_id"]: ref for ref in spec["references"]}
                direction = studio_bridge.direct(spec, snap)
                jobs.append((run_id, name, direction, spec, snap, plan, by_ref, run["created_by"]))
            with cf.ThreadPoolExecutor(args.workers) as pool:
                rows += list(pool.map(lambda job: safe(*job), jobs))
        studio_bridge.LabModeling = base
    for row in rows:
        print(json.dumps(row, ensure_ascii=False), flush=True)
    for name, _ in arms:
        scores = [row["score"] for row in rows if row["arm"] == name and row.get("score") is not None]
        approved = sum(1 for row in rows if row["arm"] == name and row.get("approved"))
        costs = [row["cost"] for row in rows if row["arm"] == name and row.get("cost") is not None]
        if scores:
            print(f"# {name}: nota média {sum(scores) / len(scores):.1f} · aprovadas {approved}/{len(scores)} · "
                  f"custo médio US$ {sum(costs) / max(1, len(costs)):.3f}", flush=True)


if __name__ == "__main__":
    main()
