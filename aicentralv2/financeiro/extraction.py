"""
Extração de dados de comprovante (nota/recibo/cupom) a partir de imagem ou PDF,
usando visão via OpenRouter (Gemini 2.5 Flash) — reutiliza openrouter_image_extract.
PDFs são rasterizados com PyMuPDF (fitz) e processados como PNG.

Retorna dict com: expense_date, total_amount, merchant_name,
suggested_category_slug, confidence, items.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from aicentralv2.services.openrouter_image_extract import extract_fields_from_image_bytes

RECEIPT_MODEL = 'google/gemini-2.5-flash'

CATEGORY_SLUGS = (
    'alimentacao', 'transporte', 'hospedagem', 'combustivel',
    'pedagio', 'material', 'software', 'outros',
)

PROMPT_RECEIPT = """Você é um assistente de OCR especializado em comprovantes de despesa (notas fiscais, cupons, recibos, faturas).

Analise a imagem e extraia os dados do comprovante. Responda APENAS com um JSON válido (sem markdown), neste formato exato:
{
  "expense_date": "YYYY-MM-DD",
  "total_amount": 0.00,
  "merchant_name": "nome do estabelecimento",
  "suggested_category_slug": "uma das categorias listadas abaixo",
  "confidence": 0.0,
  "items": [
    { "description": "descrição do item", "quantity": 1, "unit_amount": 0.00, "amount": 0.00 }
  ]
}

Categorias válidas para suggested_category_slug (escolha a mais adequada):
- alimentacao (restaurantes, lanchonetes, mercado, comida)
- transporte (táxi, uber, ônibus, estacionamento, aéreo)
- hospedagem (hotéis, pousadas, airbnb)
- combustivel (posto de gasolina, etanol, diesel)
- pedagio (praças de pedágio)
- material (materiais de escritório, papelaria, insumos)
- software (assinaturas, licenças, serviços digitais)
- outros (qualquer outra coisa)

Regras:
- expense_date: data da compra/emissão no formato YYYY-MM-DD. Se só houver DD/MM/AAAA, converta. Se não achar, use null.
- total_amount: valor TOTAL pago (o maior valor final, já com impostos/serviço). Use ponto como separador decimal (ex.: 1234.56). Se ilegível, null.
- merchant_name: nome do estabelecimento/loja. Se não achar, null.
- suggested_category_slug: exatamente um dos slugs listados. Se em dúvida, "outros".
- confidence: sua confiança geral (0.0 a 1.0) de que os dados estão corretos e o documento é um comprovante legível.
- items: lista de itens quando visíveis; se não houver detalhamento, retorne lista vazia.
- Não invente valores; prefira null quando incerto.
"""

_MAX_PDF_PAGES = 5


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
    # trata formato brasileiro 1.234,56 -> 1234.56
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


def _normalize_category(slug: Any) -> Optional[str]:
    if not slug:
        return None
    s = str(slug).strip().lower()
    if s in CATEGORY_SLUGS:
        return s
    # tolera pequenas variações/acentos
    aliases = {
        'alimentação': 'alimentacao',
        'combustível': 'combustivel',
        'pedágio': 'pedagio',
        'transporte publico': 'transporte',
    }
    return aliases.get(s, 'outros')


def _clamp_confidence(v: Any) -> Optional[float]:
    f = _to_float(v)
    if f is None:
        return None
    return max(0.0, min(1.0, f))


def _normalize_items(raw_items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return out
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        desc = str(it.get('description') or '').strip()
        if not desc:
            continue
        amount = _to_float(it.get('amount'))
        unit = _to_float(it.get('unit_amount'))
        qty = _to_float(it.get('quantity'))
        out.append({
            'description': desc[:500],
            'quantity': qty if qty is not None else 1,
            'unit_amount': unit,
            'amount': amount if amount is not None else 0.0,
        })
    return out


def _parse_receipt_payload(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    src = raw
    # fallback: conteúdo textual não parseado como JSON de topo
    if 'total_amount' not in src and 'expense_date' not in src:
        content = src.get('content')
        if isinstance(content, str):
            parsed = _parse_json_object_fallback(content)
            if parsed:
                src = parsed
    if 'total_amount' not in src and 'expense_date' not in src and 'merchant_name' not in src:
        return None
    return {
        'expense_date': _normalize_date(src.get('expense_date')),
        'total_amount': _to_float(src.get('total_amount')),
        'merchant_name': (str(src.get('merchant_name')).strip() if src.get('merchant_name') else None),
        'suggested_category_slug': _normalize_category(src.get('suggested_category_slug')),
        'confidence': _clamp_confidence(src.get('confidence')),
        'items': _normalize_items(src.get('items')),
    }


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


def _extract_from_image(image_bytes: bytes, filename: Optional[str]) -> Optional[Dict[str, Any]]:
    raw = extract_fields_from_image_bytes(
        image_bytes, filename=filename, model=RECEIPT_MODEL, prompt=PROMPT_RECEIPT
    )
    return _parse_receipt_payload(raw)


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

    base = filename or 'comprovante.pdf'
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
            # escolhe a página com maior valor/confiança (geralmente a que tem o total)
            if best is None:
                best = result
            else:
                cur_total = result.get('total_amount') or 0
                best_total = best.get('total_amount') or 0
                if cur_total > best_total:
                    best = result
        return best
    finally:
        doc.close()


def extract_receipt(file_bytes: bytes, ext: str, filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Extrai dados de um comprovante (imagem ou PDF).
    Retorna dict {expense_date, total_amount, merchant_name,
    suggested_category_slug, confidence, items} ou None em caso de falha.
    """
    e = (ext or '').lower()
    if not e.startswith('.'):
        e = '.' + e
    try:
        if e == '.pdf':
            return _extract_from_pdf(file_bytes, filename)
        return _extract_from_image(file_bytes, filename)
    except Exception:
        return None
