"""Build the Dify v4 prompt JSON files (one per app) from docs/dify/v4/*.md.

Run from the repository root: python scripts/build_dify_prompts.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "dify" / "v4"
INPUTS = ["core", "task", "current_context", "user_request", "evidence", "response_policy", "output_contract"]
LEGACY_UNUSED = ["prompt_boundary", "briefing_instruction", "skill_context", "projeto_context", "files_context",
                 "user_memory_context", "user_profile_context", "is_first_message"]
APPS = {
    "cadu-fast": {
        "file": "cadu-fast", "execution_mode": "fast",
        "settings": {"model": "GPT 5.4", "reasoning_effort": "baixo", "temperature": 0.3, "max_output_tokens": 3000},
        "uso": "Perguntas simples, conversa rápida e planos pedidos como rápidos ou resumidos.",
    },
    "cadu-analyst": {
        "file": "cadu-analyst", "execution_mode": "analysis",
        "settings": {"model": "GPT 5.4", "reasoning_effort": "médio", "temperature": 0.4, "max_output_tokens": 10000},
        "uso": "Modo padrão: perguntas sobre o projeto, análises, recomendações, briefings, planejamento de mídia e pesquisa.",
    },
    "cadu-operator": {
        "file": "cadu-operator", "execution_mode": "agentic",
        "settings": {"model": "GPT 5.4", "reasoning_effort": "alto", "temperature": 0.2, "max_output_tokens": 14000},
        "uso": "Entregas editáveis complexas (documentos, HTML, mapas de projeto), ações com confirmação e tarefas de alta complexidade.",
    },
}


def body(path: Path) -> str:
    """Prompt text below the first '---' line (the header above it is instructions for people)."""
    text = path.read_text(encoding="utf-8")
    return re.split(r"^---\s*$", text, maxsplit=1, flags=re.MULTILINE)[1].strip()


def build() -> dict:
    base = body(ROOT / "00-base-orquestrador.md")
    files = {}
    for app, spec in APPS.items():
        files[f"{app}.json"] = {
            "version": "4.0",
            "name": f"Cadu Conversations v4 — {app}",
            "app": app,
            "execution_mode": spec["execution_mode"],
            "uso": spec["uso"],
            "settings": {**spec["settings"], "conversation_memory": False, "knowledge_base": False, "tools": [],
                         "nota": "Valores sugeridos. Se o Dify não expuser temperatura para o GPT 5.4, ignore-a e use o esforço de raciocínio. "
                                 "Em modelos com raciocínio o limite de tokens de saída inclui o raciocínio, por isso é maior que o da resposta visível."},
            "inputs": INPUTS,
            "output_contract": {
                "format": "json",
                "text_field": "text.content",
                "ui_field": "ui",
                "instruction": "Retorne somente JSON válido conforme o campo output_contract recebido: text primeiro, com text.content "
                               "contendo a resposta ao usuário; ui, artifact_patch e task_proposal somente quando contratados e úteis.",
            },
            "system_prompt": base + "\n\n" + body(ROOT / f"{spec['file']}.md"),
            "runtime_contract": {
                "current_request": ["query", "user_request"],
                "top_level_provider_fields": ["query", "user", "files", "conversation_id", "response_mode"],
                "continuity": ["evidence.conversation_state", "evidence.conversation_history", "evidence.selected_context"],
                "project_and_tool_evidence": "evidence",
                "legacy_inputs_sent_but_unused": LEGACY_UNUSED,
                "legacy_policy": "O backend ainda envia estes campos por compatibilidade; o prompt v4 não os usa. "
                                 "Podem ser removidos de prompt_assembler.build_payload depois que os três apps estiverem no v4.",
                "variable_syntax": "No Chatflow, troque cada {{nome}} do system_prompt pela variável do nó de início (digite / no editor).",
            },
        }
    return files


if __name__ == "__main__":
    for name, content in build().items():
        (ROOT / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("gerado", ROOT / name)
