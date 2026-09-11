---
name: visual-diff-qa
pack: validate
triggers:
  - after chromium render
expected_inputs:
  - render
  - reference if any
  - format skill
expected_outputs:
  - passed
  - defects
  - patches
failure_conditions:
  - full HTML rewrite
  - taste feedback without geometry
---

# Visual Validation Pack

Compare reference vs browser render.

Check: canvas, geometry, spacing, typography, image crop, contrast, hierarchy, brand position, CTA position.

Do not provide general design feedback.
Output only actionable differences as patches.

Never rewrite entire HTML. Always PATCH.
Preserve format mechanic and Marcas brand position.
