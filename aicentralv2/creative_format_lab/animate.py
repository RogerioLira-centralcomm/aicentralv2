"""Fachada Trocar → creative_media. Sem lógica de Seedance aqui."""

from __future__ import annotations

import base64
from io import BytesIO

from werkzeug.datastructures import FileStorage

from ..creative_media.composition.overlay_renderer import compose_still, render_overlay
from ..creative_media.composition.plate_renderer import render_plate
from ..creative_media.composition.scene_snapshot import (
    snapshot_fingerprint,
    snapshot_scene,
    validate_snapshot,
)
from ..creative_media.jobs import spawn
from ..creative_media.planner import build_plan, public_quote
from ..creative_media.public import job_payload
from ..creative_media.repository import MediaNotFoundError
from ..creative_media.storage import read_path
from ..creative_media.worker import AnimateWorker
from ..creative_modeling_repository import CreativeNotFoundError


FLAT_WARNING = (
    "Esta versão será animada como uma imagem única. "
    "Texto, logo, preço e detalhes do produto podem sofrer variações. "
    "Para maior fidelidade, mapeie a peça no Camadas."
)
PROTECTED_WARNING = (
    "Textos e logos entram como overlay depois do Seedance. "
    "O modelo anima a placa sem tipo. Sem garantia literal de fala."
)
TRANSITION_WARNING = (
    "Esta transição trava o primeiro e o último quadro. "
    "Música de referência não entra."
)
VOICEOVER_WARNING = (
    "A locução é gerada à parte (Gemini TTS) e mixada no master. "
    "O Seedance não fala o roteiro. Sem lip-sync."
)
STORYBOARD_WARNING = (
    "O storyboard manda 2 a 30 stills da marca como referências, sem first frame. "
    "Texto e logo podem variar."
)
EXTEND_WARNING = (
    "A extensão continua o clipe escolhido. Sem first frame. "
    "A cotação usa a tarifa de referência de vídeo."
)


def quote_animate(payload=None):
    data = payload if isinstance(payload, dict) else {}
    plan = build_plan({**data, "require_voiceover": False})
    mode = (plan.get("source") or {}).get("mode") or "flattened_still"
    snapshot = (plan.get("source") or {}).get("snapshot")
    unplaced = list((snapshot or {}).get("unplaced_layer_ids") or [])
    warning = PROTECTED_WARNING if mode == "protected_scene" and snapshot else FLAT_WARNING
    if mode == "protected_scene" and not snapshot:
        warning = "Mapeie a peça no Camadas antes de animar com cena protegida."
    if mode == "transition_ab":
        warning = TRANSITION_WARNING
        if (plan.get("source") or {}).get("snapshot_a") and not (plan.get("source") or {}).get("snapshot_b"):
            warning = (
                "A está mapeada; B entra achatada. "
                "O overlay do end card só existe se B também estiver no Camadas."
            )
    if mode == "storyboard":
        warning = STORYBOARD_WARNING
    if mode == "extend_video":
        warning = EXTEND_WARNING
    if plan.get("audio_mode") == "voiceover":
        warning = VOICEOVER_WARNING
        quote = plan.get("quote") or {}
        if quote.get("voiceover_fits") is False:
            warning = (
                "O roteiro passa do tempo da peça. "
                "Encurte o texto, use ritmo rápido ou aumente a duração."
            )
    return {
        **public_quote(plan),
        "plan": {
            "source": plan["source"],
            "duration": plan["duration"],
            "resolution": plan["resolution"],
            "aspect_ratio": plan["aspect_ratio"],
            "audio_mode": plan["audio_mode"],
            "model": plan["model"],
        },
        "eta": {"minimum_seconds": 120, "maximum_seconds": 360},
        "warning": warning,
        "needs_review": bool(unplaced),
        "unplaced_layer_ids": unplaced,
    }


class AnimateService:
    def __init__(self, store, repository, spawn_job=None, camadas=None):
        self.store = store
        self.repository = repository
        self.spawn_job = spawn_job or spawn
        self.camadas = camadas

    def quote(self, payload=None):
        return quote_animate(payload)

    def script(self, payload=None, user_id=None):
        from .video_script import build_video_script

        modeling = getattr(self.store, "modeling", None)
        text_callable = getattr(modeling, "text_callable", None)
        if text_callable is None and modeling is not None:
            generator = getattr(modeling, "generator", None)
            text_callable = getattr(generator, "text_callable", None)
        return build_video_script(self.store, payload, user_id=user_id, text_callable=text_callable)

    def submit(self, payload=None, user_id=None):
        data = payload if isinstance(payload, dict) else {}
        mode = str((data.get("source") or {}).get("mode") or data.get("source_mode") or "")
        if mode == "storyboard":
            return self._submit_storyboard(data, user_id=user_id)
        history = self.store.load(data, user_id=user_id)
        version = _find_version(
            history,
            data.get("base_id") or (data.get("source") or {}).get("base_id") or history.get("active_id"),
        )
        if not version:
            raise ValueError("Selecione uma versão com still para animar.")
        if mode == "transition_ab":
            return self._submit_transition(data, history, version, user_id=user_id)
        if mode == "extend_video":
            return self._submit_extend(data, history, version, user_id=user_id)
        snapshot = self._resolve_snapshot(data, version, user_id=user_id)
        if snapshot:
            data = {
                **data,
                "source": {
                    **(data.get("source") if isinstance(data.get("source"), dict) else {}),
                    "mode": "protected_scene",
                    "camadas_creative_id": snapshot.get("creative_id"),
                    "snapshot": snapshot,
                },
                "scene_snapshot": snapshot,
                "camadas_creative_id": snapshot.get("creative_id"),
            }
        plan = build_plan(data)
        if plan["source"]["mode"] == "protected_scene":
            snap = plan["source"].get("snapshot")
            if not snap:
                raise ValueError("A composição protegida exige um snapshot da cena. Mapeie a peça no Camadas.")
            validate_snapshot(snap)
        reference = self.store.materialize_reference(version.get("image_url") or version.get("image") or "")
        if not reference:
            raise ValueError("Não foi possível ler o still da versão.")
        plan["source"]["base_id"] = version.get("id") or ""
        plan["source"]["reference"] = reference
        plan["reference"] = reference
        job = self.repository.create_job({
            "user_id": user_id,
            "client_id": data.get("client_id") or history.get("client_id"),
            "run_id": history.get("run_id") or data.get("run_id") or "",
            "source_version_id": version.get("id") or "",
            "source_revision": history.get("revision"),
            "plan_json": plan,
            "plan_hash": plan.get("plan_hash"),
            "quote_json": plan.get("quote") or {},
            "model": plan.get("model"),
            "seed": plan.get("seed"),
        })
        self.spawn_job(self._run, job["public_id"])
        return job_payload(job)

    def _submit_transition(self, data, history, version_a, user_id=None):
        to_id = str(
            data.get("to_id")
            or (data.get("source") or {}).get("to_id")
            or (data.get("extra_ids") or [None])[0]
            or ""
        )
        version_b = _find_exact_version(history, to_id)
        if not version_b:
            raise ValueError("Selecione a versão B da transição.")
        if str(version_a.get("id") or "") == str(version_b.get("id") or ""):
            raise ValueError("A e B precisam ser versões diferentes.")
        if str(version_a.get("media") or "") == "video":
            raise ValueError("A versão A precisa ser um still, não um vídeo.")
        if str(version_b.get("media") or "") == "video":
            raise ValueError("A versão B precisa ser um still, não um vídeo.")
        piece_a = str(data.get("aspect_ratio") or history.get("aspect_ratio") or "16:9")
        piece_b = str(
            data.get("to_aspect_ratio")
            or version_b.get("aspect_ratio")
            or history.get("aspect_ratio")
            or piece_a
        )
        from ..creative_media.geometry import map_aspect

        if map_aspect(piece_a) != map_aspect(piece_b):
            raise ValueError("As duas peças precisam do mesmo formato.")
        snap_a = self._snapshot_for_version(data, version_a, key="a", user_id=user_id)
        snap_b = self._snapshot_for_version(data, version_b, key="b", user_id=user_id)
        packed = {
            **data,
            "source": {
                **(data.get("source") if isinstance(data.get("source"), dict) else {}),
                "mode": "transition_ab",
                "base_id": version_a.get("id") or "",
                "to_id": version_b.get("id") or "",
                "snapshot_a": snap_a,
                "snapshot_b": snap_b,
            },
            "to_id": version_b.get("id") or "",
            "to_aspect_ratio": piece_b,
            "aspect_ratio": piece_a,
            "snapshot_a": snap_a,
            "snapshot_b": snap_b,
        }
        plan = build_plan(packed)
        ref_a = self.store.materialize_reference(version_a.get("image_url") or version_a.get("image") or "")
        ref_b = self.store.materialize_reference(version_b.get("image_url") or version_b.get("image") or "")
        if not ref_a or not ref_b:
            raise ValueError("Não foi possível ler os stills A e B.")
        plan["source"]["base_id"] = version_a.get("id") or ""
        plan["source"]["to_id"] = version_b.get("id") or ""
        plan["source"]["reference"] = ref_a
        plan["source"]["reference_b"] = ref_b
        plan["reference"] = ref_a
        job = self.repository.create_job({
            "user_id": user_id,
            "client_id": data.get("client_id") or history.get("client_id"),
            "run_id": history.get("run_id") or data.get("run_id") or "",
            "source_version_id": version_a.get("id") or "",
            "source_revision": history.get("revision"),
            "plan_json": plan,
            "plan_hash": plan.get("plan_hash"),
            "quote_json": plan.get("quote") or {},
            "model": plan.get("model"),
            "seed": plan.get("seed"),
        })
        self.spawn_job(self._run, job["public_id"])
        return job_payload(job)

    def _submit_storyboard(self, data, user_id=None):
        from ..creative_media.settings import STORYBOARD_MAX, STORYBOARD_MIN

        ids = _unique_ids(
            data.get("scene_ids")
            or data.get("ref_ids")
            or (data.get("source") or {}).get("ref_ids")
            or data.get("extra_ids")
        )
        if not (STORYBOARD_MIN <= len(ids) <= STORYBOARD_MAX):
            raise ValueError(
                f"O storyboard precisa de {STORYBOARD_MIN} a {STORYBOARD_MAX} stills da marca."
            )
        stills = []
        first_run = None
        for ident in ids:
            item, run = self.store.find_still(data, ident, user_id=user_id)
            if not item:
                raise ValueError("Uma cena do storyboard não está na biblioteca da marca.")
            if str(item.get("media") or "") == "video":
                raise ValueError("O storyboard aceita só stills, não clipes.")
            reference = self.store.materialize_reference(item.get("image_url") or item.get("image") or "")
            if not reference:
                raise ValueError("Não foi possível ler um still do storyboard.")
            stills.append((ident, item, reference, run))
            if first_run is None:
                first_run = run
        version = stills[0][1]
        script = data.get("script") if isinstance(data.get("script"), dict) else None
        packed = {
            **data,
            "source": {
                **(data.get("source") if isinstance(data.get("source"), dict) else {}),
                "mode": "storyboard",
                "base_id": version.get("id") or ids[0],
                "ref_ids": [item[0] for item in stills],
            },
            "ref_ids": [item[0] for item in stills],
            "extra_ids": [item[0] for item in stills],
            "require_refs": True,
        }
        plan = build_plan(packed)
        plan["source"]["base_id"] = version.get("id") or ids[0]
        plan["source"]["ref_ids"] = [item[0] for item in stills]
        plan["source"]["references"] = [item[2] for item in stills]
        plan["source"]["reference"] = stills[0][2]
        plan["reference"] = stills[0][2]
        if script:
            plan["script"] = script
        history = {
            "run_id": (first_run or {}).get("run_id") or data.get("run_id") or "",
            "client_id": data.get("client_id") or (first_run or {}).get("client_id"),
            "revision": (first_run or {}).get("revision"),
        }
        job = self.repository.create_job({
            "user_id": user_id,
            "client_id": data.get("client_id") or history.get("client_id"),
            "run_id": history.get("run_id") or data.get("run_id") or "",
            "source_version_id": version.get("id") or "",
            "source_revision": history.get("revision"),
            "plan_json": plan,
            "plan_hash": plan.get("plan_hash"),
            "quote_json": plan.get("quote") or {},
            "model": plan.get("model"),
            "seed": plan.get("seed"),
        })
        self.spawn_job(self._run, job["public_id"])
        return job_payload(job)

    def _submit_extend(self, data, history, version, user_id=None):
        clip_id = str(
            data.get("extended_from")
            or (data.get("source") or {}).get("extended_from")
            or version.get("id")
            or ""
        )
        clip = _find_exact_version(history, clip_id) or version
        if str(clip.get("media") or "") != "video":
            raise ValueError("Selecione um clipe para estender.")
        reference = self._materialize_video(clip)
        if not reference:
            raise ValueError("Não foi possível ler o clipe de origem.")
        packed = {
            **data,
            "source": {
                **(data.get("source") if isinstance(data.get("source"), dict) else {}),
                "mode": "extend_video",
                "base_id": clip.get("id") or "",
                "extended_from": clip.get("id") or "",
            },
            "extended_from": clip.get("id") or "",
        }
        plan = build_plan(packed)
        plan["source"]["base_id"] = clip.get("id") or ""
        plan["source"]["extended_from"] = clip.get("id") or ""
        plan["source"]["reference"] = reference
        plan["reference"] = reference
        job = self.repository.create_job({
            "user_id": user_id,
            "client_id": data.get("client_id") or history.get("client_id"),
            "run_id": history.get("run_id") or data.get("run_id") or "",
            "source_version_id": clip.get("id") or "",
            "source_revision": history.get("revision"),
            "plan_json": plan,
            "plan_hash": plan.get("plan_hash"),
            "quote_json": plan.get("quote") or {},
            "model": plan.get("model"),
            "seed": plan.get("seed"),
        })
        self.spawn_job(self._run, job["public_id"])
        return job_payload(job)

    def _materialize_video(self, version):
        asset_id = str((version or {}).get("master_asset_id") or "")
        if asset_id:
            try:
                path, mime = self.asset_file(asset_id)
                raw = path.read_bytes()
                if raw:
                    return f"data:{mime or 'video/mp4'};base64,{base64.b64encode(raw).decode('ascii')}"
            except Exception:
                pass
        url = str((version or {}).get("video_url") or "")
        if url.startswith("data:video/") and "," in url:
            return url
        if url.startswith(("http://", "https://")):
            import requests

            response = requests.get(url, timeout=60)
            response.raise_for_status()
            return "data:video/mp4;base64," + base64.b64encode(response.content).decode("ascii")
        return ""

    def status(self, job_id):
        try:
            row = self.repository.get_job(job_id)
        except MediaNotFoundError as exc:
            raise CreativeNotFoundError(str(exc)) from exc
        return job_payload(row, scene_ahead=self._scene_ahead(row))

    def layers(self, payload=None, user_id=None):
        data = payload if isinstance(payload, dict) else {}
        history = self.store.load(data, user_id=user_id)
        version = _find_version(history, data.get("base_id") or history.get("active_id"))
        creative_id = str(
            data.get("camadas_creative_id")
            or (version or {}).get("camadas_creative_id")
            or ""
        )
        if not creative_id:
            return {
                "linked": False,
                "creative_id": "",
                "scene_version": 0,
                "layers": [],
                "unplaced_layer_ids": [],
            }
        live = self._camadas().get_creative(creative_id)
        snapshot = snapshot_scene(
            live,
            source_version_id=(version or {}).get("id") or "",
            overrides=data.get("layer_intents"),
        )
        return {
            "linked": True,
            "creative_id": creative_id,
            "scene_version": snapshot.get("scene_version"),
            "layers": snapshot.get("elements") or [],
            "unplaced_layer_ids": snapshot.get("unplaced_layer_ids") or [],
            "protected_layer_ids": snapshot.get("protected_layer_ids") or [],
            "animate_layer_ids": snapshot.get("animate_layer_ids") or [],
        }

    def map_camadas(self, payload=None, user_id=None):
        data = payload if isinstance(payload, dict) else {}
        history = self.store.load(data, user_id=user_id)
        version = _find_version(history, data.get("base_id") or history.get("active_id"))
        if not version:
            raise ValueError("Selecione uma versão com still para mapear.")
        reference = self.store.materialize_reference(version.get("image_url") or version.get("image") or "")
        raw = _still_bytes(reference)
        if not raw:
            raise ValueError("Não foi possível ler o still da versão.")
        created = self._camadas().find_or_create_from_still(
            _file_from_bytes(raw),
            {
                "brand_id": data.get("client_id") or history.get("client_id"),
                "client_id": data.get("client_id") or history.get("client_id"),
                "name": version.get("name") or "Trocar",
            },
            user_id=user_id,
        )
        creative_id = created.get("creative_id") or ""
        if creative_id and hasattr(self.store, "attach_camadas"):
            self.store.attach_camadas(
                {
                    "client_id": data.get("client_id") or history.get("client_id"),
                    "run_id": history.get("run_id") or data.get("run_id"),
                },
                version.get("id"),
                creative_id,
                user_id=user_id,
            )
        return {
            **created,
            "version_id": version.get("id"),
            "camadas_creative_id": creative_id,
        }

    def preview(self, payload=None, user_id=None):
        data = payload if isinstance(payload, dict) else {}
        snapshot, still = self._live_plate(data, user_id=user_id)
        plate = render_plate(still, snapshot)
        overlay = render_overlay(still, snapshot)
        composite = compose_still(plate, overlay)
        job = None
        finder = getattr(self.repository, "find_latest_job_by_creative", None)
        if callable(finder) and snapshot.get("creative_id"):
            job = finder(snapshot["creative_id"])
        return {
            "creative_id": snapshot.get("creative_id"),
            "scene_version": snapshot.get("scene_version"),
            "fingerprint": snapshot.get("fingerprint"),
            "plate": _data_url(plate, "image/jpeg"),
            "overlay": _data_url(overlay, "image/png"),
            "composite": _data_url(composite, "image/jpeg"),
            "job_id": (job or {}).get("public_id") or "",
            "scene_ahead": bool(job) and self._scene_ahead(job),
        }

    def recompose(self, job_id, payload=None, user_id=None):
        data = payload if isinstance(payload, dict) else {}
        try:
            row = self.repository.get_job(job_id)
        except MediaNotFoundError as exc:
            raise CreativeNotFoundError(str(exc)) from exc
        if row.get("status") not in {"ready", "failed"}:
            raise ValueError("Só é possível recompor um job já gerado.")
        plan = row.get("plan_json") if isinstance(row.get("plan_json"), dict) else {}
        source = plan.get("source") if isinstance(plan.get("source"), dict) else {}
        stored = source.get("snapshot_b") or source.get("snapshot")
        if not stored and source.get("mode") != "transition_ab":
            raise ValueError("Este job não tem cena protegida.")
        if source.get("mode") == "transition_ab":
            return self._recompose_transition(job_id, row, plan, data, user_id=user_id)
        live, still = self._live_plate(
            {
                **data,
                "camadas_creative_id": stored.get("creative_id"),
                "run_id": row.get("run_id") or data.get("run_id"),
                "client_id": row.get("client_id") or data.get("client_id"),
                "base_id": source.get("base_id") or row.get("source_version_id"),
                "layer_intents": data.get("layer_intents"),
            },
            user_id=user_id,
        )
        if snapshot_fingerprint(live) == snapshot_fingerprint(stored):
            raise ValueError("A cena não mudou. Nada para recompor.")
        version = self._worker().recompose(job_id, live, still)
        return job_payload(self.repository.get_job(job_id), scene_ahead=False) | {"version": version}

    def _recompose_transition(self, job_id, row, plan, data, user_id=None):
        source = plan.get("source") or {}
        history = self.store.load(
            {
                "run_id": row.get("run_id") or data.get("run_id"),
                "client_id": row.get("client_id") or data.get("client_id"),
            },
            user_id=user_id,
        )
        version_a = _find_version(history, source.get("base_id"))
        version_b = _find_exact_version(history, source.get("to_id"))
        snap_a = self._snapshot_for_version(data, version_a or {}, key="a", user_id=user_id)
        snap_b = self._snapshot_for_version(data, version_b or {}, key="b", user_id=user_id)
        old_a = snapshot_fingerprint(source.get("snapshot_a") or {})
        old_b = snapshot_fingerprint(source.get("snapshot_b") or {})
        if snapshot_fingerprint(snap_a or {}) == old_a and snapshot_fingerprint(snap_b or {}) == old_b:
            raise ValueError("A cena não mudou. Nada para recompor.")
        still_a = _still_bytes(
            self.store.materialize_reference((version_a or {}).get("image_url") or (version_a or {}).get("image") or "")
        ) if version_a else b""
        still_b = _still_bytes(
            self.store.materialize_reference((version_b or {}).get("image_url") or (version_b or {}).get("image") or "")
        ) if version_b else b""
        version = self._worker().recompose(
            job_id,
            snap_a or source.get("snapshot_a"),
            still_a,
            snapshot_b=snap_b or source.get("snapshot_b"),
            still_b=still_b,
        )
        return job_payload(self.repository.get_job(job_id), scene_ahead=False) | {"version": version}

    def retry(self, job_id, user_id=None):
        worker = self._worker()
        try:
            return job_payload(worker.retry_transcode(job_id))
        except MediaNotFoundError as exc:
            raise CreativeNotFoundError(str(exc)) from exc

    def cancel(self, job_id):
        try:
            row = self.repository.get_job(job_id)
        except MediaNotFoundError as exc:
            raise CreativeNotFoundError(str(exc)) from exc
        if row.get("status") in {"ready", "failed", "cancelled"}:
            return job_payload(row)
        updated = self.repository.update_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            message="Cancelamento solicitado",
            locked_at=None,
        )
        return job_payload(updated)

    def asset_file(self, asset_id):
        try:
            asset = self.repository.get_asset(asset_id)
        except MediaNotFoundError as exc:
            raise CreativeNotFoundError(str(exc)) from exc
        path = read_path(asset.get("storage_key"))
        if path is None:
            raise CreativeNotFoundError("Arquivo não encontrado.")
        return path, asset.get("mime_type") or "application/octet-stream"

    def _run(self, job_id):
        self._worker().run(job_id)

    def _worker(self):
        return AnimateWorker(
            self.repository,
            persist_fn=self._persist,
            materialize_fn=self._materialize,
        )

    def _materialize(self, plan):
        return (plan.get("source") or {}).get("reference") or plan.get("reference") or ""

    def _persist(self, job, plan, version):
        payload = {
            "run_id": job.get("run_id"),
            "client_id": job.get("client_id"),
            "base_id": (plan.get("source") or {}).get("base_id"),
        }
        extra = dict(version or {})
        extra.setdefault(
            "camadas_creative_id",
            (plan.get("source") or {}).get("camadas_creative_id")
            or ((plan.get("source") or {}).get("snapshot") or {}).get("creative_id")
            or "",
        )
        extra.setdefault("scene_version", ((plan.get("source") or {}).get("snapshot") or {}).get("scene_version"))
        extra.setdefault("transition_from", (plan.get("source") or {}).get("base_id") or "")
        extra.setdefault("transition_to", (plan.get("source") or {}).get("to_id") or "")
        extra.setdefault("voiceover_asset_id", extra.get("voiceover_asset_id") or "")
        extra.setdefault("voiceover_script", plan.get("voiceover_script") or "")
        extra.setdefault("storyboard_ids", (plan.get("source") or {}).get("ref_ids") or extra.get("storyboard_ids") or [])
        extra.setdefault("script", plan.get("script") if isinstance(plan.get("script"), dict) else extra.get("script"))
        extra.setdefault("extended_from", (plan.get("source") or {}).get("extended_from") or extra.get("extended_from") or "")
        extra.setdefault(
            "name",
            "Extensão" if (plan.get("source") or {}).get("mode") == "extend_video"
            else f"Clipe {int(plan.get('duration') or extra.get('duration') or 8)}s"
            if (plan.get("source") or {}).get("mode") == "storyboard"
            else extra.get("name") or "Animação",
        )
        stored = self.store.persist_animate(payload, extra, user_id=job.get("user_id"))
        return stored or extra

    def _camadas(self):
        if self.camadas is not None:
            return self.camadas
        from ..camadas.service import CamadasService

        return CamadasService()

    def _snapshot_for_version(self, data, version, *, key="a", user_id=None):
        provided = data.get(f"snapshot_{key}") or (data.get("source") or {}).get(f"snapshot_{key}")
        if isinstance(provided, dict) and provided:
            return provided if provided.get("fingerprint") else {**provided, "fingerprint": snapshot_fingerprint(provided)}
        creative_id = str(
            (data.get("source") or {}).get(f"camadas_creative_id_{key}")
            or version.get("camadas_creative_id")
            or ""
        )
        if not creative_id:
            return None
        live = self._camadas().get_creative(creative_id)
        return snapshot_scene(
            live,
            source_version_id=version.get("id") or "",
            overrides=(data.get("layer_intents_b") if key == "b" else data.get("layer_intents")),
        )

    def _resolve_snapshot(self, data, version, user_id=None):
        mode = str((data.get("source") or {}).get("mode") or data.get("source_mode") or "")
        provided = data.get("scene_snapshot") or (data.get("source") or {}).get("snapshot")
        if provided:
            snap = validate_snapshot(provided)
            if not snap.get("fingerprint"):
                snap = dict(snap)
                snap["fingerprint"] = snapshot_fingerprint(snap)
            return snap
        if mode != "protected_scene":
            return None
        creative_id = str(
            data.get("camadas_creative_id")
            or (data.get("source") or {}).get("camadas_creative_id")
            or version.get("camadas_creative_id")
            or ""
        )
        if not creative_id:
            raise ValueError("Mapeie a peça no Camadas antes de animar com cena protegida.")
        live = self._camadas().get_creative(creative_id)
        return snapshot_scene(
            live,
            source_version_id=version.get("id") or "",
            overrides=data.get("layer_intents"),
        )

    def _live_plate(self, data, user_id=None):
        creative_id = str(data.get("camadas_creative_id") or "")
        history = None
        version = None
        if data.get("run_id") or data.get("client_id") or data.get("base_id"):
            history = self.store.load(data, user_id=user_id)
            version = _find_version(history, data.get("base_id") or history.get("active_id"))
            creative_id = creative_id or str((version or {}).get("camadas_creative_id") or "")
        if not creative_id:
            raise ValueError("Informe o criativo do Camadas.")
        live = self._camadas().get_creative(creative_id)
        snapshot = snapshot_scene(
            live,
            source_version_id=(version or {}).get("id") or "",
            overrides=data.get("layer_intents"),
        )
        validate_snapshot(snapshot)
        still = b""
        if version:
            reference = self.store.materialize_reference(version.get("image_url") or version.get("image") or "")
            still = _still_bytes(reference)
        if not still:
            original = (live.get("creative") or {}).get("original_path") or ""
            if original:
                from ..camadas.storage import CamadasStorage

                path = CamadasStorage().absolute_path(original)
                if path is not None:
                    still = path.read_bytes()
        if not still:
            raise ValueError("Não foi possível ler o still da cena.")
        return snapshot, still

    def _scene_ahead(self, row):
        plan = row.get("plan_json") if isinstance(row.get("plan_json"), dict) else {}
        snaps = []
        source = plan.get("source") or {}
        if source.get("snapshot"):
            snaps.append(source.get("snapshot"))
        for key in ("snapshot_a", "snapshot_b"):
            if source.get(key):
                snaps.append(source.get(key))
        for snap in snaps:
            creative_id = (snap or {}).get("creative_id")
            if not creative_id:
                continue
            try:
                live = self._camadas().get_creative(creative_id)
            except Exception:
                continue
            if int(live.get("scene_version") or 0) > int((snap or {}).get("scene_version") or 0):
                return True
        return False


def _unique_ids(raw):
    ids = []
    for item in list(raw or []):
        text = str(item or "").strip()
        if text and text not in ids:
            ids.append(text)
    return ids


def _find_exact_version(history, version_id):
    wanted = str(version_id or "")
    if not wanted:
        return None
    for item in (history.get("versions") or []):
        if isinstance(item, dict) and str(item.get("id") or "") == wanted:
            return item
    return None


def _find_version(history, version_id):
    wanted = str(version_id or "")
    versions = [item for item in (history.get("versions") or []) if isinstance(item, dict)]
    for item in versions:
        if str(item.get("id") or "") == wanted:
            return item
    if versions:
        active = str(history.get("active_id") or history.get("base_id") or "")
        for item in versions:
            if str(item.get("id") or "") == active:
                return item
        return versions[-1]
    return None


def _still_bytes(reference):
    text = str(reference or "")
    if text.startswith("data:image/") and "," in text:
        return base64.b64decode(text.split(",", 1)[1])
    if text.startswith(("http://", "https://")):
        import requests

        response = requests.get(text, timeout=30)
        response.raise_for_status()
        return response.content
    return b""


def _file_from_bytes(raw, name="still.png"):
    return FileStorage(stream=BytesIO(raw), filename=name, content_type="image/png")


def _data_url(payload, mime):
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"
