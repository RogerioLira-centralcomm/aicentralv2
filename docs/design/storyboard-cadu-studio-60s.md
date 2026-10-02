# Storyboard — "Cadu Studio para agências" (60s, 16:9)

Prova de conceito: cada cena nasce em **Criar** (still) e vira clipe no **Vídeo** (Seedance 2.5,
`source.mode = "storyboard"` ou `flattened_still`). Locução e trilha entram depois (ElevenLabs),
por isso todo clipe usa o preset de áudio `voiceover` (sem fala, só ambiência leve).

Formato: Criar → canal **CTV**, 16:9, 1920×1080, qualidade Alta, 1 variação por cena.
Marca do projeto: Cadu (logo e paleta oficiais do Workspace; `creation_intent = branded_creative`).

Cenas de interface (2–7) não devem ser inventadas pelo modelo de imagem: usar as **capturas reais**
das telas (Fase 0, 1440px, tema escuro) como referência `source="project"`, role `primary`, e no
Seedance o preset `live` + intensidade `subtle` (layout travado — texto de UI não pode deformar).

| # | Tempo | Locução (pt-BR) | Prompt para Criar (still) | Seedance 2.5 (movimento) |
|---|---|---|---|---|
| 1 | 0–7s | "Sua agência cria em dez ferramentas. E se fosse uma só, que conhece a sua marca?" | Mesa de agência à noite, vista de cima a 45°, monitor ultrawide com muitas janelas sobrepostas e desfocadas, post-its, celular com notificações; luz fria do monitor e luz âmbar de luminária; área limpa no terço direito para título. Sem logos de terceiros, sem texto legível nas janelas. | preset `camera`, `moderate`: push-in lento até o monitor; as janelas se recolhem para o centro e a tela termina escura e limpa. Hold de 1s. |
| 2 | 7–14s | "Este é o Cadu Studio. Escolha o cliente: logo, cores e histórico já estão aqui." | Referência: captura da navbar + seletor de projeto aberto. Pedido: "aplicar a captura como tela de um monitor em ambiente de estúdio escuro, enquadramento frontal, leve reflexo". | preset `live`, `subtle`: parallax mínimo, brilho percorre o seletor de marca. Layout travado. |
| 3 | 14–22s | "Descreva a ideia. O Studio monta a direção criativa e gera as peças no formato certo." | Referência: captura do Criar com direção aprovada e 2 variações. Mesmo ambiente da cena 2. | `live`, `subtle`: luz desliza dos cards de resultado para o painel Entrega. |
| 4 | 22–30s | "Precisa mudar só o produto ou a chamada? Marque a área. O resto fica intacto." | Referência: captura do Editor com máscara pintada sobre o produto. | `live`, `subtle`: a área mascarada pulsa suavemente; nada mais se move. |
| 5 | 30–38s | "Transforme o estático em vídeo com o modelo mais avançado do momento." | Still da peça gerada na cena 3 (vem da biblioteca, sem nova geração). | `product`, `expressive`: câmera orbita o produto, luz e reflexo ganham vida; sem deformar embalagem/rótulo. |
| 6 | 38–45s | "E finalize na timeline com legendas, cortes e transições." | Referência: captura do Vídeo com timeline, legendas e trilhas. | `live`, `subtle`: playhead percorre a timeline da esquerda para a direita. |
| 7 | 45–52s | "Locução e trilha sob medida, prontas para mixar." | Referência: captura do Áudio (forma de onda + vozes). | `live`, `subtle`: forma de onda acende em ritmo; layout travado. |
| 8 | 52–60s | "Do briefing à peça aprovada, num só lugar. Cadu Studio." | End card: fundo escuro profundo com gradiente sutil da paleta da marca, logo oficial Cadu centralizado dentro da área segura, espaço abaixo para assinatura. Sem texto gerado. | `transition`, `subtle`: entra a partir do último frame da cena 7 (`transition_ab`) e segura 2s como end card. |

Observação: o Analisador ficou fora desta versão (escopo adiado).

## O que hoje impede este fluxo de ser "fácil" (verificado no código e no banco, 2026-10-02)

| Ferramenta | Onde grava | Problema |
|---|---|---|
| Criar | `cx_studio_creation_runs` (2), `cx_studio_image_generations` (11), `cx_studio_project_items` | Imagens ficam no histórico do projeto de criação |
| Vídeo | `cx_media_jobs` (6), `cx_media_assets` (24, arquivos em `instance/creative_media/`) | A biblioteca do Vídeo lê **só** a biblioteca do Trocr (`swapApi/library?media=still`) — imagens do Criar não aparecem |
| Editor | `cx_studio_sessions` (0 linhas) | Sessões duráveis ainda sem uso real |
| Hub | `cx_studio_assets` (**0 linhas**) | A tabela pensada para ser a biblioteca única existe mas ninguém grava nela |

No Criar, o único elo com vídeo é um link estático "Vídeo é criado no Video Studio"
(`cadu-studio-create-v2.js:9`), sem levar a imagem.

## Correção proposta — "Biblioteca única + Enviar para Vídeo"
1. Toda saída (imagem do Criar, sessão do Editor, clipe/export do Vídeo, áudio) grava uma linha em
   `cx_studio_assets` com `project_id`, `source_type` (`create|editor|video|audio|trocr`) e `source_id`.
   Backfill das 11 gerações e 24 mídias existentes.
2. Endpoint único `GET /studio/api/assets?project_id&kind=image|video|audio` usado por todas as telas.
3. Ação **"Enviar para Vídeo"** em cada resultado do Criar (e seleção múltipla = storyboard):
   abre o Vídeo com `?project_id=…&scenes=<asset_ids>` e já monta as cenas na ordem.
4. O planner do Vídeo aceita `asset_id` de `cx_studio_assets` além dos ids do Trocr.
5. Arquivos de vídeo saem de `instance/` local para o mesmo storage dos assets do Studio.
