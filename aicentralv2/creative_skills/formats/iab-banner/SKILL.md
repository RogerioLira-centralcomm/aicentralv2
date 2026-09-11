# IAB banner 15s

Animated IAB unit. Same 4 or 5 beats as the CTV concept. The rectangle changes; the story does not.

The IAB base kit on Placas mounts **scene 1 only**. Later scenes stay in the Bancada.

## Rules

- Keep layer IDs: layer-brand, layer-headline, layer-support, layer-cta, layer-key-visual, layer-ground, layer-cast, layer-meta, layer-chips, layer-lockup.
- Do not invent player chrome, app UI or extra frames.
- Use the native canvas. Do not force 16:9 onto a banner.
- Billboard and leaderboard read left to right. Half page and skyscraper read top to bottom.
- Medium rectangle is a compact split: type left, object right.
- Thin units (320×50, 728×90): one line, hide support, tiny product at the far end.
- Vertical units: type on top, product in the lower third, smaller than the canvas.
- Typeface comes from Marcas DNA `fonts.primary` / `fonts.fallback`. Never reuse another brand's face.
- Product cutouts are two transparent PNGs (horizontal and vertical), applied with `contain`, 55–70% of the shorter side. No full-bleed on the IAB base.
- Event posters (cast): Image 2 splits people (transparent PNG) from the field. Bunting, dates, names and logos stay HTML/CSS so the same layers reflow to every IAB rectangle. Use `plate-cast`. Never bake type into the photo.
- Last scene always has the CTA and the logo on. The base kit is scene 1.
- Copy in Brazilian Portuguese. Spell lines exactly when locked.
- Safe area stays inside the IAB unit. No bleed past the canvas.
- Refine with patches only. Three GPT-4o-mini passes per family (horizontal / box / vertical). Do not return a new HTML document.
