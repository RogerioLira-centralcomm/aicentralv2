"""Opaque, reversible brand references for Workspace URLs.

The database id never appears in the address bar: ``/marcas/50`` becomes
``/marcas/b...``. The reference is a keyed 4-round Feistel permutation over the
id, so it needs no column or migration. It hides the id; it is not an access
control, and every route still checks the tenant that owns the brand.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re

from flask import current_app
from werkzeug.routing import BaseConverter, ValidationError

_PREFIX = "b"
_MAX_ID = 1 << 40
_ROUNDS = 4
_TOKEN = re.compile(r"^b[a-z2-7]{13}$")


def _key() -> bytes:
    secret = current_app.config.get("SECRET_KEY") or "cadu-brand-ref"
    return hashlib.sha256(f"cadu-brand-ref:{secret}".encode()).digest()


def _round(key: bytes, index: int, half: int) -> int:
    digest = hmac.new(key, bytes([index]) + half.to_bytes(4, "big"), hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big")


def encode_brand_id(brand_id: int) -> str:
    brand_id = int(brand_id)
    if not 0 < brand_id < _MAX_ID:
        raise ValueError("Marca inválida.")
    key = _key()
    left, right = brand_id >> 32, brand_id & 0xFFFFFFFF
    for index in range(_ROUNDS):
        left, right = right, left ^ _round(key, index, right)
    raw = ((left << 32) | right).to_bytes(8, "big")
    return _PREFIX + base64.b32encode(raw).decode().lower().rstrip("=")


def decode_brand_ref(value: str) -> int | None:
    if not _TOKEN.match(value or ""):
        return None
    padded = value[1:].upper() + "=" * 3
    try:
        raw = base64.b32decode(padded)
    except ValueError:
        return None
    key = _key()
    block = int.from_bytes(raw, "big")
    left, right = block >> 32, block & 0xFFFFFFFF
    for index in reversed(range(_ROUNDS)):
        left, right = right ^ _round(key, index, left), left
    brand_id = (left << 32) | right
    return brand_id if 0 < brand_id < _MAX_ID else None


class BrandRefConverter(BaseConverter):
    """Accept the opaque reference and, for old links and API calls, the numeric id."""

    regex = r"[A-Za-z0-9]+"

    def to_python(self, value: str) -> int:
        if value.isdigit():
            number = int(value)
            if number > 0:
                return number
            raise ValidationError()
        brand_id = decode_brand_ref(value)
        if brand_id is None:
            raise ValidationError()
        return brand_id

    def to_url(self, value) -> str:
        return encode_brand_id(int(value))
