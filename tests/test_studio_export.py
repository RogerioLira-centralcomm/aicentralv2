import base64
import io

from PIL import Image, ImageDraw

from aicentralv2.creative_media import export


def _encoded(image):
    buffer = io.BytesIO(); image.save(buffer, "PNG"); return base64.b64encode(buffer.getvalue()).decode()


def _photo(size):
    image = Image.effect_noise(size, 60).convert("RGB")
    ImageDraw.Draw(image).ellipse((10, 10, size[0] - 10, size[1] - 10), fill=(200, 120, 40))
    return image


def test_display_unit_fits_the_weight_budget_as_jpeg():
    encoded, fmt, size_kb = export.smallest_encoding(_encoded(_photo((600, 500))), budget_kb=150)
    assert fmt == "jpeg" and size_kb <= 150


def test_flat_artwork_and_transparency_stay_png():
    flat = Image.new("RGB", (728, 90), (12, 80, 56))
    assert export.smallest_encoding(_encoded(flat), budget_kb=150)[1] == "png"
    clear = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    assert export.smallest_encoding(_encoded(clear))[1] == "png"
