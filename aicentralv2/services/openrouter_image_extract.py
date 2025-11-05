"""
OpenRouter Vision extraction service

Reads API key from environment (.env supported via project Config load) and sends an image to
OpenRouter chat/completions using a vision-capable model (default: anthropic/claude-3.5-sonnet).

Provides:
- extract_fields_from_image_bytes(image_bytes, filename=None, model=None) -> dict
- extract_fields_from_image_path(path, model=None) -> dict

Return shape (best-effort):
{
  "cliente": str,
  "pedido": str,
  "data": str,
  "valor_total": str,
  "_raw": <full response object or raw content string for troubleshooting>
}
"""
from __future__ import annotations
import base64
import json
import os
import mimetypes
from typing import Any, Dict, Optional
import requests

DEFAULT_MODEL = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')
API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
APP_REFERER = os.getenv('APP_REFERER', 'https://aicentral.local')
APP_TITLE = os.getenv('APP_TITLE', 'AIcentralv2 - Image Extraction')

PROMPT = (
    "Você é um extrator de dados visual especializado.\n\n"
    "Tarefa:\n"
    "A imagem fornecida sempre contém os seguintes campos em posições fixas:\n"
    "- Nome do cliente\n"
    "- Número do pedido\n"
    "- Data de emissão\n"
    "- Valor total\n\n"
    "Instruções:\n"
    "1. Leia o conteúdo da imagem cuidadosamente.\n"
    "2. Extraia apenas os campos listados.\n"
    "3. Retorne exclusivamente um JSON válido, no formato:\n\n"
    "{\n"
    "  \"cliente\": \"...\",\n"
    "  \"pedido\": \"...\",\n"
    "  \"data\": \"...\",\n"
    "  \"valor_total\": \"...\"\n"
    "}\n"
)


def _detect_mime_from_filename(filename: Optional[str]) -> str:
    if not filename:
        return 'image/png'
    mt, _ = mimetypes.guess_type(filename)
    if not mt:
        return 'image/png'
    if not mt.startswith('image/'):
        return 'image/png'
    return mt


essential_headers = lambda: {
    'Authorization': f'Bearer {API_KEY}',
    'HTTP-Referer': APP_REFERER,
    'X-Title': APP_TITLE,
    'Content-Type': 'application/json',
}


def _call_openrouter(image_b64: str, content_type: str, model: Optional[str] = None) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError('OPENROUTER_API_KEY não configurada no .env')

    payload = {
        'model': model or DEFAULT_MODEL,
        'messages': [
            {
                'role': 'user',
                'content': [
                    { 'type': 'text', 'text': PROMPT },
                    { 'type': 'image_url', 'image_url': f'data:{content_type};base64,{image_b64}' }
                ]
            }
        ],
        'max_tokens': 500,
    }
    resp = requests.post(OPENROUTER_URL, headers=essential_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _parse_response_to_json_fields(resp_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort parser supporting different OpenRouter content formats.
    Tries in order:
    - choices[0].message.content (string JSON)
    - choices[0].message.content[0].text (structured array)
    Then cleans code fences and json.loads.
    """
    raw = None
    content = None
    try:
        choice = (resp_obj or {}).get('choices', [{}])[0]
        message = (choice or {}).get('message', {})
        content = message.get('content')
        raw = content
        if isinstance(content, list) and content:
            # e.g., [{type:'output_text', text:'{...}'}]
            first = content[0]
            if isinstance(first, dict) and 'text' in first:
                content = first['text']
        # If content is dict (rare), convert to string
        if isinstance(content, dict):
            content = json.dumps(content)
        if not isinstance(content, str):
            # fallback: return raw
            return { '_raw': resp_obj }
        # Strip code fences
        txt = content.strip()
        if txt.startswith('```'):
            txt = txt.strip('`')
            # remove optional language prefix
            if '\n' in txt:
                txt = txt.split('\n', 1)[1]
        # Try to find a JSON object substring
        start = txt.find('{')
        end = txt.rfind('}')
        if start != -1 and end != -1 and end > start:
            txt = txt[start:end+1]
        data = json.loads(txt)
        # normalize keys
        result = {
            'cliente': data.get('cliente', ''),
            'pedido': data.get('pedido', ''),
            'data': data.get('data', ''),
            'valor_total': data.get('valor_total', ''),
            '_raw': resp_obj,
        }
        return result
    except Exception:
        return { '_raw': resp_obj, 'content': content }


def extract_fields_from_image_bytes(image_bytes: bytes, filename: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    content_type = _detect_mime_from_filename(filename)
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    resp = _call_openrouter(image_b64, content_type, model=model)
    return _parse_response_to_json_fields(resp)


def extract_fields_from_image_path(path: str, model: Optional[str] = None) -> Dict[str, Any]:
    with open(path, 'rb') as f:
        data = f.read()
    return extract_fields_from_image_bytes(data, filename=os.path.basename(path), model=model)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Uso: python -m aicentralv2.services.openrouter_image_extract <caminho_da_imagem>')
        sys.exit(1)
    image_path = sys.argv[1]
    out = extract_fields_from_image_path(image_path)
    print(json.dumps(out, ensure_ascii=False, indent=2))
