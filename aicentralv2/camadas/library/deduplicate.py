"""Deduplicação de ativos por sha256."""

from __future__ import annotations

import hashlib


def asset_fingerprint(element, storage=None):
    path = (element or {}).get("png_path") or (element or {}).get("asset_path") or ""
    hasher = getattr(storage, "sha256_of", None) if storage is not None else None
    if path and callable(hasher):
        digest = hasher(path)
        if digest:
            return digest
    raw = "|".join(
        [
            str((element or {}).get("role") or ""),
            str((element or {}).get("text_content") or (element or {}).get("text") or ""),
            str((element or {}).get("label") or ""),
            path,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_duplicate(repository, client_id, sha256):
    if not client_id or not sha256:
        return None
    return repository.find_asset_by_sha(client_id, sha256)
