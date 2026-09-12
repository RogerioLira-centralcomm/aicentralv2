"""Sessão do Trocr: histórico com CAS, original travada e still autenticado."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from ..creative_modeling_repository import CreativeConflictError, CreativeNotFoundError
from ..creative_modeling_service import _integer, _serialize
from ..creative_modeling_storage import GENERATED_PREFIX, TROCR_STILL_NAME, TROCR_STILL_PREFIX

logger = logging.getLogger(__name__)

STILL_PREFIXES = (
    "/static/uploads/creative_generated/",
    "/static/uploads/creative_trocr/",
    TROCR_STILL_PREFIX,
)


class TrocrStore:
    def __init__(self, modeling, repository, client_lookup=None):
        self.modeling = modeling
        self.repository = repository
        self.client_lookup = client_lookup

    def load(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        session = self.read(self.session_key(payload, user_id), client_id)
        return _serialize(self.public_history(session, client_id))

    def save(self, payload, user_id=None):
        payload = payload if isinstance(payload, dict) else {}
        client_id = optional_client(payload)
        key = self.session_key(payload, user_id)
        existing = self.read(key, client_id)
        current = history_revision(existing)
        sent = payload.get("revision")
        if sent not in (None, ""):
            try:
                expected = int(sent)
            except (TypeError, ValueError):
                expected = -1
            if expected != current:
                raise CreativeConflictError("O histórico mudou. Recarregue e tente de novo.")
        versions = self.merge_versions(existing.get("versions") or [], payload.get("versions") or [])
        session = {
            "client_id": client_id or "",
            "active_id": str(payload.get("active_id") or (versions[-1]["id"] if versions else "")),
            "base_id": str(payload.get("base_id") or (versions[0]["id"] if versions else "")),
            "aspect_ratio": str(payload.get("aspect_ratio") or "16:9"),
            "revision": current + 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "versions": versions[:60],
        }
        self.write(key, session, client_id)
        if client_id and user_id not in (None, ""):
            self.write(f"user-{user_id}", session, None)
        return _serialize(self.public_history(session, client_id))

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
                "versions": versions,
                "active_id": next_id,
                "base_id": existing.get("base_id") or (versions[0]["id"] if versions else next_id),
                "aspect_ratio": result.get("aspect_ratio") or payload.get("aspect_ratio") or "16:9",
                "revision": existing.get("revision"),
            },
            user_id=user_id,
        )

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
        return {
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

    def storeable_image(self, raw):
        url = self.persist_still(raw)
        return url if accepted_still(url) else ""

    def public_history(self, session, client_id=None):
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
        return {
            "client_id": data.get("client_id") or client_id or "",
            "active_id": data.get("active_id") or "",
            "base_id": data.get("base_id") or "",
            "aspect_ratio": data.get("aspect_ratio") or "16:9",
            "revision": history_revision(data),
            "updated_at": data.get("updated_at") or "",
            "versions": versions,
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
