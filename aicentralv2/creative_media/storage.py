"""Arquivos de clipe, poster e pacotes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from flask import current_app, has_app_context


def media_root():
    if has_app_context():
        path = Path(current_app.instance_path) / "creative_media"
    else:
        path = Path.cwd() / "instance" / "creative_media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_bytes(public_id: str, suffix: str, payload: bytes) -> str:
    name = f"{_safe(public_id)}{suffix}"
    path = media_root() / name
    path.write_bytes(payload)
    return str(path)


def read_path(storage_key: str):
    path = Path(str(storage_key or ""))
    if not path.is_file():
        return None
    root = media_root().resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return None
    return path


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe(value):
    return "".join(ch for ch in str(value or "") if ch.isalnum() or ch in {"_", "-"})
