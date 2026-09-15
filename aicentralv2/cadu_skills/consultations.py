"""Política da demonstração pública e do convite ao ecossistema."""

FREE_LIMIT = 3
INVITE_AFTER = 2


def consultation_state(count: int, *, is_client: bool = False) -> dict:
    count = max(0, int(count or 0))
    remaining = max(0, FREE_LIMIT - count)
    ecosystem_stage = ""
    if not is_client and count >= FREE_LIMIT:
        ecosystem_stage = "family"
    elif not is_client and count >= INVITE_AFTER:
        ecosystem_stage = "discover"
    return {
        "count": count,
        "remaining": remaining,
        "limit": FREE_LIMIT,
        "allowed": remaining > 0,
        "show_ecosystem_invite": bool(ecosystem_stage),
        "ecosystem_stage": ecosystem_stage,
    }
