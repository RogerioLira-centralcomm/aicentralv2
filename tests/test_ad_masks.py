import io

from PIL import Image

from aicentralv2.creative_media import ad_masks, studio_create


def _overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def test_every_combination_stays_inside_the_canvas_and_keeps_text_apart():
    count = 0
    for spec in ad_masks.all_specs():
        count += 1
        zones = spec["zones"]
        for name, (x, y, w, h) in zones.items():
            assert x >= -1e-6 and y >= -1e-6 and x + w <= 1 + 1e-6 and y + h <= 1 + 1e-6, (spec["id"], name)
        assert not (("headline" in zones and "cta" in zones) and _overlap(zones["headline"], zones["cta"])), spec["id"]
        if "logo" in zones:
            for name in ("headline", "cta"):
                assert name not in zones or not _overlap(zones[name], zones["logo"]), (spec["id"], name)
    assert count > 300


def test_mask_png_has_the_exact_delivery_ratio_and_is_black_and_white():
    spec = ad_masks.build_spec("feed-4x5", "split", "bottom-right", True)
    image = Image.open(io.BytesIO(ad_masks.render_mask(spec, longest_side=1350)))
    assert image.size == (1080, 1350) and image.mode == "L"
    wide = Image.open(io.BytesIO(ad_masks.render_mask(ad_masks.build_spec("iab-728x90", "split", "none", True))))
    assert abs(wide.size[0] / wide.size[1] - 728 / 90) < 0.05


def test_contract_states_cta_and_logo_presence():
    with_all = ad_masks.layout_contract(ad_masks.build_spec("feed-4x5", "foto-texto-base", "bottom-right", True))
    bare = ad_masks.layout_contract(ad_masks.build_spec("feed-4x5", "foto-texto-base", "none", False))
    assert "CTA BUTTON" in with_all and "LOGO SPACE" in with_all
    assert "NO call-to-action" in bare and "NO logo" in bare and "CTA BUTTON:" not in bare
    assert "NO headline" in ad_masks.layout_contract(ad_masks.build_spec("feed-4x5", "visual-puro", "none", False))


def test_pilot_masks_round_trip_through_their_urls():
    for spec in ad_masks.served_specs():
        assert ad_masks.spec_from_url(ad_masks.MASK_URL_PREFIX + ad_masks.mask_filename(spec)) == spec
    assert ad_masks.spec_from_url("/static/images/cadu/studio/references/feed/feed-mask-01.webp") is None
    assert ad_masks.spec_from_url(ad_masks.MASK_URL_PREFIX + "../x.png") is None


def test_studio_uses_the_mask_contract_and_its_logo_policy():
    no_logo = ad_masks.build_spec("feed-4x5", "foto-texto-topo", "none", True)
    refs = [{"source": "global", "data": ad_masks.MASK_URL_PREFIX + ad_masks.mask_filename(no_logo)}]
    lines = studio_create.composition_layout_lines(refs)
    assert len(lines) == 1 and "HEADLINE" in lines[0]
    url_refs = [{"url": refs[0]["data"]}]
    assert studio_create.mask_logo_policy(url_refs) == "none"
    brand = studio_create.brand_without_logo({"name": "X", "logo_url": "/static/a.png", "assets": {"logo": ["/static/a.png"]}})
    assert "logo_url" not in brand and brand["assets"]["logo"] == []
    with_logo = ad_masks.build_spec("feed-4x5", "split", "bottom-right", True)
    assert studio_create.logo_position([{"url": ad_masks.MASK_URL_PREFIX + ad_masks.mask_filename(with_logo)}]) == "bottom-right"


def test_every_served_mask_obeys_its_format_rules():
    from aicentralv2.creative_format_registry import catalog_entries
    rules = {row["format_key"]: row for row in catalog_entries()}
    for spec in ad_masks.served_specs():
        rule = rules[ad_masks.REGISTRY_KEYS[spec["format"]]]
        assert (rule["width"], rule["height"]) == (spec["width"], spec["height"]), spec["id"]
        zones = spec["zones"]
        required, forbidden = set(rule["required_elements"]), set(rule["forbidden_elements"])
        if "headline" in required:
            assert "headline" in zones, spec["id"]
        if "cta" in required:
            assert "cta" in zones, spec["id"]
        if "logo" in required:
            assert "logo" in zones, spec["id"]
        if {"cta", "pill_cta", "site_button"} & forbidden:
            assert "cta" not in zones, spec["id"]
        if {"product", "lifestyle"} <= forbidden:
            assert "subject" not in zones, spec["id"]
        left, top, width, height = spec["safe"]
        for name, (x, y, w, h) in zones.items():
            if name in {"panel", "logo"}:
                continue
            assert x >= left - 1e-3 and y >= top - 1e-3 and x + w <= left + width + 1e-3 and y + h <= top + height + 1e-3, (spec["id"], name)


def test_story_keeps_clear_of_the_app_interface():
    for family, logo, cta in ad_masks.MASK_SETS["story-9x16"]:
        spec = ad_masks.build_spec("story-9x16", family, logo, cta)
        for name in ("headline", "cta", "logo"):
            if name in spec["zones"]:
                x, y, w, h = spec["zones"][name]
                assert y >= 0.12 - 1e-3 and y + h <= 0.80 + 1e-3, (spec["id"], name)


def test_logo_is_applied_inside_the_slot_of_the_mask():
    import base64
    from PIL import Image
    spec = ad_masks.build_spec("story-9x16", "foto-texto-base", "bottom-right", True)
    canvas = Image.new("RGB", (1080, 1920), (20, 20, 20)); buffer = io.BytesIO(); canvas.save(buffer, "PNG")
    logo = Image.new("RGBA", (200, 60), (255, 255, 255, 255))
    out = Image.open(io.BytesIO(base64.b64decode(studio_create.apply_brand_logo(
        base64.b64encode(buffer.getvalue()).decode(), "png", logo, "bottom-right", rect=spec["zones"]["logo"])))).convert("RGB")
    x, y, w, h = spec["zones"]["logo"]
    bright = [(px, py) for py in range(0, 1920, 4) for px in range(0, 1080, 4) if out.getpixel((px, py))[0] > 200]
    assert bright and max(p[1] for p in bright) <= (y + h) * 1920 + 2 and max(p[0] for p in bright) <= (x + w) * 1080 + 2
