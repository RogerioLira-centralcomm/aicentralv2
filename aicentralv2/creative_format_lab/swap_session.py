"""Sessão do Trocr: histórico com CAS, original travada e still autenticado."""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from ..creative_modeling_repository import CreativeConflictError, CreativeNotFoundError
from ..creative_modeling_service import _integer, _serialize
from ..creative_modeling_storage import (
    GENERATED_PREFIX,
    TROCR_STILL_NAME,
    TROCR_STILL_PREFIX,
    still_filename_candidates,
)

logger = logging.getLogger(__name__)

RUN_SCHEMA = "runs-v1"
RUNS_LIMIT = 24
TIM_LINE = re.compile(
    r"\b(?:tim black|tim controle|tim ultra|tim pr[eé]|tim fam[ií]lia)\b",
    re.IGNORECASE,
)

MEDIA_ASSET_PREFIX = "/parametros/api/media/assets/"

STILL_PREFIXES = (
    "/static/uploads/creative_generated/",
    "/static/uploads/creative_trocr/",
    TROCR_STILL_PREFIX,
    MEDIA_ASSET_PREFIX,
)


class TrocrStore:
    def __init__(self, modeling, repository, client_lookup=None):
        self.modeling = modeling
        self.repository = repository
        self.client_lookup = client_lookup

    def load(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        key = self.session_key(payload, user_id)
        store = wrap_store(self.read(key, client_id), client_id)
        store, changed = self.scrub_store(store, client_id)
        if changed:
            packed = store_with_mirror(store)
            self.write(key, packed, client_id)
            if client_id and user_id not in (None, ""):
                self.write(f"user-{user_id}", packed, None)
        run = pick_run(store, payload.get("run_id"))
        return _serialize(self.public_history(run, store, client_id, media=payload.get("media")))

    def library(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        key = self.session_key(payload, user_id)
        store = wrap_store(self.read(key, client_id), client_id)
        store, changed = self.scrub_store(store, client_id)
        if changed:
            packed = store_with_mirror(store)
            self.write(key, packed, client_id)
            if client_id and user_id not in (None, ""):
                self.write(f"user-{user_id}", packed, None)
        want_video = str(payload.get("media") or "still").strip().lower() == "video"
        drop_tim = self.should_drop_tim(client_id)
        items = []
        seen = set()
        for run in store.get("runs") or []:
            if not isinstance(run, dict):
                continue
            if not run_matches_client(run, client_id):
                continue
            run_id = str(run.get("run_id") or "")
            aspect = str(run.get("aspect_ratio") or "16:9")
            for item in run.get("versions") or []:
                if not isinstance(item, dict):
                    continue
                if not self.keep_library_item(item, run, client_id, drop_tim=drop_tim):
                    continue
                video = is_video_version(item)
                if want_video != video:
                    continue
                url = published_still_url(item.get("image_url") or item.get("thumb_url") or "")
                video_url = str(item.get("video_url") or "")
                ident = video_url or url or f"{run_id}:{item.get('id')}"
                if not ident or ident in seen:
                    continue
                seen.add(ident)
                version_id = str(item.get("id") or "")
                params = slim_context(item.get("params")) if isinstance(item.get("params"), dict) else None
                ocr = slim_context(item.get("ocr"))
                headline = ""
                if isinstance(params, dict):
                    headline = str(params.get("headline") or "").strip()
                if not headline and isinstance(ocr, dict):
                    headline = str(ocr.get("headline") or "").strip()
                items.append({
                    "id": f"{run_id}:{version_id}" if run_id and version_id else version_id,
                    "version_id": version_id,
                    "run_id": run_id,
                    "name": str(item.get("name") or version_id or "Peça"),
                    "origin": str(item.get("origin") or ""),
                    "image_url": url,
                    "thumb_url": published_still_url(item.get("thumb_url") or url),
                    "image": url,
                    "thumb": published_still_url(item.get("thumb_url") or url),
                    "ocr": ocr,
                    "params": params,
                    "headline": headline,
                    "scene_index": scene_index_value(item, params),
                    "scene_group": str(item.get("scene_group") or (params or {}).get("scene_group") or ""),
                    "aspect_ratio": aspect,
                    "created_at": str(item.get("created_at") or run.get("updated_at") or ""),
                    "broken": (not video) and not self.still_alive(url),
                    **({
                        "media": "video",
                        "video_url": video_url,
                        "poster_url": published_still_url(item.get("poster_url") or url),
                        "job_id": str(item.get("job_id") or ""),
                        "duration": item.get("duration"),
                        "storyboard_ids": item.get("storyboard_ids") or [],
                    } if video else {}),
                })
        items.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return _serialize({
            "client_id": client_id or "",
            "media": "video" if want_video else "still",
            "items": items,
        })

    def add_library_still(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        image_url = self.storeable_image(payload.get("image") or payload.get("reference") or payload.get("image_url"))
        if not image_url:
            raise ValueError("Solte uma imagem para a biblioteca.")
        client_id = optional_client(payload)
        key = self.session_key(payload, user_id)
        store = wrap_store(self.read(key, client_id), client_id)
        if payload.get("new_run") or payload.get("new_piece"):
            run = empty_run(client_id, payload.get("aspect_ratio"))
            versions = []
        else:
            run = pick_run(store, payload.get("run_id"))
            versions = list(run.get("versions") or [])
        next_id = f"v{len(versions) + 1}"
        piece_name = str(payload.get("name") or "Peça").strip() or "Peça"
        run_id = str(run.get("run_id") or "")
        group = f"{run_id}:{next_id}" if run_id else next_id
        versions.append({
            "id": next_id,
            "attempt": len(versions) + 1,
            "name": piece_name,
            "origin": "library",
            "quality": "",
            "status": "ready",
            "created_at": utc_now(),
            "image_url": image_url,
            "thumb_url": image_url,
            "scene_index": 1,
            "scene_group": group,
            "params": {"scene_index": 1, "scene_group": group},
        })
        run = write_run(run, {
            "active_id": next_id,
            "base_id": run.get("base_id") or next_id,
            "aspect_ratio": payload.get("aspect_ratio") or run.get("aspect_ratio") or "16:9",
            "title": run.get("title") or "",
        }, versions, client_id, history_revision(run) + 1)
        packed = store_with_mirror(put_run(store, run, active=True))
        self.write(key, packed, client_id)
        if client_id and user_id not in (None, ""):
            self.write(f"user-{user_id}", packed, None)
        return _serialize({
            "id": f"{run.get('run_id')}:{next_id}",
            "version_id": next_id,
            "run_id": run.get("run_id") or "",
            "name": piece_name,
            "origin": "library",
            "image_url": image_url,
            "thumb_url": image_url,
            "image": image_url,
            "thumb": image_url,
            "ocr": None,
            "params": {"scene_index": 1, "scene_group": group},
            "scene_index": 1,
            "scene_group": group,
            "aspect_ratio": run.get("aspect_ratio") or "16:9",
            "created_at": run.get("updated_at") or "",
        })

    def remove_library_items(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        key = self.session_key(payload, user_id)
        store = wrap_store(self.read(key, client_id), client_id)
        wanted = set()
        raw_ids = list(payload.get("ids") or [])
        if payload.get("id"):
            raw_ids.insert(0, payload.get("id"))
        for raw in raw_ids:
            run_id, version_id = parse_scene_ref(raw)
            ident = str(raw or "").strip()
            if version_id:
                wanted.add((run_id, version_id))
                wanted.add(("", version_id))
            elif ident:
                wanted.add(("", ident))
        drop_broken = bool(payload.get("broken") or payload.get("drop_broken"))
        media = str(payload.get("media") or "").strip().lower()
        if not wanted and not drop_broken:
            raise ValueError("Escolha uma peça para apagar.")
        changed = False
        removed = 0
        runs = []
        for run in store.get("runs") or []:
            if not isinstance(run, dict) or not run.get("run_id"):
                continue
            run_id = str(run.get("run_id") or "")
            versions = []
            for item in run.get("versions") or []:
                if not isinstance(item, dict):
                    continue
                version_id = str(item.get("id") or "")
                video = is_video_version(item)
                if media == "video" and not video:
                    versions.append(item)
                    continue
                if media in {"still", "image"} and video:
                    versions.append(item)
                    continue
                hit = (run_id, version_id) in wanted or ("", version_id) in wanted
                url = item.get("image_url") or item.get("thumb_url") or item.get("image") or ""
                dead = (not video) and not self.still_alive(url)
                if hit or (drop_broken and dead):
                    changed = True
                    removed += 1
                    continue
                versions.append(item)
            if versions:
                if len(versions) != len([item for item in (run.get("versions") or []) if isinstance(item, dict)]):
                    run = dict(run)
                    run["versions"] = versions
                    changed = True
                runs.append(run)
            elif run.get("versions"):
                changed = True
        if not changed:
            raise ValueError("Essa peça já não está na biblioteca.")
        next_store = {
            "schema": RUN_SCHEMA,
            "active_run_id": store.get("active_run_id") or "",
            "runs": runs,
        }
        ids = {str(item.get("run_id") or "") for item in runs}
        if next_store["active_run_id"] not in ids:
            next_store["active_run_id"] = runs[0]["run_id"] if runs else ""
        if not next_store["runs"]:
            run = empty_run(client_id)
            next_store["runs"] = [run]
            next_store["active_run_id"] = run["run_id"]
        packed = store_with_mirror(next_store)
        self.write(key, packed, client_id)
        if client_id and user_id not in (None, ""):
            self.write(f"user-{user_id}", packed, None)
        listed = self.library({**payload, "media": media or "still"}, user_id=user_id)
        return _serialize({
            "removed": removed,
            "client_id": listed.get("client_id") or client_id or "",
            "media": listed.get("media") or (media or "still"),
            "items": listed.get("items") or [],
        })

    def find_still(self, payload, scene_id, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        store = wrap_store(self.read(self.session_key(payload, user_id), client_id), client_id)
        run_id, version_id = parse_scene_ref(scene_id)
        if not version_id:
            return None, None
        for run in store.get("runs") or []:
            if not isinstance(run, dict):
                continue
            if run_id and str(run.get("run_id") or "") != run_id:
                continue
            for item in run.get("versions") or []:
                if not isinstance(item, dict):
                    continue
                if is_video_version(item):
                    continue
                if str(item.get("id") or "") == version_id:
                    return item, run
        return None, None

    def save_still_ocr(self, payload, scene_id, ocr, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        key = self.session_key(payload, user_id)
        store = wrap_store(self.read(key, client_id), client_id)
        run_id, version_id = parse_scene_ref(scene_id)
        if not version_id:
            return False
        slim = slim_context(ocr)
        changed = False
        for run in store.get("runs") or []:
            if not isinstance(run, dict):
                continue
            if run_id and str(run.get("run_id") or "") != run_id:
                continue
            versions = []
            run_changed = False
            for item in run.get("versions") or []:
                if not isinstance(item, dict):
                    versions.append(item)
                    continue
                if is_video_version(item) or str(item.get("id") or "") != version_id:
                    versions.append(item)
                    continue
                packed = dict(item)
                packed["ocr"] = slim
                versions.append(packed)
                run_changed = True
                changed = True
            if run_changed:
                run["versions"] = versions
        if not changed:
            return False
        packed = store_with_mirror(store)
        self.write(key, packed, client_id)
        if client_id and user_id not in (None, ""):
            self.write(f"user-{user_id}", packed, None)
        return True

    def save(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        key = self.session_key(payload, user_id)
        store = wrap_store(self.read(key, client_id), client_id)
        incoming = payload.get("versions") or []
        start_new = bool(payload.get("new_run") or payload.get("reset"))
        if start_new:
            run = empty_run(client_id, payload.get("aspect_ratio"))
            versions = self.merge_versions([], incoming)
            run = write_run(run, payload, versions, client_id, history_revision(run) + 1)
            store = put_run(store, run, active=True)
        else:
            run = pick_run(store, payload.get("run_id"))
            current = history_revision(run)
            sent = payload.get("revision")
            if sent not in (None, ""):
                try:
                    expected = int(sent)
                except (TypeError, ValueError):
                    expected = -1
                if expected != current:
                    raise CreativeConflictError("O histórico mudou. Recarregue e tente de novo.")
            versions = self.merge_versions(run.get("versions") or [], incoming)
            run = write_run(run, payload, versions, client_id, current + 1)
            store = put_run(store, run, active=True)
        packed = store_with_mirror(store)
        self.write(key, packed, client_id)
        if client_id and user_id not in (None, ""):
            self.write(f"user-{user_id}", packed, None)
        return _serialize(self.public_history(run, packed, client_id))

    def persist_generated(self, payload, result, user_id=None):
        image_url = result.get("image_url") or ""
        if not accepted_still(image_url):
            return
        existing = self.load(payload, user_id=user_id)
        versions = list(existing.get("versions") or [])
        if any(item.get("image_url") == image_url for item in versions if isinstance(item, dict)):
            return
        quality = str(result.get("quality") or payload.get("quality") or "production")
        mode = str(result.get("mode") or "")
        try:
            variant = int((payload or {}).get("scene_variant") or 0)
        except (TypeError, ValueError):
            variant = 0
        parent_id = str(payload.get("base_id") or existing.get("base_id") or "")
        parent = next((item for item in versions if str(item.get("id") or "") == parent_id), None)
        if parent is None and versions:
            parent = next((item for item in versions if item.get("origin") == "original"), versions[0])
        if variant in {2, 3}:
            origin = "scene"
            name = f"Cena {variant}"
        elif mode in {"typeset", "recrop"}:
            origin = mode
            name = "Tipo na foto" if mode == "typeset" else "Recorte + tipo"
        elif quality == "draft":
            origin = "draft"
            name = "Rascunho"
        else:
            origin = "production"
            name = "Produção"
        next_id = f"v{len(versions) + 1}"
        if parent_id == next_id:
            parent_id = ""
        params = generated_params(payload, existing, parent, variant)
        ocr = generated_ocr(payload, parent, params)
        versions.append({
            "id": next_id,
            "attempt": len(versions) + 1,
            "name": name,
            "origin": origin,
            "parent_id": parent_id,
            "quality": quality,
            "status": "ready",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "image_url": image_url,
            "thumb_url": image_url,
            "ocr": ocr,
            "params": params,
            "scene_index": params.get("scene_index") or (variant if variant in {2, 3} else 1),
            "scene_group": params.get("scene_group") or "",
            "qa": result.get("qa") if isinstance(result.get("qa"), dict) else None,
            "plan_hash": result.get("plan_hash") or payload.get("plan_hash") or "",
        })
        self.save(
            {
                **payload,
                "run_id": existing.get("run_id") or payload.get("run_id"),
                "versions": versions,
                "active_id": next_id,
                "base_id": existing.get("base_id") or (versions[0]["id"] if versions else next_id),
                "aspect_ratio": result.get("aspect_ratio") or payload.get("aspect_ratio") or "16:9",
                "revision": existing.get("revision"),
            },
            user_id=user_id,
        )

    def persist_animate(self, payload, version, user_id=None):
        """Append de vídeo. Sem CAS — um job de minutos não pode morrer por edição paralela."""
        payload = payload if isinstance(payload, dict) else {}
        existing = self.load(payload, user_id=user_id)
        versions = list(existing.get("versions") or [])
        next_id = f"v{len(versions) + 1}"
        parent_id = str(payload.get("base_id") or existing.get("base_id") or "")
        parent = next((item for item in versions if str(item.get("id") or "") == parent_id), None)
        parent_still = str((parent or {}).get("image_url") or "")
        stale = existing.get("revision") not in (None, payload.get("source_revision"), version.get("source_revision"))
        if payload.get("source_revision") not in (None, "", existing.get("revision")):
            stale = True
        row = {
            "id": next_id,
            "attempt": len(versions) + 1,
            "name": version.get("name") or clip_name(version.get("duration")),
            "origin": "animate",
            "parent_id": parent_id if parent_id != next_id else "",
            "quality": version.get("quality") or "",
            "status": "ready",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "media": "video",
            "image_url": version.get("poster_url") or version.get("image_url") or parent_still,
            "thumb_url": version.get("poster_url") or version.get("image_url") or parent_still,
            "video_url": version.get("video_url") or "",
            "master_asset_id": version.get("master_asset_id") or "",
            "poster_asset_id": version.get("poster_asset_id") or "",
            "duration": version.get("duration"),
            "has_audio": bool(version.get("has_audio")),
            "packs": version.get("packs") or [],
            "job_id": version.get("job_id") or "",
            "source_version_id": version.get("source_version_id") or parent_id,
            "camadas_creative_id": version.get("camadas_creative_id") or "",
            "seedance_base_asset_id": version.get("seedance_base_asset_id") or "",
            "scene_version": version.get("scene_version"),
            "protected_layers": bool(version.get("protected_layers")),
            "transition_from": version.get("transition_from") or "",
            "transition_to": version.get("transition_to") or "",
            "end_card_asset_id": version.get("end_card_asset_id") or "",
            "voiceover_asset_id": version.get("voiceover_asset_id") or "",
            "voiceover_script": version.get("voiceover_script") or "",
            "storyboard_ids": version.get("storyboard_ids") or [],
            "script": version.get("script") if isinstance(version.get("script"), dict) else None,
            "extended_from": version.get("extended_from") or "",
            "based_on_stale_revision": stale,
        }
        versions.append(row)
        saved = self.save(
            {
                **payload,
                "run_id": existing.get("run_id") or payload.get("run_id"),
                "versions": versions,
                "active_id": next_id,
                "base_id": existing.get("base_id") or (versions[0]["id"] if versions else next_id),
                "aspect_ratio": existing.get("aspect_ratio") or payload.get("aspect_ratio") or "16:9",
            },
            user_id=user_id,
        )
        created = next((item for item in saved.get("versions") or [] if item.get("id") == next_id), row)
        return created

    def attach_camadas(self, payload, version_id, creative_id, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        existing = self.load(payload, user_id=user_id)
        versions = []
        for item in existing.get("versions") or []:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if str(row.get("id") or "") == str(version_id or ""):
                row["camadas_creative_id"] = str(creative_id or "")
            versions.append(row)
        return self.save(
            {
                "client_id": payload.get("client_id") or existing.get("client_id"),
                "run_id": existing.get("run_id") or payload.get("run_id"),
                "versions": versions,
                "active_id": existing.get("active_id"),
                "base_id": existing.get("base_id"),
                "aspect_ratio": existing.get("aspect_ratio"),
            },
            user_id=user_id,
        )

    def materialize_reference(self, raw):
        """Still autenticado vira data URL. OpenRouter e o OCR não leem caminho relativo."""
        text = str(raw or "").strip()
        if not text:
            return ""
        if text.startswith("data:image/"):
            return text
        if text.startswith(("https://", "http://")):
            local = local_still_path(text)
            if not local:
                return text
            text = local
        url = published_still_url(text)
        if not url.startswith(STILL_PREFIXES):
            return text
        try:
            path = self.still_path(Path(url).name)
        except CreativeNotFoundError:
            return text
        data = Path(path).read_bytes()
        if not data:
            return text
        mime = mimetypes.guess_type(Path(path).name)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    def still_path(self, filename):
        storage = getattr(self.modeling, "storage", None)
        loader = getattr(storage, "load_trocr_still", None)
        legacy = getattr(storage, "load_generated_still", None)
        names = still_filename_candidates(filename) or [Path(str(filename or "")).name]
        for name in names:
            if not name:
                continue
            path = loader(name) if callable(loader) else None
            if path is not None:
                return path
            path = legacy(name) if callable(legacy) else None
            if path is not None:
                return path
        raise CreativeNotFoundError("Still do Trocr não encontrado.")

    def persist_still(self, raw):
        text = str(raw or "").strip()
        if not text:
            return ""
        if text.startswith(("https://", "http://")):
            text = local_still_path(text)
            if not text:
                return ""
        if accepted_still(text):
            return text
        if text.startswith("/static/"):
            return ""
        if not text.startswith("data:image/"):
            return ""
        encoded = text.split(",", 1)[-1]
        storage = getattr(self.modeling, "storage", None)
        private = getattr(storage, "save_trocr_still", None)
        public = getattr(storage, "save_generated_base64", None)
        saver = private if callable(private) else public
        if not callable(saver) or not encoded:
            return ""
        output_format = still_data_format(text)
        try:
            return saver(encoded, output_format) or ""
        except TypeError:
            try:
                return saver(encoded) or ""
            except Exception:
                logger.exception("Não gravou still do Trocr")
                return ""
        except Exception:
            logger.exception("Não gravou still do Trocr")
            return ""

    def merge_versions(self, existing, incoming):
        have = {
            str(item.get("id") or ""): item
            for item in existing
            if isinstance(item, dict) and item.get("id")
        }
        originals = [
            item for item in existing
            if isinstance(item, dict) and item.get("origin") == "original" and item.get("id")
        ]
        merged = []
        seen = set()
        for item in incoming:
            stored = self.store_version(item)
            if not stored:
                continue
            prev = have.get(stored["id"])
            if prev and prev.get("origin") == "original":
                stored["origin"] = "original"
                stored["image_url"] = prev.get("image_url") or stored["image_url"]
                stored["thumb_url"] = prev.get("thumb_url") or stored["image_url"]
            if prev and prev.get("camadas_creative_id") and not stored.get("camadas_creative_id"):
                stored["camadas_creative_id"] = prev.get("camadas_creative_id")
            if prev:
                for key in ("params", "scene_group", "scene_index", "ocr"):
                    if prev.get(key) and not stored.get(key):
                        stored[key] = prev[key]
            if prev and is_video_version(prev):
                stored = keep_video_fields(stored, prev)
            if not stored["id"]:
                stored["id"] = f"v{len(merged) + 1}"
            if not stored["attempt"]:
                stored["attempt"] = len(merged) + 1
            merged.append(stored)
            seen.add(stored["id"])
        for orig in originals:
            ident = orig.get("id")
            if ident and ident not in seen:
                merged.insert(0, orig)
                seen.add(ident)
        for prev in existing:
            if not isinstance(prev, dict) or not prev.get("id"):
                continue
            if prev["id"] in seen:
                continue
            if is_video_version(prev):
                merged.append(prev)
                seen.add(prev["id"])
        return merged

    def store_version(self, item):
        if not isinstance(item, dict):
            return None
        is_video = str(item.get("media") or "") == "video" or item.get("origin") == "animate"
        image_url = self.storeable_image(
            item.get("image_url") or item.get("image") or item.get("poster_url")
        )
        video_url = str(item.get("video_url") or "")
        if not image_url and not (is_video and video_url):
            return None
        thumb_url = self.storeable_image(item.get("thumb_url") or item.get("thumb") or item.get("poster_url")) or image_url
        created = item.get("created_at") or item.get("createdAt") or datetime.now(timezone.utc).isoformat()
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        packed = {
            "id": str(item.get("id") or ""),
            "attempt": item.get("attempt") or 0,
            "name": str(item.get("name") or item.get("id") or "versão"),
            "origin": str(item.get("origin") or "edited"),
            "quality": str(item.get("quality") or ""),
            "status": str(item.get("status") or "ready"),
            "created_at": str(created),
            "image_url": image_url,
            "thumb_url": thumb_url,
            "ocr": slim_context(item.get("ocr")),
            "analysis": slim_context(item.get("analysis")),
            "qa": slim_context(item.get("qa")) if isinstance(item.get("qa"), dict) else None,
            "plan_hash": str(item.get("plan_hash") or ""),
            "parent_id": str(item.get("parent_id") or item.get("parentId") or ""),
        }
        packed = attach_scene_fields(packed, item)
        if item.get("camadas_creative_id"):
            packed["camadas_creative_id"] = str(item.get("camadas_creative_id"))
        if is_video:
            packed.update({
                "media": "video",
                "video_url": video_url,
                "poster_url": str(item.get("poster_url") or image_url or ""),
                "master_asset_id": str(item.get("master_asset_id") or ""),
                "poster_asset_id": str(item.get("poster_asset_id") or ""),
                "seedance_base_asset_id": str(item.get("seedance_base_asset_id") or ""),
                "duration": item.get("duration"),
                "has_audio": bool(item.get("has_audio")),
                "packs": item.get("packs") if isinstance(item.get("packs"), list) else [],
                "job_id": str(item.get("job_id") or ""),
                "source_version_id": str(item.get("source_version_id") or ""),
                "scene_version": item.get("scene_version"),
                "protected_layers": bool(item.get("protected_layers")),
                "transition_from": str(item.get("transition_from") or ""),
                "transition_to": str(item.get("transition_to") or ""),
                "end_card_asset_id": str(item.get("end_card_asset_id") or ""),
                "voiceover_asset_id": str(item.get("voiceover_asset_id") or ""),
                "voiceover_script": str(item.get("voiceover_script") or ""),
                "storyboard_ids": item.get("storyboard_ids") if isinstance(item.get("storyboard_ids"), list) else [],
                "script": item.get("script") if isinstance(item.get("script"), dict) else None,
                "extended_from": str(item.get("extended_from") or ""),
                "based_on_stale_revision": bool(item.get("based_on_stale_revision")),
            })
            if item.get("camadas_creative_id"):
                packed["camadas_creative_id"] = str(item.get("camadas_creative_id"))
        return packed

    def storeable_image(self, raw):
        url = self.persist_still(raw)
        return url if accepted_still(url) else ""

    def keep_library_item(self, item, run=None, client_id=None, drop_tim=False, require_file=False):
        if not isinstance(item, dict):
            return False
        if not run_matches_client(run, client_id):
            return False
        if drop_tim and item_looks_tim(item, run):
            return False
        if is_video_version(item):
            return bool(str(item.get("video_url") or "").strip())
        url = item.get("image_url") or item.get("thumb_url") or item.get("image") or ""
        if require_file:
            return self.still_alive(url)
        return True

    def scrub_store(self, store, client_id=None):
        pack = store if isinstance(store, dict) else {}
        drop_tim = self.should_drop_tim(client_id)
        changed = False
        runs = []
        for run in pack.get("runs") or []:
            if not isinstance(run, dict) or not run.get("run_id"):
                continue
            if not run_matches_client(run, client_id):
                changed = True
                continue
            versions = []
            for item in run.get("versions") or []:
                if not isinstance(item, dict):
                    continue
                if not self.keep_library_item(item, run, client_id, drop_tim=drop_tim):
                    changed = True
                    continue
                versions.append(item)
            if not versions and (run.get("versions") or []):
                changed = True
                continue
            if len(versions) != len([item for item in (run.get("versions") or []) if isinstance(item, dict)]):
                run = dict(run)
                run["versions"] = versions
                changed = True
            runs.append(run)
        if not changed:
            return pack, False
        next_store = {
            "schema": RUN_SCHEMA,
            "active_run_id": pack.get("active_run_id") or "",
            "runs": runs,
        }
        ids = {str(item.get("run_id") or "") for item in runs}
        if next_store["active_run_id"] not in ids:
            next_store["active_run_id"] = runs[0]["run_id"] if runs else ""
        if not next_store["runs"]:
            run = empty_run(client_id)
            next_store["runs"] = [run]
            next_store["active_run_id"] = run["run_id"]
        return next_store, True

    def still_alive(self, raw):
        text = published_still_url(raw)
        if not text:
            return False
        if text.startswith("data:image/"):
            return True
        local = local_still_path(text) or (text if accepted_still(text) else "")
        if not local:
            return True
        storage = getattr(self.modeling, "storage", None)
        can_check = callable(getattr(storage, "load_trocr_still", None)) or callable(
            getattr(storage, "load_generated_still", None)
        )
        if not can_check:
            return True
        try:
            self.still_path(Path(local).name)
        except CreativeNotFoundError:
            return False
        except Exception:
            return True
        return True

    def should_drop_tim(self, client_id):
        if not client_id or not callable(self.client_lookup):
            return False
        try:
            client = self.client_lookup(client_id)
        except Exception:
            return False
        if not isinstance(client, dict):
            return False
        return not client_named_tim(client)

    def public_history(self, session, store=None, client_id=None, media=None):
        data = session if isinstance(session, dict) else {}
        drop_tim = self.should_drop_tim(client_id)
        versions = []
        for item in data.get("versions") or []:
            if not isinstance(item, dict):
                continue
            if not match_media(item, media):
                continue
            if drop_tim and item_looks_tim(item, data):
                continue
            if not is_video_version(item) and not self.still_alive(item.get("image_url") or item.get("image") or ""):
                continue
            url = published_still_url(item.get("image_url") or "")
            thumb = published_still_url(item.get("thumb_url") or url)
            poster = published_still_url(item.get("poster_url") or "") or url
            versions.append({
                **item,
                "image_url": url,
                "thumb_url": thumb,
                "image": url,
                "thumb": thumb,
                **({"poster_url": poster} if is_video_version(item) else {}),
            })
        pack = store if isinstance(store, dict) else wrap_store(data, client_id)
        active_id = str(data.get("run_id") or pack.get("active_run_id") or "")
        runs = []
        for item in pack.get("runs") or []:
            if not isinstance(item, dict):
                continue
            if not run_matches_client(item, client_id):
                continue
            if drop_tim and run_looks_tim(item):
                continue
            summary = run_summary(item, active_id, media=media)
            if media and not summary.get("version_count"):
                continue
            runs.append(summary)
        return {
            "client_id": data.get("client_id") or client_id or "",
            "run_id": data.get("run_id") or "",
            "title": data.get("title") or run_title(data),
            "created_at": data.get("created_at") or "",
            "active_id": data.get("active_id") or "",
            "base_id": data.get("base_id") or "",
            "aspect_ratio": data.get("aspect_ratio") or "16:9",
            "revision": history_revision(data),
            "updated_at": data.get("updated_at") or "",
            "versions": versions,
            "runs": runs,
        }

    def session_key(self, payload, user_id=None):
        client_id = optional_client(payload)
        if client_id:
            return f"client-{client_id}"
        uid = user_id if user_id not in (None, "") else "anon"
        return f"user-{uid}"

    def read(self, key, client_id=None):
        store = getattr(self.repository, "trocr_sessions", None)
        if isinstance(store, dict) and isinstance(store.get(key), dict):
            return dict(store[key])
        if client_id and callable(self.client_lookup):
            try:
                client = self.client_lookup(client_id)
                profile = client.get("brand_profile") if isinstance(client, dict) else {}
                if isinstance(profile, dict) and isinstance(profile.get("trocr"), dict):
                    return dict(profile["trocr"])
            except Exception:
                pass
        loader = getattr(getattr(self.modeling, "storage", None), "load_trocr_session", None)
        if callable(loader):
            try:
                data = loader(key)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def write(self, key, session, client_id=None):
        store = getattr(self.repository, "trocr_sessions", None)
        if not isinstance(store, dict):
            try:
                self.repository.trocr_sessions = {}
                store = self.repository.trocr_sessions
            except Exception:
                store = None
        if isinstance(store, dict):
            store[key] = session
        if client_id and callable(self.client_lookup):
            try:
                client = self.client_lookup(client_id)
                profile = dict((client or {}).get("brand_profile") or {})
                profile["trocr"] = session
                updater = getattr(self.repository, "update_client_brand_profile", None)
                if callable(updater):
                    updater(client_id, profile)
            except Exception:
                logger.exception("Não gravou histórico Trocr na marca")
        saver = getattr(getattr(self.modeling, "storage", None), "save_trocr_session", None)
        if callable(saver):
            try:
                saver(key, session)
            except Exception:
                logger.exception("Não gravou histórico Trocr em arquivo")


def optional_client(payload):
    raw = (payload or {}).get("client_id")
    if raw in (None, ""):
        return None
    try:
        return _integer(raw, "Cliente")
    except Exception:
        return None


def run_matches_client(run, client_id):
    if not client_id:
        return True
    owned = optional_client(run if isinstance(run, dict) else {})
    return owned in (None, client_id)


def client_named_tim(client):
    name = str((client or {}).get("name") or "").strip()
    folded = name.casefold()
    return folded == "tim" or folded.startswith("tim ")


def item_looks_tim(item, run=None):
    row = item if isinstance(item, dict) else {}
    ocr = row.get("ocr") if isinstance(row.get("ocr"), dict) else {}
    logo = str(ocr.get("logo_text") or row.get("logo_text") or "").strip()
    if logo.casefold() == "tim":
        return True
    blob = " ".join([
        str(row.get("name") or ""),
        str(ocr.get("headline") or ""),
        str(ocr.get("logo_text") or ""),
        str((run or {}).get("title") or "") if isinstance(run, dict) else "",
    ])
    return bool(TIM_LINE.search(blob))


def run_looks_tim(run):
    data = run if isinstance(run, dict) else {}
    if TIM_LINE.search(str(data.get("title") or "")):
        return True
    return any(item_looks_tim(item, data) for item in (data.get("versions") or []) if isinstance(item, dict))


def new_run_id():
    return f"r-{uuid.uuid4().hex[:12]}"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def empty_run(client_id=None, aspect="16:9"):
    now = utc_now()
    return {
        "run_id": new_run_id(),
        "title": "",
        "created_at": now,
        "updated_at": now,
        "client_id": client_id or "",
        "active_id": "",
        "base_id": "",
        "aspect_ratio": aspect or "16:9",
        "revision": 0,
        "versions": [],
    }


def is_run_store(data):
    return isinstance(data, dict) and data.get("schema") == RUN_SCHEMA and isinstance(data.get("runs"), list)


def wrap_store(session, client_id=None):
    if is_run_store(session):
        store = {
            "schema": RUN_SCHEMA,
            "active_run_id": session.get("active_run_id") or "",
            "runs": [
                dict(item)
                for item in session.get("runs") or []
                if isinstance(item, dict) and item.get("run_id") and run_matches_client(item, client_id)
            ],
        }
        if not store["runs"]:
            run = empty_run(client_id)
            store["runs"] = [run]
            store["active_run_id"] = run["run_id"]
        elif store["active_run_id"] not in {str(item.get("run_id") or "") for item in store["runs"]}:
            store["active_run_id"] = store["runs"][0]["run_id"]
        return store
    if isinstance(session, dict) and (session.get("versions") or session.get("revision") or session.get("run_id")):
        run = {
            **empty_run(client_id or session.get("client_id"), session.get("aspect_ratio") or "16:9"),
            "run_id": session.get("run_id") or new_run_id(),
            "title": session.get("title") or run_title(session),
            "created_at": session.get("created_at") or session.get("updated_at") or utc_now(),
            "updated_at": session.get("updated_at") or utc_now(),
            "active_id": session.get("active_id") or "",
            "base_id": session.get("base_id") or "",
            "aspect_ratio": session.get("aspect_ratio") or "16:9",
            "revision": history_revision(session),
            "versions": list(session.get("versions") or []),
        }
        return {
            "schema": RUN_SCHEMA,
            "active_run_id": run["run_id"],
            "runs": [run],
        }
    run = empty_run(client_id)
    return {"schema": RUN_SCHEMA, "active_run_id": run["run_id"], "runs": [run]}


def pick_run(store, run_id=None):
    runs = [item for item in (store.get("runs") or []) if isinstance(item, dict)]
    wanted = str(run_id or "").strip()
    if wanted:
        for item in runs:
            if str(item.get("run_id") or "") == wanted:
                return item
    active = str(store.get("active_run_id") or "")
    for item in runs:
        if str(item.get("run_id") or "") == active:
            return item
    return runs[0] if runs else empty_run()


def write_run(run, payload, versions, client_id, revision):
    payload = payload if isinstance(payload, dict) else {}
    data = dict(run or empty_run(client_id))
    data["client_id"] = client_id or data.get("client_id") or ""
    data["active_id"] = str(payload.get("active_id") or (versions[-1]["id"] if versions else ""))
    data["base_id"] = str(payload.get("base_id") or (versions[0]["id"] if versions else ""))
    data["aspect_ratio"] = str(payload.get("aspect_ratio") or data.get("aspect_ratio") or "16:9")
    data["revision"] = revision
    data["updated_at"] = utc_now()
    data["versions"] = versions[:60]
    data["title"] = str(payload.get("title") or "").strip() or run_title(data)
    if not data.get("created_at"):
        data["created_at"] = data["updated_at"]
    if not data.get("run_id"):
        data["run_id"] = new_run_id()
    return data


def put_run(store, run, active=True):
    pack = {
        "schema": RUN_SCHEMA,
        "active_run_id": store.get("active_run_id") or "",
        "runs": [],
    }
    seen = False
    run_id = str(run.get("run_id") or "")
    for item in store.get("runs") or []:
        if not isinstance(item, dict) or not item.get("run_id"):
            continue
        if str(item.get("run_id")) == run_id:
            pack["runs"].append(run)
            seen = True
        else:
            pack["runs"].append(item)
    if not seen:
        pack["runs"].insert(0, run)
    pack["runs"] = pack["runs"][:RUNS_LIMIT]
    if active or not pack["active_run_id"]:
        pack["active_run_id"] = run.get("run_id") or pack["active_run_id"]
    return pack


def run_title(session):
    versions = [
        item for item in (session.get("versions") or [])
        if isinstance(item, dict)
    ]
    first = versions[0] if versions else {}
    name = str(first.get("name") or "Troca").strip() or "Troca"
    aspect = str(session.get("aspect_ratio") or "").strip()
    return f"{name} · {aspect}" if aspect else name


def store_with_mirror(store):
    run = pick_run(store)
    return {
        **store,
        "client_id": run.get("client_id") or "",
        "run_id": run.get("run_id") or "",
        "title": run.get("title") or "",
        "active_id": run.get("active_id") or "",
        "base_id": run.get("base_id") or "",
        "aspect_ratio": run.get("aspect_ratio") or "16:9",
        "revision": history_revision(run),
        "updated_at": run.get("updated_at") or "",
        "versions": list(run.get("versions") or []),
    }


def clip_name(duration):
    try:
        seconds = int(duration)
    except (TypeError, ValueError):
        seconds = 0
    return f"Clipe {seconds}s" if seconds else "Clipe"


def is_video_version(item):
    return str((item or {}).get("media") or "") == "video" or (item or {}).get("origin") == "animate"


def match_media(item, media=None):
    wanted = str(media or "").strip().lower()
    if wanted not in {"still", "video", "image"}:
        return True
    video = is_video_version(item)
    return video if wanted == "video" else not video


def parse_scene_ref(raw):
    text = str(raw or "").strip()
    if not text:
        return "", ""
    if ":" in text:
        run_id, version_id = text.split(":", 1)
        if run_id.startswith("r-") and version_id:
            return run_id, version_id
    return "", text


def keep_video_fields(stored, previous):
    packed = dict(stored or {})
    prev = previous if isinstance(previous, dict) else {}
    for key in (
        "video_url",
        "poster_url",
        "master_asset_id",
        "poster_asset_id",
        "seedance_base_asset_id",
        "job_id",
        "source_version_id",
        "voiceover_asset_id",
        "voiceover_script",
        "end_card_asset_id",
        "extended_from",
    ):
        if not packed.get(key) and prev.get(key):
            packed[key] = prev.get(key)
    if not packed.get("packs") and prev.get("packs"):
        packed["packs"] = prev.get("packs")
    if not packed.get("storyboard_ids") and prev.get("storyboard_ids"):
        packed["storyboard_ids"] = prev.get("storyboard_ids")
    if not packed.get("script") and prev.get("script"):
        packed["script"] = prev.get("script")
    if packed.get("duration") in (None, "") and prev.get("duration") not in (None, ""):
        packed["duration"] = prev.get("duration")
    return packed


def run_summary(run, active_id="", media=None):
    versions = [
        item for item in (run.get("versions") or [])
        if isinstance(item, dict) and match_media(item, media)
    ]
    thumb = ""
    for item in reversed(versions):
        thumb = published_still_url(
            item.get("poster_url") or item.get("thumb_url") or item.get("image_url") or ""
        )
        if thumb:
            break
    run_id = str(run.get("run_id") or "")
    return {
        "run_id": run_id,
        "title": run.get("title") or run_title(run),
        "created_at": run.get("created_at") or "",
        "updated_at": run.get("updated_at") or "",
        "aspect_ratio": run.get("aspect_ratio") or "16:9",
        "version_count": len(versions),
        "thumb_url": thumb,
        "active": bool(run_id and run_id == str(active_id or "")),
    }


def history_revision(session):
    try:
        return int((session or {}).get("revision") or 0)
    except (TypeError, ValueError):
        return 0


def accepted_still(raw):
    return str(raw or "").strip().startswith(STILL_PREFIXES)


def local_still_path(raw):
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.startswith(("https://", "http://")):
        path = urlparse(text).path or ""
        return path if accepted_still(path) else ""
    return text if accepted_still(text) else ""


def still_data_format(raw):
    header = str(raw or "").split(",", 1)[0].lower()
    if "image/jpeg" in header or "image/jpg" in header:
        return "jpg"
    if "image/webp" in header:
        return "webp"
    return "png"


def published_still_url(raw):
    text = str(raw or "").strip()
    if text.startswith(("https://", "http://")):
        text = local_still_path(text) or text
    if text.startswith(TROCR_STILL_PREFIX):
        return text
    if text.startswith(GENERATED_PREFIX):
        name = Path(text).name
        if TROCR_STILL_NAME.fullmatch(name):
            return f"{TROCR_STILL_PREFIX}{name}"
    return text


def slim_context(value):
    if not isinstance(value, dict):
        return None
    slim = {}
    for key, item in value.items():
        if key in {"reference", "png_data_url", "image", "image_url", "thumb"}:
            continue
        if isinstance(item, str) and item.startswith("data:"):
            continue
        slim[key] = item
    return slim or None


def scene_index_value(item, params=None):
    from .swap_schema import scene_index_of

    data = item if isinstance(item, dict) else {}
    number = scene_index_of(data)
    if number:
        return number
    return scene_index_of(params if isinstance(params, dict) else {})


def attach_scene_fields(packed, item):
    from .swap_schema import PARAM_COPY_KEYS, piece_params

    data = item if isinstance(item, dict) else {}
    raw = data.get("params") if isinstance(data.get("params"), dict) else None
    if raw or any(str(data.get(key) or "").strip() for key in PARAM_COPY_KEYS) or data.get("scene_group") or data.get("scene_index") or data.get("scene_variant"):
        packed["params"] = piece_params(raw or data)
    params = packed.get("params") if isinstance(packed.get("params"), dict) else None
    index = scene_index_value(data, params)
    if index:
        packed["scene_index"] = index
        if params is not None:
            params["scene_index"] = index
    group = str(data.get("scene_group") or (params or {}).get("scene_group") or "").strip()[:64]
    if group:
        packed["scene_group"] = group
        if params is not None:
            params["scene_group"] = group
    return packed


def generated_params(payload, existing, parent, variant):
    from .swap_schema import piece_params

    data = dict(payload) if isinstance(payload, dict) else {}
    if variant in {2, 3}:
        data["scene_index"] = variant
    params = piece_params(data, parent)
    original = None
    for item in (existing or {}).get("versions") or []:
        if not isinstance(item, dict):
            continue
        if item.get("origin") == "original":
            original = item
            break
        if item.get("scene_group") and original is None:
            original = item
    group = str(params.get("scene_group") or "").strip()
    if not group:
        group = str(
            (original or {}).get("scene_group")
            or (parent or {}).get("scene_group")
            or ""
        ).strip()
    if not group:
        run_id = str((existing or {}).get("run_id") or data.get("run_id") or "")[:32]
        anchor = str(
            (original or {}).get("id")
            or data.get("base_id")
            or (existing or {}).get("base_id")
            or (parent or {}).get("id")
            or "v1"
        )
        group = f"{run_id}:{anchor}" if run_id else anchor
    params["scene_group"] = group[:64]
    if variant in {2, 3}:
        params["scene_index"] = variant
    elif not params.get("scene_index"):
        params["scene_index"] = 1
    return params


def generated_ocr(payload, parent, params):
    from .swap_schema import PARAM_COPY_KEYS

    ocr = slim_context((payload or {}).get("ocr")) or slim_context((parent or {}).get("ocr"))
    copy = params if isinstance(params, dict) else {}
    if ocr:
        for key in PARAM_COPY_KEYS:
            if copy.get(key) and not ocr.get(key):
                ocr[key] = copy[key]
        return ocr
    if any(copy.get(key) for key in PARAM_COPY_KEYS):
        return {key: copy.get(key) or "" for key in PARAM_COPY_KEYS}
    return None
