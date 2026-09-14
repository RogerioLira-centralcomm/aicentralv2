"""Cliente OpenRouter compartilhado pelo Agente CentralX e serviços legados."""
import os
import json
import base64
import requests
from typing import Dict, Any, List, Optional

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images"
OPENROUTER_VIDEO_URL = "https://openrouter.ai/api/v1/videos"
OPENROUTER_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
DEFAULT_IMAGE_MODEL = os.getenv("CREATIVE_IMAGE_MODEL", "openai/gpt-image-2")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


DEFAULT_CHAT_MODEL = os.getenv("AGENT_OPENROUTER_MODEL", "openai/gpt-4o-mini")
DEFAULT_TEMPERATURE = _env_float("AGENT_TEMPERATURE", 0.15)
DEFAULT_TOP_P = _env_float("AGENT_TOP_P", 0.9)
DEFAULT_TOP_K = _env_int("AGENT_TOP_K", 40)
DEFAULT_FREQUENCY_PENALTY = _env_float("AGENT_FREQUENCY_PENALTY", 0.1)
DEFAULT_PRESENCE_PENALTY = _env_float("AGENT_PRESENCE_PENALTY", 0.0)


class OpenRouterError(RuntimeError):
    """Erro seguro e recuperável do provedor."""


_SAMPLING_KEYS = (
    "temperature",
    "top_p",
    "top_k",
    "frequency_penalty",
    "presence_penalty",
)
_NO_SAMPLING_SLUGS = frozenset({"gpt-5", "gpt-5-mini", "gpt-5-nano"})


def model_omits_sampling(model=None) -> bool:
    """GPT-5 mini/nano e o-series recusam temperature/top_p/top_k no OpenAI."""
    slug = str(model or "").strip().lower()
    if "/" in slug:
        slug = slug.split("/", 1)[1]
    if slug in _NO_SAMPLING_SLUGS:
        return True
    if slug.startswith(("gpt-5-mini-", "gpt-5-nano-")):
        return True
    return slug.startswith(("o1", "o3", "o4-"))


def sanitize_chat_payload(payload):
    """Tira sampling que o provedor rejeita com 'Provider returned error'."""
    clean = dict(payload or {})
    if model_omits_sampling(clean.get("model")):
        for key in _SAMPLING_KEYS:
            clean.pop(key, None)
    return clean


def _provider_error_detail(error):
    if not isinstance(error, dict):
        return str(error or "").strip()
    metadata = error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
    raw = metadata.get("raw")
    if isinstance(raw, str) and raw.strip():
        try:
            inner = json.loads(raw)
        except ValueError:
            inner = None
        if isinstance(inner, dict):
            nested = inner.get("error") if isinstance(inner.get("error"), dict) else inner
            message = str(nested.get("message") or "").strip()
            if message:
                return message
    return str(error.get("message") or "").strip()


def _chat_error_message(response):
    status = getattr(response, "status_code", None)
    detail = ""
    try:
        payload = response.json() if response is not None else {}
        error = payload.get("error") if isinstance(payload, dict) else {}
        detail = _provider_error_detail(error)
    except (AttributeError, TypeError, ValueError):
        detail = ""
    detail = str(detail or "").strip()
    if status in (401, 403):
        return "A credencial OpenRouter não foi aceita."
    if status == 402:
        return "O saldo da conta OpenRouter é insuficiente."
    if status == 429:
        return "O OpenRouter limitou as gerações. Aguarde e tente novamente."
    if status and status >= 500:
        return "O provedor de IA está indisponível no momento."
    if detail:
        return f"O provedor recusou a consulta: {detail[:180]}"
    return "Não foi possível consultar o provedor de IA."


def resolve_api_key() -> str:
    try:
        from . import integration_credentials

        config = integration_credentials.get_configuration(
            "openrouter", include_secrets=True
        )
        key = str(config.get("api_key") or "").strip()
        if key:
            return key
    except Exception:
        pass
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def resolve_chat_model(explicit=None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    try:
        from . import integration_credentials

        config = integration_credentials.get_configuration("openrouter")
        model = str(config.get("default_model") or "").strip()
        if model:
            return model
    except Exception:
        pass
    return os.getenv("AGENT_OPENROUTER_MODEL", DEFAULT_CHAT_MODEL) or "openai/gpt-4o-mini"


def resolve_image_model(explicit=None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    try:
        from . import integration_credentials

        config = integration_credentials.get_configuration("openrouter")
        model = str(config.get("image_model") or "").strip()
        if model:
            return model
    except Exception:
        pass
    return os.getenv("CREATIVE_IMAGE_MODEL", DEFAULT_IMAGE_MODEL) or "openai/gpt-image-2"


def _api_key() -> str:
    key = resolve_api_key()
    if not key:
        raise OpenRouterError("OpenRouter não está configurado.")
    return key


def chat_completion(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    plugins: Optional[List[Dict[str, Any]]] = None,
    *,
    model: Optional[str] = None,
    timeout: int = 90,
    max_tokens: int = 2200,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    response_format: Optional[Dict[str, Any]] = None,
    reasoning: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Executa chat/tool-calling com parâmetros conservadores para uso operacional."""
    payload = {
        "model": resolve_chat_model(model),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": DEFAULT_TEMPERATURE if temperature is None else max(0.0, min(float(temperature), 2.0)),
        "top_p": DEFAULT_TOP_P if top_p is None else max(0.0, min(float(top_p), 1.0)),
        "top_k": DEFAULT_TOP_K if top_k is None else max(1, min(int(top_k), 100)),
        "frequency_penalty": (
            DEFAULT_FREQUENCY_PENALTY
            if frequency_penalty is None
            else max(-2.0, min(float(frequency_penalty), 2.0))
        ),
        "presence_penalty": (
            DEFAULT_PRESENCE_PENALTY
            if presence_penalty is None
            else max(-2.0, min(float(presence_penalty), 2.0))
        ),
        "stream": False,
        "usage": {"include": True},
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
        payload["parallel_tool_calls"] = False
    if plugins:
        payload["plugins"] = plugins
    if response_format:
        payload["response_format"] = response_format
    if reasoning:
        payload["reasoning"] = reasoning
    payload = sanitize_chat_payload(payload)
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "Agente CentralX",
        "X-OpenRouter-Title": "CentralX",
    }
    last_error = None
    last_response = None
    for attempt in range(2):
        try:
            response = requests.post(
                OPENROUTER_URL, headers=headers, json=payload,
                timeout=max(5, min(int(timeout), 90)),
            )
            last_response = response
            response.raise_for_status()
            result = response.json()
            message = result["choices"][0]["message"]
            return {
                "message": message,
                "model": result.get("model") or payload["model"],
                "usage": result.get("usage") or {},
            }
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            last_error = exc
            last_response = getattr(exc, "response", None) or last_response
            status = getattr(last_response, "status_code", None)
            if (
                attempt == 0
                and isinstance(exc, requests.RequestException)
                and (status is None or int(status) >= 500)
            ):
                continue
            break
    raise OpenRouterError(_chat_error_message(last_response)) from last_error


def _image_error_message(response):
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
        payload = response.json() if response is not None else {}
        error = payload.get("error") if isinstance(payload, dict) else {}
        detail = error.get("message") if isinstance(error, dict) else str(error or "")
    except (AttributeError, TypeError, ValueError):
        detail = ""
    if status == 400 and detail:
        return f"O provedor recusou a imagem: {str(detail)[:240]}"
    return "Não foi possível gerar a imagem."


def _video_error_message(response):
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "A credencial OpenRouter não foi aceita."
    if status == 402:
        return "O saldo da conta OpenRouter é insuficiente."
    if status == 429:
        return "O OpenRouter limitou as gerações. Aguarde e tente novamente."
    if status and status >= 500:
        return "O provedor de vídeo está indisponível no momento."
    detail = ""
    try:
        payload = response.json() if response is not None else {}
        error = payload.get("error") if isinstance(payload, dict) else {}
        detail = str(error.get("message") or error.get("code") or "")
    except (AttributeError, TypeError, ValueError):
        detail = ""
    lower = detail.lower()
    if is_real_person_block(detail):
        return "O Seedance recusou o still: a imagem parece ter uma pessoa real."
    if "only https" in lower or "invalid reference url" in lower:
        return "A referência de vídeo precisa ser uma URL HTTPS pública. Data URL e URL autenticada não entram."
    if "resource download failed" in lower:
        return "O Seedance não conseguiu baixar o vídeo de referência. Use uma URL HTTPS pública."
    if status == 400 and detail:
        return f"O provedor recusou o vídeo: {detail[:240]}"
    return "Não foi possível enviar o vídeo."


def is_real_person_block(exc_or_text):
    """True quando o provedor (Seedance) recusa still com pessoa real."""
    text = str(getattr(exc_or_text, "args", [exc_or_text])[0] if not isinstance(exc_or_text, str) else exc_or_text)
    if not text and exc_or_text is not None:
        text = str(exc_or_text)
    lower = text.lower()
    return (
        "pessoa real" in lower
        or "real person" in lower
        or "privacyinformation" in lower
    )


GPT_IMAGE_BACKGROUNDS = frozenset({"auto", "opaque"})


def sanitize_image_payload(payload):
    """Remove parâmetros que o modelo recusa — GPT Image 2 não aceita fundo transparente."""
    clean = dict(payload or {})
    model = str(clean.get("model") or "").strip()
    background = str(clean.get("background") or "").strip().lower()
    if model.startswith("openai/gpt-image") and background not in GPT_IMAGE_BACKGROUNDS:
        clean["background"] = "opaque"
    return clean


def image_reference(value):
    """Normaliza URL/data URL para o contrato ContentPartImage do OpenRouter."""
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
            return {"type": "image_url", "image_url": {"url": image_url["url"]}}
    raise ValueError("Referência de imagem inválida.")


def build_image_payload(
    prompt: str,
    *,
    aspect_ratio: str = "16:9",
    quality: str = "high",
    output_format: str = "png",
    resolution: str = "2K",
    background: str = "opaque",
    model: Optional[str] = None,
    input_references=None,
) -> Dict[str, Any]:
    resolved = resolve_image_model(model)
    payload = sanitize_image_payload({
        "model": resolved,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio or "16:9",
        "quality": quality,
        "output_format": output_format,
        "resolution": resolution,
        "background": background,
    })
    if "gemini-3" in resolved or "seedream" in resolved:
        payload.pop("quality", None)
        payload.pop("background", None)
    refs = []
    for item in list(input_references or [])[:2]:
        try:
            refs.append(image_reference(item))
        except ValueError:
            continue
    if refs:
        payload["input_references"] = refs
    return payload


def generate_image(
    prompt: str,
    *,
    aspect_ratio: str = "16:9",
    quality: str = "high",
    output_format: str = "png",
    resolution: str = "2K",
    background: str = "opaque",
    model: Optional[str] = None,
    timeout: int = 180,
    input_references=None,
) -> Dict[str, Any]:
    """Gera imagem no GPT Image 2 via OpenRouter (`/api/v1/images`)."""
    payload = build_image_payload(
        prompt,
        aspect_ratio=aspect_ratio,
        quality=quality,
        output_format=output_format,
        resolution=resolution,
        background=background,
        model=model,
        input_references=input_references,
    )
    image_model = payload.get("model") or resolve_image_model(model)
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralX - Smart Planner",
        "X-OpenRouter-Title": "CentralX",
    }
    try:
        response = requests.post(
            OPENROUTER_IMAGE_URL,
            headers=headers,
            json=payload,
            timeout=max(30, min(int(timeout), 180)),
        )
        response.raise_for_status()
        data = response.json()
        images = data.get("data") or []
        first = images[0] if images else {}
        encoded = first.get("b64_json") if isinstance(first, dict) else None
        url = first.get("url") if isinstance(first, dict) else None
        if not encoded and url:
            fetched = requests.get(url, timeout=60)
            fetched.raise_for_status()
            encoded = base64.b64encode(fetched.content).decode("ascii")
        if not encoded:
            raise OpenRouterError("O provedor não retornou a imagem.")
        return {
            "b64_json": encoded,
            "model": data.get("model") or image_model,
            "usage": data.get("usage") or {},
            "output_format": output_format,
        }
    except OpenRouterError:
        raise
    except requests.HTTPError as exc:
        raise OpenRouterError(_image_error_message(getattr(exc, "response", None))) from exc
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        raise OpenRouterError("Não foi possível gerar a imagem.") from exc


DEFAULT_VIDEO_MODEL = os.getenv("CREATIVE_VIDEO_MODEL", "bytedance/seedance-2.5")
VIDEO_MAX_BYTES = _env_int("CREATIVE_VIDEO_MAX_BYTES", 80 * 1024 * 1024)


def build_video_payload(
    prompt: str,
    *,
    model: Optional[str] = None,
    duration: int = 8,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    size: Optional[str] = None,
    generate_audio: bool = False,
    frame_images=None,
    input_references=None,
    seed=None,
    watermark: bool = False,
    req_key: Optional[str] = None,
    output_format: str = "mp4",
) -> Dict[str, Any]:
    """Monta o body de `POST /api/v1/videos`. Não mistura frame_images com refs."""
    frames = [item for item in list(frame_images or []) if isinstance(item, dict)][:2]
    refs = [item for item in list(input_references or []) if isinstance(item, dict)]
    if frames and refs:
        raise ValueError("Não envie frame_images e input_references no mesmo pedido.")
    payload = {
        "model": (model or DEFAULT_VIDEO_MODEL).strip() or DEFAULT_VIDEO_MODEL,
        "prompt": prompt,
        "duration": max(4, min(int(duration or 8), 30)),
        "generate_audio": bool(generate_audio),
    }
    if size:
        payload["size"] = str(size)
    else:
        payload["resolution"] = resolution or "720p"
        payload["aspect_ratio"] = aspect_ratio or "16:9"
    if frames:
        payload["frame_images"] = frames
    if refs:
        payload["input_references"] = refs
    if seed not in (None, ""):
        payload["seed"] = int(seed)
    parameters = {
        "watermark": bool(watermark),
        "output_format": output_format or "mp4",
    }
    if req_key:
        parameters["req_key"] = str(req_key)
    payload["provider"] = {"options": {"seed": {"parameters": parameters}}}
    return payload


def generate_video(
    prompt: str,
    *,
    model: Optional[str] = None,
    duration: int = 5,
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    size: Optional[str] = None,
    generate_audio: bool = False,
    frame_images=None,
    input_references=None,
    seed=None,
    req_key: Optional[str] = None,
    watermark: bool = False,
    timeout: int = 90,
) -> Dict[str, Any]:
    """Submete vídeo assíncrono no OpenRouter (`POST /api/v1/videos`)."""
    payload = build_video_payload(
        prompt,
        model=model,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        size=size,
        generate_audio=generate_audio,
        frame_images=frame_images,
        input_references=input_references,
        seed=seed,
        watermark=watermark,
        req_key=req_key,
    )
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralX - Studio",
        "X-OpenRouter-Title": "CentralX",
    }
    try:
        response = requests.post(
            OPENROUTER_VIDEO_URL,
            headers=headers,
            json=payload,
            timeout=max(15, min(int(timeout), 90)),
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        return {
            "id": data.get("id") or "",
            "polling_url": data.get("polling_url") or "",
            "status": data.get("status") or "pending",
            "generation_id": data.get("generation_id") or "",
            "model": payload["model"],
            "usage": data.get("usage") or {},
        }
    except requests.HTTPError as exc:
        raise OpenRouterError(_video_error_message(getattr(exc, "response", None))) from exc
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise OpenRouterError("Não foi possível enviar o vídeo.") from exc


def poll_video(job_id: str, polling_url: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    """Consulta o job de vídeo no OpenRouter."""
    url = str(polling_url or "").strip() or f"{OPENROUTER_VIDEO_URL}/{job_id}"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralX - Studio",
    }
    try:
        response = requests.get(url, headers=headers, timeout=max(10, min(int(timeout), 90)))
        response.raise_for_status()
        data = response.json() if response.content else {}
        return {
            "id": data.get("id") or job_id,
            "status": data.get("status") or "pending",
            "generation_id": data.get("generation_id") or "",
            "polling_url": data.get("polling_url") or url,
            "unsigned_urls": list(data.get("unsigned_urls") or []),
            "error": data.get("error") or "",
            "usage": data.get("usage") or {},
            "model": data.get("model") or "",
        }
    except requests.HTTPError as exc:
        raise OpenRouterError(_video_error_message(getattr(exc, "response", None))) from exc
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise OpenRouterError("Não foi possível consultar o vídeo.") from exc


def is_mp4_bytes(payload: bytes) -> bool:
    return isinstance(payload, (bytes, bytearray)) and len(payload) >= 12 and payload[4:8] == b"ftyp"


def download_video(job_id: str, *, index: int = 0, timeout: int = 120) -> bytes:
    """Baixa o MP4 com a API key. As unsigned_urls exigem Authorization."""
    ident = str(job_id or "").strip()
    if not ident:
        raise OpenRouterError("O job de vídeo não tem identificador.")
    url = f"{OPENROUTER_VIDEO_URL}/{ident}/content"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralX - Studio",
    }
    try:
        response = requests.get(
            url,
            headers=headers,
            params={"index": max(0, int(index or 0))},
            timeout=max(15, min(int(timeout), 180)),
            stream=True,
        )
        response.raise_for_status()
        chunks = []
        total = 0
        for chunk in response.iter_content(64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > VIDEO_MAX_BYTES:
                raise OpenRouterError("O vídeo retornado excede o tamanho permitido.")
            chunks.append(chunk)
        data = b"".join(chunks)
        if not is_mp4_bytes(data):
            raise OpenRouterError("O provedor não devolveu um MP4 válido.")
        return data
    except OpenRouterError:
        raise
    except requests.HTTPError as exc:
        raise OpenRouterError(_video_error_message(getattr(exc, "response", None))) from exc
    except (requests.RequestException, ValueError) as exc:
        raise OpenRouterError("Não foi possível baixar o vídeo.") from exc


DEFAULT_SPEECH_MODEL = os.getenv("CREATIVE_TTS_MODEL", "google/gemini-3.1-flash-tts-preview")
AUDIO_MAX_BYTES = _env_int("CREATIVE_AUDIO_MAX_BYTES", 20 * 1024 * 1024)


def is_audio_bytes(payload: bytes) -> bool:
    if not isinstance(payload, (bytes, bytearray)) or len(payload) < 12:
        return False
    if payload[:3] == b"ID3" or payload[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"):
        return True
    if payload[:4] == b"RIFF" and payload[8:12] == b"WAVE":
        return True
    if payload[:4] == b"fLaC" or payload[:4] == b"OggS":
        return True
    return False


def _pcm_to_wav(pcm: bytes, *, rate: int = 24000, channels: int = 1, width: int = 2) -> bytes:
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def generate_speech(
    text: str,
    *,
    model: Optional[str] = None,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    response_format: str = "mp3",
    timeout: int = 90,
) -> bytes:
    """Sintetiza locução em `POST /api/v1/audio/speech`. Devolve WAV ou MP3."""
    script = str(text or "").strip()
    if not script:
        raise OpenRouterError("O roteiro da locução está vazio.")
    payload = {
        "model": (model or DEFAULT_SPEECH_MODEL).strip() or DEFAULT_SPEECH_MODEL,
        "input": script,
        "voice": str(voice or "Charon").strip() or "Charon",
        "response_format": response_format or "mp3",
    }
    if speed not in (None, ""):
        payload["speed"] = float(speed)
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralX - Studio",
    }
    try:
        response = requests.post(
            OPENROUTER_SPEECH_URL,
            headers=headers,
            json=payload,
            timeout=max(15, min(int(timeout), 90)),
        )
        response.raise_for_status()
        data = response.content or b""
        if len(data) > AUDIO_MAX_BYTES:
            raise OpenRouterError("O áudio retornado excede o tamanho permitido.")
        ctype = str(response.headers.get("Content-Type") or "").lower()
        if "json" in ctype or data[:1] in (b"{", b"["):
            raise OpenRouterError(_speech_error_message(response))
        if "pcm" in ctype or "l16" in ctype:
            data = _pcm_to_wav(data)
        if not is_audio_bytes(data):
            raise OpenRouterError("O provedor não devolveu um áudio válido.")
        return data
    except OpenRouterError:
        raise
    except requests.HTTPError as exc:
        raise OpenRouterError(_speech_error_message(getattr(exc, "response", None))) from exc
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise OpenRouterError("Não foi possível gerar a locução.") from exc


def _speech_error_message(response):
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "A credencial OpenRouter não foi aceita."
    if status == 402:
        return "O saldo da conta OpenRouter é insuficiente."
    if status == 429:
        return "O OpenRouter limitou as gerações. Aguarde e tente novamente."
    if status and status >= 500:
        return "O provedor de áudio está indisponível no momento."
    detail = ""
    try:
        payload = response.json() if response is not None else {}
        error = payload.get("error") if isinstance(payload, dict) else {}
        detail = error.get("message") if isinstance(error, dict) else str(error or "")
    except (AttributeError, TypeError, ValueError):
        detail = ""
    if status == 400 and detail:
        return f"O provedor recusou a locução: {str(detail)[:240]}"
    return "Não foi possível gerar a locução."


# Prompt otimizado para transformar texto em FAQ estruturado
ANALYSIS_PROMPT = {
    "system": """Você é um especialista em análise e estruturação de documentos corporativos.
Sua tarefa é analisar textos e transformá-los em um FAQ abrangente e bem estruturado.

Regras de processamento:
1. Mantenha o contexto técnico e profissional
2. Identifique os principais conceitos e definições
3. Estruture em formato de perguntas e respostas claras
4. Agrupe informações relacionadas
5. Preserve termos técnicos importantes
6. Mantenha um tom profissional e objetivo
7. Inclua exemplos práticos quando relevante
8. Organize do mais geral para o mais específico
9. Mantenha referência a dados e métricas importantes
10. Inclua uma seção de conceitos-chave no início

Formato de saída:
# Conceitos-Chave
[Liste 3-5 conceitos fundamentais do texto]

# FAQ
Q: [Pergunta clara e direta]
A: [Resposta detalhada e estruturada]

[Continue com mais perguntas e respostas, organizadas por temas]""",
    "max_tokens": 4000,
    "temperature": 0.3
}

def process_text_with_gemini(text: str) -> Dict[str, Any]:
    """
    Processa um texto usando o modelo Gemini através do OpenRouter.
    
    Args:
        text: Texto a ser processado
        
    Returns:
        Dict com o texto processado e metadados
    """
    try:
        key = _api_key()
    except OpenRouterError as exc:
        return {
            "success": False,
            "error": str(exc),
            "processed_text": text,
            "metadata": {"error_details": str(exc)},
        }
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralComm AI"
    }
    
    messages = [
        {
            "role": "system",
            "content": ANALYSIS_PROMPT["system"]
        },
        {
            "role": "user",
            "content": f"Analise e estruture o seguinte texto em formato FAQ:\n\n{text}"
        }
    ]
    
    payload = {
        "model": "google/gemini-pro",  # Usando Gemini Pro para melhor processamento de texto
        "messages": messages,
        "max_tokens": ANALYSIS_PROMPT["max_tokens"],
        "temperature": ANALYSIS_PROMPT["temperature"]
    }
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=180  # Timeout aumentado para textos longos
        )
        
        response.raise_for_status()
        result = response.json()
        
        processed_text = result['choices'][0]['message']['content']
        
        return {
            'success': True,
            'processed_text': processed_text,
            'metadata': {
                'model': result.get('model', 'google/gemini-pro'),
                'usage': result.get('usage', {}),
                'processing_stats': {
                    'tokens': result.get('usage', {}).get('total_tokens', 0)
                }
            }
        }
        
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': str(e),
            'processed_text': text,  # Retorna texto original em caso de erro
            'metadata': {
                'error_details': str(e)
            }
        }

# Função auxiliar para processar textos muito longos em chunks
def process_large_text(text: str, max_chunk_size: int = 8000) -> str:
    """
    Processa textos longos dividindo em chunks e mantendo contexto.
    
    Args:
        text: Texto completo
        max_chunk_size: Tamanho máximo de cada chunk
        
    Returns:
        Texto processado completo
    """
    if len(text) <= max_chunk_size:
        result = process_text_with_gemini(text)
        return result['processed_text'] if result['success'] else text
    
    # Dividir em chunks preservando parágrafos
    chunks = []
    current_chunk = []
    current_size = 0
    
    for paragraph in text.split('\n\n'):
        if current_size + len(paragraph) > max_chunk_size:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
        
        current_chunk.append(paragraph)
        current_size += len(paragraph) + 2  # +2 para \n\n
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    # Processar cada chunk
    processed_chunks = []
    for i, chunk in enumerate(chunks):
        context = f"Este é o segmento {i+1} de {len(chunks)} do documento. "
        chunk_with_context = context + chunk
        
        result = process_text_with_gemini(chunk_with_context)
        if result['success']:
            processed_chunks.append(result['processed_text'])
        else:
            processed_chunks.append(chunk)
    
    # Combinar resultados
    return "\n\n# Próxima Seção\n\n".join(processed_chunks)