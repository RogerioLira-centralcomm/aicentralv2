"""Orquestra upload, job e documento da Camadas V2."""

from __future__ import annotations

import logging

from .analysis.ocr import read_creative
from .extraction.cutouts import detection_to_row, extract_image_elements
from .html.compiler import apply_operations
from .html.sanitizer import sanitize_scene
from .html.scene import build_scene, merge_scene, text_elements_from_reading
from .jobs import spawn, stage_payload
from .library.collections import resolve_collection
from .library.deduplicate import asset_fingerprint, find_duplicate
from .library.search import filter_assets, group_counts
from .repositories import CamadasConflictError, CamadasNotFoundError, CamadasRepository
from .schemas import (
    asset_kind_from_role,
    is_public_id,
    new_public_id,
    normalize_provenance,
    optional_int,
    strip_client_injections,
)
from .segmentation.contours import contours_from_mask
from .segmentation.matting import refine_mask
from .segmentation.provider import segment_all, segment_at
from .segmentation.quality import REVIEW
from .storage import CamadasStorage, validate_still

logger = logging.getLogger(__name__)

_UNSET = object()


class CamadasService:
    def __init__(self, repository=None, storage=None, text_callable=_UNSET, spawn_job=None, predictor=_UNSET):
        self.repository = repository or CamadasRepository()
        self.storage = storage or CamadasStorage()
        self._text_callable = text_callable
        self.spawn_job = spawn_job or spawn
        self._predictor = predictor

    def create_creative(self, file_storage, payload=None, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        validate_still(file_storage)
        self.repository.ready()
        creative_id = new_public_id("creative")
        saved = self.storage.save_original(file_storage, creative_id)
        client_id = optional_int(payload.get("brand_id") or payload.get("client_id"))
        collection_pk = None
        if payload.get("collection_id") and client_id:
            collection_pk = resolve_collection(
                self.repository,
                client_id,
                payload.get("collection_id"),
            ).get("id")
        elif payload.get("collection_id"):
            collection_pk = optional_int(payload.get("collection_id"))
        creative = self.repository.create_creative(
            {
                "public_id": creative_id,
                "client_id": client_id,
                "collection_id": collection_pk,
                "name": str(payload.get("name") or saved.get("original_name") or "").strip(),
                "status": "queued",
                "original_path": saved["asset_path"],
                "original_name": saved.get("original_name") or "",
                "mime_type": saved.get("mime_type") or "",
                "sha256": saved.get("sha256") or "",
                "width": saved.get("width") or 0,
                "height": saved.get("height") or 0,
                "created_by": user_id,
            }
        )
        job = self.repository.create_job(creative["id"])
        self.spawn_job(self.analyze_creative, job["public_id"], creative["public_id"])
        return {
            "creative_id": creative["public_id"],
            "job_id": job["public_id"],
            "status": "queued",
        }

    def get_creative(self, creative_id):
        self.repository.ready()
        creative = self.repository.get_creative(creative_id)
        elements = self.repository.list_elements(creative["id"])
        scene_row = self.repository.get_scene(creative["id"])
        reading = creative.get("reading") if isinstance(creative.get("reading"), dict) else {}
        scene = sanitize_scene(
            (scene_row or {}).get("document")
            or build_scene(
                creative["public_id"],
                reading.get("read_full") or reading,
                elements,
                creative.get("width"),
                creative.get("height"),
            )
        )
        return {
            "creative": _public_creative(creative),
            "elements": [_public_element(item) for item in elements],
            "scene": scene,
            "scene_version": int((scene_row or {}).get("version") or 1),
            "collections": [
                _public_collection(item)
                for item in self.repository.list_collections(creative.get("client_id"))
            ],
            "assets": [
                _public_asset(item)
                for item in self.repository.list_assets(creative.get("client_id"))
            ],
            "warnings": list(creative.get("warnings") or []),
        }

    def get_job(self, job_id):
        self.repository.ready()
        job = self.repository.get_job(job_id)
        return {
            "status": job.get("status") or "queued",
            "stage": job.get("stage") or "queued",
            "progress": int(job.get("progress") or 0),
            "message": job.get("message") or "",
            "error": job.get("error") or "",
            "creative_id": job.get("creative_public_id") or "",
        }

    def analyze_creative(self, job_id, creative_id):
        try:
            self.repository.ready()
            creative = self.repository.get_creative(creative_id)
            self.repository.update_creative(creative_id, status="running")
            self.repository.update_job(job_id, **stage_payload("reading_creative"))
            reading = read_creative(
                self.storage.as_data_url(creative.get("original_path")),
                self._resolve_text_callable(),
            )
            warnings = []
            if reading.get("ocr_status") in {"unavailable", "failed"}:
                warnings.append("1 texto não foi identificado" if reading.get("ocr_status") == "failed" else "OCR indisponível")
            self.repository.update_job(job_id, **stage_payload("finding_objects"))
            image_rows = []
            source = self._open_source(creative)
            if source is not None:
                self.repository.update_job(job_id, **stage_payload("extracting_elements"))
                detections = segment_all(
                    source,
                    reading.get("read_full") or {},
                    predictor=self._resolve_predictor(),
                )
                image_rows, _field, _kind = extract_image_elements(
                    source,
                    detections,
                    reading.get("read_full") or {},
                    self.storage,
                    creative_id,
                )
            self.repository.update_job(job_id, **stage_payload("assembling_scene"))
            rows = list(image_rows) + text_elements_from_reading(reading.get("read_full") or {})
            review = [item for item in rows if item.get("quality") in REVIEW]
            if review:
                warnings.append(f"{len(review)} elementos precisam de revisão")
            elements = self.repository.replace_elements(creative["id"], rows)
            scene = build_scene(
                creative_id,
                reading.get("read_full") or {},
                elements,
                creative.get("width"),
                creative.get("height"),
            )
            self.repository.upsert_scene(creative["id"], sanitize_scene(scene), version=1)
            self.repository.update_job(job_id, **stage_payload("preparing_review"))
            self.repository.update_creative(
                creative_id,
                status="ready",
                reading=reading,
                warnings=warnings,
            )
            done = stage_payload("done", _done_message(elements, warnings))
            self.repository.update_job(job_id, **done)
            return {
                "creative_id": creative_id,
                "reading": reading,
                "elements": elements,
                "scene": scene,
            }
        except (CamadasNotFoundError, CamadasConflictError, ValueError) as exc:
            self._fail_job(job_id, creative_id, str(exc))
            raise
        except Exception:
            logger.exception("Falha ao analisar criativo %s", creative_id)
            self._fail_job(job_id, creative_id, "Não foi possível analisar o criativo.")
            raise

    def _fail_job(self, job_id, creative_id, message):
        try:
            self.repository.update_job(job_id, **stage_payload("failed", message), error=message)
        except Exception:
            logger.exception("Não atualizei o job %s", job_id)
        try:
            self.repository.update_creative(creative_id, status="failed")
        except Exception:
            logger.exception("Não atualizei o criativo %s", creative_id)

    def segment_point(self, creative_id, payload=None):
        payload = strip_client_injections(payload if isinstance(payload, dict) else {})
        self.repository.ready()
        creative = self.repository.get_creative(creative_id)
        source = self._open_source(creative)
        if source is None:
            raise ValueError("Não abri o criativo original.")
        positives = list(payload.get("positive_points") or [])
        negatives = list(payload.get("negative_points") or [])
        if not positives:
            raise ValueError("Envie um ponto positivo.")
        existing = self._existing_masks(creative["id"])
        wanted = str(payload.get("element_id") or "").strip()
        detection = segment_at(
            source,
            positives,
            negatives,
            predictor=self._resolve_predictor(),
            existing=existing,
        )
        if detection is None:
            raise CamadasNotFoundError("Nenhum elemento nesse ponto.")
        if detection.get("hit") and detection.get("element"):
            row = detection["element"]
            if wanted and row.get("public_id") != wanted:
                row = self.repository.get_element(wanted)
            return {
                "element_id": row.get("public_id"),
                "created": False,
                "element": _public_element(row),
            }
        index = 1 + sum(
            1
            for item in self.repository.list_elements(creative["id"])
            if item.get("role") == (detection.get("role") or "product")
        )
        row = detection_to_row(source, detection, self.storage, creative_id, index)
        saved = self.repository.add_element(creative["id"], row)
        self.repository.save_mask(
            saved["id"],
            {
                "version": 1,
                "mask_path": saved.get("mask_path"),
                "contours": (saved.get("metadata") or {}).get("contours") or [],
                "points": (saved.get("metadata") or {}).get("points") or [],
            },
        )
        self._refresh_scene(creative)
        return {
            "element_id": saved["public_id"],
            "created": True,
            "element": _public_element(saved),
        }

    def refine_element_mask(self, element_id, payload=None):
        payload = strip_client_injections(payload if isinstance(payload, dict) else {})
        self.repository.ready()
        element = self.repository.get_element(element_id)
        creative = self.repository.get_creative(element["creative_public_id"])
        source = self._open_source(creative)
        mask = self.storage.open_image(element.get("mask_path"))
        if source is None or mask is None:
            raise ValueError("Este elemento ainda não tem máscara.")
        updated = refine_mask(
            mask.convert("L"),
            source,
            positive_points=payload.get("positive_points"),
            negative_points=payload.get("negative_points"),
            brush_strokes=payload.get("brush_strokes"),
            expand_px=payload.get("expand_px") or 0,
            feather_px=payload.get("feather_px") or 0,
            remove_halo=bool(payload.get("remove_halo")),
        )
        from ..creative_format_lab.split_layers import _cutout

        crop, box = _cutout(source, updated)
        png_path = self.storage.save_png(creative["public_id"], f"{element_id}-cut", crop)
        mask_path = self.storage.save_png(creative["public_id"], f"{element_id}-mask", updated)
        geometry = contours_from_mask(updated)
        metadata = dict(element.get("metadata") or {})
        metadata.update(geometry)
        saved = self.repository.update_element(
            element_id,
            bbox=box,
            png_path=png_path,
            mask_path=mask_path,
            metadata=metadata,
        )
        self.repository.save_mask(
            element["id"],
            {
                "version": int(metadata.get("version") or 1) + 1,
                "mask_path": mask_path,
                "contours": geometry["contours"],
                "points": geometry["points"],
            },
        )
        self._refresh_scene(creative)
        return _public_element(self.repository.get_element(element_id))

    def patch_element(self, element_id, payload=None):
        payload = strip_client_injections(payload if isinstance(payload, dict) else {})
        self.repository.ready()
        allowed = ("label", "visible", "locked", "z_index", "approved", "bbox")
        fields = {key: payload[key] for key in allowed if key in payload}
        if not fields:
            return _public_element(self.repository.get_element(element_id))
        self.repository.update_element(element_id, **fields)
        element = self.repository.get_element(element_id)
        self._refresh_scene(self.repository.get_creative(element["creative_public_id"]))
        return _public_element(element)

    def patch_scene(self, creative_id, payload=None):
        payload = strip_client_injections(payload if isinstance(payload, dict) else {})
        self.repository.ready()
        creative = self.repository.get_creative(creative_id)
        row = self.repository.get_scene(creative["id"])
        if not row:
            raise CamadasNotFoundError("Cena não encontrada.")
        if payload.get("version") in (None, ""):
            raise ValueError("Envie a versão da cena.")
        try:
            expected = int(payload.get("version"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Versão da cena inválida.") from exc
        operations = payload.get("operations")
        if not isinstance(operations, list):
            raise ValueError("Envie operações da cena.")
        next_scene = apply_operations(row.get("document") or {}, operations)
        saved = self.repository.update_scene_if_version(creative["id"], expected, next_scene)
        self._sync_elements_from_scene(creative, next_scene)
        return {
            "scene": sanitize_scene(saved.get("document") or next_scene),
            "scene_version": int(saved.get("version") or expected + 1),
        }

    def list_brand_library(self, brand_id, payload=None):
        payload = payload if isinstance(payload, dict) else {}
        self.repository.ready()
        client_id = optional_int(brand_id)
        collection = None
        if payload.get("collection_id"):
            collection = resolve_collection(self.repository, client_id, payload.get("collection_id"))
        rows = [
            _public_asset(item)
            for item in self.repository.list_assets(client_id, (collection or {}).get("id"))
        ]
        assets = filter_assets(
            rows,
            query=payload.get("q") or payload.get("query") or "",
            kind=payload.get("kind") or "",
            provenance=payload.get("provenance") or "",
        )
        return {
            "assets": assets,
            "collections": [_public_collection(item) for item in self.repository.list_collections(client_id)],
            "counts": group_counts(rows),
        }

    def create_brand_collection(self, brand_id, payload=None):
        payload = strip_client_injections(payload if isinstance(payload, dict) else {})
        self.repository.ready()
        client_id = optional_int(brand_id)
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("Dê um nome à coleção.")
        row = resolve_collection(self.repository, client_id, name=name)
        return _public_collection(row)

    def publish_element(self, element_id, payload=None):
        payload = strip_client_injections(payload if isinstance(payload, dict) else {})
        self.repository.ready()
        element = self.repository.get_element(element_id)
        creative = self.repository.get_creative(element["creative_public_id"])
        client_id = creative.get("client_id")
        if not client_id:
            raise ValueError("Associe uma marca antes de publicar.")
        collection = resolve_collection(
            self.repository,
            client_id,
            payload.get("collection_id"),
            payload.get("collection_name") or "",
        )
        provenance = normalize_provenance(element.get("provenance"), element.get("layer_type"))
        sha256 = asset_fingerprint(element, self.storage)
        duplicate = find_duplicate(self.repository, client_id, sha256)
        if duplicate:
            return {
                "asset": _public_asset(_with_collection(duplicate, collection)),
                "created": False,
                "duplicate": True,
            }
        tags = [str(item).strip() for item in (payload.get("tags") or []) if str(item).strip()]
        metadata = {
            "tags": tags[:20],
            "role": element.get("role"),
            "quality": element.get("quality") or "",
            "text": element.get("text_content") or "",
            "source_element_id": element.get("public_id"),
            "source_creative_id": creative.get("public_id"),
        }
        row = self.repository.create_asset(
            {
                "public_id": new_public_id("asset"),
                "client_id": client_id,
                "collection_id": collection.get("id"),
                "element_id": element.get("id"),
                "creative_id": creative.get("id"),
                "name": str(payload.get("name") or element.get("label") or element.get("role") or "Ativo")[:200],
                "kind": asset_kind_from_role(element.get("role"), element.get("layer_type")),
                "provenance": provenance,
                "sha256": sha256,
                "asset_path": element.get("png_path") or "",
                "thumb_path": element.get("thumb_path") or element.get("png_path") or "",
                "metadata": metadata,
            }
        )
        return {
            "asset": _public_asset(_with_collection(row, collection)),
            "created": True,
            "duplicate": False,
        }

    def place_asset(self, creative_id, payload=None):
        payload = strip_client_injections(payload if isinstance(payload, dict) else {})
        self.repository.ready()
        creative = self.repository.get_creative(creative_id)
        asset_id = str(payload.get("asset_id") or "").strip()
        if not is_public_id(asset_id, "asset"):
            raise ValueError("Envie o ativo da biblioteca.")
        asset = self.repository.get_asset(asset_id)
        if creative.get("client_id") and asset.get("client_id") and int(creative["client_id"]) != int(asset["client_id"]):
            raise ValueError("Este ativo pertence a outra marca.")
        meta = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        kind = asset.get("kind") or "graphic"
        layer_type = "text" if kind == "composition" else "image"
        role = meta.get("role") or ("support" if layer_type == "text" else kind)
        box = {
            "x": _pct(payload.get("x"), 20),
            "y": _pct(payload.get("y"), 20),
            "w": _pct(payload.get("width") or payload.get("w"), 30),
            "h": _pct(payload.get("height") or payload.get("h"), 40),
        }
        z_index = 1 + max(
            [int(item.get("z_index") or 0) for item in self.repository.list_elements(creative["id"])] or [0]
        )
        saved = self.repository.add_element(
            creative["id"],
            {
                "role": role,
                "label": asset.get("name") or role,
                "layer_type": layer_type,
                "bbox": box,
                "quality": "placed",
                "provenance": normalize_provenance(asset.get("provenance"), layer_type),
                "z_index": z_index,
                "text_content": meta.get("text") or "",
                "png_path": asset.get("asset_path") or "",
                "thumb_path": asset.get("thumb_path") or "",
                "metadata": {
                    "library_asset_id": asset.get("public_id"),
                    "tags": meta.get("tags") or [],
                },
            },
        )
        scene = self._refresh_scene(creative)
        row = self.repository.get_scene(creative["id"])
        return {
            "element": _public_element(saved),
            "scene": scene,
            "scene_version": int((row or {}).get("version") or 1),
            "placed": True,
        }

    def _open_source(self, creative):
        opener = getattr(self.storage, "open_image", None)
        if callable(opener):
            image = opener(creative.get("original_path"))
            if image is not None:
                return image
        try:
            from ..creative_format_lab.split_layers import _open_image

            data = self.storage.as_data_url(creative.get("original_path"))
            if data:
                return _open_image(data)
        except Exception:
            return None
        return None

    def _existing_masks(self, creative_pk):
        found = []
        for item in self.repository.list_elements(creative_pk):
            if item.get("layer_type") != "image" or item.get("role") == "background":
                continue
            mask = self.storage.open_image(item.get("mask_path"))
            if mask is None:
                continue
            found.append({"mask": mask.convert("L"), "element": item, "hit": True})
        return found

    def _refresh_scene(self, creative):
        elements = self.repository.list_elements(creative["id"])
        reading = creative.get("reading") if isinstance(creative.get("reading"), dict) else {}
        current = self.repository.get_scene(creative["id"])
        built = build_scene(
            creative["public_id"],
            reading.get("read_full") or {},
            elements,
            creative.get("width"),
            creative.get("height"),
        )
        scene = merge_scene((current or {}).get("document"), built)
        version = int((current or {}).get("version") or 1)
        self.repository.upsert_scene(creative["id"], scene, version=version)
        return scene

    def _sync_elements_from_scene(self, creative, scene):
        elements = {
            item.get("public_id"): item
            for item in self.repository.list_elements(creative["id"])
        }
        for layer in scene.get("layers") or []:
            row = elements.get(layer.get("id"))
            if not row:
                continue
            fields = {}
            if layer.get("type") == "text" and layer.get("text") is not None:
                fields["text_content"] = layer.get("text") or ""
            box = dict(row.get("bbox") or {})
            changed_box = False
            for src, dst in (("x", "x"), ("y", "y"), ("width", "w"), ("height", "h")):
                if layer.get(src) is not None:
                    box[dst] = layer[src]
                    changed_box = True
            if changed_box:
                fields["bbox"] = box
            if "visible" in layer:
                fields["visible"] = bool(layer.get("visible"))
            if layer.get("z_index") is not None:
                fields["z_index"] = int(layer.get("z_index") or 0)
            if layer.get("label"):
                fields["label"] = layer.get("label")
            if fields:
                self.repository.update_element(row["public_id"], **fields)

    def _resolve_predictor(self):
        if self._predictor is not _UNSET:
            return self._predictor if callable(self._predictor) else None
        return None

    def _resolve_text_callable(self):
        if self._text_callable is not _UNSET:
            return self._text_callable if callable(self._text_callable) else None
        try:
            from ..creative_modeling_service import CreativeModelingService

            generator = getattr(CreativeModelingService(), "generator", None)
            return getattr(generator, "text_callable", None)
        except Exception:
            return None


def _done_message(elements, warnings):
    count = len(elements or [])
    review = len(warnings or [])
    if review:
        return f"{count} elementos encontrados. {review} precisam de revisão."
    if count:
        return f"{count} elementos encontrados"
    return "Análise pronta. Sem textos identificados."


def _public_creative(row):
    return {
        "id": row.get("public_id"),
        "brand_id": row.get("client_id"),
        "collection_id": row.get("collection_id"),
        "name": row.get("name") or "",
        "status": row.get("status") or "",
        "original_path": row.get("original_path") or "",
        "width": row.get("width") or 0,
        "height": row.get("height") or 0,
        "reading": row.get("reading") or {},
        "created_at": _iso(row.get("created_at")),
    }


def _public_element(row):
    return {
        "id": row.get("public_id"),
        "role": row.get("role"),
        "label": row.get("label") or "",
        "type": row.get("layer_type") or "image",
        "bbox": row.get("bbox") or {},
        "quality": row.get("quality") or "",
        "provenance": row.get("provenance") or "",
        "visible": bool(row.get("visible", True)),
        "locked": bool(row.get("locked", False)),
        "z_index": int(row.get("z_index") or 0),
        "approved": bool(row.get("approved", False)),
        "text": row.get("text_content") or "",
        "png_path": row.get("png_path") or "",
        "mask_path": row.get("mask_path") or "",
        "metadata": row.get("metadata") or {},
    }


def _with_collection(row, collection):
    data = dict(row or {})
    if collection:
        data["collection_public_id"] = collection.get("public_id")
        data["collection_name"] = collection.get("name")
    return data


def _public_collection(row):
    return {
        "id": row.get("public_id"),
        "name": row.get("name") or "",
        "brand_id": row.get("client_id"),
    }


def _public_asset(row):
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return {
        "id": row.get("public_id"),
        "brand_id": row.get("client_id"),
        "collection_id": row.get("collection_public_id") or "",
        "collection_name": row.get("collection_name") or "",
        "element_id": row.get("element_public_id") or "",
        "creative_id": row.get("creative_public_id") or "",
        "name": row.get("name") or "",
        "kind": row.get("kind") or "",
        "provenance": normalize_provenance(row.get("provenance")),
        "sha256": row.get("sha256") or "",
        "asset_path": row.get("asset_path") or "",
        "thumb_path": row.get("thumb_path") or row.get("asset_path") or "",
        "tags": list(meta.get("tags") or []),
        "text": meta.get("text") or "",
        "role": meta.get("role") or row.get("kind") or "",
        "archived": bool(meta.get("archived")),
        "created_at": _iso(row.get("created_at")),
    }


def _pct(value, default):
    if value in (None, ""):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(100.0, number))


def _iso(value):
    if value is None:
        return ""
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)
