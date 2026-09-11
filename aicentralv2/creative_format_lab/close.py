"""Fecha a cena: gera camadas isoladas, posiciona, junta e confere guideline."""

from __future__ import annotations

import base64

from .catalog import plate_for
from .compose import compose_stack
from .guidelines import check_stack
from .stack import build_stack


def close_scene(
    scene,
    *,
    brand=None,
    assets=None,
    image_callable=None,
    generate=True,
):
    scene = scene if isinstance(scene, dict) else {}
    assets = dict(assets or {})
    stack = build_stack(
        scene,
        brand=brand,
        assets=assets,
        plate=scene.get("plate") or plate_for(scene.get("purpose")),
    )
    rasters = {}
    generated = []
    if generate and image_callable:
        for item in stack["layers"]:
            if not item.get("generate") and item.get("asset_url"):
                continue
            if item.get("role") not in {"product", "logo"}:
                continue
            if item.get("role") == "logo" and (assets.get("logo_url") or item.get("asset_url")):
                continue
            prompt = item.get("prompt")
            if not prompt:
                continue
            png = image_callable(
                prompt,
                aspect_ratio="1:1",
                background="opaque",
            )
            if isinstance(png, dict):
                raw = png.get("b64_json")
                png = base64.b64decode(raw) if raw else None
            if png:
                rasters[item["role"]] = png
                item["generate"] = False
                generated.append(item["role"])
    if assets.get("scene_image") and stack["background"]["kind"] in {"image", "wash"}:
        rasters.setdefault("background", assets.get("scene_image"))
    if assets.get("logo_url"):
        rasters.setdefault("logo", assets.get("logo_url"))
    if assets.get("product_url"):
        rasters.setdefault("product", assets.get("product_url"))
    for item in stack["layers"]:
        if item.get("png"):
            rasters.setdefault(item["role"], item["png"])
    composed = compose_stack(stack, rasters)
    report = check_stack(stack)
    return {
        "scene_id": stack["id"],
        "stack": stack,
        "guidelines": report,
        "png_data_url": composed["png_data_url"],
        "width": composed["width"],
        "height": composed["height"],
        "placed": composed["placed"],
        "generated": generated,
        "passed": report["passed"],
        "ready_for_motion": True,
    }
