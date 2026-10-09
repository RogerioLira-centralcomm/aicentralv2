# Ícones dos temas do Radar (image 2.5)

Gerados por `scripts/generate_radar_icons.py` (`gpt-image-2.5-sunburst`, ~US$ 0,01 cada). Traço único, preto, sem cor; o script converte o brilho em transparência (256×256) e a interface pinta com `mask` + `currentColor`.
Saída: `aicentralv2/static/images/radar-tipos/{chave}.png`. Para refazer um: `.venv/bin/python scripts/generate_radar_icons.py --refazer midia`.

Prompt-base: *minimalist app icon glyph, monoline outline, uniform rounded stroke, pure black on pure white, no colors/gradients/shadows/text, centered with margin, legible at 24px, custom-drawn rather than generic.*

| Chave | Tema (regex em `RadarHub.jsx`) | Motivo |
|---|---|---|
| concorrentes | concorr, lançamento | lupa sobre pessoa/pódio |
| midia | programátic, ctv, mídia, tv | janela com play e ondas |
| logistica | transporte, logíst, frota | caminhão + rota com pino |
| consumo | consum, conta, luz, tarifa, energia | lâmpada com folha |
| investimento | invest, capital, debênture | barras + seta + moeda |
| regulacao | regula, norma, lei | documento com balança |
| pauta | (ângulo tipo conteúdo) | bloco de notas com lápis |
| tendencias | padrão / tipo "para saber" | pulso + arco de radar |

Novo tema: acrescentar a chave em `ICONS` do script e a regex em `THEMES`.
