"""Resolve coleções por id público, pk ou nome."""

from __future__ import annotations

from ..schemas import is_public_id, new_public_id, optional_int


def resolve_collection(repository, client_id, collection_id=None, name=""):
    if not client_id:
        raise ValueError("Associe uma marca antes de publicar.")
    wanted = str(collection_id or name or "").strip()
    if wanted and is_public_id(wanted, "collection"):
        row = repository.get_collection(wanted)
        if not row or int(row.get("client_id") or 0) != int(client_id):
            raise ValueError("Coleção não encontrada.")
        return row
    if wanted:
        try:
            pk = optional_int(wanted)
        except ValueError:
            pk = None
        if pk:
            row = repository.get_collection_by_pk(pk)
            if not row or int(row.get("client_id") or 0) != int(client_id):
                raise ValueError("Coleção não encontrada.")
            return row
        found = repository.find_collection_by_name(client_id, wanted)
        if found:
            return found
        return repository.create_collection({
            "public_id": new_public_id("collection"),
            "client_id": client_id,
            "name": wanted[:200],
        })
    found = repository.find_collection_by_name(client_id, "Geral")
    if found:
        return found
    return repository.create_collection({
        "public_id": new_public_id("collection"),
        "client_id": client_id,
        "name": "Geral",
    })
