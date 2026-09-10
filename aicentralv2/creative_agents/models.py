"""Slugs GPT no OpenRouter — nunca SDK OpenAI direto."""

import os

AGENT_MODELS = {
    "dna": os.getenv("CREATIVE_AGENT_DNA_MODEL", "openai/gpt-5.4"),
    "extractor": os.getenv("CREATIVE_AGENT_EXTRACTOR_MODEL", "openai/gpt-5.4"),
    "scriptwriter": os.getenv("CREATIVE_AGENT_SCRIPTWRITER_MODEL", "openai/gpt-5.4"),
    "producer": os.getenv("CREATIVE_AGENT_PRODUCER_MODEL", "openai/gpt-4o-mini"),
    "reviewer": os.getenv("CREATIVE_AGENT_REVIEWER_MODEL", "openai/gpt-4o-mini"),
}

OPENROUTER_PREFIX = "openai/gpt-"


def assert_openrouter_gpt(model):
    slug = str(model or "")
    if not slug.startswith(OPENROUTER_PREFIX):
        raise ValueError("Agente da Modelagem só aceita modelo openai/gpt-* no OpenRouter.")
    return slug
