"""/lab on the Studio host: the page, its JSON API and the public image files."""

from __future__ import annotations

import logging

from flask import jsonify, make_response, render_template, request, session

from ..creative_media.studio_csrf import get_or_create_token, studio_csrf_required
from . import archetypes, brands, catalog, evaluation, intelligence, repository, runner, scenarios
from .access import current_client_id, lab_enabled, lab_required

log = logging.getLogger(__name__)
MAX_UPLOAD = 15 * 1024 * 1024


def _user_id():
    try:
        return int(session.get("user_id") or 0) or None
    except (TypeError, ValueError):
        return None


def _error(message, status=400):
    return jsonify({"error": message}), status


@lab_required
def lab_page():
    from ..creative_modeling_routes import _host_redirect
    redirected = _host_redirect("studio")
    if redirected:
        return redirected
    response = make_response(render_template("cadu_studio/lab.html", lab_csrf=get_or_create_token()))
    response.headers["Cache-Control"] = "no-store, private"
    return response


@lab_required
def api_state():
    client_id = current_client_id()
    repository.fail_stale_runs()
    return jsonify({
        "models": catalog.models_view(),
        "scenarios": scenarios.scenarios(),
        "brands": brands.list_brands(client_id),
        "references": repository.list_references(client_id),
        "runs": repository.list_runs(client_id),
        "notes": repository.list_notes(client_id),
        "proposals": repository.list_proposals(),
        **archetypes.catalog_view(),
        "catalog_fetched_at": catalog.catalog().get("fetched_at"),
    })


@lab_required
def api_brand(brand_id):
    client_id = current_client_id()
    try:
        snapshot = brands.brand_snapshot(client_id, brand_id)
    except LookupError as exc:
        return _error(str(exc), 404)
    return jsonify({"brand": snapshot, "references": repository.list_references(client_id, brand_id)})


@lab_required
@studio_csrf_required
def api_upload_reference():
    upload = request.files.get("file")
    if not upload:
        return _error("Envie uma imagem.")
    content = upload.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        return _error("A imagem passa de 15 MB.")
    has_person = request.form.get("has_person") in ("1", "true", "on")
    if has_person and request.form.get("consent") not in ("1", "true", "on"):
        return _error("Confirme que há autorização de uso da imagem da pessoa.")
    try:
        ref = repository.save_reference(current_client_id(), content, role=request.form.get("role") or "OTHER",
                                        label=request.form.get("label") or upload.filename or "Upload",
                                        source="upload", brand_id=int(request.form["brand_id"]) if request.form.get("brand_id") else None,
                                        has_person=has_person, user_id=_user_id())
    except (OSError, ValueError):
        return _error("O arquivo não é uma imagem válida.")
    return jsonify({"reference": ref})


@lab_required
@studio_csrf_required
def api_import_reference():
    data = request.get_json(silent=True) or {}
    try:
        ref = repository.import_brand_asset(current_client_id(), int(data["asset_id"]), role=data.get("role") or "OTHER",
                                            label=data.get("label") or "", has_person=bool(data.get("has_person")),
                                            user_id=_user_id())
    except (KeyError, ValueError, LookupError) as exc:
        return _error(str(exc) or "Imagem inválida.")
    except Exception as exc:
        log.warning("Lab brand asset import failed", exc_info=True)
        return _error(f"Não foi possível baixar a imagem da marca: {str(exc)[:160]}")
    return jsonify({"reference": ref})


@lab_required
@studio_csrf_required
def api_update_reference(ref_id):
    data = request.get_json(silent=True) or {}
    try:
        ref = repository.update_reference(current_client_id(), ref_id, role=data.get("role"), label=data.get("label"),
                                          has_person=data.get("has_person"))
    except LookupError as exc:
        return _error(str(exc), 404)
    return jsonify({"reference": ref})


@lab_required
@studio_csrf_required
def api_prepare_scenario(key):
    """Import the scenario's brand assets as references and return a ready-to-run form."""
    try:
        item = scenarios.scenario(key)
    except KeyError:
        return _error("Cenário desconhecido.", 404)
    if item.get("reserved"):
        return _error("Cenário reservado: ainda sem definição.")
    client_id = current_client_id()
    refs = []
    for ref in item["references"]:
        try:
            stored = repository.import_brand_asset(client_id, ref["asset_id"], role=ref["role"], label=ref["label"],
                                                   has_person=ref.get("has_person", False), user_id=_user_id())
            refs.append({"ref_id": stored["ref_id"], "role": ref["role"], "label": ref["label"]})
        except Exception as exc:
            log.warning("Scenario %s asset %s unavailable", key, ref["asset_id"], exc_info=True)
            return _error(f"Imagem {ref['asset_id']} da marca indisponível: {str(exc)[:160]}")
    form = {key_: item.get(key_) for key_ in ("task", "brand_id", "aspect_ratio", "quality", "objective", "instruction",
                                              "must_include_text", "preserve", "alter", "logo_mode")}
    form.update({"scenario_key": item["key"], "title": item["title"], "references": refs, "avoid": [],
                 "payload_policy": "verified_and_probable"})
    return jsonify({"form": form})


@lab_required
@studio_csrf_required
def api_run_scenario(key):
    data = request.get_json(silent=True) or {}
    try:
        result = runner.run_scenario(current_client_id(), key, data.get("models") or [], _user_id(),
                                     format_key=data.get("format_key") or None)
    except KeyError:
        return _error("Cenário desconhecido.", 404)
    except (ValueError, LookupError) as exc:
        return _error(str(exc))
    return jsonify(result), 201


@lab_required
@studio_csrf_required
def api_preview():
    try:
        return jsonify(runner.preview(current_client_id(), request.get_json(silent=True) or {}, _user_id()))
    except (ValueError, LookupError, KeyError) as exc:
        return _error(str(exc))


@lab_required
@studio_csrf_required
def api_create_experiment():
    """One experiment per format: a multi-format briefing becomes one matrix row per format."""
    data = request.get_json(silent=True) or {}
    if not data.get("models"):
        return _error("Escolha ao menos um modelo.")
    formats = [item for item in data.get("formats") or [] if archetypes.format_info(item)]
    try:
        if not formats:
            result = runner.create_experiment_runs(current_client_id(), data, _user_id())
            return jsonify(result), 201
        import time as _time
        base = str(data.get("scenario_key") or f"teste-{int(_time.time())}")[:40]
        run_ids, experiment_ids = [], []
        for format_key in formats:
            item = {**data, "brief": {**(data.get("brief") or {}), "format_key": format_key},
                    "scenario_key": f"{base}@{format_key}"}
            if data.get("task") == "edit":
                item["aspect_ratio"] = archetypes.format_info(format_key)["ratio"]
            created = runner.create_experiment_runs(current_client_id(), item, _user_id(), start=False)
            run_ids += created["run_ids"]
            experiment_ids.append(created["experiment_id"])
        runner.start_worker(current_client_id(), run_ids)
    except (ValueError, LookupError, KeyError) as exc:
        return _error(str(exc))
    return jsonify({"experiment_ids": experiment_ids, "run_ids": run_ids}), 201


@lab_required
@studio_csrf_required
def api_brief():
    data = request.get_json(silent=True) or {}
    client_id = current_client_id()
    brand = None
    if data.get("brand_id"):
        snapshot = brands.brand_snapshot(client_id, int(data["brand_id"]))
        brand = brands.payload_fields(snapshot, data.get("payload_policy") or "verified_and_probable")
    anatomy = None
    if data.get("ref_id"):
        anatomy = repository.get_reference(client_id, int(data["ref_id"])).get("anatomy")
    if not str(data.get("idea") or "").strip() and not anatomy:
        return _error("Escreva a ideia ou escolha uma peça real analisada.")
    try:
        return jsonify(intelligence.write_brief(str(data.get("idea") or "")[:1500], brand,
                                                objective=str(data.get("objective") or ""),
                                                format_key=str(data.get("format_key") or ""),
                                                archetype=str(data.get("archetype") or ""), anatomy=anatomy))
    except Exception as exc:
        log.warning("Lab brief writer failed", exc_info=True)
        return _error(f"O redator não respondeu: {str(exc)[:160]}", 502)


@lab_required
@studio_csrf_required
def api_anatomy(ref_id):
    try:
        return jsonify({"reference": intelligence.read_anatomy(current_client_id(), ref_id)})
    except LookupError as exc:
        return _error(str(exc), 404)
    except Exception as exc:
        log.warning("Lab anatomy failed", exc_info=True)
        return _error(f"A análise não respondeu: {str(exc)[:160]}", 502)


@lab_required
@studio_csrf_required
def api_reformat(ref_id):
    data = request.get_json(silent=True) or {}
    if not data.get("models") or not data.get("formats"):
        return _error("Escolha formatos e modelos.")
    try:
        return jsonify(runner.run_reformat(current_client_id(), ref_id, data["formats"], data["models"], _user_id())), 201
    except (ValueError, LookupError, KeyError) as exc:
        return _error(str(exc))


@lab_required
@studio_csrf_required
def api_queue_runs(experiment_id):
    data = request.get_json(silent=True) or {}
    try:
        run_ids = runner.queue_models(current_client_id(), experiment_id, data.get("models") or [], _user_id())
    except (ValueError, LookupError, KeyError) as exc:
        return _error(str(exc))
    return jsonify({"run_ids": run_ids}), 201


@lab_required
def api_runs():
    repository.fail_stale_runs()
    return jsonify({"runs": repository.list_runs(current_client_id())})


@lab_required
def api_run(run_id):
    try:
        return jsonify({"run": repository.get_run(current_client_id(), run_id)})
    except LookupError as exc:
        return _error(str(exc), 404)


@lab_required
@studio_csrf_required
def api_evaluate(run_id):
    try:
        return jsonify({"run": evaluation.evaluate_run(current_client_id(), run_id)})
    except (LookupError, ValueError) as exc:
        return _error(str(exc))


@lab_required
@studio_csrf_required
def api_rate(run_id):
    try:
        repository.save_rating(current_client_id(), run_id, request.get_json(silent=True) or {}, _user_id())
        return jsonify({"run": repository.get_run(current_client_id(), run_id)})
    except LookupError as exc:
        return _error(str(exc), 404)


@lab_required
@studio_csrf_required
def api_note():
    data = request.get_json(silent=True) or {}
    try:
        repository.add_note(current_client_id(), scope=data.get("scope"), scope_key=str(data.get("scope_key") or ""),
                            body=str(data.get("body") or ""), author_id=_user_id(),
                            author_name=session.get("user_name") or "")
    except ValueError as exc:
        return _error(str(exc))
    return jsonify({"notes": repository.list_notes(current_client_id())})


@lab_required
@studio_csrf_required
def api_refresh_catalog():
    catalog.catalog(refresh=True)
    return jsonify({"models": catalog.models_view()})


def public_file(token):
    """Public by unguessable token, like Studio public links; required for provider-fetchable URLs."""
    from . import files
    row = files.read_file(token.removesuffix(".webp"))
    if not row:
        return _error("not_found", 404)
    response = make_response(bytes(row["content"]))
    response.headers["Content-Type"] = row["mime"]
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def register_lab_routes(blueprint, app=None):
    rules = [
        ("/lab", "studio_lab", lab_page, ["GET"]),
        ("/lab/api/state", "studio_lab_state", api_state, ["GET"]),
        ("/lab/api/brands/<int:brand_id>", "studio_lab_brand", api_brand, ["GET"]),
        ("/lab/api/references", "studio_lab_upload", api_upload_reference, ["POST"]),
        ("/lab/api/references/import", "studio_lab_import", api_import_reference, ["POST"]),
        ("/lab/api/references/<int:ref_id>", "studio_lab_reference", api_update_reference, ["PATCH"]),
        ("/lab/api/scenarios/<key>/prepare", "studio_lab_scenario", api_prepare_scenario, ["POST"]),
        ("/lab/api/scenarios/<key>/run", "studio_lab_scenario_run", api_run_scenario, ["POST"]),
        ("/lab/api/preview", "studio_lab_preview", api_preview, ["POST"]),
        ("/lab/api/experiments", "studio_lab_experiments", api_create_experiment, ["POST"]),
        ("/lab/api/experiments/<int:experiment_id>/runs", "studio_lab_queue", api_queue_runs, ["POST"]),
        ("/lab/api/runs", "studio_lab_runs", api_runs, ["GET"]),
        ("/lab/api/runs/<int:run_id>", "studio_lab_run", api_run, ["GET"]),
        ("/lab/api/runs/<int:run_id>/evaluate", "studio_lab_evaluate", api_evaluate, ["POST"]),
        ("/lab/api/runs/<int:run_id>/rating", "studio_lab_rate", api_rate, ["POST"]),
        ("/lab/api/notes", "studio_lab_notes", api_note, ["POST"]),
        ("/lab/api/brief", "studio_lab_brief", api_brief, ["POST"]),
        ("/lab/api/references/<int:ref_id>/anatomy", "studio_lab_anatomy", api_anatomy, ["POST"]),
        ("/lab/api/references/<int:ref_id>/reformat", "studio_lab_reformat", api_reformat, ["POST"]),
        ("/lab/api/catalog/refresh", "studio_lab_catalog", api_refresh_catalog, ["POST"]),
        ("/lab/files/<token>", "studio_lab_file", public_file, ["GET"]),
    ]
    for path, endpoint, view, methods in rules:
        blueprint.add_url_rule(path, endpoint=endpoint, view_func=view, methods=methods)
    if app is not None:
        app.jinja_env.globals["studio_lab_enabled"] = lab_enabled
