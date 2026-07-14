"""
Extração de dados de NFS-e / nota fiscal de serviço a partir de PDF ou imagem,
usando visão via OpenRouter (Gemini). PDFs são rasterizados com PyMuPDF.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from aicentralv2.services.openrouter_image_extract import extract_fields_from_image_bytes

NF_MODEL = 'google/gemini-2.5-flash'
_MAX_PDF_PAGES = 5
_MAX_DISCRIMINACAO_LEN = 8000
_PDF_RENDER_MATRIX = 2.5

PROMPT_NFSE = """Você é um assistente de OCR especializado em Notas Fiscais de Serviço eletrônicas (NFS-e) e DANFSe brasileiras.

Analise a imagem e extraia os dados da nota fiscal. Responda APENAS com um JSON válido (sem markdown), neste formato exato:
{
  "numero_nota": "número da NFS-e",
  "data_emissao": "YYYY-MM-DD",
  "valor_total": 0.00,
  "valor_liquido": 0.00,
  "cnpj_tomador": "somente dígitos do CNPJ do tomador/cliente",
  "codigo_pi": "código ou referência de PI/pedido de inserção se aparecer no documento",
  "codigo_verificacao": "código de verificação/autenticidade da NFS-e",
  "numero_rps": "número do RPS ou DPS se existir",
  "discriminacao": "texto COMPLETO da descrição/discriminação dos serviços",
  "impostos": {
    "issqn": 0.00,
    "pis": 0.00,
    "cofins": 0.00,
    "irrf": 0.00,
    "aliquota_issqn": 0.00
  },
  "confidence": 0.0
}

Regras:
- numero_nota: número da nota fiscal de serviço (não confundir com número do RPS/DPS).
- data_emissao: data de emissão em YYYY-MM-DD. Se DD/MM/AAAA, converta.
- valor_total: valor do serviço / valor total da NFS-e antes de retenções finais (campo "Valor do Serviço").
- valor_liquido: valor líquido da NFS-e após retenções (campo "Valor Líquido da NFS-e"); senão null.
- cnpj_tomador: CNPJ do TOMADOR do serviço (cliente), apenas 14 dígitos.
- codigo_pi: referência interna, código PI, pedido ou campanha se visível; senão null.
- codigo_verificacao: chave/código alfanumérico de verificação municipal; senão null.
- numero_rps: número do RPS ou DPS; senão null.
- discriminacao: COPIE INTEGRALMENTE e SEM RESUMIR o texto do campo "Descrição do Serviço" ou "Discriminação dos Serviços".
  * Inclua TODAS as linhas visíveis desse campo, do início ao fim.
  * Preserve números, valores (R$), PI, campanha, vencimento, dados bancários, Pix, etc.
  * NÃO inclua códigos de tributação (ex.: 17.25.01), títulos de seção nem textos de outras áreas da nota.
  * NÃO resuma, abrevie com "..." nem omita partes por tamanho.
- impostos.issqn: ISSQN apurado ou retido; impostos.pis e impostos.cofins: valores de débito/apuração própria; impostos.irrf: IRRF se houver; impostos.aliquota_issqn: percentual (ex.: 5.00).
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
    s = str(v).strip().replace('R$', '').replace(' ', '').replace('%', '')
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


def _normalize_discriminacao_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        return None
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in text.split('\n')]
    lines = [ln for ln in lines if ln]
    if not lines:
        return None
    return ' '.join(lines)


def _clean_discriminacao_pollution(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.strip()
    patterns = (
        r'^(?:descri[cç][aã]o do servi[cç]o|discrimina[cç][aã]o(?: dos servi[cç]os)?)\s*[:\-]?\s*',
        r'^(?:c[oó]digo de tributa[cç][aã]o(?: nacional| municipal)?)\s*[:\-]?\s*',
        r'^\d{1,2}\.\d{2}\.\d{2}\s*-\s*Inser[cç][aã]o de textos.+?(?:propag\.{3}|propaganda)\s*',
        r'^\d{3}\s*-\s*Inser[cç][aã]o de textos.+?(?:propag\.{3}|propaganda)\s*',
    )
    changed = True
    while changed:
        changed = False
        for pat in patterns:
            new_t = re.sub(pat, '', t, flags=re.IGNORECASE)
            if new_t != t:
                t = new_t.strip()
                changed = True
    return t or None


def _pick_best_discriminacao(*candidates: Any) -> Optional[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        norm = _normalize_discriminacao_text(raw)
        clean = _clean_discriminacao_pollution(norm)
        if not clean or len(clean) < 3:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(clean)
    if not cleaned:
        return None
    cleaned.sort(key=len, reverse=True)
    best = cleaned[0]
    for alt in cleaned[1:]:
        if alt in best:
            continue
        if best in alt:
            best = alt
            continue
        # Une trechos complementares quando o OCR truncou no meio
        if not best.endswith(alt[:40]) and not alt.startswith(best[-40:]):
            overlap = 0
            max_ov = min(len(best), len(alt), 120)
            for size in range(max_ov, 19, -1):
                if best[-size:].casefold() == alt[:size].casefold():
                    overlap = size
                    break
            if overlap:
                best = best + alt[overlap:]
            elif len(alt) > len(best):
                best = alt
    return best[:_MAX_DISCRIMINACAO_LEN]


def _extract_discriminacao_from_pdf_text(text: str) -> Optional[str]:
    if not text or not text.strip():
        return None

    section_end = (
        r'(?:TRIBUTA[cç][aã]O MUNICIPAL|TRIBUTA[cç][aã]O FEDERAL|VALOR TOTAL DA NFS-E|'
        r'VALOR TOTAL DO SERVI[cç]O|BASE DE C[aá]LCULO|INFORMA[cç][õO]ES COMPLEMENTARES|'
        r'C[oó]digo do Servi[cç]o|Detalhamento do Servi[cç]o)'
    )
    patterns = (
        rf'Descri[cç][aã]o do Servi[cç]o\s*\n(.+?)\n\s*{section_end}',
        rf'Discrimina[cç][aã]o(?: dos Servi[cç]os)?\s*\n(.+?)\n\s*{section_end}',
        rf'Discrimina[cç][aã]o(?: dos Servi[cç]os)?\s*[:\-]?\s*\n(.+?)\n\s*{section_end}',
    )
    best: Optional[str] = None
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if not m:
            continue
        chunk = _normalize_discriminacao_text(m.group(1))
        clean = _clean_discriminacao_pollution(chunk)
        if clean and (best is None or len(clean) > len(best)):
            best = clean
    return best


def _parse_impostos(src: Dict[str, Any]) -> Dict[str, Optional[float]]:
    imp_raw = src.get('impostos') if isinstance(src.get('impostos'), dict) else {}
    return {
        'issqn': _to_float(imp_raw.get('issqn') or src.get('valor_issqn')),
        'pis': _to_float(imp_raw.get('pis') or src.get('valor_pis')),
        'cofins': _to_float(imp_raw.get('cofins') or src.get('valor_cofins')),
        'irrf': _to_float(imp_raw.get('irrf') or src.get('valor_irrf')),
        'aliquota_issqn': _to_float(imp_raw.get('aliquota_issqn') or src.get('aliquota_issqn')),
    }


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
        if codigo_pi:
            if not re.fullmatch(r'\d+', codigo_pi):
                m_pi = re.search(r'\bPI\s*[#:\-]?\s*(\d+)\b', codigo_pi, re.I)
                if m_pi:
                    codigo_pi = m_pi.group(1).strip()

    impostos = _parse_impostos(src)

    return {
        'numero_nota': (str(src.get('numero_nota')).strip() if src.get('numero_nota') else None),
        'data_emissao': _normalize_date(src.get('data_emissao')),
        'valor_total': _to_float(src.get('valor_total')),
        'valor_liquido': _to_float(src.get('valor_liquido')),
        'cnpj_tomador': cnpj if cnpj and len(cnpj) == 14 else None,
        'codigo_pi': codigo_pi,
        'codigo_verificacao': (str(src.get('codigo_verificacao')).strip() if src.get('codigo_verificacao') else None),
        'numero_rps': (str(src.get('numero_rps')).strip() if src.get('numero_rps') else None),
        'discriminacao': _pick_best_discriminacao(src.get('discriminacao')),
        'impostos': impostos,
        'valor_issqn': impostos.get('issqn'),
        'valor_pis': impostos.get('pis'),
        'valor_cofins': impostos.get('cofins'),
        'valor_irrf': impostos.get('irrf'),
        'aliquota_issqn': impostos.get('aliquota_issqn'),
        'confidence': _clamp_confidence(src.get('confidence')),
    }


def _extract_from_image(image_bytes: bytes, filename: Optional[str]) -> Optional[Dict[str, Any]]:
    raw = extract_fields_from_image_bytes(
        image_bytes, filename=filename, model=NF_MODEL, prompt=PROMPT_NFSE
    )
    return _parse_nf_payload(raw)


def _pdf_text(pdf_bytes: bytes) -> str:
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        text = '\n'.join(doc[i].get_text() for i in range(min(doc.page_count, _MAX_PDF_PAGES)))
        doc.close()
        return text
    except Exception:
        return ''


def _first_match_float(text: str, patterns) -> Optional[float]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _to_float(m.group(1))
            if val is not None:
                return val
    return None


def _extract_from_pdf_text(pdf_bytes: bytes) -> Dict[str, Any]:
    """Fallback: extrai campos do texto embutido no PDF (DANFSe)."""
    out: Dict[str, Any] = {
        'valor_total': None,
        'valor_liquido': None,
        'valor_issqn': None,
        'valor_pis': None,
        'valor_cofins': None,
        'valor_irrf': None,
        'aliquota_issqn': None,
    }
    text = _pdf_text(pdf_bytes)
    if not text.strip():
        return out

    out['valor_total'] = _first_match_float(text, (
        r'Valor do Servi[^\n]*\n\s*R\$\s*([\d.\,]+)',
        r'VALOR TOTAL DA NFS-E[\s\S]{0,120}?Valor do Servi[^\n]*\n\s*R\$\s*([\d.\,]+)',
    ))
    out['valor_liquido'] = _first_match_float(text, (
        r'Valor L[ií]quido da NFS-e\n\s*R\$\s*([\d.\,]+)',
        r'Valor L[ií]quido da NFS-e[^\n]*\n\s*R\$\s*([\d.\,]+)',
    ))
    out['valor_issqn'] = _first_match_float(text, (
        r'ISSQN Apurado\n\s*R\$\s*([\d.\,]+)',
        r'ISSQN Retido\n\s*R\$\s*([\d.\,]+)',
    ))
    out['valor_pis'] = _first_match_float(text, (
        r'PIS - D[eé]bito Apura[cç][aã]o Pr[oó]pria\n\s*R\$\s*([\d.\,]+)',
    ))
    out['valor_cofins'] = _first_match_float(text, (
        r'COFINS - D[eé]bito Apura[cç][aã]o Pr[oó]pria\n\s*R\$\s*([\d.\,]+)',
    ))
    out['valor_irrf'] = _first_match_float(text, (
        r'IRRF\n\s*R\$\s*([\d.\,]+)',
    ))
    out['aliquota_issqn'] = _first_match_float(text, (
        r'Al[ií]quota Aplicada\n\s*([\d.\,]+)\s*%',
    ))
    out['discriminacao'] = _extract_discriminacao_from_pdf_text(text)
    return out


def _merge_extraction_with_text_fallback(result: Optional[Dict[str, Any]], pdf_bytes: bytes) -> Optional[Dict[str, Any]]:
    if not result:
        result = {}
    fallback = _extract_from_pdf_text(pdf_bytes)

    for key in ('valor_total', 'valor_liquido', 'valor_issqn', 'valor_pis', 'valor_cofins', 'valor_irrf', 'aliquota_issqn'):
        if result.get(key) is None and fallback.get(key) is not None:
            result[key] = fallback[key]

    merged_disc = _pick_best_discriminacao(result.get('discriminacao'), fallback.get('discriminacao'))
    if merged_disc:
        result['discriminacao'] = merged_disc

    impostos = result.get('impostos') if isinstance(result.get('impostos'), dict) else {}
    impostos = {
        'issqn': impostos.get('issqn') or result.get('valor_issqn'),
        'pis': impostos.get('pis') or result.get('valor_pis'),
        'cofins': impostos.get('cofins') or result.get('valor_cofins'),
        'irrf': impostos.get('irrf') or result.get('valor_irrf'),
        'aliquota_issqn': impostos.get('aliquota_issqn') or result.get('aliquota_issqn'),
    }
    result['impostos'] = impostos
    result['valor_issqn'] = impostos.get('issqn')
    result['valor_pis'] = impostos.get('pis')
    result['valor_cofins'] = impostos.get('cofins')
    result['valor_irrf'] = impostos.get('irrf')
    result['aliquota_issqn'] = impostos.get('aliquota_issqn')

    if not result.get('numero_nota') and not result.get('valor_total'):
        return None
    return result


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
        discriminacoes: list[Any] = []
        for i in range(n_pages):
            try:
                page = doc[i]
                mat = fitz.Matrix(_PDF_RENDER_MATRIX, _PDF_RENDER_MATRIX)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                png_bytes = pix.tobytes('png')
            except Exception:
                continue
            page_label = f'{base}#pagina{i + 1}.png'
            result = _extract_from_image(png_bytes, page_label)
            if not result:
                continue
            if result.get('discriminacao'):
                discriminacoes.append(result.get('discriminacao'))
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
        if best and discriminacoes:
            merged = _pick_best_discriminacao(best.get('discriminacao'), *discriminacoes)
            if merged:
                best['discriminacao'] = merged
        return _merge_extraction_with_text_fallback(best, pdf_bytes)
    finally:
        doc.close()


def extract_nf_pdf(file_bytes: bytes, ext: str, filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Extrai campos de NFS-e de PDF ou imagem. Retorna dict normalizado ou None."""
    e = (ext or '').lower()
    if not e.startswith('.'):
        e = '.' + e
    try:
        if e == '.pdf':
            result = _extract_from_pdf(file_bytes, filename)
            if result:
                return result
            return _merge_extraction_with_text_fallback({}, file_bytes)
        if e in ('.png', '.jpg', '.jpeg', '.webp'):
            return _extract_from_image(file_bytes, filename)
        return None
    except Exception:
        return None
