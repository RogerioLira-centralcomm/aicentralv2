import io

from PIL import Image

from aicentralv2.cadu_planner import portal_thumbs


def _png(color, size=(64, 64)):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, 'PNG')
    return buffer.getvalue()


def test_compose_returns_fixed_size_and_uses_brand_color_of_icon():
    image = portal_thumbs.compose(_png((240, 240, 240), (1440, 810)), _png((200, 30, 30)), 'Portal de Teste com um nome bem comprido que precisa quebrar', 'Notícias gerais', 'Top 10')
    assert image.size == portal_thumbs.SIZE
    assert portal_thumbs.brand_color(Image.open(io.BytesIO(_png((200, 30, 30)))))[0] > 150


def test_compose_without_icon_falls_back_to_planner_green():
    assert portal_thumbs.brand_color(None) == portal_thumbs.DEFAULT_ACCENT
    assert portal_thumbs.brand_color(Image.new('RGB', (32, 32), (255, 255, 255))) == portal_thumbs.DEFAULT_ACCENT
    assert portal_thumbs.compose(_png((10, 10, 10), (800, 800)), None, 'X', '').size == portal_thumbs.SIZE
