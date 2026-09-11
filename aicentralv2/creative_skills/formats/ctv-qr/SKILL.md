---
name: ctv-qr
aliases:
  - ctv-video-qr
triggers:
  - Video + QR
  - companion
expected_inputs:
  - brand_context
  - campaign_model
expected_outputs:
  - 4 scenes with QR on 03 and 04
failure_conditions:
  - removing QR
  - converting QR into a website button
---

# CTV Video + QR / Companion

Canvas: 1920×1080
Interaction: companion — QR on TV, response on mobile
Adapter: youtube_ctv

QR stays on scene_03 and scene_04, right side, inside the safe area.
Keep id="layer-qr" and the tip above the QR.
Do not convert the QR into a desktop URL button.
Brand name, logo and DNA colors come from Marcas.
