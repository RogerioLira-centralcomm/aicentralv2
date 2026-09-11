---
name: ctv-video
aliases:
  - ctv-video-linear-30
  - ctv-video-cta
triggers:
  - CTV video 30s
  - Video + CTA
expected_inputs:
  - brand_context
  - campaign_model
expected_outputs:
  - 4 scenes 1920x1080
failure_conditions:
  - mobile UI chrome
  - extra scenes
  - landing page
---

# CTV Video Format

Canvas: 16:9
Primary outputs: 1920×1080
Default narrative: 4 scenes
Interaction: none — linear storyboard

Scene roles:
1. Hook
2. Context / benefit
3. Proof / emotion
4. CTA

Rules:
- TV viewing distance
- very low text density
- large typography
- strong branding from Marcas
- CTA simple
- avoid mobile-like controls

Compositions:
- A Hook → Benefit → Proof → CTA
- B Problem → Solution → Experience → CTA
- C Brand → Product → Lifestyle → CTA
- D Question → Discovery → Benefit → CTA

Do not invent extra scenes. Remap purpose and copy slots only.
Adapters: generic_ctv, netflix.
Prototype files: scene-01.html … scene-04.html.
