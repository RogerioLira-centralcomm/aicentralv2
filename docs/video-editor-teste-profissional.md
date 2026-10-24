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

## Montar na timeline a partir do storyboard (24/10)

`POST …/video-editor/projects/<id>/montage` lê o storyboard salvo no projeto pela tela de Vídeo (`script.beats` + `scene_ids`), vincula as imagens das cenas como mídia do projeto e monta a timeline. No editor: menu **Cadu → Montar do storyboard…**.

- **Diretor** (`creative_media/studio_montage.py`, padrão `anthropic/claude-sonnet-5.5` pelo A/B abaixo, trocável por `CREATIVE_VIDEO_MONTAGE_MODEL`): vê uma imagem por cena e devolve só o plano (peso, texto já gravado, enquadramento preencher/inteira, caixa do sujeito, movimento, frase curta, zona). O código aproxima e centraliza a caixa do sujeito e põe o texto na faixa que não encosta nela. Cobrança pela mesma régua do storyboard (`stage=video_montage`). Se falhar, a montagem usa as regras e avisa.
- **Compilador** (código): área segura do Reels (texto entre 13% e 82% da altura), texto troca de lado se cair sobre o sujeito, preenchimento sem bordas ou imagem inteira sobre fundo desfocado, imagem com texto gravado entra inteira e sem zoom e sem texto por cima, soma das durações, vídeo não estica além da origem, cores da marca nas caixas de texto, logo da marca no canto seguro.

### A/B no Lab (`scripts/lab_montage.py`)

Casos com mídia real do Studio: **tecnologia** (vídeo de celular + 4 ilustrações) e **CEMIG** (4 artes verticais com título, CTA e logo já gravados). Juiz cego com visão (`anthropic/claude-haiku-5.5`).

Rodada parcial de 24/10 (sem juiz: a chave do OpenRouter não está no `.env` local):

| Caso | Regras | gpt-5-mini |
|---|---|---|
| CEMIG | Põe "Saiba mais." por cima do texto da arte | Detecta o texto gravado: artes inteiras, nenhum texto por cima |
| Tecnologia | Vídeo e ilustrações inteiros; títulos só no fim | Títulos em todas as cenas, mas escolhe "preencher" e corta a cena da equipe |

Rodada completa de 24/10 (juiz cego Haiku 5.5, chave lida de Integrações só para leitura), já com a caixa do sujeito:

| Variante | Tecnologia (nota) | CEMIG (nota) | Texto sobre o sujeito | Tempo do plano | Tokens (entrada+saída) |
|---|---|---|---|---|---|
| Regras | 3,4 | 3,5 (texto por cima da arte) | 0 / 0 | — | — |
| Opus 5.5 | 3,2 | 3,75 | 0 / 1* | 13–19 s | ~4 mil + 1,2–1,8 mil |
| **Sonnet 5.5** | **3,4** | **3,75** | 0 / 1* | **5–6 s** | ~4 mil + 0,6–0,9 mil |
| gpt-5-mini | 3,0 | 3,75 | 1 / 1* | 12–18 s | ~3 mil + 1–1,4 mil |

\* no CEMIG o juiz marca o texto já gravado na arte, que nenhum modelo cobriu.

**Decisão:** Sonnet 5.5 como diretor padrão (empata ou supera o Opus com metade do custo e 3× mais rápido). O ganho sobre as regras aparece onde o código sozinho não alcança: detectar arte com texto gravado (CEMIG) e escrever títulos por cena. Na primeira rodada, sem a caixa do sujeito, todos os modelos cobriam o celular com o texto do gancho; a caixa resolveu. Limite que nenhum modelo resolve: arte quadrada com sujeito pequeno em 9:16 fica com muito fundo (as cenas de ilustração tiraram notas 2–3 em todas as variantes).

Rodada nova:

```sh
OPENROUTER_API_KEY=… .venv/bin/python scripts/lab_montage.py --gpu metal
```

Saída: tabela por caso e variante (nota do juiz, texto sobre o sujeito, texto duplicado, ilegível, sujeito cortado, bordas, tempo e tokens), vídeos e quadros em `instance/lab-montage/`. O modelo do diretor no Studio só muda com ganho medido aqui.
