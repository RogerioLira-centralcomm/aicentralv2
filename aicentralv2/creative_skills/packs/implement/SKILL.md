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

- fixed creative canvas 1920×1080
- independent layers
- stable IDs
- CSS variables from Marcas DNA
- no unnecessary dependencies
- animation-ready
- screenshot-safe
- browser deterministic

Fill prototype slots only. Do not invent a new layout.

Before the first campaign still, model a black 16:9 HTML mockup (the format skill wireframe) with GPT-4o-mini, 1 to 3 cheap passes. That base HTML is the pattern every later scene inherits.

Layer IDs stay: layer-brand, layer-headline, layer-support, layer-cta, layer-qr, layer-key-visual.
Brand ink and accent come from the Marcas payload.
Logo is not mandatory on every beat: last scene always on and centered; opening scenes follow the storyboard lock.
Do not rewrite the entire HTML during refinements — apply patches.
