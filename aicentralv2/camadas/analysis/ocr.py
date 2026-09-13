"""OCR estrito. Persiste o bloco completo, não o slim da V1."""

from __future__ import annotations


def read_creative(image_data_url, text_callable=None):
    from ...creative_format_lab.engineer import read_still_blocks

    blocks = read_still_blocks(image_data_url, text_callable)
    return {
        "read": blocks.get("read") or {},
        "read_full": blocks.get("read_full") or {},
        "ocr_status": blocks.get("ocr_status") or "unavailable",
    }
