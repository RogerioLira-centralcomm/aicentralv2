import sys
from types import SimpleNamespace
from unittest.mock import patch

from aicentralv2.cadu_workspace import project_sources


def test_image_ocr_returns_text_and_processing_state_when_adapter_is_available():
    image = SimpleNamespace(load=lambda: None)
    pytesseract = SimpleNamespace(image_to_string=lambda _image, lang: "Texto do criativo")
    with patch("PIL.Image.open", return_value=image), patch.dict(sys.modules, {"pytesseract": pytesseract}):
        text, processing = project_sources._ocr_image(b"image-bytes")

    assert text == "Texto do criativo"
    assert processing == "ocr"
