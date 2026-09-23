"""Single policy for actions that must be completed in the Workspace UI."""

from __future__ import annotations

from urllib.parse import urlencode


WORKSPACE_ONLY_TOOLS = frozenset({
    "workspace.delete_project",
    "workspace.merge_projects",
    "projects.delete",
    "projects.merge",
    "brands.delete",
})

WORKSPACE_ONLY_ACTIONS = frozenset({"open_project_delete", "open_project_merge", "open_brand_delete"})


def is_workspace_only_tool(name: str) -> bool:
    return str(name or "") in WORKSPACE_ONLY_TOOLS


def action_link(action: str, *, project_ref: str | None = None,
                brand_ref: str | None = None, target_project_ref: str | None = None) -> dict:
    """Build a safe relative deep link without granting the agent mutation authority."""
    if action == "open_brand_delete":
        entity_id = str(brand_ref or "").removeprefix("studio:")
        path, query, label = (f"/marcas/{entity_id}" if entity_id else "/marcas"), {"acao": "apagar"}, "Abrir gestão da marca"
        answer = "A marca só pode ser apagada na página de detalhes do Workspace."
    else:
        entity_id = str(project_ref or "").removeprefix("ci:")
        path = f"/projetos/{entity_id}" if entity_id else "/projetos"
        query = {"acao": "mesclar" if action == "open_project_merge" else "excluir"}
        target_id = str(target_project_ref or "").removeprefix("ci:")
        if target_id and action == "open_project_merge":
            query["destino"] = target_id
        label = "Abrir mesclagem no Workspace" if action == "open_project_merge" else "Abrir gestão do projeto"
        answer = ("A mesclagem é concluída na página de detalhes do projeto no Workspace."
                  if action == "open_project_merge" else
                  "O projeto só pode ser excluído na página de detalhes do Workspace.")
    href = f"{path}?{urlencode(query)}"
    return {
        "answer": answer,
        "block": {"type": "workspace_action", "title": label,
                  "summary": "Revise o impacto e confirme a ação na página administrativa.",
                  "href": href, "label": label},
    }
