# CTV Video Linear 30s

FORMAT: ctv-video-linear-30
CANVAS: 1920 × 1080
INTERACTION: none — linear storyboard, 30 seconds
ADAPTERS: generic_ctv, netflix
PROTOTYPE: 4 independent HTML scenes, same skeleton

## Mechanic

A 30-second linear CTV spot. No QR, no companion, no pause takeover.
The viewer watches. The CTA is visual on the last beat.

## Scenes

| id | default purpose | timecode | file |
|----|-----------------|----------|------|
| scene_01 | hook | 00:01 | scene-01.html |
| scene_02 | benefit | 00:08 | scene-02.html |
| scene_03 | proof | 00:15 | scene-03.html |
| scene_04 | cta | 00:28 | scene-04.html |

## Compositions

- A: hook → benefit → proof → cta
- B: problem → solution → experience → cta
- C: brand → product → lifestyle → cta
- D: question → discovery → benefit → cta

Do not invent extra scenes. Remap purpose and copy slots only.

## Layers that must stay

- layer-safe (5% inset)
- layer-brand + layer-brand-mark
- layer-platform
- layer-copy (headline + support)
- layer-timeline
- scene_04 also has layer-cta

## Brand slots

- brand name replaces SUA MARCA
- logo replaces .brand-mark
- DNA colors become --brand-ink and --brand-accent
- platform label stays GENERIC CTV or NETFLIX — do not turn it into a website header

## Forbidden

- Do not add navigation, forms, or a landing page.
- Do not move CTA to scene 1 unless composition explicitly asks for an early CTA.
- Do not drop the timeline chrome — it is the CTV metaphor.
