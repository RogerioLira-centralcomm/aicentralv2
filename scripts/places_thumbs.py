"""Pre-generate the resized copies of the Places gallery (run after deploying new photos).

    .venv/bin/python scripts/places_thumbs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aicentralv2.places.thumbs import STATIC_GALLERY, WIDTHS, make_thumb  # noqa: E402

IMAGES = {".jpg", ".jpeg", ".png", ".webp"}

if __name__ == "__main__":
    files = sorted(path for path in STATIC_GALLERY.iterdir() if path.is_file() and path.suffix.lower() in IMAGES)
    failed = 0
    for index, source in enumerate(files, 1):
        for width in WIDTHS:
            try:
                make_thumb(source, width)
            except Exception as exc:  # noqa: BLE001 — one bad file must not stop the rest
                failed += 1
                print(f"falhou {source.name} ({width}px): {exc}")
        if index % 50 == 0:
            print(f"{index}/{len(files)}")
    print(f"pronto: {len(files)} fotos, {failed} falhas")
