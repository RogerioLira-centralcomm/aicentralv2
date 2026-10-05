from PIL import Image

from aicentralv2.creative_media import ad_masks, banner_compose, brand_fonts
from aicentralv2.creative_format_lab.brand_context import _fonts


def test_copy_is_read_literally_from_the_briefing():
    headline, cta = banner_compose.extract_copy(
        "Banner da Cemig. Título: Sua casa, sua energia. Botão: Simule agora."
    )
    assert headline == "Sua casa, sua energia." and cta == "Simule agora"
    assert banner_compose.extract_copy("sem copy literal") == ("", "")
    assert banner_compose.extract_copy('Headline: "Energia limpa"\nCTA: Saiba mais') == ("Energia limpa", "Saiba mais")


def test_typography_stays_inside_the_zones_of_every_compact_banner():
    for key in ("iab-728x90", "iab-320x50", "iab-970x250", "iab-160x600"):
        family, logo, cta = ad_masks.MASK_SETS[key][0]
        spec = ad_masks.build_spec(key, family, logo, True)
        base = Image.new("RGB", (spec["width"] * 2, spec["height"] * 2), (10, 40, 30))
        image, layers = banner_compose.render_text_layers(
            base, spec, "Energia que acompanha você", "Saiba mais", {"fonts": []}, ["#0F6C58", "#C4FF3F"],
        )
        assert image.size == base.size and {layer["type"] for layer in layers} == {"headline", "cta"}
        for layer in layers:
            x, y, w, h = layer["box"]
            assert 0 <= x and x + w <= 1.0001 and 0 <= y and y + h <= 1.0001, (key, layer)
        cta_layer = next(layer for layer in layers if layer["type"] == "cta")
        assert cta_layer["fill"] == "#c4ff3f"


def test_uploaded_font_files_survive_profile_rewrites_and_reach_the_studio():
    old = [{"family": "Gotham", "file_url": "/static/uploads/brand_fonts/abc.otf", "file_style": "Bold"}]
    kept = brand_fonts.keep_font_files([{"family": "gotham", "role": "display"}], old)
    assert kept[0]["file_url"] == "/static/uploads/brand_fonts/abc.otf"
    normalized = _fonts([{"family": "Gotham", "file_url": "/static/uploads/brand_fonts/abc.otf"}, {"family": "X", "file_url": "https://evil/x.ttf"}])
    assert normalized[0]["file_url"].endswith("abc.otf") and "file_url" not in normalized[1]


def test_font_resolution_falls_back_to_a_licensed_neutral_font():
    resolved = brand_fonts.resolve_font({"fonts": [{"family": "Fonte Inexistente", "role": "display"}]})
    assert resolved["source"] == "fallback" and resolved["path"].is_file()


def test_without_button_is_not_a_button_whose_text_is_the_rest_of_the_sentence():
    briefing = "Peça institucional da Cemig, sem botão: um amanhecer sobre montanhas.\nTítulo: Energia que move Minas"
    assert banner_compose.extract_copy(briefing) == ("Energia que move Minas", "")
    assert banner_compose.extract_copy("Peça sem CTA: só a frase.\nTítulo: Olá") == ("Olá", "")
    assert banner_compose.extract_copy("Título: Olá\nBotão: Saiba mais")[1] == "Saiba mais"
    assert banner_compose.extract_copy("Título: Olá\nassem Botão: Saiba mais")[1] == "Saiba mais"
