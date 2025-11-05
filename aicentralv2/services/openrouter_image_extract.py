"""
OpenRouter Vision extraction service

Reads API key from environment (.env supported via project Config load) and sends an image to
OpenRouter chat/completions using a vision-capable model (default: google/gemini-1.5-pro),
with smart fallbacks to other Gemini IDs (e.g., -latest, 1.5-flash, 2.0-flash-exp).

Provides:
- extract_fields_from_image_bytes(image_bytes, filename=None, model=None, prompt=None) -> dict
- extract_fields_from_image_path(path, model=None, prompt=None) -> dict

Return shape (best-effort): a dict parsed from the model output according to the provided prompt.
On success we return the parsed JSON object augmented with the key "_raw" containing the full
OpenRouter response for cost/usage inspection. On failure to parse JSON, we return:
{
    "_raw": <full OpenRouter response>,
    "content": <original textual content if available>
}
"""
from __future__ import annotations
import base64
import json
import os
import mimetypes
from typing import Any, Dict, Optional, List, Tuple
import requests

DEFAULT_MODEL = os.getenv('OPENROUTER_MODEL', 'google/gemini-1.5-flash-8b')
SECONDARY_VISION_MODEL = os.getenv('OPENROUTER_MODEL_FALLBACK', 'google/gemini-1.5-flash-8b')
API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
APP_REFERER = os.getenv('APP_REFERER', 'https://aicentral.local')
APP_TITLE = os.getenv('APP_TITLE', 'AIcentralv2 - Image Extraction')

# Note: Prompt must be provided by the caller (textarea). This placeholder is unused.
PROMPT = ""


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


def get_available_models() -> List[Dict[str, str]]:
    """Return a list of available LLM models for selection (id + label).
    Tries to fetch from OpenRouter; falls back to a curated Gemini list.
    """
    curated = [
        { 'id': 'google/gemini-1.5-flash-8b', 'label': 'google/Gemini 1.5 Flash 8B (recomendado)' },
        { 'id': 'google/gemini-1.5-flash-latest', 'label': 'google/Gemini 1.5 Flash (latest)' },
        { 'id': 'google/gemini-1.5-pro-latest', 'label': 'google/Gemini 1.5 Pro (latest)' },
        { 'id': 'google/gemini-1.5-pro', 'label': 'google/Gemini 1.5 Pro' },
        { 'id': 'google/gemini-1.5-flash', 'label': 'google/Gemini 1.5 Flash' },
    ]
    try:
        r = requests.get('https://openrouter.ai/api/v1/models', headers=essential_headers(), timeout=15)
        if r.status_code != 200:
            return curated
        data = r.json() or {}
        items = data.get('data') or data.get('models') or []
        models: List[Dict[str, str]] = []
        seen: set = set()
        for it in items:
            if not isinstance(it, dict):
                continue
            mid = it.get('id')
            name = it.get('name') or it.get('id')
            if not mid or not isinstance(mid, str):
                continue
            if 'google/' in mid and 'gemini' in mid:
                # Keep only Gemini for now
                if mid not in seen:
                    models.append({ 'id': mid, 'label': name })
                    seen.add(mid)
        # Ensure curated defaults are present at top if not already
        final = []
        existing_ids = {m['id'] for m in models}
        for c in curated:
            if c['id'] not in existing_ids:
                final.append(c)
        final.extend(models)
        return final
    except Exception:
        return curated


def _call_openrouter(image_b64: str, content_type: str, model: Optional[str] = None, prompt_text: Optional[str] = None) -> Dict[str, Any]:
    if not API_KEY:
        raise RuntimeError('OPENROUTER_API_KEY não configurada no .env')
    if not prompt_text or not prompt_text.strip():
        raise ValueError('Prompt não informado')

    # Normaliza aliases de modelos para IDs válidos da OpenRouter
    def _normalize_model_id(m: Optional[str]) -> Optional[str]:
        if not m:
            return m
        alias_map = {
            'google/gemini-pro-vision': 'google/gemini-1.5-pro',
            'google/gemini-pro': 'google/gemini-1.5-pro',
            'gemini-pro-vision': 'google/gemini-1.5-pro',
            'gemini-pro': 'google/gemini-1.5-pro',
            # também normaliza -latest para a base (a lista de candidatos incluirá os -latest explicitamente)
            'google/gemini-1.5-pro-latest': 'google/gemini-1.5-pro',
            'google/gemini-1.5-flash-latest': 'google/gemini-1.5-flash',
            # nomes amigáveis
            'google/Gemini 1.5 Flash 8B': 'google/gemini-1.5-flash-8b',
            'Gemini 1.5 Flash 8B': 'google/gemini-1.5-flash-8b',
            'gemini 1.5 flash 8b': 'google/gemini-1.5-flash-8b',
        }
        m2 = alias_map.get(m.strip(), m.strip())
        return m2

    def _build_payload(m: str) -> Dict[str, Any]:
        return {
            'model': m,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        { 'type': 'text', 'text': prompt_text },
                        { 'type': 'image_url', 'image_url': f'data:{content_type};base64,{image_b64}' }
                    ]
                }
            ],
            'max_tokens': 500,
        }

    # Tenta em cascata usando candidatos (definidos mais abaixo)

    def _get_model_candidates(preferred: Optional[str]) -> list[str]:
        # Ordem de tentativa: preferido -> secundário -> default -> env list -> conhecidos
        env_list = os.getenv('OPENROUTER_MODEL_CANDIDATES')
        env_candidates = []
        if env_list:
            try:
                env_candidates = [s.strip() for s in env_list.split(',') if s.strip()]
            except Exception:
                env_candidates = []
        known = [
            'google/gemini-1.5-flash-8b',
            'google/gemini-1.5-pro-latest',
            'google/gemini-1.5-flash-latest',
            'google/gemini-1.5-pro',
            'google/gemini-1.5-flash',
            'google/gemini-2.0-flash-exp',
            'google/gemini-2.0-flash',
        ]
        seq = [preferred, _normalize_model_id(SECONDARY_VISION_MODEL), _normalize_model_id(DEFAULT_MODEL)] + env_candidates + known
        # normaliza e remove vazios/duplicados mantendo a ordem
        out = []
        seen = set()
        for m in seq:
            mm = _normalize_model_id(m) if m else None
            if not mm:
                continue
            if mm in seen:
                continue
            seen.add(mm)
            out.append(mm)
        return out

    # Preferir o modelo de visão como primário; se não definido, usar o default geral, com fallback em cascata
    chosen_model = _normalize_model_id(model) or _normalize_model_id(SECONDARY_VISION_MODEL) or _normalize_model_id(DEFAULT_MODEL)
    candidates = _get_model_candidates(chosen_model)

    errors: list[str] = []
    for cm in candidates:
        try:
            resp = requests.post(OPENROUTER_URL, headers=essential_headers(), json=_build_payload(cm), timeout=60)
            resp.raise_for_status()
            data = resp.json()
            # Anexa cabeçalhos úteis da OpenRouter para custo/uso
            try:
                hdrs = {k.lower(): v for k, v in dict(resp.headers or {}).items()}
                data['__headers__'] = {k: v for k, v in hdrs.items() if k.startswith('x-openrouter') or k.startswith('openrouter') or k.startswith('x-request')}
            except Exception:
                pass
            return data
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else ''
            body = e.response.text if e.response is not None else str(e)
            errors.append(f"HTTPError ({cm}) {status}: {body}")
            continue
        except requests.exceptions.RequestException as e:
            errors.append(f"RequestException ({cm}): {str(e)}")
            continue

    # Segunda tentativa: busca a lista de modelos disponíveis na sua conta e tenta IDs do Gemini presentes
    try:
        models_url = 'https://openrouter.ai/api/v1/models'
        r = requests.get(models_url, headers=essential_headers(), timeout=30)
        if r.status_code == 200:
            j = r.json() or {}
            data_list = j.get('data') or j.get('models') or []
            dynamic_ids = []
            for item in data_list:
                try:
                    mid = item.get('id') if isinstance(item, dict) else None
                    if not mid or not isinstance(mid, str):
                        continue
                    # Filtra apenas modelos do Google Gemini
                    if 'google/' in mid and 'gemini' in mid:
                        dynamic_ids.append(mid)
                except Exception:
                    continue
            # Remove duplicados preservando ordem
            seen = set()
            dynamic_ids = [m for m in dynamic_ids if (m not in seen and not seen.add(m))]
            for cm in dynamic_ids:
                try:
                    resp = requests.post(OPENROUTER_URL, headers=essential_headers(), json=_build_payload(cm), timeout=60)
                    resp.raise_for_status()
                    data = resp.json()
                    try:
                        hdrs = {k.lower(): v for k, v in dict(resp.headers or {}).items()}
                        data['__headers__'] = {k: v for k, v in hdrs.items() if k.startswith('x-openrouter') or k.startswith('openrouter') or k.startswith('x-request')}
                    except Exception:
                        pass
                    return data
                except requests.exceptions.HTTPError as e:
                    status = e.response.status_code if e.response is not None else ''
                    body = e.response.text if e.response is not None else str(e)
                    errors.append(f"HTTPError ({cm}) {status}: {body}")
                    continue
                except requests.exceptions.RequestException as e:
                    errors.append(f"RequestException ({cm}): {str(e)}")
                    continue
    except Exception as _e:
        errors.append(f"ModelsFetchError: {str(_e)}")

    # Se nenhuma alternativa funcionou, retorna erro consolidado
    detail = " | ".join(errors[-3:]) if errors else "sem detalhes"
    raise RuntimeError(f"Falha ao chamar OpenRouter. Tentativas: {', '.join(candidates)}. Erros recentes: {detail}")


def _parse_response_to_json_fields(resp_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort parser supporting different OpenRouter content formats.
    Tries in order:
    - choices[0].message.content (string JSON)
    - choices[0].message.content[0].text (structured array)
    Strips code fences and parses JSON. Returns the parsed object as-is,
    augmented with "_raw". If parsing fails, returns {"_raw": resp, "content": <text>}.
    """
    content = None
    try:
        choice = (resp_obj or {}).get('choices', [{}])[0]
        message = (choice or {}).get('message', {})
        content = message.get('content')
        if isinstance(content, list) and content:
            # e.g., [{type:'output_text', text:'{...}'}]
            first = content[0]
            if isinstance(first, dict) and 'text' in first:
                content = first['text']
        # If content is dict (rare), it's already structured
        if isinstance(content, dict):
            data = dict(content)
            data['_raw'] = resp_obj
            return data
        if not isinstance(content, str):
            # fallback: return raw only
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
            txt_obj = txt[start:end+1]
        else:
            txt_obj = txt
        data = json.loads(txt_obj)
        if isinstance(data, dict):
            data['_raw'] = resp_obj
            return data
        # If it's a list or another structure, wrap it
        return { 'data': data, '_raw': resp_obj }
    except Exception:
        return { '_raw': resp_obj, 'content': content }


def extract_fields_from_image_bytes(image_bytes: bytes, filename: Optional[str] = None, model: Optional[str] = None, prompt: Optional[str] = None) -> Dict[str, Any]:
    content_type = _detect_mime_from_filename(filename)
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    resp = _call_openrouter(image_b64, content_type, model=model, prompt_text=prompt)
    return _parse_response_to_json_fields(resp)


def extract_fields_from_image_path(path: str, model: Optional[str] = None, prompt: Optional[str] = None) -> Dict[str, Any]:
    with open(path, 'rb') as f:
        data = f.read()
    return extract_fields_from_image_bytes(data, filename=os.path.basename(path), model=model, prompt=prompt)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Uso: python -m aicentralv2.services.openrouter_image_extract <caminho_da_imagem>')
        sys.exit(1)
    image_path = sys.argv[1]
    out = extract_fields_from_image_path(image_path)
    print(json.dumps(out, ensure_ascii=False, indent=2))
