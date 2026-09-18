import io
from unittest.mock import Mock, patch

import fitz

from aicentralv2.services import rag_pdf_ocr


def _pdf_with_pages(count=2):
    doc = fitz.open()
    for index in range(count):
        page = doc.new_page(width=300, height=200)
        if index == 0:
            page.insert_text((20, 40), "Conteudo da pagina")
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def test_prepare_pdf_removes_blank_pages():
    prepared, pages = rag_pdf_ocr.prepare_pdf(_pdf_with_pages())
    result = fitz.open(stream=prepared, filetype="pdf")
    assert len(result) == 1
    assert pages == [1]
    result.close()


@patch.object(rag_pdf_ocr, "resolve_openai_api_key", return_value="sk-test")
@patch.object(rag_pdf_ocr.requests, "delete")
@patch.object(rag_pdf_ocr.requests, "post")
def test_ocr_pdf_uploads_batches_and_returns_clean_content(post, delete, key):
    upload = Mock(ok=True)
    upload.json.return_value = {"id": "file-test"}
    response = Mock(ok=True)
    response.json.return_value = {"output_text": "<!-- Página 1 -->\n\nTexto extraído"}
    post.side_effect = [upload, response]
    result = rag_pdf_ocr.ocr_pdf(_pdf_with_pages(), batch_pages=1)
    assert result["content"] == "<!-- Página 1 -->\n\nTexto extraído"
    assert result["pages"] == [1]
    delete.assert_called_once()
