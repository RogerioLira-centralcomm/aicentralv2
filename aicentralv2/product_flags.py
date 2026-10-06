"""Chaves centrais de produto da família Cadu.

Skills não roda no lançamento (2026-10-11). Toda a interface consulta
``skills_enabled()``; ligue com ``CADU_SKILLS_ENABLED=true``. A
infraestrutura interna (cadu_skills.repository: créditos, planos, RAG) e o
MCP continuam ativos independentemente desta chave.
"""
import os

_TRUE = {"1", "true", "yes", "on", "sim"}


def skills_enabled():
    return (os.getenv("CADU_SKILLS_ENABLED") or "").strip().lower() in _TRUE


def visible_solutions(items, key=None):
    """Remove Skills de uma lista/dict de soluções quando a chave está desligada."""
    if skills_enabled():
        return items
    if isinstance(items, dict):
        return {k: v for k, v in items.items() if k != "skills"}
    pick = key or (lambda item: item.get("id") if isinstance(item, dict) else item[0])
    return [item for item in items if pick(item) != "skills"]


def register_product_flags(app):
    app.jinja_env.globals["skills_enabled"] = skills_enabled
    app.jinja_env.globals["visible_solutions"] = visible_solutions
