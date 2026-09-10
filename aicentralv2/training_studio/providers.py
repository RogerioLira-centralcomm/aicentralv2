"""Provedores de IA trocáveis do Studio de Treinamentos."""

import os

from ..creative_modeling_generation import CreativeGenerationClient, _usage_cost
from ..services.openrouter_service import OpenRouterError, chat_completion


DEFAULT_TEXT_MODEL = os.getenv("TRAINING_AGENT_MODEL", "anthropic/claude-sonnet-4.5")
DEFAULT_RESEARCH_MODEL = os.getenv("TRAINING_RESEARCH_MODEL", "perplexity/sonar-pro")


def usage_cost(usage):
    return _usage_cost(usage) or 0.0


class TextProvider:
    def complete(self, messages, *, max_tokens=1600, temperature=0.45, model=None):
        response = chat_completion(
            messages,
            model=model or DEFAULT_TEXT_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=90,
        )
        message = response.get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict)
            )
        return {
            "content": str(content).strip(),
            "model": response.get("model") or DEFAULT_TEXT_MODEL,
            "usage": response.get("usage") or {},
            "cost_usd": usage_cost(response.get("usage")),
            "tool_calls": message.get("tool_calls") or [],
        }


class ResearchProvider:
    def search(self, query, *, context=""):
        messages = [
            {
                "role": "system",
                "content": (
                    "Você pesquisa mercado para um treinamento executivo de mídia. "
                    "Responda em português do Brasil, com fatos atuais, números e fontes. "
                    "Não invente estatísticas. Se não houver dado confiável, diga isso."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Pesquise: {query}\n\nContexto do trecho:\n{context or '(sem seleção)'}"
                ),
            },
        ]
        response = chat_completion(
            messages,
            model=DEFAULT_RESEARCH_MODEL,
            max_tokens=1400,
            temperature=0.2,
            timeout=90,
        )
        message = response.get("message") or {}
        return {
            "content": str(message.get("content") or "").strip(),
            "model": response.get("model") or DEFAULT_RESEARCH_MODEL,
            "usage": response.get("usage") or {},
            "cost_usd": usage_cost(response.get("usage")),
        }


class ImageProvider:
    def __init__(self, client=None):
        self.client = client or CreativeGenerationClient()

    def generate(self, prompt, aspect_ratio="16:9"):
        generated = self.client.generate_image(
            prompt,
            None,
            aspect_ratio,
        )
        return {
            "b64_json": generated.get("b64_json"),
            "model": generated.get("model"),
            "usage": generated.get("usage") or {},
            "cost_usd": float(generated.get("actual_cost_usd") or 0),
            "output_format": generated.get("output_format") or "png",
        }


class TrainingProviders:
    def __init__(self, text=None, research=None, image=None):
        self.text = text or TextProvider()
        self.research = research or ResearchProvider()
        self.image = image or ImageProvider()


__all__ = [
    "DEFAULT_RESEARCH_MODEL",
    "DEFAULT_TEXT_MODEL",
    "ImageProvider",
    "OpenRouterError",
    "ResearchProvider",
    "TextProvider",
    "TrainingProviders",
    "usage_cost",
]
