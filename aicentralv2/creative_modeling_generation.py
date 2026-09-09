"""Clientes de IA e contratos de geração para Modelagem de Criativos."""

import json
import math
import os
import re

import requests

from .services.openrouter_service import OpenRouterError, chat_completion


OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images"
DEFAULT_TEXT_MODEL = os.getenv("CREATIVE_TEXT_MODEL", "openai/gpt-5.4")
DEFAULT_IMAGE_MODEL = os.getenv("CREATIVE_IMAGE_MODEL", "openai/gpt-image-2")
SUPPORTED_IMAGE_ASPECT_RATIOS = (
    "1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9",
)

PROMPT_SYSTEM = """Você é diretor de criação e especialista em mídia digital.
Transforme o briefing recebido em uma especificação de produção objetiva.
Respeite dimensões, área segura, mecânica, identidade da marca anunciante e
somente as referências autorizadas do canal parceiro. Não copie logos ou
interfaces de terceiros. Retorne JSON puro com:
{"prompt_en":"...", "rationale_pt":"...", "checks":["..."]}.
O prompt_en deve descrever composição, hierarquia, conteúdo, cores, iluminação,
texto permitido e restrições técnicas sem inventar preços ou claims."""

SCRIPT_SYSTEM = """Você é roteirista de publicidade digital premium.
Crie um roteiro que conecte exatamente quatro imagens na ordem informada.
Retorne JSON puro com:
{"title":"...", "duration_seconds":15, "voiceover_pt":"...",
"shots":[{"position":1,"seconds":"0-3","direction":"..."}],
"endcard":"..."}. Não cite plataformas como se fossem a marca anunciante."""


def _json_content(content):
    if not isinstance(content, str):
        raise OpenRouterError("O provedor retornou conteúdo inválido.")
    clean = content.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise OpenRouterError("O provedor não retornou JSON válido.") from exc
    if not isinstance(parsed, dict):
        raise OpenRouterError("O provedor retornou uma estrutura inválida.")
    return parsed


def _usage_cost(usage):
    if not isinstance(usage, dict):
        return None
    for key in ("cost", "total_cost", "cost_usd"):
        value = usage.get(key)
        if value is not None:
            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                continue
    return None


def _image_reference(value):
    """Normaliza URLs/data URLs para o contrato ContentPartImage do OpenRouter."""
    if isinstance(value, str) and value.startswith(("https://", "http://", "data:image/")):
        return {"type": "image_url", "image_url": {"url": value}}
    if isinstance(value, dict):
        image_url = value.get("image_url")
        if isinstance(image_url, str):
            return {"type": "image_url", "image_url": {"url": image_url}}
        if (
            value.get("type") == "image_url"
            and isinstance(image_url, dict)
            and isinstance(image_url.get("url"), str)
        ):
            return {
                "type": "image_url",
                "image_url": {"url": image_url["url"]},
            }
    raise ValueError("Referência de imagem inválida.")


def normalize_image_aspect_ratio(value):
    """Converte proporções de mídia para a opção suportada mais próxima."""
    value = str(value or "16:9").strip()
    if value in SUPPORTED_IMAGE_ASPECT_RATIOS:
        return value
    try:
        width, height = (float(part) for part in value.split(":", 1))
        target = width / height
        if width <= 0 or height <= 0:
            raise ValueError
    except (TypeError, ValueError, ZeroDivisionError):
        return "16:9"

    def distance(candidate):
        width, height = (float(part) for part in candidate.split(":", 1))
        return abs(math.log(target / (width / height)))

    return min(SUPPORTED_IMAGE_ASPECT_RATIOS, key=distance)


def _image_http_error(exc):
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "A credencial OpenRouter não foi aceita."
    if status == 402:
        return "O saldo da conta OpenRouter é insuficiente."
    if status == 429:
        return "O OpenRouter limitou as gerações. Aguarde e tente novamente."
    if status and status >= 500:
        return "O provedor de imagem está indisponível no momento."
    detail = ""
    try:
        payload = response.json()
        error = payload.get("error") or {}
        detail = error.get("message") if isinstance(error, dict) else str(error)
    except (AttributeError, TypeError, ValueError):
        detail = ""
    if status == 400 and detail:
        return f"O provedor recusou a imagem: {detail[:240]}"
    return "Não foi possível conectar ao provedor de imagem."


class CreativeGenerationClient:
    def __init__(self, text_callable=None, http=None):
        self.text_callable = text_callable or chat_completion
        self.http = http or requests

    def generate_prompt(self, context):
        response = self.text_callable(
            [
                {"role": "system", "content": PROMPT_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, default=str),
                },
            ],
            model=DEFAULT_TEXT_MODEL,
            max_tokens=1800,
            temperature=0.25,
        )
        result = _json_content(response["message"].get("content"))
        if not str(result.get("prompt_en") or "").strip():
            raise OpenRouterError("O provedor não gerou o prompt.")
        return {
            "result": result,
            "model": response.get("model") or DEFAULT_TEXT_MODEL,
            "usage": response.get("usage") or {},
            "actual_cost_usd": _usage_cost(response.get("usage")),
        }

    def generate_script(self, context):
        response = self.text_callable(
            [
                {"role": "system", "content": SCRIPT_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, default=str),
                },
            ],
            model=DEFAULT_TEXT_MODEL,
            max_tokens=1800,
            temperature=0.3,
        )
        result = _json_content(response["message"].get("content"))
        shots = result.get("shots")
        if not isinstance(shots, list) or len(shots) != 4:
            raise OpenRouterError("O roteiro deve conter exatamente quatro cenas.")
        return {
            "result": result,
            "model": response.get("model") or DEFAULT_TEXT_MODEL,
            "usage": response.get("usage") or {},
            "actual_cost_usd": _usage_cost(response.get("usage")),
        }

    def generate_image(
        self,
        prompt,
        input_references=None,
        aspect_ratio="16:9",
        quality="high",
        output_format="png",
        resolution="2K",
        background="opaque",
    ):
        raw_references = list(input_references or [])
        if len(raw_references) > 2:
            raise ValueError("Use no máximo duas imagens de referência.")
        references = [_image_reference(item) for item in raw_references]
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise OpenRouterError("OpenRouter não está configurado.")
        requested_aspect_ratio = aspect_ratio
        provider_aspect_ratio = normalize_image_aspect_ratio(aspect_ratio)
        payload = {
            "model": DEFAULT_IMAGE_MODEL,
            "prompt": prompt,
            "aspect_ratio": provider_aspect_ratio,
            "quality": quality,
            "output_format": output_format,
            "size": resolution,
            "background": background,
        }
        if references:
            payload["input_references"] = references
        try:
            response = self.http.post(
                OPENROUTER_IMAGE_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://centralcomm.media",
                    "X-Title": "CentralX - Modelagem de Criativos",
                },
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()
            images = data.get("data") or []
            encoded = images[0].get("b64_json") if images else None
            if not encoded:
                raise OpenRouterError("O provedor não retornou a imagem.")
            usage = data.get("usage") or {}
            return {
                "b64_json": encoded,
                "model": data.get("model") or DEFAULT_IMAGE_MODEL,
                "usage": usage,
                "actual_cost_usd": _usage_cost(usage),
                "output_format": output_format,
                "response_metadata": {
                    "id": data.get("id"),
                    "created": data.get("created"),
                    "requested_aspect_ratio": requested_aspect_ratio,
                    "provider_aspect_ratio": provider_aspect_ratio,
                },
            }
        except requests.HTTPError as exc:
            raise OpenRouterError(_image_http_error(exc)) from exc
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            raise OpenRouterError("Não foi possível gerar a imagem.") from exc


def build_higgsfield_payload(job_id, script, assets, aspect_ratio, duration):
    if len(assets) != 4:
        raise ValueError("Selecione exatamente quatro imagens aprovadas.")
    return {
        "external_job_id": str(job_id),
        "status": "ready_for_higgsfield",
        "aspect_ratio": aspect_ratio or "16:9",
        "duration_seconds": int(duration or 15),
        "script": script,
        "image_inputs": [
            {"position": index, "asset_url": asset["asset_url"]}
            for index, asset in enumerate(assets, start=1)
        ],
    }


def build_display_motion_payload(job_id, asset, aspect_ratio):
    if asset.get("asset_type") not in ("image", "mockup"):
        raise ValueError("A animação de display exige uma imagem estática.")
    return {
        "external_job_id": str(job_id),
        "status": "ready_for_higgsfield",
        "mode": "image_to_video",
        "aspect_ratio": aspect_ratio or "16:9",
        "duration_seconds": 3,
        "script": (
            "Animate this approved advertising creative for exactly 3 seconds. "
            "Preserve its layout, typography, brand colors, logo, product, CTA and "
            "advertising-format mechanism. Use restrained premium motion only: subtle "
            "depth, parallax, light movement and a clear interaction cue. Do not add, "
            "remove, rewrite or crop any content. End on the complete static keyframe."
        ),
        "image_inputs": [{"position": 1, "asset_url": asset["asset_url"]}],
        "source_asset_id": asset["id"],
    }
