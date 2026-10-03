"""Provider connectors for the Lab: one explicit route per call, never a silent fallback.

Production's ``generate_image`` tries OpenAI and then OpenRouter and prunes parameters by model name;
a benchmark needs to know exactly which route answered with which payload, so the Lab talks to each
provider directly. Only pure helpers from the production module are reused.
"""

from __future__ import annotations

import base64
import json
import time

import requests

from ..services import openrouter_service as production

OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images"
TIMEOUT = 240
DEADLINE = 300  # wall-clock cap per call: ``timeout`` only bounds each socket read, so keep-alive bytes could hold a call open forever


class ProviderError(RuntimeError):
    def __init__(self, message, *, status=None, blocked=False, detail=None):
        super().__init__(message)
        self.status = status
        self.blocked = blocked
        self.detail = detail


def _cost_from_usage(usage: dict, pricing: list[dict]) -> float | None:
    """Price token usage with the catalog rates when the provider did not report a cost."""
    if not isinstance(usage, dict):
        return None
    rates = {row.get("billable"): float(row.get("cost_usd") or 0) for row in pricing or [] if row.get("unit") == "token"}
    if not rates:
        return None
    details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    text_in = details.get("text_tokens")
    image_in = details.get("image_tokens") or 0
    total_in = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    if text_in is None:
        text_in = max(0, total_in - image_in)
    out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    if not (text_in or image_in or out):
        return None
    return round(text_in * rates.get("input_text", 0) + image_in * rates.get("input_image", 0)
                 + out * rates.get("output_image", 0), 6)


def _blocked(text: str) -> bool:
    try:
        return production.is_real_person_block(text)
    except Exception:
        return False


def _post_with_deadline(url: str, *, headers: dict, payload: dict) -> tuple[int, bytes, dict]:
    started = time.monotonic()
    with requests.post(url, headers=headers, json=payload, timeout=(15, TIMEOUT), stream=True) as response:
        chunks = []
        for chunk in response.iter_content(chunk_size=65536):
            chunks.append(chunk)
            if time.monotonic() - started > DEADLINE:
                raise requests.Timeout(f"sem resposta completa em {DEADLINE}s")
        return response.status_code, b"".join(chunks), dict(response.headers)


def call_openrouter(*, model_id: str, prompt: str, parameters: dict, references: list[str], pricing: list[dict]) -> dict:
    payload = {"model": model_id, "prompt": prompt, "n": 1, **parameters}
    if references:
        payload["input_references"] = [{"type": "image_url", "image_url": {"url": url}} for url in references]
    headers = {
        "Authorization": f"Bearer {production.resolve_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "Cadu Studio Lab",
    }
    started = time.monotonic()
    try:
        status_code, body, response_headers = _post_with_deadline(OPENROUTER_IMAGE_URL, headers=headers, payload=payload)
    except requests.Timeout as exc:
        raise ProviderError(f"O OpenRouter não respondeu a tempo ({DEADLINE}s).") from exc
    except requests.RequestException as exc:
        raise ProviderError(f"Falha de rede no OpenRouter ({type(exc).__name__}).") from exc
    latency = round((time.monotonic() - started) * 1000)
    if status_code >= 400:
        detail = body.decode("utf-8", "replace")[:600]
        raise ProviderError(f"OpenRouter HTTP {status_code}", status=status_code,
                            blocked=_blocked(detail) or status_code == 451, detail=detail)
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise ProviderError("O OpenRouter devolveu uma resposta inválida.", detail=body[:400].decode("utf-8", "replace")) from exc
    first = (data.get("data") or [{}])[0] or {}
    encoded = first.get("b64_json")
    if not encoded and first.get("url"):
        fetched = requests.get(first["url"], timeout=60)
        fetched.raise_for_status()
        encoded = base64.b64encode(fetched.content).decode("ascii")
    if not encoded:
        raise ProviderError("O OpenRouter não devolveu imagem.", detail=str(data)[:400])
    usage = data.get("usage") or {}
    reported = usage.get("cost")
    cost, source = (float(reported), "provider") if isinstance(reported, (int, float)) else (_cost_from_usage(usage, pricing), "catalog_tokens")
    return {"b64": encoded, "latency_ms": latency, "usage": usage, "cost_usd": cost,
            "cost_source": source if cost is not None else None,
            "request_id": data.get("id") or response_headers.get("x-request-id"),
            "model": data.get("model") or model_id}


def call_openai_direct(*, model_id: str, prompt: str, parameters: dict, references: list[str], pricing: list[dict]) -> dict:
    payload = {"prompt": prompt, "quality": parameters.get("quality") or "medium", "aspect_ratio": "1:1"}
    size = parameters.get("size")
    started = time.monotonic()
    try:
        if references:
            result = production._openai_edit_image(
                payload, image_model=model_id, output_format="png", timeout=TIMEOUT,
                input_references=[{"type": "image_url", "image_url": {"url": url}} for url in references], size=size,
            )
        else:
            result = production._openai_generate_image(payload, image_model=model_id, output_format="png",
                                                       timeout=TIMEOUT, size=size)
    except production.OpenRouterError as exc:
        raise ProviderError(str(exc), blocked=_blocked(str(exc)), detail=str(exc)[:600]) from exc
    latency = round((time.monotonic() - started) * 1000)
    usage = result.get("usage") or {}
    cost = _cost_from_usage(usage, pricing)
    return {"b64": result["b64_json"], "latency_ms": latency, "usage": usage, "cost_usd": cost,
            "cost_source": "catalog_tokens" if cost is not None else None, "request_id": None,
            "model": result.get("model") or model_id}


def call(provider: str, **kwargs) -> dict:
    if provider == "openrouter":
        return call_openrouter(**kwargs)
    if provider == "openai_direct":
        return call_openai_direct(**kwargs)
    raise ProviderError(f"Provedor sem conector no Lab: {provider}")
