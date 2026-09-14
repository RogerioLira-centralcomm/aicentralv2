"""Orquestra catálogo → anatomia → assets → recomposição → placement → viewer → quality."""

from ..creative_format_assets import resolve_assets
from . import anatomy, catalog, placement, quality, recompose, review, viewer


def run_training(payload):
    payload = payload if isinstance(payload, dict) else {}
    catalog_result = catalog.run(payload)
    if catalog_result.get("status") == "blocked":
        return _bundle(payload, catalog=catalog_result, blocked=catalog_result)
    body = dict(payload)
    body["catalog"] = catalog_result
    anatomy_result = anatomy.run(body)
    body["anatomy"] = anatomy_result
    assets = resolve_assets({
        **payload,
        "format_key": catalog_result["format_key"],
    })
    body["assets"] = assets
    recompose_result = recompose.run(body)
    place = placement.run(body)
    if place.get("status") == "blocked":
        return _bundle(
            payload,
            catalog=catalog_result,
            anatomy=anatomy_result,
            assets=assets,
            recompose=recompose_result,
            placement=place,
            blocked=place,
        )
    body["placement"] = place
    view = viewer.run(body)
    body["viewer"] = view
    qa = quality.run(body)
    planned = review.plan_rounds(payload.get("revision_count") or 3)
    snap = review.snapshot({**body, "quality": qa}, 1)
    return _bundle(
        payload,
        catalog=catalog_result,
        anatomy=anatomy_result,
        assets=assets,
        recompose=recompose_result,
        placement=place,
        viewer=view,
        quality=qa,
        review=planned,
        snapshot=snap,
        blocked=qa if qa.get("status") == "blocked" else None,
    )


def _bundle(payload, blocked=None, **steps):
    catalog_result = steps.get("catalog") or {}
    return {
        "status": "blocked" if blocked else "ok",
        "blocked": blocked,
        "format_key": catalog_result.get("format_key") or payload.get("format_key"),
        "path": _path(steps.get("assets")),
        "steps": steps,
        "public": {
            "label": (steps.get("assets") or {}).get("public_label"),
            "disclaimer": "Simulação de ambiente · sem afiliação com o veículo",
            "enabled": bool((steps.get("quality") or {}).get("public_enabled")),
        },
    }


def _path(assets):
    source = (assets or {}).get("source_type")
    return {
        "client_creative": "A",
        "client_assets_recomposed": "A",
        "generated_mock": "B",
        "internal_demo": "B",
        "smart_placeholder": "C",
    }.get(source, "C")
