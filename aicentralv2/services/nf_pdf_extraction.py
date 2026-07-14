"""
Extração de dados de NFS-e / nota fiscal de serviço a partir de PDF ou imagem,
usando visão via OpenRouter (Gemini). PDFs são rasterizados com PyMuPDF.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from aicentralv2.services.openrouter_image_extract import extract_fields_from_image_bytes

NF_MODEL = 'google/gemini-2.5-flash'
_MAX_PDF_PAGES = 5

PROMPT_NFSE = """Você é um assistente de OCR especializado em Notas Fiscais de Serviço eletrônicas (NFS-e) brasileiras.

Analise a imagem e extraia os dados da nota fiscal. Responda APENAS com um JSON válido (sem markdown), neste formato exato:
{
  "numero_nota": "número da NFS-e",
  "data_emissao": "YYYY-MM-DD",
  "valor_total": 0.00,
  "cnpj_tomador": "somente dígitos do CNPJ do tomador/cliente",
  "codigo_pi": "código ou referência de PI/pedido de inserção se aparecer no documento",
  "codigo_verificacao": "código de verificação/autenticidade da NFS-e",
  "numero_rps": "número do RPS se existir",
  "discriminacao": "descrição/discriminação dos serviços",
  "confidence": 0.0
}

Regras:
- numero_nota: número da nota fiscal de serviço (não confundir com número do RPS).
- data_emissao: data de emissão em YYYY-MM-DD. Se DD/MM/AAAA, converta.
- valor_total: valor total da nota (serviços). Ponto como decimal (ex.: 1234.56).
- cnpj_tomador: CNPJ do TOMADOR do serviço (cliente), apenas 14 dígitos.
- codigo_pi: referência interna, código PI, pedido ou campanha se visível; senão null.
- codigo_verificacao: código alfanumérico de verificação municipal; senão null.
- numero_rps: número do RPS; senão null.
- discriminacao: texto da discriminação dos serviços; senão null.
- confidence: confiança geral 0.0 a 1.0.
- Não invente valores; use null quando incerto.
"""


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == '':
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace('R$', '').replace(' ', '')
    if not s:
        return None
    if re.search(r',\d{1,2}$', s):
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '')
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        try:
            return float(s)
        except ValueError:
            return None


def _normalize_date(s: Any) -> Optional[str]:
    if s is None or s == '':
        return None
    t = str(s).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', t):
        return t
    m = re.match(r'^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})$', t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return f'{y:04d}-{mo:02d}-{d:02d}'
        except Exception:
            return None
    return None


def _only_digits(value: Any, max_len: int = 14) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r'\D', '', str(value))
    return digits[:max_len] if digits else None


def _clamp_confidence(v: Any) -> Optional[float]:
    f = _to_float(v)
    if f is None:
        return None
    return max(0.0, min(1.0, f))


def _parse_json_object_fallback(text: str) -> Optional[Dict[str, Any]]:
    t = (text or '').strip()
    if t.startswith('```'):
        t = t.lstrip('`')
        if '\n' in t:
            lines = t.split('\n')
            if lines[0].strip().lower() in ('json', ''):
                t = '\n'.join(lines[1:])
        t = t.rstrip('`').strip()
    i = t.find('{')
    j = t.rfind('}')
    if i == -1 or j == -1 or j <= i:
        return None
    try:
        obj = json.loads(t[i:j + 1])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _parse_nf_payload(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    src = raw
    if 'numero_nota' not in src and 'valor_total' not in src:
        content = src.get('content')
        if isinstance(content, str):
            parsed = _parse_json_object_fallback(content)
            if parsed:
                src = parsed
    if 'numero_nota' not in src and 'valor_total' not in src and 'data_emissao' not in src:
        return None

    cnpj = _only_digits(src.get('cnpj_tomador'))
    codigo_pi = src.get('codigo_pi')
    if codigo_pi is not None:
        codigo_pi = str(codigo_pi).strip() or None

    return {
        'numero_nota': (str(src.get('numero_nota')).strip() if src.get('numero_nota') else None),
        'data_emissao': _normalize_date(src.get('data_emissao')),
        'valor_total': _to_float(src.get('valor_total')),
        'cnpj_tomador': cnpj if cnpj and len(cnpj) == 14 else None,
        'codigo_pi': codigo_pi,
        'codigo_verificacao': (str(src.get('codigo_verificacao')).strip() if src.get('codigo_verificacao') else None),
        'numero_rps': (str(src.get('numero_rps')).strip() if src.get('numero_rps') else None),
        'discriminacao': (str(src.get('discriminacao')).strip()[:2000] if src.get('discriminacao') else None),
        'confidence': _clamp_confidence(src.get('confidence')),
    }


def _extract_from_image(image_bytes: bytes, filename: Optional[str]) -> Optional[Dict[str, Any]]:
    raw = extract_fields_from_image_bytes(
        image_bytes, filename=filename, model=NF_MODEL, prompt=PROMPT_NFSE
    )
    return _parse_nf_payload(raw)


def _extract_from_pdf(pdf_bytes: bytes, filename: Optional[str]) -> Optional[Dict[str, Any]]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    except Exception:
        return None

    base = filename or 'nota_fiscal.pdf'
    try:
        if doc.page_count <= 0:
            return None
        n_pages = min(doc.page_count, _MAX_PDF_PAGES)
        best: Optional[Dict[str, Any]] = None
        for i in range(n_pages):
            try:
                page = doc[i]
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                png_bytes = pix.tobytes('png')
            except Exception:
                continue
            page_label = f'{base}#pagina{i + 1}.png'
            result = _extract_from_image(png_bytes, page_label)
            if not result:
                continue
            if best is None:
                best = result
            else:
                cur_conf = result.get('confidence') or 0
                best_conf = best.get('confidence') or 0
                if cur_conf > best_conf:
                    best = result
                elif cur_conf == best_conf:
                    cur_total = result.get('valor_total') or 0
                    best_total = best.get('valor_total') or 0
                    if cur_total > best_total:
                        best = result
        return best
    finally:
        doc.close()


def extract_nf_pdf(file_bytes: bytes, ext: str, filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Extrai campos de NFS-e de PDF ou imagem. Retorna dict normalizado ou None."""
    e = (ext or '').lower()
    if not e.startswith('.'):
        e = '.' + e
    try:
        if e == '.pdf':
            return _extract_from_pdf(file_bytes, filename)
        if e in ('.png', '.jpg', '.jpeg', '.webp'):
            return _extract_from_image(file_bytes, filename)
        return None
    except Exception:
        return None
