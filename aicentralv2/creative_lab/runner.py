"""Experiments and runs: plan everything up front, then generate one image at a time in the background.

Runs execute sequentially in a worker thread (never inside the HTTP request); the page polls. A run
that does not finish in 15 minutes is marked failed on the next read.
"""

from __future__ import annotations

import base64
import io
import logging
import threading

from flask import current_app
from PIL import Image

from ..creative_media.studio_create import apply_brand_logo
from ..services.openrouter_service import _download_reference_bytes
from . import adapter, brands, catalog, connector, evaluation, files, repository, studio_bridge

log = logging.getLogger(__name__)
_lock = threading.Lock()

POLICIES = ("verified_only", "verified_and_probable", "all")


def _clean_list(values, limit=8, size=200):
    return [str(item).strip()[:size] for item in (values or []) if str(item).strip()][:limit]


def build_spec(client_id: int, data: dict, user_id: int | None) -> tuple[dict, dict]:
    task = "edit" if data.get("task") == "edit" else "generate"
    brand_id = int(data["brand_id"]) if data.get("brand_id") else None
    snapshot = brands.brand_snapshot(client_id, brand_id) if brand_id else {}
    policy = data.get("payload_policy") if data.get("payload_policy") in POLICIES else "verified_and_probable"
    brand_payload = brands.payload_fields(snapshot, policy) if snapshot else None
    logo_mode = data.get("logo_mode") if data.get("logo_mode") in ("composer", "native", "none") else "composer"
    references = []
    for item in data.get("references") or []:
        ref = repository.get_reference(client_id, int(item["ref_id"]))
        role = item.get("role") or ref["role"]
        references.append({"ref_id": ref["ref_id"], "role": role, "label": item.get("label") or ref["label"],
                           "file_id": ref["file_id"], "sha256": ref["sha256"], "has_person": ref["has_person"]})
    if task == "edit" and not any(ref["role"] == "BASE" for ref in references):
        raise ValueError("Editar exige uma imagem-base (papel BASE).")
    if logo_mode != "none" and snapshot.get("logo_url") and not any(ref["role"] == "LOGO" for ref in references):
        try:
            content, _mime = _download_reference_bytes(snapshot["logo_url"], max_bytes=8 * 1024 * 1024)
            logo = repository.save_reference(client_id, content, role="LOGO", label=f"Logo {snapshot['name']}",
                                             source="brand_asset", source_ref="logo_url", brand_id=brand_id, user_id=user_id)
            references.append({"ref_id": logo["ref_id"], "role": "LOGO", "label": logo["label"],
                               "file_id": logo["file_id"], "sha256": logo["sha256"], "has_person": False})
        except Exception:
            log.warning("Brand logo could not be imported for the Lab", exc_info=True)
    brief = _clean_brief(data.get("brief"))
    from .archetypes import format_info
    fmt = format_info(brief.get("format_key")) if brief else None
    aspect = fmt["ratio"] if fmt else str(data.get("aspect_ratio") or "1:1")
    must = _clean_list(data.get("must_include_text"), 8, 160) or (adapter.copy_strings(brief) if brief else [])
    pipeline = "studio" if data.get("pipeline") == "studio" else "raw"
    mockup = _clean_mockup(data.get("mockup"), brief, pipeline, task)
    spec = {
        "spec_version": 3 if pipeline == "studio" else 2 if brief else 1, "pipeline": pipeline, "mockup": mockup, "task": task, "brief": brief, "objective": str(data.get("objective") or "")[:120],
        "instruction": str(data.get("instruction") or "").strip()[:1500],
        "must_include_text": must,
        "avoid": _clean_list(data.get("avoid")), "preserve": _clean_list(data.get("preserve")),
        "alter": str(data.get("alter") or "")[:500], "aspect_ratio": aspect,
        "quality": data.get("quality") if data.get("quality") in ("draft", "standard", "high") else "standard",
        "logo_mode": logo_mode, "payload_policy": policy, "brand_payload": brand_payload, "references": references,
    }
    if not spec["instruction"] and task == "edit" and fmt:
        spec["instruction"] = f"Reformatar a peça para {fmt['label']}"
    if not spec["instruction"] and brief:
        spec["instruction"] = " · ".join(adapter.copy_strings(brief)[:3]) or brief.get("offer") or ""
    if not spec["instruction"]:
        raise ValueError("Escreva a instrução do teste.")
    spec["director_prompt"] = str(data.get("director_prompt") or "").strip() or (
        studio_bridge.briefing_text(spec) if pipeline == "studio" else adapter.director_prompt(spec, brand_payload))
    spec["director_source"] = ("manual" if data.get("director_prompt") else "studio_director" if pipeline == "studio"
                               else "template_v2" if adapter.has_brief(spec) else "template_v1")
    return spec, snapshot


def _clean_mockup(raw, brief: dict, pipeline: str, task: str) -> dict:
    """The composition mask (mockup) of a Studio-pipeline test: off, as an image, or described in words."""
    if pipeline != "studio" or task != "generate":
        return {"id": "", "family": "", "mode": "none"}
    raw = raw if isinstance(raw, dict) else {}
    mode = raw.get("mode") if raw.get("mode") in studio_bridge.MOCKUP_MODES else "image"
    if mode == "none":
        return {"id": "", "family": str(raw.get("family") or ""), "mode": "none"}
    format_key = (brief or {}).get("format_key")
    mask = studio_bridge.get_mask(str(raw.get("id") or ""))
    if not mask or mask["format"] != studio_bridge.mask_format(format_key):
        mask = studio_bridge.pick_mask(format_key, str(raw.get("family") or ""))
    if not mask:
        return {"id": "", "family": str(raw.get("family") or ""), "mode": "none"}
    return {"id": mask["id"], "family": mask["family"], "mode": mode}


BRIEF_TEXT = ("objective", "audience", "offer", "archetype", "format_key")
COPY_KEYS = ("kicker", "headline", "highlight", "support", "cta", "seal", "tagline", "legal")


def _clean_brief(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    brief = {key: str(raw.get(key) or "").strip()[:400] for key in BRIEF_TEXT if str(raw.get(key) or "").strip()}
    copy = raw.get("copy") if isinstance(raw.get("copy"), dict) else {}
    brief["copy"] = {key: str(copy.get(key) or "").strip()[:160] for key in COPY_KEYS if str(copy.get(key) or "").strip()}
    brief["casting"] = _clean_list(raw.get("casting"), 5, 300)
    brief["devices"] = _clean_list(raw.get("devices"), 6, 200)
    if raw.get("source_ref_id"):
        brief["source_ref_id"] = int(raw["source_ref_id"])
    return brief if (brief.get("copy") or brief.get("archetype") or brief.get("format_key")) else {}


def _ratio_value(value: str) -> float:
    try:
        width, height = (float(part) for part in str(value).split(":"))
        return width / height
    except (ValueError, ZeroDivisionError):
        return 0.0


def fit_to_ratio(payload: bytes, ratio: str) -> tuple[bytes, dict | None]:
    """Center-crop (cover) to the target ratio when the model could not deliver it exactly."""
    target = _ratio_value(ratio)
    image = files.open_image(payload)
    current = image.width / image.height
    if not target or abs(current - target) / target < 0.02:
        return payload, None
    if current > target:
        width = round(image.height * target)
        left = (image.width - width) // 2
        box = (left, 0, left + width, image.height)
    else:
        height = round(image.width / target)
        top = (image.height - height) // 2
        box = (0, top, image.width, top + height)
    out = io.BytesIO()
    image.crop(box).save(out, "PNG")
    return out.getvalue(), {"from": [image.width, image.height], "to": [box[2] - box[0], box[3] - box[1]], "ratio": ratio}


def preview(client_id: int, data: dict, user_id: int | None) -> dict:
    """Plan for every requested model without calling any provider (and without saving anything)."""
    spec, snapshot = build_spec(client_id, data, user_id)
    cat = catalog.catalog()
    plans = []
    for model_key in data.get("models") or list(catalog.manifests()):
        manifest = catalog.manifest(model_key)
        caps = catalog.capabilities(model_key, cat)
        plan = adapter.plan(spec, manifest, caps, [{k: ref[k] for k in ("ref_id", "role", "label")} for ref in spec["references"]])
        prompt = adapter.model_prompt(spec["director_prompt"], plan, manifest)
        plans.append({"model_key": model_key, "plan": plan, "model_prompt": prompt,
                      "estimate": adapter.estimate_cost(plan, caps, prompt)})
    return {"spec": spec, "readiness": snapshot.get("readiness") if snapshot else None, "plans": plans}


def create_experiment_runs(client_id: int, data: dict, user_id: int | None, *, start: bool = True) -> dict:
    spec, snapshot = build_spec(client_id, data, user_id)
    title = str(data.get("title") or spec["instruction"][:80])
    experiment_id = repository.create_experiment(client_id, scenario_key=str(data.get("scenario_key") or "custom")[:64],
                                                 title=title, task=spec["task"], brand_id=data.get("brand_id"),
                                                 snapshot=snapshot, spec=spec, user_id=user_id)
    run_ids = queue_models(client_id, experiment_id, data.get("models") or [], user_id, start=start)
    return {"experiment_id": experiment_id, "run_ids": run_ids}


def queue_models(client_id: int, experiment_id: int, model_keys: list[str], user_id: int | None,
                 *, start: bool = True) -> list[int]:
    experiment = repository.get_experiment(client_id, experiment_id)
    spec = experiment["spec"]
    cat = catalog.catalog()
    run_ids = []
    for model_key in model_keys:
        manifest = catalog.manifest(model_key)
        caps = catalog.capabilities(model_key, cat)
        plan = adapter.plan(spec, manifest, caps, [{k: ref[k] for k in ("ref_id", "role", "label")} for ref in spec["references"]])
        prompt = adapter.model_prompt(spec["director_prompt"], plan, manifest)
        estimate = adapter.estimate_cost(plan, caps, prompt)
        summary = {"parameters": plan["parameters"]["applied"], "prompt_chars": len(prompt),
                   "estimate": estimate, "reference_hashes": [ref["sha256"][:16] for ref in spec["references"]]}
        run_ids.append(repository.create_run(experiment_id, manifest=manifest, adaptation=plan, prompt=prompt,
                                             estimate=estimate, request_summary=summary, user_id=user_id))
    if start:
        start_worker(client_id, run_ids)
    return run_ids


def _logo_image(file_id: int) -> Image.Image:
    row = files.read_file_by_id(file_id)
    image = files.open_image(bytes(row["content"])).convert("RGBA")
    box = image.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
    return image.crop(box) if box else image


def execute_run(client_id: int, run_id: int) -> None:
    if not repository.claim_run(run_id):
        return
    run = repository.get_run(client_id, run_id)
    experiment = repository.get_experiment(client_id, run["experiment_id"])
    spec = experiment["spec"]
    plan = run["adaptation_plan"]
    manifest = catalog.manifest(run["model_key"])
    caps = catalog.capabilities(run["model_key"])
    by_ref = {ref["ref_id"]: ref for ref in spec["references"]}
    try:
        if plan.get("pipeline") == "studio":
            result = _run_studio(client_id, run, experiment, spec, plan, by_ref)
        else:
            references = [files.provider_data_url(by_ref[ref["ref_id"]]["file_id"]) for ref in plan["sent"]]
            result = connector.call(manifest["provider"], model_id=manifest["provider_model_id"], prompt=run["model_prompt"],
                                    parameters=plan["parameters"]["applied"], references=references,
                                    pricing=caps.get("pricing") or [])
    except connector.ProviderError as exc:
        repository.update_run(run_id, status="blocked" if exc.blocked else "failed", finished_at="now",
                              error={"message": str(exc), "status": exc.status, "detail": (exc.detail or "")[:600]})
        return
    except Exception as exc:
        log.exception("Lab run %s failed", run_id)
        repository.update_run(run_id, status="failed", finished_at="now", error={"message": f"{type(exc).__name__}: {str(exc)[:300]}"})
        return

    try:
        _store_result(client_id, run_id, run, spec, plan, by_ref, result)
    except Exception as exc:
        log.exception("Lab run %s could not store its result", run_id)
        from ..db import get_db
        get_db().rollback()
        repository.update_run(run_id, status="failed", finished_at="now", actual_cost_usd=result.get("cost_usd"),
                              latency_ms=result.get("latency_ms"),
                              error={"message": f"Resultado recebido, mas não gravado: {type(exc).__name__}: {str(exc)[:300]}"})
        return
    try:
        evaluation.evaluate_run(client_id, run_id)
    except Exception:
        log.warning("Lab evaluation failed for run %s", run_id, exc_info=True)
        from ..db import get_db
        get_db().rollback()


def _run_studio(client_id, run, experiment, spec, plan, by_ref):
    """The Studio's own pipeline for this run's model. The director's direction is asked once per experiment."""
    snapshot = experiment.get("brand_snapshot") or {}
    direction = spec.get("studio_direction")
    if not direction:
        direction = studio_bridge.direct(spec, snapshot)
        spec["studio_direction"] = direction
        repository.update_experiment_spec(experiment["id"], spec)
    return studio_bridge.run_create(model_key=run["model_key"], spec=spec, snapshot=snapshot, plan=plan, by_ref=by_ref,
                                    direction=direction, files_module=files, client_id=client_id,
                                    user_id=run.get("created_by"))


def _store_result(client_id, run_id, run, spec, plan, by_ref, result):
    studio = plan.get("pipeline") == "studio"
    raw_bytes = base64.b64decode(result["b64"])
    cropped = None
    if not studio:
        raw_bytes, cropped = fit_to_ratio(raw_bytes, spec["aspect_ratio"])
        if cropped:
            result["b64"] = base64.b64encode(raw_bytes).decode("ascii")
    raw = files.store_image(client_id, raw_bytes, kind="output")
    final, composer = raw, None
    logos = [] if studio else [ref for ref in plan.get("post_processed", []) if ref["role"] == "LOGO"]
    if logos:
        try:
            encoded = apply_brand_logo(result["b64"], "png", _logo_image(by_ref[logos[0]["ref_id"]]["file_id"]), "bottom-right")
            final = files.store_image(client_id, base64.b64decode(encoded), kind="output")
            composer = "logo_bottom_right"
        except Exception:
            log.warning("Lab composer could not place the logo on run %s", run_id, exc_info=True)
    summary = dict(run["request_summary"] or {})
    summary.update({"raw_file_id": raw["file_id"], "raw_token": raw["token"], "output_file_id": final["file_id"],
                    "composer": composer, "provider_model": result.get("model"), "cropped_to_format": cropped,
                    "output_size": [raw["width"], raw["height"]]})
    if studio:
        summary["studio"] = {key: result.get(key) for key in ("pipeline", "mask_id", "mockup", "calls", "dropped_references", "delivered")}
        summary["composer"] = "studio_logo"
        repository.update_run(run_id, model_prompt=result["prompt"])
    repository.update_run(run_id, status="succeeded", finished_at="now", latency_ms=result["latency_ms"],
                          actual_cost_usd=result["cost_usd"], cost_source=result["cost_source"], usage=result["usage"],
                          provider_request_id=(result.get("request_id") or "")[:160] or None,
                          output_file_id=final["file_id"], thumb_file_id=final["thumb_file_id"], request_summary=summary)


def run_sequence(client_id: int, run_ids: list[int]) -> None:
    from ..db import get_db
    for run_id in run_ids:
        try:
            execute_run(client_id, run_id)
        except Exception:
            log.exception("Lab run %s crashed", run_id)
            # A failed statement aborts the shared connection; the next run must start clean.
            try:
                get_db().rollback()
            except Exception:
                pass


def start_worker(client_id: int, run_ids: list[int]) -> None:
    if not run_ids:
        return
    app = current_app._get_current_object()

    def work():
        with _lock, app.app_context():
            run_sequence(client_id, run_ids)

    threading.Thread(target=work, name=f"creative-lab-{run_ids[0]}", daemon=True).start()


def _missing(client_id: int, scenario_key: str, model_keys: list[str]):
    from ..db import get_db
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT e.id, array_remove(array_agg(DISTINCT r.model_key) FILTER (WHERE r.status = 'succeeded'), NULL) AS done
                 FROM cx_lab_experiments e LEFT JOIN cx_lab_runs r ON r.experiment_id = e.id
                WHERE e.client_id = %s AND e.scenario_key = %s GROUP BY e.id ORDER BY e.id DESC""",
            (client_id, scenario_key),
        )
        rows = cursor.fetchall()
    done = {model for row in rows for model in (row["done"] or [])}
    missing = [model for model in (model_keys or list(catalog.manifests())) if model not in done]
    return (rows[0]["id"] if rows else None), missing


def run_scenario(client_id: int, key: str, model_keys: list[str], user_id: int | None, *, start: bool = True,
                 format_key: str | None = None) -> dict:
    """Queue only the models without a successful generation for this scenario (and format).

    A scenario keeps one experiment per format: missing models become new attempts inside it, so every
    cell of the grid compares the same frozen brand snapshot, references and director prompt.
    Multi-format scenarios without ``format_key`` queue every format, one after another.
    """
    from . import scenarios
    item = scenarios.scenario(key)
    if item.get("reserved"):
        raise ValueError("Cenário reservado: ainda sem definição.")
    if item.get("formats") and not format_key:
        results = [run_scenario(client_id, key, model_keys, user_id, start=False, format_key=fmt) for fmt in item["formats"]]
        run_ids = [run_id for result in results for run_id in result["run_ids"]]
        if start:
            start_worker(client_id, run_ids)
        return {"experiment_ids": [result["experiment_id"] for result in results], "run_ids": run_ids,
                "experiment_id": results[0]["experiment_id"] if results else None}
    scenario_key = f"{key}@{format_key}" if format_key else key
    experiment_id, missing = _missing(client_id, scenario_key, model_keys)
    if not missing:
        return {"experiment_id": experiment_id, "run_ids": []}
    if experiment_id:
        return {"experiment_id": experiment_id, "run_ids": queue_models(client_id, experiment_id, missing, user_id, start=start)}
    refs = []
    for ref in item["references"]:
        stored = repository.import_brand_asset(client_id, ref["asset_id"], role=ref["role"], label=ref["label"],
                                               has_person=ref.get("has_person", False), user_id=user_id)
        refs.append({"ref_id": stored["ref_id"], "role": ref["role"], "label": ref["label"]})
    data = {field: item.get(field) for field in ("task", "brand_id", "aspect_ratio", "quality", "objective", "instruction",
                                                 "must_include_text", "preserve", "alter", "logo_mode", "payload_policy",
                                                 "pipeline", "mockup")}
    brief = dict(item.get("brief") or {})
    if format_key:
        brief["format_key"] = format_key
        if item["task"] == "edit":
            from .archetypes import format_info
            data["aspect_ratio"] = format_info(format_key)["ratio"]
    data.update({"scenario_key": scenario_key, "title": item["title"], "references": refs, "models": missing, "brief": brief})
    return create_experiment_runs(client_id, data, user_id, start=start)


def run_reformat(client_id: int, ref_id: int, format_keys: list[str], model_keys: list[str], user_id: int | None) -> dict:
    """Reformat a real piece (vertical ↔ horizontal, square → story…) on every chosen model."""
    from .archetypes import format_info
    ref = repository.get_reference(client_id, ref_id)
    run_ids, experiment_ids = [], []
    for format_key in format_keys:
        fmt = format_info(format_key)
        if not fmt:
            continue
        brief = {"format_key": format_key, "copy": ((ref.get("anatomy") or {}).get("copy") or {})}
        data = {"task": "edit", "brand_id": ref.get("brand_id"), "aspect_ratio": fmt["ratio"], "quality": "standard",
                "objective": "format adaptation", "instruction": f"Reformatar “{ref['label']}” para {fmt['label']}",
                "logo_mode": "none", "scenario_key": f"reformat-ref{ref_id}@{format_key}",
                "title": f"Reformatar {ref['label']} → {fmt['label']}", "brief": brief,
                "references": [{"ref_id": ref_id, "role": "BASE", "label": ref["label"]}], "models": model_keys,
                "must_include_text": list(brief["copy"].values())[:8]}
        created = create_experiment_runs(client_id, data, user_id, start=False)
        run_ids += created["run_ids"]
        experiment_ids.append(created["experiment_id"])
    start_worker(client_id, run_ids)
    return {"experiment_ids": experiment_ids, "run_ids": run_ids}
