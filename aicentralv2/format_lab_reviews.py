"""Snapshots R1–R5. Versão aprovada não é sobrescrita."""

from copy import deepcopy

from .format_lab_agents.review import STATUSES, plan_rounds, snapshot

_STORE = {}


def create_revision(variant_id, payload, revision_index=1):
    key = str(variant_id or "").strip()
    if not key:
        raise ValueError("Variante inválida.")
    history = _STORE.setdefault(key, [])
    previous = history[-1] if history else None
    if previous and previous.get("status") == "approved":
        return dict(previous)
    record = snapshot(payload, revision_index, previous)
    record["variant_id"] = key
    record["status"] = "analysis"
    history.append(record)
    return dict(record)


def approve_revision(variant_id, revision_index):
    key = str(variant_id or "").strip()
    for item in _STORE.get(key) or []:
        if item.get("revision") == revision_index:
            if item.get("status") == "approved":
                return dict(item)
            item["status"] = "approved"
            return dict(item)
    raise ValueError("Revisão não encontrada.")


def list_revisions(variant_id):
    return [dict(item) for item in _STORE.get(str(variant_id or "").strip()) or []]


def planned(count):
    return plan_rounds(count)


def statuses():
    return list(STATUSES)


def clone_approved(variant_id):
    items = list_revisions(variant_id)
    approved = [item for item in items if item.get("status") == "approved"]
    return deepcopy(approved[-1]) if approved else None
