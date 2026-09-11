---
name: creative-reconstruct
pack: reconstruct
triggers:
  - intent reconstruct
  - reference image
expected_inputs:
  - reference image
  - format skill
expected_outputs:
  - spec
  - patches
failure_conditions:
  - modernizing the design
  - aesthetic improvement during reconstruction
---

# Reconstruct Pack

Reconstruct an advertising creative from a visual reference with maximum fidelity.

- Treat reference image as source of truth.
- Do not reinterpret, modernize or improve aesthetics.
- Preserve aspect ratio, composition, hierarchy, card and CTA locations.

Raster-first: if CSS loses fidelity, keep photography, texture and complex gradients as raster.
HTML for text and buttons.
Return patches, not a full rewrite.
