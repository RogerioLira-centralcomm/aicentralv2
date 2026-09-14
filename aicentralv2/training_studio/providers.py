"""Provedores de IA do Studio — OpenAI direto quando a chave existe."""

import os

import requests

from ..creative_modeling_generation import CreativeGenerationClient, _usage_cost
from ..services.openrouter_service import (
    OpenRouterError,
    chat_completion,
    generate_image as openai_generate_image,
    openai_model_slug,
    resolve_openai_api_key,
    uses_direct_openai,
)


DEFAULT_TEXT_MODEL = os.getenv("TRAINING_AGENT_MODEL", "openai/gpt-5-mini")
DEFAULT_RESEARCH_MODEL = os.getenv("TRAINING_RESEARCH_MODEL", "openai/gpt-5-mini")
DEFAULT_VISION_MODEL = os.getenv("TRAINING_VISION_MODEL", "google/gemini-2.5-flash")
SEARCH_DOMAINS = (
    "datareportal.com",
    "wearesocial.com",
    "iab.com",
    "iab.com.br",
    "lumen-research.com",
    "adelaidemetrics.com",
    "tvisioninsights.com",
    "kantaribopemedia.com.br",
)
RESPONSES_URL = "https://api.openai.com/v1/responses"


def usage_cost(usage):
    return _usage_cost(usage) or 0.0


def _provider_name(model=None):
    if uses_direct_openai(model):
        return "openai"
    return "openrouter"


class TextProvider:
    def complete(self, messages, *, max_tokens=1600, temperature=0.45, model=None, tools=None):
        chosen = model or DEFAULT_TEXT_MODEL
        response = chat_completion(
            messages,
            tools=tools,
            model=chosen,
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
            "model": response.get("model") or chosen,
            "usage": response.get("usage") or {},
            "cost_usd": usage_cost(response.get("usage")),
            "tool_calls": message.get("tool_calls") or [],
            "provider": _provider_name(chosen),
        }


class ResearchProvider:
    def search(self, query, *, context=""):
        key = resolve_openai_api_key()
        if not key:
            raise OpenRouterError(
                "OpenAI não está configurada. Cadastre a chave em Integrações."
            )
        preferred = ", ".join(SEARCH_DOMAINS)
        prompt = (
            "Pesquise para um treinamento de especialistas em mídia. "
            "Responda em português do Brasil com fatos atuais, números e URLs. "
            "Não invente estatística. Se não houver dado confiável, diga pendente. "
            f"Prefira estas fontes quando existirem: {preferred}.\n\n"
            f"Pesquise: {query}\n\nContexto:\n{context or '(sem seleção)'}"
        )
        body = {
            "model": openai_model_slug(DEFAULT_RESEARCH_MODEL),
            "input": prompt,
            "tools": [{"type": "web_search"}],
        }
        response = requests.post(
            RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=90,
        )
        if response.status_code >= 400:
            raise OpenRouterError(
                f"A OpenAI recusou a busca: {(response.text or '')[:180]}"
            )
        data = response.json()
        text = _responses_text(data)
        usage = data.get("usage") or {}
        return {
            "content": text or "A busca não devolveu trecho utilizável.",
            "model": data.get("model") or DEFAULT_RESEARCH_MODEL,
            "usage": {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            },
            "cost_usd": usage_cost(usage),
            "provider": "openai",
            "citations": _responses_citations(data),
        }


def _responses_text(data):
    chunks = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("text"):
                chunks.append(str(part["text"]))
        if item.get("type") == "message" and item.get("content"):
            continue
    if not chunks and data.get("output_text"):
        chunks.append(str(data["output_text"]))
    return "\n".join(chunks).strip()


def _responses_citations(data):
    urls = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if not isinstance(part, dict):
                continue
            for ann in part.get("annotations") or []:
                url = (ann or {}).get("url")
                if url and url not in urls:
                    urls.append(url)
    return urls


class VisionProvider:
    def interpret(self, prompt, image_urls, *, system="", model=None):
        chosen = model or DEFAULT_VISION_MODEL
        parts = [{"type": "text", "text": prompt}]
        for url in list(image_urls or [])[:6]:
            if not url:
                continue
            parts.append({"type": "image_url", "image_url": {"url": url}})
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": parts})
        response = chat_completion(
            messages,
            model=chosen,
            max_tokens=900,
            temperature=0.2,
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
            "model": response.get("model") or chosen,
            "usage": response.get("usage") or {},
            "cost_usd": usage_cost(response.get("usage")),
            "provider": _provider_name(chosen),
        }


class ImageProvider:
    def generate(self, prompt, aspect_ratio="16:9"):
        if resolve_openai_api_key():
            generated = openai_generate_image(
                prompt,
                aspect_ratio=aspect_ratio,
                model="openai/gpt-image-2",
            )
            return {
                "b64_json": generated.get("b64_json"),
                "model": generated.get("model") or "gpt-image-2",
                "usage": generated.get("usage") or {},
                "cost_usd": usage_cost(generated.get("usage")),
                "output_format": generated.get("output_format") or "png",
                "provider": "openai",
            }
        generated = CreativeGenerationClient().generate_image(
            prompt, None, aspect_ratio
        )
        return {
            "b64_json": generated.get("b64_json"),
            "model": generated.get("model"),
            "usage": generated.get("usage") or {},
            "cost_usd": float(generated.get("actual_cost_usd") or 0),
            "output_format": generated.get("output_format") or "png",
            "provider": "openrouter",
        }


class TrainingProviders:
    def __init__(self, text=None, research=None, image=None, vision=None):
        self.text = text or TextProvider()
        self.research = research or ResearchProvider()
        self.image = image or ImageProvider()
        self.vision = vision or VisionProvider()


__all__ = [
    "DEFAULT_RESEARCH_MODEL",
    "DEFAULT_TEXT_MODEL",
    "DEFAULT_VISION_MODEL",
    "ImageProvider",
    "OpenRouterError",
    "ResearchProvider",
    "TextProvider",
    "TrainingProviders",
    "VisionProvider",
    "usage_cost",
]
