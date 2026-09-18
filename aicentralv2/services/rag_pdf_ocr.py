"""OCR de PDFs da Base Cadu usando a API multimodal da OpenAI.

O processamento de imagem fica no backend Python: páginas vazias são removidas
e, quando solicitado para capturas de tela, a moldura do navegador é cortada.
O OCR propriamente dito acontece na API; nenhum modelo local é usado.
"""
from __future__ import annotations

import io
import os
from typing import Any

import fitz
import requests

from .openrouter_service import OpenRouterError, resolve_openai_api_key
from ..cadu_skills.knowledge import clean_rag_content


OPENAI_FILES_URL = "https://api.openai.com/v1/files"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.getenv("RAG_PDF_OCR_MODEL", "gpt-5-mini")
DEFAULT_BATCH_PAGES = max(1, min(12, int(os.getenv("RAG_PDF_OCR_BATCH_PAGES", "8"))))


class RagPdfOcrError(RuntimeError):
    """Falha recuperável na preparação ou no OCR do documento."""


def _image_is_blank(pixmap: fitz.Pixmap) -> bool:
    """Detecta páginas praticamente brancas sem depender de OCR local."""
    samples = pixmap.samples
    if not samples:
        return True
    channels = pixmap.n
    stride = max(channels, len(samples) // 30000)
    dark = 0
    inspected = 0
    for offset in range(0, len(samples), stride * channels):
        values = samples[offset:offset + channels]
        if not values:
            continue
        inspected += 1
        if sum(values[:3]) / min(3, len(values)) < 245:
            dark += 1
    # A slide may contain only a small title, so the threshold must be much
    # lower than a document-page heuristic. Blank exported pages are pure
    # white and remain safely at zero.
    return inspected == 0 or (dark / inspected) < 0.00001


def prepare_pdf(pdf_bytes: bytes, *, screen_capture: bool = False) -> tuple[bytes, list[int]]:
    """Renderiza um PDF limpo, removendo páginas vazias antes da API.

    ``screen_capture`` é útil para PDFs feitos de screenshots de Zoom/navegador.
    Ele remove a moldura conhecida da captura, mas mantém o slide inteiro.
    """
    try:
        source = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # pragma: no cover - mensagem de borda do fitz
        raise RagPdfOcrError("Não foi possível abrir o PDF enviado.") from exc
    output = fitz.open()
    kept_pages: list[int] = []
    try:
        for index, page in enumerate(source):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
            if _image_is_blank(pixmap):
                continue
            if screen_capture:
                bounds = page.rect
                # Capturas do deck enviado: barra do navegador/Zoom acima e
                # pequena faixa de controles abaixo. Os limites são ajustáveis.
                rect = fitz.Rect(
                    bounds.x0 + bounds.width * 0.04,
                    bounds.y0 + bounds.height * 0.18,
                    bounds.x0 + bounds.width * 0.79,
                    bounds.y0 + bounds.height * 0.94,
                )
                image = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), clip=rect, alpha=False)
            else:
                image = pixmap
            image = fitz.Pixmap(fitz.csRGB, image)
            new_page = output.new_page(width=image.width, height=image.height)
            new_page.insert_image(new_page.rect, pixmap=image)
            kept_pages.append(index + 1)
        if not kept_pages:
            raise RagPdfOcrError("O PDF não contém páginas com conteúdo visível.")
        buffer = io.BytesIO()
        output.save(buffer, garbage=4, deflate=True)
        return buffer.getvalue(), kept_pages
    finally:
        output.close()
        source.close()


def _response_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in payload.get("output") or []:
        for content in item.get("content") or []:
            text = content.get("text") if isinstance(content, dict) else None
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts).strip()


def _api_error(response: requests.Response) -> str:
    try:
        error = response.json().get("error") or {}
        detail = str(error.get("message") or "").strip()
    except (ValueError, AttributeError):
        detail = ""
    return detail[:240] or "A OpenAI recusou o OCR do documento."


def _ocr_batch(pdf_bytes: bytes, *, model: str, first_page: int, last_page: int) -> str:
    key = resolve_openai_api_key()
    if not key:
        raise RagPdfOcrError("OpenAI não está configurada para o OCR da Base Cadu.")
    headers = {"Authorization": f"Bearer {key}"}
    file_id = None
    try:
        upload = requests.post(
            OPENAI_FILES_URL,
            headers=headers,
            files={"file": (f"cadu-rag-{first_page}-{last_page}.pdf", pdf_bytes, "application/pdf")},
            data={"purpose": "user_data"},
            timeout=120,
        )
        if not upload.ok:
            raise RagPdfOcrError(_api_error(upload))
        file_id = upload.json().get("id")
        if not file_id:
            raise RagPdfOcrError("A OpenAI não retornou o identificador do PDF.")

        prompt = f"""Você é o OCR editorial da Base Global Cadu.
Extraia TODO o conteúdo legível das páginas {first_page} a {last_page} deste PDF.
Não faça resumo, não omita slides, exemplos, números, fontes, tabelas ou rodapés.
Conserve a ordem e marque cada página como `<!-- Página N -->`.
Converta títulos em Markdown, listas em listas e tabelas em Markdown quando forem
legíveis. Remova apenas molduras de navegador, controles de reunião e avisos de
interface. Não invente texto: quando algo não puder ser lido, escreva
`[OCR incompleto]`. Não inclua comentários sobre o seu processo."""
        body = {
            "model": model,
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_file", "file_id": file_id},
            ]}],
            "max_output_tokens": 30000,
        }
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={**headers, "Content-Type": "application/json"},
            json=body,
            timeout=300,
        )
        if not response.ok:
            raise RagPdfOcrError(_api_error(response))
        text = _response_text(response.json())
        if len(text) < 20:
            raise RagPdfOcrError("A OpenAI retornou pouco conteúdo para este lote do PDF.")
        return text
    except requests.RequestException as exc:
        raise RagPdfOcrError("Não foi possível conectar à OpenAI para fazer o OCR.") from exc
    finally:
        if file_id:
            try:
                requests.delete(f"{OPENAI_FILES_URL}/{file_id}", headers=headers, timeout=30)
            except requests.RequestException:
                pass


def ocr_pdf(pdf_bytes: bytes, *, model: str | None = None, batch_pages: int | None = None,
            screen_capture: bool = False) -> dict[str, Any]:
    """Prepara e OCRiza o PDF, retornando conteúdo completo para rascunho RAG."""
    prepared, kept_pages = prepare_pdf(pdf_bytes, screen_capture=screen_capture)
    document = fitz.open(stream=prepared, filetype="pdf")
    total = len(document)
    document.close()
    size = max(1, int(batch_pages or DEFAULT_BATCH_PAGES))
    chosen_model = str(model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    chunks = []
    for start in range(0, total, size):
        end = min(total, start + size)
        batch = fitz.open(stream=prepared, filetype="pdf")
        batch.select(list(range(start, end)))
        buffer = io.BytesIO()
        batch.save(buffer, garbage=4, deflate=True)
        batch.close()
        chunks.append(_ocr_batch(buffer.getvalue(), model=chosen_model, first_page=start + 1, last_page=end))
    content = clean_rag_content("\n\n".join(chunks))
    return {"content": content, "model": chosen_model, "pages": kept_pages, "batches": len(chunks)}
