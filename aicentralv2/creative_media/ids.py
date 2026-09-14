from __future__ import annotations

import uuid

PREFIX = {
    "job": "anim_",
    "asset": "asset_",
}


def new_id(kind):
    prefix = PREFIX[kind]
    return prefix + uuid.uuid4().hex[:20]
