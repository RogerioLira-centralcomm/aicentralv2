import io

from PIL import Image

from aicentralv2.creative_lab import scenarios
from aicentralv2.creative_media import position_layouts


def test_every_layout_keeps_copy_inside_the_safe_frame_and_has_a_sketch():
    for layout_id in position_layouts.LAYOUTS:
        spec = position_layouts.spec(layout_id)
        left, top, width, height = spec["safe"]
        for name in [name for name in ("headline", "cta", "logo") if name in spec["zones"]]:
            x, y, w, h = spec["zones"][name]
            assert x >= left - 0.002 and y >= top - 0.002, (layout_id, name)
            assert x + w <= left + width + 0.002 and y + h <= top + height + 0.002, (layout_id, name)
        sketch = Image.open(io.BytesIO(position_layouts.render_sketch(layout_id)))
        item = position_layouts.get(layout_id)
        scale = 1200 / max(item["width"], item["height"])
        assert max(sketch.size) == 1200 and all(abs(got - want * scale) <= 1 for got, want in zip(sketch.size, (item["width"], item["height"])))
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
    assert " ".join(headline["lines"]).endswith("DA MÃO") and headline["lines"][0].startswith("SUA")
    assert not any(len(line) <= 3 and " " not in line for line in headline["lines"]), "no lone short word"


def test_layouts_with_a_painted_block_or_a_seal_are_never_mirrored():
    from aicentralv2.creative_media import banner_compose
    busy = Image.effect_noise((1200, 1000), 120).convert("RGB")
    for layout_id in ("faixa-foto-bloco", "tipografico-selo"):
        spec = position_layouts.spec(layout_id)
        assert banner_compose.place_position(busy, spec) is spec


def test_a_layout_has_its_half_page_version():
    assert position_layouts.for_format("pessoa-circulo", "iab-300x600") == "pessoa-circulo-300x600"
    assert position_layouts.for_format("pessoa-circulo", "iab-300x250") == "pessoa-circulo"
    spec = position_layouts.spec("faixa-foto-bloco-300x600")
    assert spec["class"] == "vertical" and spec["format_label"] == "IAB 300×600" and spec["height"] == 600


def test_every_standard_format_has_its_layouts_and_a_missing_one_is_empty_not_a_wrong_size():
    commercial = ("pessoa-circulo", "produto-diagonal", "faixa-foto-bloco", "tipografico-selo")
    institutional = ("manifesto-foto-plena", "assinatura-centro")
    dropped = {("pessoa-circulo", "iab-970x250"), ("pessoa-circulo", "iab-728x90"), ("produto-diagonal", "iab-728x90")}
    for fmt in ("iab-300x600", "iab-160x600", "iab-728x90", "iab-970x250"):
        for base in (*commercial, *institutional):
            sized = position_layouts.for_format(base, fmt)
            if (base, fmt) in dropped:
                assert sized == "", (base, fmt)
                continue
            assert sized != base and position_layouts.get(sized)["format"] == fmt, (base, fmt)
            assert position_layouts.get(sized)["cta"] == (base in commercial), sized
    assert position_layouts.for_format("retrato-dividido", "iab-970x250") == "retrato-dividido-970x250"
    assert position_layouts.for_format("retrato-dividido", "iab-300x600") == ""


def test_the_director_reads_the_layout_of_the_format_and_never_loses_the_copy_to_the_cap(monkeypatch):
    from aicentralv2.creative_lab import studio_bridge

    seen = {}

    def fake_create(payload, text_callable):
        seen["prompt"] = payload["prompt"]
        return {"directions": [{"title": "t", "prompt": "p", "copy": None}], "model": "m", "provider": "p"}, {}

    monkeypatch.setattr(studio_bridge.studio_create, "create", fake_create)
    spec = {"instruction": "Peça da Vivara.", "aspect_ratio": "1:3.75",
            "brief": {"format_key": "iab-160x600", "copy": {"headline": "Joias que contam histórias", "highlight": "ATÉ 30% OFF",
                                                              "cta": "Compre agora"}}}
    monkeypatch.setattr(studio_bridge.LabModeling, "position_layout", "pessoa-circulo")
    studio_bridge.direct(spec, {})
    assert "arranha-céu" in seen["prompt"] and "Botão: Compre agora" in seen["prompt"]
    assert len(seen["prompt"]) <= studio_bridge.DIRECTOR_PROMPT_CHARS


def test_the_rule_picks_by_button_offer_product_and_person_and_falls_back_by_format():
    pick = position_layouts.choose
    base = "Peça da marca.\nTítulo: Semana do cliente\n"
    assert pick("iab-300x250", base + "Botão: Compre") == "faixa-foto-bloco"
    assert pick("iab-300x250", base + "Destaque: 20% OFF\nBotão: Compre") == "tipografico-selo"
    assert pick("iab-300x250", "Foto de um smartphone.\n" + base + "Botão: Compre") == "produto-diagonal"
    assert pick("iab-300x250", "Uma mulher sorrindo.\n" + base + "Botão: Compre") == "pessoa-circulo"
    assert pick("iab-300x250", base) == "manifesto-foto-plena"
    assert pick("iab-728x90", "Uma mulher sorrindo.\n" + base + "Botão: Compre") == "faixa-foto-bloco-728x90"
    assert pick("iab-160x600", "Uma mulher sorrindo.\n" + base + "Botão: Compre") == "pessoa-circulo-160x600"
    assert pick("iab-300x250", "Peça sem copy") == "" and pick("iab-320x50", base + "Botão: Compre") == ""


def test_the_studio_picks_a_layout_only_with_the_flag_and_never_over_a_chosen_mask(monkeypatch):
    from aicentralv2.creative_media import studio_create

    briefing = "Título: Semana do cliente\nBotão: Compre"
    assert studio_create.auto_position(300, 250, briefing) == ""  # flag off by default
    assert studio_create.auto_position(300, 250, briefing, enabled=True) == "faixa-foto-bloco"
    assert studio_create.auto_position(1080, 1080, briefing, enabled=True) == ""  # a feed is not a display unit
    monkeypatch.setattr(studio_create, "POSITION_LAYOUTS", True)
    assert studio_create.auto_position(300, 600, briefing) == "faixa-foto-bloco-300x600"
    from aicentralv2.creative_media import ad_masks
    served = ad_masks.served_specs()[0]
    url = ad_masks.MASK_URL_PREFIX + served["id"].replace(":", "__") + ".png"
    assert ad_masks.spec_from_url(url)
    assert studio_create.auto_position(served["width"], served["height"], briefing, [{"url": url}]) == ""


def test_both_steps_decide_on_the_first_1200_characters(monkeypatch):
    from aicentralv2.creative_media import studio_create

    briefing = "Título: Semana do cliente\nBotão: Compre\n" + "x" * 1200 + "\nUma mulher sorrindo."
    assert studio_create.auto_position(300, 250, briefing, enabled=True) == "faixa-foto-bloco"  # not pessoa-circulo
