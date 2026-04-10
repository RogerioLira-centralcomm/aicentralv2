"""
Extração de múltiplas linhas de cotação (itens da proposta) a partir de imagem ou PDF,
usando visão via OpenRouter (Gemini) — reutiliza openrouter_image_extract.
PDFs são rasterizados página a página com PyMuPDF e processados como PNG.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from aicentralv2.services.openrouter_image_extract import extract_fields_from_image_bytes

PROMPT_LINHAS_COTACAO = """Você é um assistente de OCR inteligente. A imagem pode ser uma tabela, print de planilha, página de PDF ou documento com um ou mais ITENS DE PROPOSTA / LINHAS DE MÍDIA.

Extraia cada linha lógica como um item separado. Ignore cabeçalhos, totais e rodapés que não sejam uma linha de produto.

Responda APENAS com um JSON válido (sem markdown), neste formato exato:
{
  "itens": [
    {
      "segmentacao": "texto — público, interesses, targeting (obrigatório se houver; senão descreva o que aparecer)",
      "praca": "cidade/região ou vazio",
      "formatos": "lista separada por vírgula entre: Carroussel, Video, Display, CTV, Audio, Interativos, Outros",
      "plataforma": "ex.: Meta Ads, DV360, Google Ads, TikTok Ads, Programática, etc.",
      "objetivo_kpi": "CPM, CPC, CPA, CPL, CPV, CPCV, CPE, CPO ou Fixo",
      "viewability_minimo": 70,
      "data_inicio": "YYYY-MM-DD ou DD/MM/AAAA",
      "data_fim": "YYYY-MM-DD ou DD/MM/AAAA",
      "especificacoes": "texto curto ou vazio",
      "produto": "lista separada por vírgula entre: Midia, Dados, Interativo, Parceiro",
      "valor_unitario_tabela": null,
      "desconto_percentual": null,
      "valor_unitario_negociado": null,
      "volume_contratado": null,
      "investimento_bruto": null,
      "investimento_liquido": null
    }
  ]
}

Regras:
- Números monetários e percentuais: use ponto como decimal na saída JSON (ex.: 1500.50), ou null se ilegível.
- volume_contratado: inteiro (impressões, cliques, visualizações, dias, etc. conforme o contexto da linha).
- Colunas de preço (CPM, CPV, CPC, "Preço unit.", "Valor unitário", "Net", etc.): preencha valor_unitario_tabela e/ou valor_unitario_negociado em R$ (ex.: CPM R$ 25,00 → 25.0 em valor_unitario_negociado). objetivo_kpi deve refletir o tipo (CPM, CPV, …).
- desconto_percentual: percentual de desconto sobre a tabela, quando houver coluna explícita; senão null.
- investimento_liquido: quando constar na linha; se só houver bruto e desconto, calcule líquido coerente com o desconto.
- Se um campo não existir na imagem, use null ou string vazia.
- Se houver apenas um item na imagem, retorne um array com um elemento.
- Não invente valores; prefira null quando incerto.
"""


def _parse_json_array_fallback(text: str) -> Optional[List[Any]]:
    t = text.strip()
    if t.startswith("```"):
        t = t.lstrip("`")
        if "\n" in t:
            lines = t.split("\n")
            if lines[0].strip().lower() in ("json", ""):
                t = "\n".join(lines[1:])
            else:
                t = "\n".join(lines)
        t = t.rstrip("`").strip()
    i = t.find("[")
    j = t.rfind("]")
    if i == -1 or j == -1 or j <= i:
        return None
    try:
        arr = json.loads(t[i : j + 1])
        return arr if isinstance(arr, list) else None
    except json.JSONDecodeError:
        return None


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace("%", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", ".")
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        try:
            return float(s)
        except ValueError:
            return None


def _to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    s = re.sub(r"\D", "", str(v))
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _normalize_date(s: Any) -> Optional[str]:
    if s is None or s == "":
        return None
    t = str(s).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", t):
        return t
    m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def _ensure_segmentacao(s: str) -> str:
    t = (s or "").strip()
    if len(t) >= 10:
        return t
    base = t or "Item importado"
    suf = " — OCR"
    return (base + suf) if len(base + suf) >= 10 else (base + suf + "." * max(0, 10 - len(base + suf)))


def _normalize_formatos(s: Any) -> str:
    known = (
        "Carroussel",
        "Video",
        "Display",
        "CTV",
        "Audio",
        "Interativos",
        "Outros",
    )
    if not s:
        return "Outros"
    parts = [p.strip() for p in re.split(r"[,;]", str(s)) if p.strip()]
    if not parts:
        return "Outros"
    out: List[str] = []
    lower_map = {k.lower(): k for k in known}
    for p in parts:
        key = p.lower()
        if key in lower_map:
            out.append(lower_map[key])
        else:
            hit = next((v for k, v in lower_map.items() if k in key or key in k), None)
            out.append(hit or "Outros")
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return ", ".join(uniq)


def extrair_itens_linhas_de_imagem(
    image_bytes: bytes,
    filename: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Retorna (lista de dicts prontos para API /api/cotacoes/linhas, mensagem_erro ou None).
    """
    raw = extract_fields_from_image_bytes(
        image_bytes, filename=filename, model=model, prompt=PROMPT_LINHAS_COTACAO
    )
    itens_src: Optional[List[Any]] = None
    if isinstance(raw, dict) and isinstance(raw.get("itens"), list):
        itens_src = raw["itens"]
    elif isinstance(raw, dict) and isinstance(raw.get("data"), list):
        itens_src = raw["data"]
    if itens_src is None and isinstance(raw, dict):
        content = raw.get("content")
        if isinstance(content, str):
            parsed = _parse_json_array_fallback(content)
            if parsed:
                itens_src = parsed
    if not itens_src:
        err = None
        if isinstance(raw, dict):
            err = raw.get("_parse_error") or "Não foi possível identificar itens na imagem."
        return [], err or "Nenhum item extraído."

    out: List[Dict[str, Any]] = []
    for row in itens_src:
        if not isinstance(row, dict):
            continue
        seg = _ensure_segmentacao(str(row.get("segmentacao") or ""))
        vu_tabela = _to_float(row.get("valor_unitario_tabela"))
        desc = _to_float(row.get("desconto_percentual"))
        vu_neg = _to_float(row.get("valor_unitario_negociado"))
        vol = _to_int(row.get("volume_contratado"))
        inv_b = _to_float(row.get("investimento_bruto"))
        inv_l = _to_float(row.get("investimento_liquido"))
        view = _to_float(row.get("viewability_minimo"))
        if view is None:
            view = 70.0
        view = max(0.0, min(100.0, view))
        prod = row.get("produto")
        if isinstance(prod, list):
            prod_str = ", ".join(str(x) for x in prod if x)
        else:
            prod_str = str(prod or "").strip()
        item = {
            "segmentacao": seg,
            "praca": str(row.get("praca") or "").strip(),
            "formatos": _normalize_formatos(row.get("formatos")),
            "plataforma": str(row.get("plataforma") or "").strip(),
            "objetivo_kpi": str(row.get("objetivo_kpi") or "").strip(),
            "viewability_minimo": view,
            "data_inicio": _normalize_date(row.get("data_inicio")),
            "data_fim": _normalize_date(row.get("data_fim")),
            "especificacoes": str(row.get("especificacoes") or "").strip(),
            "produto": prod_str,
            "valor_unitario_tabela": vu_tabela if vu_tabela is not None else 0.0,
            "desconto_percentual": desc if desc is not None else 0.0,
            "valor_unitario_negociado": vu_neg if vu_neg is not None else 0.0,
            "valor_unitario": vu_neg if vu_neg is not None else 0.0,
            "volume_contratado": vol if vol is not None else 0,
            "investimento_bruto": inv_b if inv_b is not None else 0.0,
            "investimento_liquido": inv_l if inv_l is not None else None,
            "pedido_sugestao": seg[:100],
            "detalhamento": str(row.get("especificacoes") or "").strip(),
        }
        out.append(item)

    return out, None if out else "Nenhum item válido após normalização."


# Máximo de páginas do PDF enviadas à IA (cada página = uma chamada de visão).
_MAX_PDF_PAGES = 12


def extrair_itens_linhas_de_pdf_bytes(
    pdf_bytes: bytes,
    filename: Optional[str] = None,
    model: Optional[str] = None,
    max_pages: int = _MAX_PDF_PAGES,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Rasteriza cada página do PDF (até max_pages) e reutiliza extrair_itens_linhas_de_imagem.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return [], (
            "Suporte a PDF requer PyMuPDF. Instale com: pip install PyMuPDF"
        )

    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        return [], f"Não foi possível abrir o PDF: {e}"

    base = filename or "documento.pdf"
    merged: List[Dict[str, Any]] = []
    last_err: Optional[str] = None

    try:
        if doc.page_count <= 0:
            return [], "O PDF não contém páginas."

        n_pages = min(doc.page_count, max_pages)
        for i in range(n_pages):
            page = doc[i]
            mat = fitz.Matrix(2.0, 2.0)
            try:
                pix = page.get_pixmap(matrix=mat, alpha=False)
            except Exception as e:
                last_err = str(e)
                continue
            png_bytes = pix.tobytes("png")
            page_label = f"{base}#pagina{i + 1}.png"
            itens, err = extrair_itens_linhas_de_imagem(
                png_bytes, filename=page_label, model=model
            )
            if err:
                last_err = err
            if itens:
                merged.extend(itens)

        if not merged:
            return [], last_err or "Nenhum item extraído do PDF."
        return merged, None
    finally:
        doc.close()


def extrair_itens_linhas_de_upload(
    file_bytes: bytes,
    ext: str,
    filename: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Despacha por extensão: PDF (rasterizado) ou imagem."""
    e = (ext or "").lower()
    if not e.startswith("."):
        e = "." + e
    if e == ".pdf":
        return extrair_itens_linhas_de_pdf_bytes(
            file_bytes, filename=filename, model=model
        )
    return extrair_itens_linhas_de_imagem(
        file_bytes, filename=filename, model=model
    )
