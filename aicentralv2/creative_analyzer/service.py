"""Orquestra upload, processamento e persistência da análise."""

from __future__ import annotations

import time
import uuid
import os

from .processor import ImageCreativeAnalyzer, VideoCreativeAnalyzer
from .storage import AnalyzerStorage


class AnalyzerBilling:
    """Commercial credit boundary for an Analyzer run.

    The provider response is charged once, keyed by the public analysis id.
    A conservative preflight prevents paying a vision-provider call that the
    customer's balance cannot cover.
    """
    def __init__(self, ledger=None):
        from ..cadu_credit_connector import CaduCreditConnector
        self.credits = CaduCreditConnector(ledger)

    @staticmethod
    def credit_client_id(client_id):
        from ..creative_modeling_service import CreativeModelingService
        return CreativeModelingService()._credits_crm_id(client_id) or int(client_id)

    @staticmethod
    def estimate(media_type):
        name = "CREATIVE_ANALYZER_VIDEO_CREDIT_ESTIMATE" if media_type == "video" else "CREATIVE_ANALYZER_IMAGE_CREDIT_ESTIMATE"
        fallback = 22000 if media_type == "video" else 12000
        try:
            return max(1, int(os.getenv(name, str(fallback))))
        except ValueError:
            return fallback

    def reserve(self, public_id, client_id, user_id, media_type):
        """Atomically hold the published maximum before provider work starts.

        ``assert_available`` is deliberately not used here: it is only a
        snapshot and two uploads could otherwise both spend the same balance.
        The ledger debit is idempotent and is the reservation itself.
        """
        from ..cadu_credit_connector import CreditActor
        credit_client = self.credit_client_id(client_id)
        held = self.estimate(media_type)
        row = self.credits.charge_tokens(
            actor=CreditActor.from_values(credit_client, user_id),
            idempotency_key=f"studio:creative-analyzer:{public_id}",
            app="Cadu Analyzer",
            stage=f"{media_type}_analysis",
            model="creative-analyzer",
            charged_tokens=held,
            metadata={
                "analysis_id": str(public_id),
                "media_type": media_type,
                "reservation": True,
                "credit_ceiling": held,
            },
        ) or {}
        return int(row.get("tokens_cobrados") or held)

    def settle(self, reserved_credits, result):
        """Expose measured provider usage without creating a second debit.

        The reservation is the customer's maximum payable amount (shown in the
        UI before upload). Provider usage remains attached to the analysis for
        support and future price reconciliation; it must never be charged a
        second time under the same analysis id.
        """
        technical = result.get("technical") if isinstance(result, dict) else {}
        technical = technical if isinstance(technical, dict) else {}
        technical["reserved_credits"] = int(reserved_credits)
        return int(reserved_credits)


class AnalyzerService:
    def __init__(self, repository, storage=None, image_analyzer=None, video_analyzer=None, billing=None):
        self.repository = repository
        self.storage = storage or AnalyzerStorage()
        self.image_analyzer = image_analyzer or ImageCreativeAnalyzer()
        self.video_analyzer = video_analyzer or VideoCreativeAnalyzer()
        self.billing = billing

    def analyze_image(self, upload, *, user_id, client_id, context="", brand_ref=None, project_ref=None):
        public_id = str(uuid.uuid4())
        reserved_credits = 0
        if self.billing:
            reserved_credits = self.billing.reserve(public_id, client_id, user_id, "image")
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
                "media_type": "image",
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
            if self.billing:
                result["technical"]["charged_credits"] = self.billing.settle(reserved_credits, result)
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

    def analyze_video(self, upload, *, user_id, client_id, context="", brand_ref=None, project_ref=None):
        public_id = str(uuid.uuid4())
        reserved_credits = 0
        if self.billing:
            reserved_credits = self.billing.reserve(public_id, client_id, user_id, "video")
        saved = self.storage.save_video(public_id, upload)
        analysis = None
        run_id = None
        started = time.monotonic()
        try:
            analysis = self.repository.create_analysis({
                "public_id": public_id, "user_id": user_id, "client_id": client_id,
                "brand_ref": str(brand_ref or "")[:160] or None,
                "project_ref": str(project_ref or "")[:160] or None,
                "original_name": saved["original_name"], "media_type": "video",
                "mime_type": saved["mime_type"], "format": saved["format"],
                "thumbnail_url": f"/studio/api/analyzer/assets/{public_id}/thumbnail",
                "context_text": str(context or "")[:2000] or None,
            })
            self.repository.add_asset(analysis["id"], {
                "kind": "source", "position": 0, "storage_key": saved["source_key"],
                "mime_type": saved["mime_type"], "sha256": saved["sha256"],
                "size_bytes": saved["size_bytes"], "width": saved["width"], "height": saved["height"],
                "duration_seconds": saved["duration"],
                "metadata": {"has_audio": saved["has_audio"], "video_codec": saved["video_codec"], "audio_codec": saved["audio_codec"]},
            })
            self.repository.add_asset(analysis["id"], {
                "kind": "thumbnail", "position": 0, "storage_key": saved["thumbnail_key"],
                "mime_type": "image/jpeg", "width": saved["width"], "height": saved["height"],
            })
            for frame in saved["frames"]:
                self.repository.add_asset(analysis["id"], {
                    "kind": "frame", "position": frame["position"], "storage_key": frame["storage_key"],
                    "mime_type": frame["mime_type"], "sha256": frame["sha256"],
                    "size_bytes": frame["size_bytes"], "width": saved["width"], "height": saved["height"],
                    "frame_time_seconds": frame["second"],
                })
            run_id = self.repository.start_run(analysis["id"], "video_analysis", "openrouter")
            result = self.video_analyzer.analyze(
                saved["frames"], context=context,
                technical={
                    "mime_type": saved["mime_type"], "format": saved["format"],
                    "width": saved["width"], "height": saved["height"], "size_bytes": saved["size_bytes"],
                    "sha256": saved["sha256"], "duration_seconds": saved["duration"],
                    "has_audio": saved["has_audio"], "video_codec": saved["video_codec"],
                    "audio_codec": saved["audio_codec"], "frames_count": 4,
                },
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            result["technical"]["duration_ms"] = duration_ms
            if self.billing:
                result["technical"]["charged_credits"] = self.billing.settle(reserved_credits, result)
            completed = self.repository.complete_analysis(public_id, result)
            self.repository.finish_run(run_id, "complete", duration_ms=duration_ms, usage=result["technical"].get("usage"))
            return completed
        except Exception as exc:
            if analysis:
                self.repository.fail_analysis(public_id, exc)
            else:
                self.storage.remove(public_id)
            if run_id:
                self.repository.finish_run(run_id, "failed", duration_ms=int((time.monotonic() - started) * 1000), error=exc)
            raise
