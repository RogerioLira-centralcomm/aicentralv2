"""Suggest a project for conversations that have none; the owner decides.

Nothing here binds a conversation. Binding exposes it to the project team, so
acceptance goes through the owner-only ``PATCH /familia/api/conversations/<id>``.
"""
from __future__ import annotations

import json

import click
import numpy as np
from flask import current_app
from flask.cli import with_appcontext

from ..cadu_family import repository
from ..db import close_db
from . import project_knowledge

MIN_SCORE = 0.40
MIN_MARGIN = 0.04
NAME_MENTION_MIN_SCORE = 0.30
MIN_NAME_CHARS = 4
MAX_CHUNKS = 40


def decide(ranked: list[tuple[str, float]], name_mentioned: bool, *,
           min_score: float = MIN_SCORE, margin: float = MIN_MARGIN) -> dict | None:
    """Pick the top project when it is clearly ahead; ``ranked`` is sorted best-first."""
    if not ranked:
        return None
    ref, score = ranked[0]
    runner_ref, runner_score = ranked[1] if len(ranked) > 1 else (None, 0.0)
    ahead = score - runner_score >= margin
    if not ((score >= min_score and ahead) or (name_mentioned and score >= NAME_MENTION_MIN_SCORE)):
        return None
    return {"project_ref": ref, "score": round(float(score), 4), "runner_up_ref": runner_ref,
            "runner_up_score": round(float(runner_score), 4) if runner_ref else None,
            "name_mentioned": bool(name_mentioned)}


def rank_projects(conversation_vector: np.ndarray, profiles: dict[str, np.ndarray]) -> list[tuple[str, float]]:
    norm = np.linalg.norm(conversation_vector)
    if not norm or not profiles:
        return []
    unit = conversation_vector / norm
    scored = [(ref, float(unit @ vector)) for ref, vector in profiles.items()]
    return sorted(scored, key=lambda item: item[1], reverse=True)


def _parse_vector(text: str) -> np.ndarray:
    return np.array(json.loads(text), dtype=np.float32)


def project_profiles(client_id: int) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Unit embeddings of each project's description; returns (vectors, names)."""
    projects = repository.rows(
        """SELECT 'ci:' || id::text AS ref, nome, descricao, instrucoes, publico, posicionamento
             FROM cadu_ci_projetos
            WHERE id_cliente=%s AND status <> 'deletado' AND COALESCE(tipo,'') <> 'marca'""", (client_id,))
    texts, refs, names = [], [], {}
    for item in projects:
        parts = [item.get("nome"), item.get("descricao"), item.get("instrucoes"),
                 item.get("publico"), item.get("posicionamento")]
        text = " \n".join(" ".join(str(part).split()) for part in parts if part)[:3000]
        if len(text) >= 20:
            refs.append(item["ref"])
            texts.append(text)
            names[item["ref"]] = str(item.get("nome") or "")
    vectors = []
    for start in range(0, len(texts), project_knowledge.EMBED_BATCH):
        batch, _tokens, _model = project_knowledge._embed(texts[start:start + project_knowledge.EMBED_BATCH])
        vectors.extend(batch)
    profiles = {}
    for ref, vector in zip(refs, vectors):
        array = np.array(vector, dtype=np.float32)
        profiles[ref] = array / (np.linalg.norm(array) or 1.0)
    return profiles, names


def _unbound_conversations(client_id: int, refresh: bool) -> list[dict]:
    return repository.rows(
        """SELECT conversation.id, conversation.id_contato_cliente AS owner_id
             FROM cadu_conversations conversation
        LEFT JOIN cadu_family_conversation_context binding ON binding.conversation_id=conversation.id
        LEFT JOIN cadu_conversation_project_suggestions suggestion ON suggestion.conversation_id=conversation.id
            WHERE conversation.id_cliente=%s AND binding.project_ref IS NULL
              AND (%s OR suggestion.conversation_id IS NULL)
              AND EXISTS (SELECT 1 FROM cadu_conversation_chunks chunk WHERE chunk.conversation_id=conversation.id
                            AND chunk.embedding IS NOT NULL)
         ORDER BY conversation.updated_at DESC""", (client_id, refresh))


def _conversation_vector(conversation_id: str) -> np.ndarray | None:
    rows = repository.rows(
        """SELECT embedding::text AS embedding FROM cadu_conversation_chunks
            WHERE conversation_id=%s AND embedding IS NOT NULL
            ORDER BY segment_index DESC LIMIT %s""", (conversation_id, MAX_CHUNKS))
    if not rows:
        return None
    return np.mean([_parse_vector(row["embedding"]) for row in rows], axis=0)


def _name_mentioned(conversation_id: str, name: str) -> bool:
    if len(name.strip()) < MIN_NAME_CHARS:
        return False
    rows = repository.rows(
        """SELECT 1 FROM cadu_conversation_messages
            WHERE conversation_id=%s AND role='user' AND position(lower(%s) in lower(content)) > 0 LIMIT 1""",
        (conversation_id, name.strip()))
    return bool(rows)


def generate(client_id: int, *, min_score: float = MIN_SCORE, margin: float = MIN_MARGIN,
             limit: int = 0, refresh: bool = False, dry_run: bool = False) -> dict:
    profiles, names = project_profiles(client_id)
    stats = {"conversations": 0, "suggested": 0, "no_match": 0, "no_access": 0, "scores": []}
    if not profiles:
        return stats
    access: dict[tuple[int, str], bool] = {}

    def can_view(owner_id: int, ref: str) -> bool:
        key = (owner_id, ref)
        if key not in access:
            access[key] = bool(repository.project_user_can_view(client_id, ref, owner_id))
        return access[key]

    conversations = _unbound_conversations(client_id, refresh)
    for row in conversations[:limit or None]:
        stats["conversations"] += 1
        vector = _conversation_vector(str(row["id"]))
        if vector is None:
            continue
        owner_id = int(row["owner_id"])
        # Never suggest a project the owner cannot open.
        visible = {ref: value for ref, value in profiles.items() if can_view(owner_id, ref)}
        ranked = rank_projects(vector, visible)
        if not ranked:
            stats["no_access"] += 1
            continue
        stats["scores"].append(ranked[0][1])
        decision = decide(ranked, _name_mentioned(str(row["id"]), names.get(ranked[0][0], "")),
                          min_score=min_score, margin=margin)
        if not decision:
            stats["no_match"] += 1
            continue
        stats["suggested"] += 1
        if not dry_run:
            _save(client_id, str(row["id"]), decision)
    return stats


def _save(client_id: int, conversation_id: str, decision: dict) -> None:
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cadu_conversation_project_suggestions
                    (conversation_id, client_id, project_ref, score, runner_up_ref, runner_up_score,
                     name_mentioned, status, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'suggested',NOW(),NOW())
                   ON CONFLICT (conversation_id) DO UPDATE SET project_ref=EXCLUDED.project_ref,
                       score=EXCLUDED.score, runner_up_ref=EXCLUDED.runner_up_ref,
                       runner_up_score=EXCLUDED.runner_up_score, name_mentioned=EXCLUDED.name_mentioned,
                       status=CASE WHEN cadu_conversation_project_suggestions.project_ref=EXCLUDED.project_ref
                                   THEN cadu_conversation_project_suggestions.status ELSE 'suggested' END,
                       updated_at=NOW()""",
                (conversation_id, client_id, decision["project_ref"], decision["score"],
                 decision["runner_up_ref"], decision["runner_up_score"], decision["name_mentioned"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def pending_for_owner(user_id: int, client_id: int, conversation_id: str) -> dict | None:
    """The open suggestion for a conversation, only if the caller owns it and can open the project."""
    rows = repository.rows(
        """SELECT suggestion.project_ref, suggestion.score, project.nome AS project_name
             FROM cadu_conversation_project_suggestions suggestion
             JOIN cadu_conversations conversation ON conversation.id=suggestion.conversation_id
             JOIN cadu_ci_projetos project ON 'ci:' || project.id::text = suggestion.project_ref
                                          AND project.id_cliente=suggestion.client_id
        LEFT JOIN cadu_family_conversation_context binding ON binding.conversation_id=conversation.id
            WHERE suggestion.conversation_id=%s AND suggestion.client_id=%s AND suggestion.status='suggested'
              AND conversation.id_contato_cliente=%s AND conversation.id_cliente=%s
              AND binding.project_ref IS NULL AND project.status <> 'deletado'""",
        (conversation_id, client_id, user_id, client_id))
    if not rows or not repository.project_user_can_view(client_id, rows[0]["project_ref"], user_id):
        return None
    return {"project_ref": rows[0]["project_ref"], "project_name": rows[0]["project_name"],
            "score": float(rows[0]["score"])}


def dismiss(user_id: int, client_id: int, conversation_id: str) -> bool:
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE cadu_conversation_project_suggestions suggestion SET status='dismissed', updated_at=NOW()
                    FROM cadu_conversations conversation
                   WHERE suggestion.conversation_id=%s AND suggestion.client_id=%s
                     AND conversation.id=suggestion.conversation_id
                     AND conversation.id_contato_cliente=%s AND conversation.id_cliente=%s""",
                (conversation_id, client_id, user_id, client_id))
            changed = cur.rowcount > 0
        conn.commit()
        return changed
    except Exception:
        conn.rollback()
        raise


@click.command("conversation-project-suggest")
@click.option("--client-id", required=True, type=int)
@click.option("--min-score", type=float, default=MIN_SCORE, show_default=True)
@click.option("--margin", type=float, default=MIN_MARGIN, show_default=True)
@click.option("--limit", type=int, default=0, help="Máximo de conversas (0 = todas).")
@click.option("--refresh", is_flag=True, help="Reavalia conversas que já têm sugestão.")
@click.option("--dry-run", is_flag=True, help="Só mostra os números, sem gravar.")
@with_appcontext
def suggest_command(client_id, min_score, margin, limit, refresh, dry_run):
    """Sugere um projeto para conversas sem projeto. Não vincula nada."""
    stats = generate(client_id, min_score=min_score, margin=margin, limit=limit, refresh=refresh, dry_run=dry_run)
    scores = sorted(stats.pop("scores"))
    click.echo(json.dumps(stats, ensure_ascii=False))
    if scores:
        pick = lambda q: round(scores[min(len(scores) - 1, int(len(scores) * q))], 3)
        click.echo(f"Melhor similaridade por conversa: p10={pick(.1)} p50={pick(.5)} p90={pick(.9)}"
                   " (use para calibrar --min-score)")
    close_db()
    current_app.logger.info("Sugestões de projeto: %s", stats)
