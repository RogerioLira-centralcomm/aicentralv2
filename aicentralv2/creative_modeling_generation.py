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
texto permitido e restrições técnicas sem inventar preços ou claims.
Quando context.locks existir, o prompt_en DEVE abrir com um bloco LOCK listando
headline, subhead, CTA e demais linhas de forma literal. Não reescreva, traduza
nem omita essas strings.
Quando client_identity.profile.creative_line existir, trate-a como sistema visual
aprendido de campanhas reais: preserve assinatura, composição, imagem, recursos
recorrentes e copy_system (estrutura de título, densidade, tipografia, zonas e
padrão de CTA), mas nunca recicle ofertas ou textos antigos. Inclua integralmente
gpt_image_instruction no prompt final para o GPT Image 2.
O prompt deve exigir explicitamente que toda copy publicitária visível esteja em
português do Brasil, sem slogans em inglês inventados. Nomes registrados de
marca ou produto podem ser preservados."""

SCENE_BEAT_SYSTEM = """Você escreve o roteiro de UMA batida de um criativo
animado ou interativo. As cenas 1–N são o mesmo anúncio, do primeiro ao último
quadro — não variações da cena 1 e não um recorte novo da mesma composição.
Cada batida tem um papel em format.direction.beats. Gere um prompt completo
para ESTE quadro: o que está na tela agora, o que a mecânica faz neste instante
e quais elementos (título, gancho, texto, imagem, fundo, logo, CTA) existem
neste formato e nesta batida. CTA só entra se o formato tiver CTA e o beat
permitir. O canvas é exatamente format.direction.size_label em pixels.
Respeite format.direction.orientation (horizontal, vertical ou quadrado) e
format.direction.layout: cada elemento senta no slot modelado (visual,
headline, CTA, logo). Um banner horizontal não usa a grade de um story
vertical. Não invente outra composição.
Preserve a bíblia visual e o DNA da marca. Não recicle a composição anterior.
A mensagem da campanha, a oferta do pack e o CTA são trava: não invente
história, produto ou benefício paralelos. Proibido raios, partículas, redes
neurais, glow de conexão e still com cara de IA.
Se campaign_pack existir, ele é a oferta desta campanha: use extracted e as
imagens do pack. Logo e cores só assinam. creative_line não recicla oferta.
Retorne JSON puro com:
{"prompt_en":"...", "rationale_pt":"...", "checks":["..."]}.
O prompt_en fica em inglês técnico. Toda copy visível em português do Brasil."""

ADAPT_SCENE_SYSTEM = SCENE_BEAT_SYSTEM

SCRIPT_SYSTEM = """Você é roteirista de publicidade digital premium.
Crie um roteiro que conecte exatamente quatro imagens na ordem informada.
Retorne JSON puro com:
{"title":"...", "duration_seconds":15, "voiceover_pt":"...",
"shots":[{"position":1,"seconds":"0-3","direction":"..."}],
"endcard":"..."}. Não cite plataformas como se fossem a marca anunciante."""

BRIEF_SYSTEM = """Você é estrategista e diretor de criação publicitária.
Reescreva o briefing em português do Brasil sem inventar ofertas, preços,
benefícios ou alegações. As cenas são batidas do MESMO anúncio, do gancho ao
fechamento — nunca variações da primeira. Use format.direction.beats como
roteiro da mecânica (hotspot, reveal, flip, quiz, compare, carrossel, vídeo)
NESTE retângulo: format.direction.orientation e format.direction.layout
dizem se o formato é horizontal ou vertical e onde sentam visual, título,
logo e CTA. Cenas de um leaderboard raso não são as de um story 9:16.
CTA só na última batida e só se format.direction marcar CTA. Respeite
format.direction.size_label. Retorne somente JSON puro:
{"campaign_text":"...", "cta_text":"...", "visual_bible":"...",
"scenes":[{"position":1,"role":"gancho","description":"..."}]}.
Para quatro cenas, use os roles dos beats do formato. Para uma cena, use
composição_final. Descreva toda copy visível em português do Brasil e preserve
nomes próprios da marca. Se campaign_pack existir, ele é o material principal
desta campanha (criativos, link, headline, oferta, CTA). Identidade da marca
(logo, cores, tom) só assina a peça. Se o perfil trouxer uma creative_line
aprendida, use só a assinatura visual — nunca recicle oferta, composição ou
copy de outra campanha. Proibido raios, partículas, redes neurais e still
com cara de IA. Cada cena continua o mesmo anúncio neste retângulo."""

IMAGE_REVIEW_SYSTEM = """Você é revisor de qualidade de publicidade digital.
Analise a imagem contra o briefing informado. Não presuma falhas que não estejam
visíveis. Retorne somente JSON puro:
{"approved_recommendation":true,"score":0,"warnings":[],
"defects":[],
"checks":{"language_pt_br":true,"cta_correct":true,"brand_consistent":true,
"price_authorized":true,"continuity":true,"safe_area":true,
"text_locked":true,"cta_locked":true,"logo_locked":true}}.
O score deve ser inteiro de 0 a 100. Cada warning deve ser curto, em português,
e explicar uma correção acionável.
defects deve ser uma lista com zero ou mais destes códigos:
dangling_line, icon_bar, cta_overflow, wrong_canvas, extra_chrome,
text_rewritten, cta_changed, logo_missing.
Se o canvas gerado não coincidir com o retângulo-alvo (target_size),
inclua wrong_canvas e marque safe_area como false.
safe_area não pode ser true quando wrong_canvas estiver presente.
Quando context.locks existir: text_locked/cta_locked/logo_locked só são true
se o texto, o CTA e a marca visíveis forem literais. Se o CTA sumiu ou mudou,
cta_locked=false e inclua cta_changed. Se a copy foi reescrita, inclua
text_rewritten. Se havia logo e sumiu, logo_locked=false e logo_missing."""


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


def text_temperature(name, default):
    env = os.getenv(f"CREATIVE_TEMP_{str(name or '').upper()}", "").strip()
    if env:
        try:
            return max(0.0, min(2.0, float(env)))
        except ValueError:
            pass
    return default


TEXT_TEMPERATURES = {
    "prompt": 0.25,
    "script": 0.3,
    "brief": 0.35,
    "review": 0.1,
    "extract_kv_locks": 0.05,
    "unfold_prompt": 0.20,
    "ab_simple_prompt": 0.30,
    "ab_max_prompt": 0.45,
    "review_locks": 0.10,
}


class CreativeGenerationClient:
    def __init__(self, text_callable=None, http=None):
        self.text_callable = text_callable or chat_completion
        self.http = http or requests

    def generate_prompt(self, context):
        from .creative_modeling_prompts import UNFOLD_PROMPT_SYSTEM

        context = context if isinstance(context, dict) else {}
        if context.get("flow_kind") == "unfold":
            system = UNFOLD_PROMPT_SYSTEM
            temperature = text_temperature("unfold_prompt", TEXT_TEMPERATURES["unfold_prompt"])
        elif context.get("flow_kind") != "unfold":
            system = SCENE_BEAT_SYSTEM
            temperature = text_temperature("prompt", TEXT_TEMPERATURES["prompt"])
        else:
            system = PROMPT_SYSTEM
            temperature = text_temperature("prompt", TEXT_TEMPERATURES["prompt"])
        response = self.text_callable(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, default=str),
                },
            ],
            model=DEFAULT_TEXT_MODEL,
            max_tokens=1800,
            temperature=temperature,
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

    def extract_kv_locks(self, context, image_data_url=None):
        from .creative_modeling_prompts import UNFOLD_LOCK_SYSTEM

        user_content = json.dumps(context, ensure_ascii=False, default=str)
        message = {"role": "user", "content": user_content}
        if image_data_url:
            message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    _image_reference(image_data_url),
                ],
            }
        response = self.text_callable(
            [
                {"role": "system", "content": UNFOLD_LOCK_SYSTEM},
                message,
            ],
            model=DEFAULT_TEXT_MODEL,
            max_tokens=800,
            temperature=text_temperature(
                "extract_kv_locks", TEXT_TEMPERATURES["extract_kv_locks"]
            ),
        )
        result = _json_content(response["message"].get("content"))
        return {
            "result": result,
            "model": response.get("model") or DEFAULT_TEXT_MODEL,
            "usage": response.get("usage") or {},
            "actual_cost_usd": _usage_cost(response.get("usage")),
        }

    def generate_ab_prompt(self, context, level):
        from .creative_modeling_prompts import UNFOLD_AB_MAX, UNFOLD_AB_SIMPLE

        level = "ab_max" if str(level or "") in {"ab_max", "max", "maximum"} else "ab_simple"
        system = UNFOLD_AB_MAX if level == "ab_max" else UNFOLD_AB_SIMPLE
        key = "ab_max_prompt" if level == "ab_max" else "ab_simple_prompt"
        response = self.text_callable(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, default=str),
                },
            ],
            model=DEFAULT_TEXT_MODEL,
            max_tokens=1200,
            temperature=text_temperature(key, TEXT_TEMPERATURES[key]),
        )
        result = _json_content(response["message"].get("content"))
        if not str(result.get("prompt_en") or "").strip():
            raise OpenRouterError("O provedor não gerou o prompt da variação.")
        result["variant_level"] = level
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
            temperature=text_temperature("script", TEXT_TEMPERATURES["script"]),
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

    def generate_campaign_brief(self, context):
        response = self.text_callable(
            [
                {"role": "system", "content": BRIEF_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, default=str),
                },
            ],
            model=DEFAULT_TEXT_MODEL,
            max_tokens=2200,
            temperature=text_temperature("brief", TEXT_TEMPERATURES["brief"]),
        )
        result = _json_content(response["message"].get("content"))
        return {
            "result": result,
            "model": response.get("model") or DEFAULT_TEXT_MODEL,
            "usage": response.get("usage") or {},
            "actual_cost_usd": _usage_cost(response.get("usage")),
        }

    def review_image(self, context, image_data_url):
        response = self.text_callable(
            [
                {"role": "system", "content": IMAGE_REVIEW_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                context, ensure_ascii=False, default=str
                            ),
                        },
                        _image_reference(image_data_url),
                    ],
                },
            ],
            model=DEFAULT_TEXT_MODEL,
            max_tokens=900,
            temperature=text_temperature(
                "review_locks" if isinstance(context, dict) and context.get("locks") else "review",
                TEXT_TEMPERATURES["review_locks"] if isinstance(context, dict) and context.get("locks") else TEXT_TEMPERATURES["review"],
            ),
        )
        result = _json_content(response["message"].get("content"))
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
            "resolution": resolution,
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
                    "quality": quality,
                    "resolution": resolution,
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
