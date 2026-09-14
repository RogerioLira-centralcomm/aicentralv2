"""Processa o job. GET nunca chama isto."""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone

from ..services.openrouter_service import download_video, generate_video, poll_video
from .composition.compositor import crop_video, overlay_video
from .composition.overlay_renderer import render_overlay
from .composition.plate_renderer import render_plate
from .geometry import crop_box_4x5, prepare_frame
from .public import asset_url
from .settings import POLL_INTERVAL
from . import storage, transcode

logger = logging.getLogger(__name__)

TERMINAL = {"completed", "failed", "cancelled", "expired"}


class AnimateWorker:
    def __init__(self, repository, *, persist_fn=None, materialize_fn=None, video=None):
        self.repository = repository
        self.persist_fn = persist_fn
        self.materialize_fn = materialize_fn
        self.video = video or {
            "submit": generate_video,
            "poll": poll_video,
            "download": download_video,
        }

    def run(self, job_id):
        claimed = self.repository.claim_job(job_id)
        if claimed is None:
            return self.repository.get_job(job_id)
        try:
            plan = claimed.get("plan_json") or {}
            self._stage(job_id, "prepare", 8, "Preparando composição")
            frames = self._frames(plan)
            self._stage(job_id, "submit", 18, "Enviando ao Seedance")
            submitted = self.video["submit"](
                plan.get("prompt") or "",
                model=plan.get("model"),
                duration=plan.get("duration") or 8,
                resolution=plan.get("resolution") or "720p",
                aspect_ratio=plan.get("aspect_ratio") or "16:9",
                size=plan.get("size"),
                generate_audio=bool(plan.get("generate_audio")),
                frame_images=frames,
                seed=plan.get("seed"),
                req_key=plan.get("plan_hash"),
            )
            self.repository.update_job(
                job_id,
                provider_job_id=submitted.get("id") or "",
                provider_polling_url=submitted.get("polling_url") or "",
                status="provider_pending",
            )
            status = self._wait(job_id, submitted)
            if status.get("status") != "completed":
                raise RuntimeError(status.get("error") or "A geração falhou.")
            self._stage(job_id, "download", 72, "Baixando master")
            raw = self.video["download"](submitted.get("id") or status.get("id"))
            version = self._packs(job_id, claimed, plan, raw)
            self._stage(job_id, "persist", 94, "Salvando no histórico")
            if callable(self.persist_fn):
                stored = self.persist_fn(claimed, plan, version) or version
            else:
                stored = version
            self.repository.update_job(
                job_id,
                status="ready",
                stage="ready",
                progress=100,
                message="Pronto",
                version_payload=stored,
                completed_at=datetime.now(timezone.utc),
                locked_at=None,
            )
            return self.repository.get_job(job_id)
        except Exception as exc:
            logger.exception("Animação %s falhou", job_id)
            self.repository.update_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                message=str(exc)[:240],
                error_message=str(exc)[:500],
                failed_at=datetime.now(timezone.utc),
                locked_at=None,
            )
            raise

    def retry_transcode(self, job_id):
        row = self.repository.get_job(job_id)
        if row.get("status") not in {"ready", "failed"}:
            raise ValueError("Só é possível repetir formatos de um job já gerado.")
        if not row.get("provider_job_id"):
            raise ValueError("Este job não tem master no provedor.")
        plan = row.get("plan_json") or {}
        raw = self.video["download"](row["provider_job_id"])
        version = self._packs(job_id, row, plan, raw)
        if callable(self.persist_fn):
            version = self.persist_fn(row, plan, version) or version
        return self.repository.update_job(
            job_id,
            status="ready",
            version_payload=version,
            error_message="",
            message="Formatos atualizados",
        )

    def recompose(self, job_id, snapshot, still_bytes, *, snapshot_b=None, still_b=None):
        row = self.repository.get_job(job_id)
        if row.get("status") not in {"ready", "failed"}:
            raise ValueError("Só é possível recompor um job já gerado.")
        plan = dict(row.get("plan_json") or {})
        source = dict(plan.get("source") or {})
        if source.get("mode") == "transition_ab":
            if snapshot:
                source["snapshot_a"] = snapshot
            if snapshot_b:
                source["snapshot_b"] = snapshot_b
            if still_b:
                source["reference_b"] = source.get("reference_b")
        else:
            source["snapshot"] = snapshot
            source["mode"] = "protected_scene"
        plan["source"] = source
        base = self._seedance_base(row)
        version = self._packs(
            job_id, row, plan, base, still_bytes=still_bytes, still_b=still_b
        )
        if callable(self.persist_fn):
            version = self.persist_fn(row, plan, version) or version
        self.repository.update_job(
            job_id,
            status="ready",
            stage="ready",
            plan_json=plan,
            version_payload=version,
            error_message="",
            message="Overlay atualizado",
        )
        return version

    def _wait(self, job_id, submitted):
        deadline = time.time() + 15 * 60
        status = submitted
        while time.time() < deadline:
            current = str(status.get("status") or "pending")
            if current == "pending":
                self._stage(job_id, "queue", 32, "Aguardando na fila", persist="provider_pending")
            elif current == "in_progress":
                self._stage(job_id, "generate", 52, "Gerando movimento", persist="provider_running")
            elif current in TERMINAL:
                return status
            time.sleep(POLL_INTERVAL)
            status = self.video["poll"](
                submitted.get("id") or "",
                polling_url=submitted.get("polling_url"),
            )
        raise TimeoutError("A geração excedeu o tempo máximo.")

    def _frames(self, plan):
        first = self._encode_frame(self._plate_bytes(plan), plan, "first_frame")
        frames = [first]
        if (plan.get("source") or {}).get("mode") == "transition_ab":
            frames.append(self._encode_frame(self._plate_bytes(plan, side="b"), plan, "last_frame"))
        return frames

    def _encode_frame(self, raw, plan, frame_type):
        prepared = prepare_frame(raw, plan.get("piece_ratio") or "16:9", plan.get("resolution") or "720p")
        encoded = base64.b64encode(prepared).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
            "frame_type": frame_type,
        }

    def _plate_bytes(self, plan, still_bytes=None, side="a"):
        source = plan.get("source") or {}
        mode = source.get("mode") or ""
        reference = source.get("reference_b") if side == "b" else (source.get("reference") or plan.get("reference"))
        if still_bytes:
            raw = still_bytes
        else:
            if not reference and side == "a" and callable(self.materialize_fn):
                reference = self.materialize_fn(plan)
            if not reference:
                raise ValueError("A versão não tem still para animar." if side == "a" else "A versão B não tem still.")
            raw = _decode_still(reference)
        snapshot = source.get("snapshot_a") if side == "a" and mode == "transition_ab" else (
            source.get("snapshot_b") if side == "b" else source.get("snapshot")
        )
        if mode == "protected_scene":
            if not snapshot:
                raise ValueError("A composição protegida exige um snapshot da cena.")
            return render_plate(raw, snapshot)
        if snapshot:
            return render_plate(raw, snapshot)
        return raw

    def _packs(self, job_id, row, plan, raw, still_bytes=None, still_b=None):
        job_pk = row.get("id")
        base = self._store_asset(
            job_pk,
            "seedance_base",
            raw,
            "video/mp4",
            ".mp4",
            plan,
            has_audio=bool(plan.get("generate_audio")),
            protected=False,
            composited=False,
        )
        video = raw
        width = plan.get("width")
        height = plan.get("height")
        piece = plan.get("piece_ratio") or "16:9"
        if piece == "4:5" and width and height:
            try:
                video = crop_video(raw, int(width), int(height), piece)
                _left, _top, width, height = crop_box_4x5(int(width), int(height))
            except Exception:
                logger.warning("Crop 4:5 falhou em %s", job_id)
        source = plan.get("source") or {}
        mode = source.get("mode") or ""
        snapshot = source.get("snapshot")
        snapshot_a = source.get("snapshot_a")
        snapshot_b = source.get("snapshot_b")
        protected = (mode == "protected_scene" and bool(snapshot)) or (
            mode == "transition_ab" and bool(snapshot_a or snapshot_b)
        )
        end_card = None
        if protected:
            self._stage(job_id, "compositing", 78, "Protegendo textos e logos")
            try:
                if mode == "transition_ab":
                    duration = int(plan.get("duration") or 8)
                    still_a = still_bytes or _optional_still(source.get("reference") or plan.get("reference"))
                    still_b_bytes = still_b or _optional_still(source.get("reference_b"))
                    if snapshot_a and still_a:
                        video = overlay_video(video, render_overlay(still_a, snapshot_a), start=0, end=1)
                    if snapshot_b and still_b_bytes:
                        overlay_b = render_overlay(still_b_bytes, snapshot_b)
                        video = overlay_video(
                            video, overlay_b, start=max(0, duration - 1), end=duration
                        )
                        from .composition.overlay_renderer import compose_still

                        end_card = compose_still(still_b_bytes, overlay_b)
                else:
                    plate_source = still_bytes or _optional_still(
                        source.get("reference") or plan.get("reference")
                    )
                    if not plate_source:
                        raise ValueError("A composição protegida precisa do still original.")
                    video = overlay_video(video, render_overlay(plate_source, snapshot))
            except Exception:
                logger.exception("Overlay falhou em %s", job_id)
                raise RuntimeError("Não foi possível proteger textos e logos no master.")
        self._stage(job_id, "transcode", 82, "Preparando formatos")
        master = self._store_asset(
            job_pk,
            "master",
            video,
            "video/mp4",
            ".mp4",
            plan,
            has_audio=bool(plan.get("generate_audio")),
            width=width,
            height=height,
            protected=protected,
            composited=protected,
        )
        packs = [
            {"kind": "seedance_base", "asset_id": base["public_id"], "status": "ready"},
            {"kind": "master", "asset_id": master["public_id"], "status": "ready"},
        ]
        poster = None
        try:
            poster_bytes = transcode.poster_jpg(master["storage_key"])
            poster = self._store_asset(job_pk, "poster", poster_bytes, "image/jpeg", ".jpg", plan, width=width, height=height)
        except Exception:
            logger.warning("Poster ffmpeg falhou em %s", job_id)
        if "small_mp4" in (plan.get("delivery") or []):
            try:
                small = transcode.small_mp4(master["storage_key"])
                asset = self._store_asset(job_pk, "small_mp4", small, "video/mp4", ".mp4", plan, width=width, height=height)
                packs.append({"kind": "small_mp4", "asset_id": asset["public_id"], "status": "ready"})
            except Exception:
                packs.append({"kind": "small_mp4", "status": "skipped", "reason": "ffmpeg_missing"})
        if "gif" in (plan.get("delivery") or []):
            try:
                gif = transcode.gif_bytes(
                    master["storage_key"],
                    duration=plan.get("duration") or 8,
                    window=plan.get("gif_window") or "first",
                )
                asset = self._store_asset(job_pk, "gif", gif, "image/gif", ".gif", plan, width=width, height=height)
                packs.append({"kind": "gif", "asset_id": asset["public_id"], "status": "ready"})
            except Exception:
                packs.append({"kind": "gif", "status": "skipped", "reason": "ffmpeg_missing"})
        else:
            packs.append({"kind": "gif", "status": "skipped", "reason": "not_requested"})
        poster_id = (poster or {}).get("public_id") or ""
        end_card_id = ""
        if end_card:
            try:
                stored_end = self._store_asset(
                    job_pk, "end_card", end_card, "image/jpeg", ".jpg", plan, width=width, height=height
                )
                end_card_id = stored_end["public_id"]
                packs.append({"kind": "end_card", "asset_id": end_card_id, "status": "ready"})
            except Exception:
                logger.warning("End card falhou em %s", job_id)
        payload = {
            "origin": "animate",
            "media": "video",
            "source_version_id": (plan.get("source") or {}).get("base_id") or "",
            "camadas_creative_id": (plan.get("source") or {}).get("camadas_creative_id")
            or ((plan.get("source") or {}).get("snapshot") or {}).get("creative_id")
            or "",
            "scene_version": ((plan.get("source") or {}).get("snapshot") or {}).get("scene_version"),
            "protected_layers": protected,
            "transition_from": source.get("base_id") or "",
            "transition_to": source.get("to_id") or "",
            "end_card_asset_id": "",
            "duration": plan.get("duration"),
            "has_audio": bool(plan.get("generate_audio")),
            "seedance_base_asset_id": base["public_id"],
            "master_asset_id": master["public_id"],
            "poster_asset_id": poster_id,
            "video_url": asset_url(master["public_id"]),
            "poster_url": asset_url(poster_id) if poster_id else "",
            "image_url": asset_url(poster_id) if poster_id else asset_url(master["public_id"]),
            "packs": packs,
            "job_id": job_id,
        }
        payload["end_card_asset_id"] = end_card_id
        return payload

    def _seedance_base(self, row):
        job_pk = row.get("id")
        version = row.get("version_payload") if isinstance(row.get("version_payload"), dict) else {}
        asset_id = version.get("seedance_base_asset_id")
        if asset_id:
            asset = self.repository.get_asset(asset_id)
            path = storage.read_path(asset.get("storage_key"))
            if path is not None:
                return path.read_bytes()
        finder = getattr(self.repository, "list_assets", None)
        if callable(finder):
            for item in finder(job_id=job_pk, kind="seedance_base"):
                path = storage.read_path(item.get("storage_key"))
                if path is not None:
                    return path.read_bytes()
        raise ValueError("Este job não tem o base do Seedance para recompor.")

    def _store_asset(
        self,
        job_pk,
        kind,
        payload,
        mime,
        suffix,
        plan,
        has_audio=False,
        width=None,
        height=None,
        protected=False,
        composited=False,
    ):
        public_id = None
        from .ids import new_id

        public_id = new_id("asset")
        path = storage.write_bytes(public_id, suffix, payload)
        return self.repository.add_asset({
            "public_id": public_id,
            "job_id": job_pk,
            "kind": kind,
            "mime_type": mime,
            "storage_key": path,
            "sha256": storage.sha256(payload),
            "size_bytes": len(payload),
            "width": width if width is not None else plan.get("width"),
            "height": height if height is not None else plan.get("height"),
            "duration": plan.get("duration"),
            "has_audio": has_audio,
            "provenance": {
                "type": "generated_video" if kind != "poster" else "video_poster",
                "provider": "openrouter",
                "model": plan.get("model"),
                "source_version_id": (plan.get("source") or {}).get("base_id"),
                "protected_layers": bool(protected),
                "post_composited": bool(composited),
            },
        })

    def _stage(self, job_id, stage, progress, message, persist=None):
        row = self.repository.get_job(job_id)
        stages = list(row.get("stages") or [])
        now = datetime.now(timezone.utc).isoformat()
        found = next((item for item in stages if item.get("id") == stage), None)
        if found:
            found["message"] = message
            found["updated_at"] = now
        else:
            stages.append({"id": stage, "message": message, "started_at": now})
        self.repository.update_job(
            job_id,
            stage=stage,
            progress=progress,
            message=message,
            status=persist or row.get("status") or "queued",
            stages=stages,
        )


def _optional_still(value):
    try:
        return _decode_still(value) if value else b""
    except ValueError:
        return b""


def _decode_still(value):
    text = str(value or "")
    if text.startswith("data:image/") and "," in text:
        return base64.b64decode(text.split(",", 1)[1])
    if text.startswith(("http://", "https://")):
        import requests

        response = requests.get(text, timeout=30)
        response.raise_for_status()
        return response.content
    raise ValueError("Still inválido para o first frame.")
