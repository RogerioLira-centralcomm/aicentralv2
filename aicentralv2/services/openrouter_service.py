"""Cliente OpenRouter compartilhado pelo Agente CentralX e serviços legados."""
import os
import json
import base64
import requests
from typing import Dict, Any, List, Optional

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images"
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


def _chat_error_message(response):
    status = getattr(response, "status_code", None)
    detail = ""
    try:
        payload = response.json() if response is not None else {}
        error = payload.get("error") if isinstance(payload, dict) else {}
        detail = error.get("message") if isinstance(error, dict) else str(error or "")
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
            if attempt == 0 and isinstance(exc, requests.RequestException):
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


GPT_IMAGE_BACKGROUNDS = frozenset({"auto", "opaque"})


def sanitize_image_payload(payload):
    """Remove parâmetros que o modelo recusa — GPT Image 2 não aceita fundo transparente."""
    clean = dict(payload or {})
    model = str(clean.get("model") or "").strip()
    background = str(clean.get("background") or "").strip().lower()
    if model.startswith("openai/gpt-image") and background not in GPT_IMAGE_BACKGROUNDS:
        clean["background"] = "opaque"
    return clean


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
) -> Dict[str, Any]:
    """Gera imagem no GPT Image 2 via OpenRouter (`/api/v1/images`)."""
    image_model = resolve_image_model(model)
    payload = sanitize_image_payload({
        "model": image_model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio or "16:9",
        "quality": quality,
        "output_format": output_format,
        "resolution": resolution,
        "background": background,
    })
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