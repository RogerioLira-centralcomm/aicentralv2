"""SVG logos and marks as pixels: one place that decides what an SVG may be and how it becomes an image.

An SVG is text that can carry scripts and external references, so it is never served, stored or sent to a model as
SVG. It is checked (inert: no script, foreignObject, event handler or entity), rasterized with CairoSVG without
fetching anything external, and from then on it is an ordinary transparent PNG that every flow already understands
(download, import into the Lab, Studio logo composition). CairoSVG is in requirements.txt and needs the system Cairo
library (libcairo2); without it ``rasterize`` raises and the caller keeps its existing "no logo" behaviour.
"""

from __future__ import annotations

import re

MAX_SVG_BYTES = 2 * 1024 * 1024
_UNSAFE = re.compile(rb"<\s*(script|foreignobject)\b|\bon[a-z]+\s*=|<!\s*(doctype|entity)\b", re.I)


def is_svg(content) -> bool:
    return b"<svg" in bytes(content[:4096]).lower()


def is_inert(content) -> bool:
    data = bytes(content)
    return is_svg(data) and len(data) <= MAX_SVG_BYTES and not _UNSAFE.search(data)


def rasterize(content, width: int = 1200) -> bytes:
    """The SVG as a transparent PNG. Raises ValueError for an SVG that is not inert, RuntimeError without CairoSVG."""
    data = bytes(content)
    if not is_inert(data):
        raise ValueError("O SVG contém script, entidade ou excede o limite e não é aceito.")
    try:
        import cairosvg
    except (ImportError, OSError) as exc:  # OSError: the system Cairo library is missing
        raise RuntimeError("CairoSVG indisponível: instale libcairo2 no servidor.") from exc
    return cairosvg.svg2png(bytestring=data, output_width=width, unsafe=False)
