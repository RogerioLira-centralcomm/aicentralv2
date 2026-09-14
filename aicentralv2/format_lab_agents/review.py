"""Revisões R1–R5: snapshot imutável, aprovada não é sobrescrita."""

ROUNDS = {
    1: ("estrutura",),
    2: ("estrutura", "visual"),
    3: ("estrutura", "visual", "mensagem"),
    4: ("estrutura", "visual", "mensagem", "contexto"),
    5: ("estrutura", "visual", "mensagem", "contexto", "acabamento"),
}

STATUSES = (
    "draft",
    "analysis",
    "internal_review",
    "approved",
    "showcase",
)


def plan_rounds(count=3):
    try:
        number = int(count)
    except (TypeError, ValueError):
        number = 3
    number = min(5, max(1, number))
    return {
        "count": number,
        "rounds": [
            {"index": index, "focus": list(ROUNDS[number][:index] if number == 1 else [ROUNDS[5][index - 1]])}
            for index in range(1, number + 1)
        ],
    }


def snapshot(payload, revision_index, previous=None):
    previous = previous if isinstance(previous, dict) else {}
    if previous.get("status") == "approved":
        return dict(previous)
    planned = plan_rounds((payload or {}).get("revision_count") or 3)
    focus = []
    for item in planned["rounds"]:
        if item["index"] == revision_index:
            focus = item["focus"]
    return {
        "revision": revision_index,
        "focus": focus,
        "status": "analysis",
        "immutable": True,
        "payload": {
            "format_key": (payload or {}).get("format_key"),
            "placement": (payload or {}).get("placement"),
            "quality": (payload or {}).get("quality"),
        },
    }
