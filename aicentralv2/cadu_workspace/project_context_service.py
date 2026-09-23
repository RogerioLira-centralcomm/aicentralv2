"""Canonical reads and writes for the project direction dossier."""

import re
import unicodedata
from uuid import uuid4

from psycopg.types.json import Json

from ..cadu_family import repository
from ..db import get_db


STANDARD_COLUMNS = {
    "name": "nome", "description": "descricao", "instructions": "instrucoes",
    "tone_of_voice": "tom_de_voz", "audience": "publico",
    "positioning": "posicionamento", "color": "cor",
}
TEXT_LIMITS = {
    "name": 150, "description": 4000, "instructions": 12000,
    "tone_of_voice": 4000, "audience": 4000, "positioning": 4000,
}
CONTEXT_LABELS = {
    "name": "Nome do projeto", "description": "Direção do trabalho",
    "instructions": "Orientações para o Cadu", "tone_of_voice": "Tom de voz",
    "audience": "Público", "positioning": "Posicionamento", "color": "Cor de referência",
}


class ProjectContextError(ValueError):
    pass


class ProjectContextConflict(ProjectContextError):
    pass


def _project_id(project_ref: str) -> str:
    value = str(project_ref or "")
    if not value.startswith("ci:") or not value[3:]:
        raise ProjectContextError("Selecione um projeto nativo do Cadu.")
    return value[3:]


def _field_key(value) -> str:
    ascii_value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9_]+", "_", ascii_value.lower()).strip("_")[:80]


def _snapshot(row: dict) -> dict:
    return {
        "project_ref": f"ci:{row['id']}", "revision": int(row.get("context_revision") or 1),
        "standard_fields": {key: row.get(column) for key, column in STANDARD_COLUMNS.items()},
        "custom_fields": row.get("campos_personalizados") if isinstance(row.get("campos_personalizados"), dict) else {},
        "updated_at": str(row.get("updated_at") or ""),
    }


def get_context(client_id: int, project_ref: str) -> dict:
    project_id = _project_id(project_ref)
    rows = repository.rows(
        """SELECT id,nome,descricao,instrucoes,tom_de_voz,publico,posicionamento,cor,
                  COALESCE(campos_personalizados,'{}'::jsonb) AS campos_personalizados,
                  context_revision,updated_at
             FROM cadu_ci_projetos
            WHERE id=%s AND id_cliente=%s AND status <> 'deletado'""",
        (project_id, int(client_id)),
    )
    if not rows:
        raise ProjectContextError("Projeto indisponível.")
    return _snapshot(rows[0])


def context_items(snapshot: dict) -> list[dict]:
    """Flatten a direction snapshot into a stable payload for search and UI."""
    revision = int(snapshot.get("revision") or 1)
    updated_at = str(snapshot.get("updated_at") or "")
    result = []
    for key, value in (snapshot.get("standard_fields") or {}).items():
        if value in (None, ""):
            continue
        result.append({
            "id": f"context:standard:{key}", "key": key,
            "label": CONTEXT_LABELS.get(key, key.replace("_", " ").title()),
            "value": value, "display_value": str(value), "type": "color" if key == "color" else "text",
            "field_kind": "standard", "editable": True, "revision": revision, "updated_at": updated_at,
        })
    for key, item in (snapshot.get("custom_fields") or {}).items():
        field = item if isinstance(item, dict) else {"value": item}
        value = field.get("value")
        if value in (None, "", []):
            continue
        result.append({
            "id": f"context:custom:{key}", "key": key,
            "label": str(field.get("label") or key.replace("_", " ").title()),
            "value": value,
            "display_value": ", ".join(map(str, value)) if isinstance(value, list) else str(value),
            "type": str(field.get("type") or ("list" if isinstance(value, list) else "text")),
            "field_kind": "custom", "editable": True, "revision": revision, "updated_at": updated_at,
        })
    return result


def search_context(snapshot: dict, query: str) -> list[dict]:
    """Return direction fields matching every normalized query term."""
    normalized = _field_key(query).replace("_", " ")
    terms = [term for term in normalized.split() if term]
    if not terms:
        return []
    matches = []
    for item in context_items(snapshot):
        haystack = _field_key(f"{item['key']} {item['label']} {item['display_value']}").replace("_", " ")
        compact_numbers = re.sub(r"(?<=\d)\s+(?=\d)", "", haystack)
        if all(term in haystack or (term.isdigit() and term in compact_numbers) for term in terms):
            matches.append({**item, "result_type": "project_context"})
    return matches


def _custom_fields(values) -> dict:
    if values is None:
        return {}
    if isinstance(values, dict):
        items = [{"key": key, **(item if isinstance(item, dict) else {"value": item})} for key, item in values.items()]
    elif isinstance(values, list):
        items = values
    else:
        raise ProjectContextError("Os campos personalizados possuem formato inválido.")
    if len(items) > 40:
        raise ProjectContextError("Use no máximo 40 campos personalizados.")
    result = {}
    for item in items:
        if not isinstance(item, dict):
            raise ProjectContextError("Revise os campos personalizados.")
        key = _field_key(item.get("key"))
        label = " ".join(str(item.get("label") or key.replace("_", " ").title()).split())[:120]
        if not key or not label:
            raise ProjectContextError("Todo campo personalizado precisa de chave e nome.")
        value = item.get("value")
        if isinstance(value, str):
            value = value.strip()[:12000]
        elif isinstance(value, list):
            value = [str(entry).strip()[:500] for entry in value[:100] if str(entry).strip()]
        elif not isinstance(value, (int, float, bool)) and value is not None:
            raise ProjectContextError(f"O valor de {label} não é válido.")
        result[key] = {"label": label, "value": value, **({"type": str(item.get("type"))[:24]} if item.get("type") else {})}
    return result


def update_context(*, client_id: int, actor_id: int, project_ref: str,
                   standard_fields=None, custom_fields=None, remove_custom_fields=None,
                   replace_custom_fields=False, expected_revision=None, source="workspace") -> dict:
    project_id = _project_id(project_ref)
    standard = dict(standard_fields or {})
    unknown = set(standard) - set(STANDARD_COLUMNS)
    if unknown:
        raise ProjectContextError("Campos padrão desconhecidos: " + ", ".join(sorted(unknown)))
    normalized = {}
    for key, value in standard.items():
        if key == "color":
            value = str(value or "").strip()
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ProjectContextError("Use uma cor hexadecimal válida.")
        else:
            value = " ".join(str(value or "").split()) if key == "name" else str(value or "").strip()
            value = value[:TEXT_LIMITS[key]]
            if key == "name" and len(value) < 2:
                raise ProjectContextError("O projeto precisa de um nome com ao menos dois caracteres.")
        normalized[key] = value
    custom = _custom_fields(custom_fields)
    removals = {_field_key(key)
                for key in (remove_custom_fields or [])}
    if not normalized and not custom and not removals and not replace_custom_fields:
        raise ProjectContextError("Informe ao menos um campo para atualizar.")

    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id,nome,descricao,instrucoes,tom_de_voz,publico,posicionamento,cor,status,
                          COALESCE(campos_personalizados,'{}'::jsonb) AS campos_personalizados,
                          context_revision,updated_at
                     FROM cadu_ci_projetos
                    WHERE id=%s AND id_cliente=%s AND status <> 'deletado' FOR UPDATE""",
                (project_id, int(client_id)),
            )
            row = cursor.fetchone()
            if not row:
                raise ProjectContextError("Projeto indisponível.")
            if row.get("status") == "arquivado":
                raise ProjectContextError("Reative o projeto antes de alterar sua direção.")
            before = _snapshot(dict(row))
            current_revision = int(row.get("context_revision") or 1)
            if expected_revision is not None and int(expected_revision) != current_revision:
                raise ProjectContextConflict("A direção foi alterada por outra pessoa. Atualize a página e revise novamente.")
            next_custom = {} if replace_custom_fields else dict(before["custom_fields"])
            next_custom.update(custom)
            for key in removals:
                next_custom.pop(key, None)
            assignments = [f"{STANDARD_COLUMNS[key]}=%s" for key in normalized]
            values = list(normalized.values())
            if custom or removals or replace_custom_fields:
                assignments.append("campos_personalizados=%s")
                values.append(Json(next_custom))
            assignments.extend(["context_revision=context_revision+1", "updated_at=NOW()"])
            cursor.execute(
                f"UPDATE cadu_ci_projetos SET {', '.join(assignments)} WHERE id=%s AND id_cliente=%s "
                "RETURNING id,nome,descricao,instrucoes,tom_de_voz,publico,posicionamento,cor,"
                "campos_personalizados,context_revision,updated_at",
                (*values, project_id, int(client_id)),
            )
            after = _snapshot(dict(cursor.fetchone()))
            changed = sorted([*normalized, *custom, *[f"-{key}" for key in removals if key in before["custom_fields"]]])
            cursor.execute(
                """INSERT INTO cadu_project_context_revisions
                    (id,client_id,project_id,revision,actor_id,source,changed_fields,before_context,after_context)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uuid4(), int(client_id), project_id, after["revision"], int(actor_id), str(source)[:32],
                 Json(changed), Json(before), Json(after)),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {**after, "updated_fields": changed, "status": "updated", "name": after["standard_fields"]["name"]}


def history(client_id: int, project_ref: str, limit=20) -> list[dict]:
    project_id = _project_id(project_ref)
    return repository.rows(
        """SELECT revision,actor_id,source,changed_fields,created_at
             FROM cadu_project_context_revisions
            WHERE client_id=%s AND project_id=%s ORDER BY revision DESC LIMIT %s""",
        (int(client_id), project_id, max(1, min(int(limit), 100))),
    )
