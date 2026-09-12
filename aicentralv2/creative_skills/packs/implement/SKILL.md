---
name: creative-html-engine
pack: implement
triggers:
  - spec ready
  - intent html
expected_inputs:
  - CreativeFormatSpec
  - format prototype
  - brand_context
expected_outputs:
  - HTML per scene
  - stable layer IDs
failure_conditions:
  - landing page
  - rewriting mechanic
  - missing layer IDs
---

# Implementation Pack

Convert approved creative specification into deterministic HTML/CSS.

Requirements:

- native creative canvas (1920×1080 on CTV; IAB uses the format rectangle)
- independent layers
- stable IDs
- CSS variables from Marcas DNA (`fonts.primary` / `fonts.fallback`, ink, accent, logo)
- no unnecessary dependencies
- animation-ready
- screenshot-safe
- browser deterministic

Fill prototype slots only. Do not invent a new layout.

Before the first campaign still, model a black 16:9 HTML mockup (the format skill wireframe) with GPT-5-nano, 1 to 3 cheap passes. That base HTML is the pattern every later CTV scene inherits.

The IAB base kit on Placas is a different job: scene 1 only, native IAB canvas, three patch passes per family (horizontal / box / vertical). Same patch contract. Product cutouts are transparent PNG layers, smaller than the rectangle.

Layer IDs stay: layer-brand, layer-headline, layer-support, layer-cta, layer-qr, layer-key-visual, layer-ground, layer-cast, layer-meta, layer-chips, layer-lockup.
Event/cast posters: field + pennants in CSS, people as a transparent PNG, type as HTML. Image 2 only cuts the photograph — it does not redraw the layout.
Brand ink, accent and typeface come from the Marcas payload.
Logo is not mandatory on every beat: last scene always on and centered; opening scenes follow the storyboard lock.
Do not rewrite the entire HTML during refinements — apply patches.
