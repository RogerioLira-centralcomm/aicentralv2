# CTV Video + QR / Companion

FORMAT: ctv-video-qr
CANVAS: 1920 × 1080
INTERACTION: companion — QR on TV, response on mobile
ADAPTER: youtube_ctv
PROTOTYPE: 4 HTML scenes; QR appears on scene_03 and scene_04

## Mechanic

Linear 30s CTV with a mobile companion. The QR is a scan target, not a decoration.
Keep the QR on the right, inside the safe area. Keep the tip label above the QR.

## Scenes

| id | default purpose | timecode | file | extra layers |
|----|-----------------|----------|------|--------------|
| scene_01 | hook | 00:01 | scene-01.html | layer-ctv-icon |
| scene_02 | benefit | 00:08 | scene-02.html | layer-screen |
| scene_03 | response | 00:18 | scene-03.html | layer-qr, layer-tip, layer-cta |
| scene_04 | cta | 00:28 | scene-04.html | layer-qr, layer-cta |

## Compositions

- A: QR fixed on the last two beats
- B: QR enters in the last 8s (scene_03 + scene_04)
- C: QR companion on the right, copy on the left
- D: QR + product (layer-screen stays available)

Never remove the QR from scene_03 or scene_04.

## Brand slots

- brand name, logo, DNA colors
- platform label stays YOUTUBE CTV
- .tip default: APONTE A CÂMERA
- .qr receives a real QR image when supplied; otherwise keep the placeholder

## Forbidden

- Do not convert the QR into a URL button for desktop.
- Do not redesign the companion as a website footer.
- Do not hide the tip label.
