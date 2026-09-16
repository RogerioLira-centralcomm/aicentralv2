"""Orquestra upload, processamento e persistência da análise."""

from __future__ import annotations

import time
import uuid

from .processor import ImageCreativeAnalyzer
from .storage import AnalyzerStorage


class AnalyzerService:
    def __init__(self, repository, storage=None, image_analyzer=None):
        self.repository = repository
        self.storage = storage or AnalyzerStorage()
        self.image_analyzer = image_analyzer or ImageCreativeAnalyzer()

    def analyze_image(self, upload, *, user_id, client_id, context="", brand_ref=None, project_ref=None):
        public_id = str(uuid.uuid4())
        saved = self.storage.save_image(public_id, upload)
        analysis = None
        run_id = None
        started = time.monotonic()
        try:
            analysis = self.repository.create_analysis({
                "public_id": public_id,
                "user_id": user_id,
                "client_id": client_id,
                "brand_ref": str(brand_ref or "")[:160] or None,
                "project_ref": str(project_ref or "")[:160] or None,
                "original_name": saved["original_name"],
                "mime_type": saved["mime_type"],
                "format": saved["format"],
                "thumbnail_url": f"/studio/api/analyzer/assets/{public_id}/thumbnail",
                "context_text": str(context or "")[:2000] or None,
            })
            self.repository.add_asset(analysis["id"], {
                "kind": "source", "position": 0, "storage_key": saved["source_key"],
                "mime_type": saved["mime_type"], "sha256": saved["sha256"],
                "size_bytes": saved["size_bytes"], "width": saved["width"], "height": saved["height"],
            })
            self.repository.add_asset(analysis["id"], {
                "kind": "thumbnail", "position": 0, "storage_key": saved["thumbnail_key"],
                "mime_type": "image/jpeg", "width": saved["width"], "height": saved["height"],
            })
            run_id = self.repository.start_run(analysis["id"], "image_analysis", "openrouter")
            result = self.image_analyzer.analyze(
                saved["data_url"],
                context=context,
                technical={
                    "mime_type": saved["mime_type"], "format": saved["format"],
                    "width": saved["width"], "height": saved["height"],
                    "size_bytes": saved["size_bytes"], "sha256": saved["sha256"],
                },
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            result["technical"]["duration_ms"] = duration_ms
            completed = self.repository.complete_analysis(public_id, result)
            self.repository.finish_run(
                run_id, "complete", duration_ms=duration_ms,
                usage=(result.get("technical") or {}).get("usage"),
            )
            return completed
        except Exception as exc:
            if analysis:
                self.repository.fail_analysis(public_id, exc)
            else:
                self.storage.remove(public_id)
            if run_id:
                self.repository.finish_run(
                    run_id, "failed", duration_ms=int((time.monotonic() - started) * 1000), error=exc
                )
            raise
