# Teste profissional do editor de vídeo

Objetivo: saber se o vídeo que sai do editor tem qualidade de entrega profissional, e se os três caminhos de saída geram o mesmo resultado. Roda com `scripts/studio_video_pro_test.py` (sem banco; render do servidor e com GPU) e com o botão Exportar no servidor de teste (navegador).

## Peça de teste

**Formato:** Reels/Stories, 9:16, 1080×1920, 30 fps, 12 s.
**Material:** só mídia gerada pelo próprio Studio, de `aicentralv2/static/uploads/creative_generated` (pasta local de uploads, fora do git; o script aceita outra pasta com `--assets`). Um vídeo de IA de um celular (`4ae3092d…mp4`, 720p, com áudio) e quatro ilustrações da mesma linha visual (roxo e verde-água). A trilha é o áudio do vídeo `a3f61ccb…mp4`. Ela não combina com uma peça de tecnologia, mas serve para medir a mixagem.

| Tempo | Função | Imagem | Texto na tela |
|---|---|---|---|
| 0–3 s | Gancho | Vídeo do celular, preenchendo a tela vertical | "Seu negócio na palma da mão" (topo) |
| 3–5,25 s | Benefício 1 | Ilustração de dispositivos | "Gestão em qualquer tela" |
| 5,25–7,5 s | Benefício 2 | Ilustração de painéis | "Dados em tempo real" |
| 7,5–9,75 s | Prova | Ilustração de pessoas e gráfico | "Sua equipe conectada" |
| 9,75–12 s | CTA | Ilustração do mapa | "Teste grátis por 30 dias" (caixa verde, base) |

**Áudio:** som do vídeo do celular no gancho; trilha de 0 s a 12 s, em segundo plano.

## Especificação de entrega (critérios de aprovação)

| Item | Critério | Como medir |
|---|---|---|
| Resolução e fps | 1080×1920, 30 fps constantes | ffprobe |
| Duração | 12 s ± 1 quadro | ffprobe |
| Codec | H.264 (High) + AAC, `faststart` | ffprobe |
| Taxa de bits | ≥ 5 Mb/s em 1080p (as redes recodificam; abaixo disso aparecem blocos em movimento) | ffprobe |
| Volume | −14 LUFS ± 1 (Instagram/TikTok/YouTube) | `ebur128` |
| Pico real | ≤ −1 dBTP | `ebur128` |
| Quadros pretos ou congelados | Nenhum fora do previsto | `blackdetect`, `freezedetect` |
| Área segura do texto | Fora dos 250 px de cima e dos 340 px de baixo (interface do Reels) | Leitura dos quadros |
| Legibilidade | Texto com contraste, sem cortar palavra | Leitura dos quadros |
| Consistência entre caminhos | Navegador × servidor × GPU visualmente iguais (SSIM ≥ 0,95) | `ssim` |

## O que é "profissional" além da técnica (avaliação humana)

1. Ritmo: corte a cada 2 a 3 s em peça de 12 s, gancho forte nos primeiros 1,5 s.
2. Movimento: nada parado por mais de 2 s (zoom lento em imagem, transição entre cenas).
3. Tipografia: hierarquia clara (título, apoio, CTA), fonte da marca, entrada animada.
4. Som: trilha coerente com a peça, volume sob controle, sem estalos nos cortes.
5. Marca: logo e cor da marca presentes de forma consistente.
