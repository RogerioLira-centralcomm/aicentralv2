"""Runtime pequeno e sem ferramentas para experimentar as skills curadas."""

from __future__ import annotations

from ..services.openrouter_service import chat_completion, message_text


TEST_AGENT_RULES = """
Você é o agente de teste do Cadu Skills.
- Execute somente a skill instalada abaixo e responda em português do Brasil.
- Não use ferramentas, não navegue, não alegue acesso a dados que não foram fornecidos.
- Preserve incertezas e nunca invente fatos, preços, fontes ou resultados.
- Seja útil em até 700 tokens e termine com no máximo três próximos passos.
- Não gere vídeo nem áudio. Quando a tarefa for audiovisual, entregue somente roteiro em texto.
""".strip()


def run_test_skill(skill: dict, prompt: str) -> dict:
    """Executa uma skill já instalada no agente de teste, sem tool calling."""
    clean_prompt = str(prompt or "").strip()
    if len(clean_prompt) < 12:
        raise ValueError("Conte um pouco mais sobre a tarefa.")
    if len(clean_prompt) > 4000:
        raise ValueError("A tarefa deve ter no máximo 4.000 caracteres.")
    instructions = str(skill.get("instructions") or "").strip()
    if not instructions:
        raise ValueError("Esta skill ainda não foi preparada para testes.")
    result = chat_completion(
        [
            {"role": "system", "content": f"{TEST_AGENT_RULES}\n\nSKILL INSTALADA\n{instructions}"},
            {"role": "user", "content": clean_prompt},
        ],
        model=skill.get("model") or "openai/gpt-4o-mini",
        max_tokens=700,
        temperature=0.3,
        timeout=90,
    )
    answer = str(message_text(result.get("message") or {}) or "").strip()
    if not answer:
        raise RuntimeError("O agente de teste não devolveu conteúdo.")
    return {
        "answer": answer,
        "model": result.get("model") or skill.get("model"),
        "usage": result.get("usage") or {},
    }
