import io

from PIL import Image

from aicentralv2.creative_lab import scenarios
from aicentralv2.creative_media import position_layouts


def test_every_layout_keeps_copy_inside_the_safe_frame_and_has_a_sketch():
    for layout_id in position_layouts.LAYOUTS:
        spec = position_layouts.spec(layout_id)
        left, top, width, height = spec["safe"]
        for name in ("headline", "cta", "logo"):
            x, y, w, h = spec["zones"][name]
            assert x >= left - 0.002 and y >= top - 0.002, (layout_id, name)
            assert x + w <= left + width + 0.002 and y + h <= top + height + 0.002, (layout_id, name)
        sketch = Image.open(io.BytesIO(position_layouts.render_sketch(layout_id)))
        assert sketch.size == (1200, 1000)
        assert position_layouts.sketch_path(layout_id).is_file(), "sketch PNG committed for the Studio to serve"


def test_words_describe_positions_and_keep_the_copy_area_empty():
    lines = position_layouts.words("pessoa-circulo")
    assert lines[0].startswith("LAYOUT BY POSITION") and "placement guide, not artwork" in lines[0]
    assert any("circle" in line for line in lines) and "Leave the copy area completely empty" in lines[-1]


def test_v5_rows_are_300x250_with_a_layout_by_position():
    rows = [item for item in scenarios.scenarios() if item["key"].startswith("v5-")]
    assert len(rows) == 4
    assert all(item["formats"] == ["iab-300x250"] and position_layouts.get(item["layout"]["position"]) for item in rows)


def test_the_seal_layout_sets_the_hero_inside_the_seal():
    from aicentralv2.creative_media import banner_compose
    spec = position_layouts.spec("tipografico-selo")
    _, layers = banner_compose.render_text_layers(Image.new("RGB", (1200, 1000), (10, 60, 45)), spec,
                                                  "Sua conta de luz NA PALMA DA MÃO", "Acesse agora", {},
                                                  ["#00A859", "#B5D334", "#0B3D2E"])
    headline = next(layer for layer in layers if layer["type"] == "headline")
    assert headline["hero_box"] == list(spec["zones"]["seal"])
    assert " ".join(headline["lines"]).endswith("DA MÃO") and "SUA" in headline["lines"]


def test_layouts_with_a_painted_block_or_a_seal_are_never_mirrored():
    from aicentralv2.creative_media import banner_compose
    busy = Image.effect_noise((1200, 1000), 120).convert("RGB")
    for layout_id in ("faixa-foto-bloco", "tipografico-selo"):
        spec = position_layouts.spec(layout_id)
        assert banner_compose.place_position(busy, spec) is spec
