"""Persistence for the Lab (cx_lab_* tables). Every query is scoped by the organization id."""

from __future__ import annotations

from psycopg.types.json import Json

from ..db import get_db
from ..services.openrouter_service import _download_reference_bytes
from . import files
from .brands import asset_public_url

ROLES = ("BASE", "COMPOSITION", "PRODUCT", "PERSON", "STYLE", "LOGO", "OTHER")
STALE_RUN_SECONDS = 15 * 60


def _commit():
    get_db().commit()


def _reference_view(row: dict) -> dict:
    return {
        "ref_id": row["id"], "role": row["role"], "label": row["label"], "source": row["source"],
        "source_ref": row.get("source_ref"), "brand_id": row.get("brand_id"), "has_person": row["has_person"],
        "sha256": row["sha256"], "width": row.get("width"), "height": row.get("height"),
        "file_id": row["file_id"], "url": files.file_path(row["token"]), "public_url": files.public_url(row["token"]),
        "thumb_url": files.file_path(row["thumb_token"]),
        "anatomy": row.get("anatomy"), "is_benchmark": bool(row.get("is_benchmark")),
    }


REFERENCE_SELECT = """SELECT r.*, f.token, f.width, f.height, t.token AS thumb_token
                        FROM cx_lab_references r
                        JOIN cx_lab_files f ON f.id = r.file_id
                        LEFT JOIN cx_lab_files t ON t.id = r.thumb_file_id"""


def get_reference(client_id: int, ref_id: int) -> dict:
    with get_db().cursor() as cursor:
        cursor.execute(REFERENCE_SELECT + " WHERE r.client_id = %s AND r.id = %s", (client_id, ref_id))
        row = cursor.fetchone()
    if not row:
        raise LookupError("Referência não encontrada.")
    return _reference_view(dict(row))


def list_references(client_id: int, brand_id: int | None = None) -> list[dict]:
    with get_db().cursor() as cursor:
        if brand_id:
            cursor.execute(REFERENCE_SELECT + " WHERE r.client_id = %s AND (r.brand_id = %s OR r.brand_id IS NULL) ORDER BY r.created_at DESC LIMIT 200",
                           (client_id, brand_id))
        else:
            cursor.execute(REFERENCE_SELECT + " WHERE r.client_id = %s ORDER BY r.created_at DESC LIMIT 200", (client_id,))
        return [_reference_view(dict(row)) for row in cursor.fetchall()]


def save_reference(client_id: int, payload: bytes, *, role: str, label: str, source: str, source_ref: str = "",
                   brand_id: int | None = None, has_person: bool = False, user_id: int | None = None) -> dict:
    """Store once per image: the same bytes return the existing reference (no repeated thumbnails)."""
    role = role if role in ROLES else "OTHER"
    digest = files.sha256(payload)
    with get_db().cursor() as cursor:
        cursor.execute("SELECT id FROM cx_lab_references WHERE client_id = %s AND sha256 = %s", (client_id, digest))
        existing = cursor.fetchone()
    if existing:
        return get_reference(client_id, existing["id"])
    lossless = role == "LOGO"
    stored = files.store_image(client_id, payload, kind="reference", lossless=lossless)
    with get_db().cursor() as cursor:
        cursor.execute(
            """INSERT INTO cx_lab_references (client_id, brand_id, role, label, source, source_ref, file_id, thumb_file_id,
                                              sha256, has_person, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (client_id, brand_id, role, label[:160], source, source_ref or None, stored["file_id"],
             stored["thumb_file_id"], digest, bool(has_person), user_id),
        )
        ref_id = cursor.fetchone()["id"]
    _commit()
    return get_reference(client_id, ref_id)


def import_brand_asset(client_id: int, asset_id: int, *, role: str, label: str = "", has_person: bool = False,
                       user_id: int | None = None) -> dict:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT a.id, a.client_id AS brand_id, COALESCE(a.asset_path, a.source_url) AS path
                 FROM cx_client_brand_assets a JOIN cx_clients c ON c.id = a.client_id
                WHERE a.id = %s AND c.crm_client_id = %s AND a.status = 'approved'""",
            (asset_id, client_id),
        )
        asset = cursor.fetchone()
    if not asset:
        raise LookupError("Imagem da marca não encontrada.")
    url = asset_public_url(asset["path"])
    if not url:
        raise ValueError("A imagem da marca não tem URL pública.")
    content, _mime = _download_reference_bytes(url, max_bytes=12 * 1024 * 1024)
    return save_reference(client_id, content, role=role, label=label or f"Asset {asset_id}", source="brand_asset",
                          source_ref=str(asset_id), brand_id=asset["brand_id"], has_person=has_person, user_id=user_id)


def update_reference(client_id: int, ref_id: int, *, role: str | None = None, label: str | None = None,
                     has_person: bool | None = None) -> dict:
    with get_db().cursor() as cursor:
        cursor.execute(
            """UPDATE cx_lab_references SET role = COALESCE(%s, role), label = COALESCE(%s, label),
                      has_person = COALESCE(%s, has_person) WHERE client_id = %s AND id = %s""",
            (role if role in ROLES else None, label[:160] if label is not None else None, has_person, client_id, ref_id),
        )
    _commit()
    return get_reference(client_id, ref_id)


def create_experiment(client_id: int, *, scenario_key: str, title: str, task: str, brand_id, snapshot: dict, spec: dict,
                      user_id: int | None) -> int:
    with get_db().cursor() as cursor:
        cursor.execute(
            """INSERT INTO cx_lab_experiments (client_id, scenario_key, title, task, brand_id, brand_snapshot, spec, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (client_id, scenario_key, title[:200], task, brand_id, Json(snapshot), Json(spec), user_id),
        )
        experiment_id = cursor.fetchone()["id"]
    _commit()
    return experiment_id


def update_experiment_spec(experiment_id: int, spec: dict):
    with get_db().cursor() as cursor:
        cursor.execute("UPDATE cx_lab_experiments SET spec = %s WHERE id = %s", (Json(spec), experiment_id))
    _commit()


def get_experiment(client_id: int, experiment_id: int) -> dict:
    with get_db().cursor() as cursor:
        cursor.execute("SELECT * FROM cx_lab_experiments WHERE client_id = %s AND id = %s", (client_id, experiment_id))
        row = cursor.fetchone()
    if not row:
        raise LookupError("Experimento não encontrado.")
    return dict(row)


def create_run(experiment_id: int, *, manifest: dict, adaptation: dict, prompt: str, estimate: dict,
               request_summary: dict, user_id: int | None) -> int:
    status = "blocked" if adaptation.get("blocked") else "queued"
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(max(attempt), 0) + 1 AS next FROM cx_lab_runs WHERE experiment_id = %s AND model_key = %s",
            (experiment_id, manifest["model_key"]),
        )
        attempt = cursor.fetchone()["next"]
        cursor.execute(
            """INSERT INTO cx_lab_runs (experiment_id, model_key, provider, provider_model_id, profile_version, attempt, status,
                                        adaptation_plan, model_prompt, request_summary, estimated_cost_usd, error, created_by,
                                        finished_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s::text = 'blocked' THEN NOW() END)
               RETURNING id""",
            (experiment_id, manifest["model_key"], manifest["provider"], manifest["provider_model_id"],
             manifest["profile_version"], attempt, status, Json(adaptation), prompt, Json(request_summary),
             estimate.get("usd"), Json({"message": adaptation["blocked"]}) if adaptation.get("blocked") else None,
             user_id, status),
        )
        run_id = cursor.fetchone()["id"]
    _commit()
    return run_id


def update_run(run_id: int, **fields):
    if not fields:
        return
    json_fields = {"usage", "error", "request_summary", "adaptation_plan"}
    assignments, values = [], []
    for key, value in fields.items():
        if key in ("started_at", "finished_at") and value == "now":
            assignments.append(f"{key} = NOW()")
            continue
        assignments.append(f"{key} = %s")
        values.append(Json(value) if key in json_fields and value is not None else value)
    with get_db().cursor() as cursor:
        cursor.execute(f"UPDATE cx_lab_runs SET {', '.join(assignments)} WHERE id = %s", (*values, run_id))
    _commit()


def claim_run(run_id: int) -> bool:
    with get_db().cursor() as cursor:
        cursor.execute(
            "UPDATE cx_lab_runs SET status = 'running', started_at = NOW() WHERE id = %s AND status = 'queued' RETURNING id",
            (run_id,),
        )
        claimed = cursor.fetchone() is not None
    _commit()
    return claimed


# Queued runs wait their turn behind a sequential worker; only orphans (worker lost on restart) expire.
STALE_QUEUED_SECONDS = 6 * 3600


def fail_stale_runs():
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""UPDATE cx_lab_runs SET status = 'failed', finished_at = NOW(),
                       error = jsonb_build_object('message', 'A geração não terminou em {STALE_RUN_SECONDS // 60} minutos.')
                 WHERE (status = 'running' AND COALESCE(started_at, created_at) < NOW() - INTERVAL '{STALE_RUN_SECONDS} seconds')
                    OR (status = 'queued' AND created_at < NOW() - INTERVAL '{STALE_QUEUED_SECONDS} seconds')"""
        )
    _commit()


RUN_SELECT = """SELECT r.*, e.client_id, e.scenario_key, e.title AS experiment_title, e.task, e.brand_id,
                       e.spec->>'instruction' AS instruction, e.spec->'brief'->>'format_key' AS brief_format,
                       e.spec->>'aspect_ratio' AS aspect_ratio,
                       o.token AS output_token, o.width AS output_width, o.height AS output_height, t.token AS thumb_token
                  FROM cx_lab_runs r
                  JOIN cx_lab_experiments e ON e.id = r.experiment_id
                  LEFT JOIN cx_lab_files o ON o.id = r.output_file_id
                  LEFT JOIN cx_lab_files t ON t.id = r.thumb_file_id"""


def _iso(value):
    return value.isoformat() if value else None


def _run_view(row: dict, evaluations: list[dict], ratings: list[dict]) -> dict:
    observer = next((item for item in evaluations if item["kind"] == "observer"), None)
    typesafe = next((item for item in evaluations if item["kind"] == "typesafe"), None)
    raw_token = (row.get("request_summary") or {}).get("raw_token")
    return {
        "run_id": row["id"], "experiment_id": row["experiment_id"], "scenario_key": row["scenario_key"],
        "experiment_title": row["experiment_title"], "instruction": row.get("instruction"), "task": row["task"], "brand_id": row["brand_id"],
        "model_key": row["model_key"], "provider": row["provider"], "provider_model_id": row["provider_model_id"],
        "profile_version": row["profile_version"], "attempt": row["attempt"], "status": row["status"],
        "created_by": row.get("created_by"),
        "adaptation_plan": row["adaptation_plan"], "model_prompt": row["model_prompt"],
        "request_summary": row["request_summary"], "latency_ms": row["latency_ms"],
        "estimated_cost_usd": float(row["estimated_cost_usd"]) if row["estimated_cost_usd"] is not None else None,
        "actual_cost_usd": float(row["actual_cost_usd"]) if row["actual_cost_usd"] is not None else None,
        "cost_source": row["cost_source"], "usage": row["usage"], "error": row["error"],
        "image_url": files.file_path(row["output_token"]), "public_url": files.public_url(row["output_token"]),
        "raw_url": files.file_path(raw_token) if raw_token else None,
        "thumb_url": files.file_path(row["thumb_token"]),
        "width": row["output_width"], "height": row["output_height"],
        "created_at": _iso(row["created_at"]), "started_at": _iso(row["started_at"]), "finished_at": _iso(row["finished_at"]),
        "format_key": ((row.get("brief_format") or "") or None), "aspect_ratio": row.get("aspect_ratio"),
        "observer": observer, "typesafe": typesafe, "ratings": ratings,
    }


def _evaluations(cursor, run_ids):
    if not run_ids:
        return {}
    cursor.execute(
        """SELECT DISTINCT ON (run_id, kind) id, run_id, kind, model, payload, scores, primary_failure, suggestions,
                  cost_usd, latency_ms, created_at
             FROM cx_lab_evaluations WHERE run_id = ANY(%s) ORDER BY run_id, kind, created_at DESC""",
        (list(run_ids),),
    )
    grouped = {}
    for row in cursor.fetchall():
        item = dict(row)
        item["cost_usd"] = float(item["cost_usd"]) if item["cost_usd"] is not None else None
        item["created_at"] = _iso(item["created_at"])
        grouped.setdefault(row["run_id"], []).append(item)
    return grouped


def _ratings(cursor, run_ids):
    if not run_ids:
        return {}
    cursor.execute(
        """SELECT id, run_id, composition, product_fidelity, brand_fidelity, text_quality, aesthetic, verdict, notes, blind, created_at
             FROM cx_lab_ratings WHERE run_id = ANY(%s) ORDER BY created_at DESC""",
        (list(run_ids),),
    )
    grouped = {}
    for row in cursor.fetchall():
        item = dict(row)
        item["created_at"] = _iso(item["created_at"])
        grouped.setdefault(row["run_id"], []).append(item)
    return grouped


def get_run(client_id: int, run_id: int) -> dict:
    with get_db().cursor() as cursor:
        cursor.execute(RUN_SELECT + " WHERE e.client_id = %s AND r.id = %s", (client_id, run_id))
        row = cursor.fetchone()
        if not row:
            raise LookupError("Geração não encontrada.")
        evaluations = _evaluations(cursor, [run_id]).get(run_id, [])
        ratings = _ratings(cursor, [run_id]).get(run_id, [])
    return _run_view(dict(row), evaluations, ratings)


def list_runs(client_id: int, *, limit: int = 300) -> list[dict]:
    with get_db().cursor() as cursor:
        cursor.execute(RUN_SELECT + " WHERE e.client_id = %s ORDER BY r.created_at DESC LIMIT %s", (client_id, limit))
        rows = [dict(row) for row in cursor.fetchall()]
        ids = [row["id"] for row in rows]
        evaluations = _evaluations(cursor, ids)
        ratings = _ratings(cursor, ids)
    return [_run_view(row, evaluations.get(row["id"], []), ratings.get(row["id"], [])) for row in rows]


def save_evaluation(run_id: int, *, kind: str, model: str, payload: dict, scores: dict, primary_failure: str | None,
                    suggestions: list, cost_usd, latency_ms: int | None):
    with get_db().cursor() as cursor:
        cursor.execute(
            """INSERT INTO cx_lab_evaluations (run_id, kind, model, payload, scores, primary_failure, suggestions, cost_usd, latency_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (run_id, kind, model, Json(payload), Json(scores), primary_failure, Json(suggestions), cost_usd, latency_ms),
        )
    _commit()


def save_rating(client_id: int, run_id: int, data: dict, rater_id: int | None) -> None:
    get_run(client_id, run_id)
    def score(key):
        try:
            value = int(data.get(key))
        except (TypeError, ValueError):
            return None
        return value if 1 <= value <= 5 else None
    verdict = data.get("verdict") if data.get("verdict") in ("approved", "discarded") else None
    with get_db().cursor() as cursor:
        cursor.execute(
            """INSERT INTO cx_lab_ratings (run_id, rater_id, composition, product_fidelity, brand_fidelity, text_quality,
                                           aesthetic, verdict, notes, blind)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (run_id, rater_id, score("composition"), score("product_fidelity"), score("brand_fidelity"),
             score("text_quality"), score("aesthetic"), verdict, str(data.get("notes") or "")[:2000],
             bool(data.get("blind", True))),
        )
    _commit()


def add_note(client_id: int, *, scope: str, scope_key: str, body: str, author_id, author_name: str) -> None:
    if scope not in ("model", "scenario", "experiment", "run") or not body.strip():
        raise ValueError("Anotação inválida.")
    with get_db().cursor() as cursor:
        cursor.execute(
            """INSERT INTO cx_lab_notes (client_id, scope, scope_key, body, author_id, author_name)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (client_id, scope, str(scope_key)[:120], body.strip()[:4000], author_id, (author_name or "")[:160]),
        )
    _commit()


def list_notes(client_id: int) -> list[dict]:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, scope, scope_key, body, author_name, created_at FROM cx_lab_notes
                WHERE client_id = %s ORDER BY created_at DESC LIMIT 500""",
            (client_id,),
        )
        return [{**dict(row), "created_at": _iso(row["created_at"])} for row in cursor.fetchall()]


def upsert_proposal(*, model_key: str, from_version: int, failure: str, change: dict, rationale: str, run_id: int):
    with get_db().cursor() as cursor:
        cursor.execute(
            """INSERT INTO cx_lab_profile_proposals (model_key, from_version, failure, change, rationale, evidence_run_ids)
               VALUES (%s, %s, %s, %s, %s, ARRAY[%s]::bigint[])
               ON CONFLICT (model_key, from_version, failure) DO UPDATE
                  SET evidence_run_ids = (SELECT ARRAY(SELECT DISTINCT unnest(cx_lab_profile_proposals.evidence_run_ids || EXCLUDED.evidence_run_ids)))""",
            (model_key, from_version, failure, Json(change), rationale, run_id),
        )
    _commit()


def list_proposals() -> list[dict]:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, model_key, from_version, failure, change, rationale, cardinality(evidence_run_ids) AS evidence,
                      evidence_run_ids, status, created_at
                 FROM cx_lab_profile_proposals ORDER BY cardinality(evidence_run_ids) DESC, created_at DESC LIMIT 100"""
        )
        return [{**dict(row), "created_at": _iso(row["created_at"])} for row in cursor.fetchall()]
