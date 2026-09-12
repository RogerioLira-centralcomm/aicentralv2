---
name: video-15
aliases:
  - video-linear-15
  - video-cta-15
  - ctv-video-linear-30
  - ctv-video-cta
triggers:
  - Video 15s
  - horizontal 16:9
expected_inputs:
  - brand_context
  - campaign_model
  - knobs
expected_outputs:
  - 4 or 5 scenes 1920x1080
failure_conditions:
  - 30s storyboard
  - mobile UI chrome
  - player chrome
  - landing page
  - brand only in the footer
---

# Video 15s Format

Canvas: 16:9
Primary outputs: 1920×1080 stills
Duration: 15 seconds
Scenes: 4 or 5
About 3 to 3.75 seconds per frame
Interaction: none — concept storyboard, not a finished film

4 scenes: Hook → Benefit → Proof → CTA
5 scenes: Hook → Context → Benefit → Proof → CTA

Rules:
- TV viewing distance
- very low text density
- large typography
- brand must live inside the frame (color, type, tone)
- last scene is the end card: logo always on and centered
- opening and middle beats may show the logo or not; the storyboard decides, the human can lock it
- brand beat defaults to logo on; hook / benefit / proof default off unless locked on
- first output is a black HTML mockup of the format, then scenes inherit it
- CTA simple, one action
- no YouTube / Netflix / LinkedIn chrome
- no invented extra scenes beyond 4 or 5
- QR never on the hook; if present, on proof or CTA

Image loop: up to 3 stills per scene. Version 1 is a draft. Versions 2 and 3 answer the QA defects. Keep discarded frames for the human. Generate one scene at a time.

Before scene 01, model a black HTML mockup with GPT-5-nano (1–3 cheap passes) from brand assets and the format wireframe. Later scenes clone that base and only change copy, key visual and whether the logo is on.

Key visual: the user picks photos already stored on the brand. Those photos are the campaign KV — product, box, gesture — not stock.

This experiment delivers approval stills. Do not write a shot list for a 30s film.
Adapters stay in the backend for a later player dress. Do not draw them now.

Still plates (not channel skins):
- split — type left, product floats on black (L'Oréal in Netflix)
- hero — key visual full-bleed, type over a dark left veil (NYX face)
- center — lockup and verb on axis (end card)

Brand DNA fills the plate. Do not author a new HTML template per brand.

Close the still in Python before sending:
- background is a color wash or a full-frame image
- product and logo are isolated GPT Image 2 layers (transparent PNG)
- type is drawn on the stack, not painted into the photo
- compose 1920×1080, then clamp every lockup into the 6% TV safe margin
- keep layer boxes for future motion. Do not generate the film.
