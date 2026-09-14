"""Sessão do Trocr: histórico com CAS, original travada e still autenticado."""

from __future__ import annotations

import base64
import logging
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..creative_modeling_repository import CreativeConflictError, CreativeNotFoundError
from ..creative_modeling_service import _integer, _serialize
from ..creative_modeling_storage import GENERATED_PREFIX, TROCR_STILL_NAME, TROCR_STILL_PREFIX

logger = logging.getLogger(__name__)

RUN_SCHEMA = "runs-v1"
RUNS_LIMIT = 24

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
        store = wrap_store(self.read(self.session_key(payload, user_id), client_id), client_id)
        run = pick_run(store, payload.get("run_id"))
        return _serialize(self.public_history(run, store, client_id))

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
        if mode in {"typeset", "recrop"}:
            origin = mode
            name = "Tipo na foto" if mode == "typeset" else "Recorte + tipo"
        elif quality == "draft":
            origin = "draft"
            name = "Rascunho"
        else:
            origin = "production"
            name = "Produção"
        next_id = f"v{len(versions) + 1}"
        parent_id = str(payload.get("base_id") or existing.get("base_id") or "")
        if parent_id == next_id:
            parent_id = ""
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
        stale = existing.get("revision") not in (None, payload.get("source_revision"), version.get("source_revision"))
        if payload.get("source_revision") not in (None, "", existing.get("revision")):
            stale = True
        row = {
            "id": next_id,
            "attempt": len(versions) + 1,
            "name": version.get("name") or "Animação",
            "origin": "animate",
            "parent_id": parent_id if parent_id != next_id else "",
            "quality": version.get("quality") or "",
            "status": "ready",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "media": "video",
            "image_url": version.get("poster_url") or version.get("image_url") or "",
            "thumb_url": version.get("poster_url") or version.get("image_url") or "",
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
        if text.startswith("data:image/") or text.startswith(("https://", "http://")):
            return text
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
        mime = mimetypes.guess_type(Path(url).name)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    def still_path(self, filename):
        storage = getattr(self.modeling, "storage", None)
        loader = getattr(storage, "load_trocr_still", None)
        path = loader(filename) if callable(loader) else None
        if path is not None:
            return path
        legacy = getattr(storage, "load_generated_still", None)
        path = legacy(filename) if callable(legacy) else None
        if path is None:
            raise CreativeNotFoundError("Still do Trocr não encontrado.")
        return path

    def persist_still(self, raw):
        text = str(raw or "").strip()
        if not text:
            return ""
        if accepted_still(text):
            return text
        if text.startswith(("https://", "http://", "/static/")):
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
        try:
            return saver(encoded) or ""
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
        return merged

    def store_version(self, item):
        if not isinstance(item, dict):
            return None
        image_url = self.storeable_image(item.get("image_url") or item.get("image"))
        if not image_url:
            return None
        thumb_url = self.storeable_image(item.get("thumb_url") or item.get("thumb")) or image_url
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
        if item.get("camadas_creative_id"):
            packed["camadas_creative_id"] = str(item.get("camadas_creative_id"))
        if str(item.get("media") or "") == "video" or item.get("origin") == "animate":
            packed.update({
                "media": "video",
                "video_url": str(item.get("video_url") or ""),
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
                "based_on_stale_revision": bool(item.get("based_on_stale_revision")),
            })
            if item.get("camadas_creative_id"):
                packed["camadas_creative_id"] = str(item.get("camadas_creative_id"))
        return packed

    def storeable_image(self, raw):
        url = self.persist_still(raw)
        return url if accepted_still(url) else ""

    def public_history(self, session, store=None, client_id=None):
        data = session if isinstance(session, dict) else {}
        versions = []
        for item in data.get("versions") or []:
            if not isinstance(item, dict):
                continue
            url = published_still_url(item.get("image_url") or "")
            thumb = published_still_url(item.get("thumb_url") or url)
            versions.append({
                **item,
                "image_url": url,
                "thumb_url": thumb,
                "image": url,
                "thumb": thumb,
            })
        pack = store if isinstance(store, dict) else wrap_store(data, client_id)
        active_id = str(data.get("run_id") or pack.get("active_run_id") or "")
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
            "runs": [run_summary(item, active_id) for item in pack.get("runs") or [] if isinstance(item, dict)],
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
            "runs": [dict(item) for item in session.get("runs") or [] if isinstance(item, dict) and item.get("run_id")],
        }
        if not store["runs"]:
            run = empty_run(client_id)
            store["runs"] = [run]
            store["active_run_id"] = run["run_id"]
        elif not store["active_run_id"]:
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


def run_summary(run, active_id=""):
    versions = [item for item in (run.get("versions") or []) if isinstance(item, dict)]
    thumb = ""
    for item in reversed(versions):
        thumb = published_still_url(item.get("thumb_url") or item.get("image_url") or "")
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


def published_still_url(raw):
    text = str(raw or "").strip()
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
