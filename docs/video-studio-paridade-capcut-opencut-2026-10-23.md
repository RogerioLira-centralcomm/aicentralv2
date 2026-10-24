# Editor de vídeo do Studio: o que falta para paridade com CapCut (referência OpenCut)

23/10/2026. Análise estática do código em `main` (`creative_media/studio_composition.py`, `studio_layers.py`, `studio_keyframes.py`, `static/js/cadu-video/*`) e do repositório OpenCut. Nada foi executado em tela nem em produção. Atualiza `backlog-video-studio-capcut-80.md` (14/09), que ficou parcialmente superado pelas entregas de 15/09.

## 1. O que é o OpenCut hoje

- `opencut-app/opencut` (MIT, ~96 mil estrelas) **está sendo reescrito do zero**: núcleo em Rust para web/desktop/mobile, Editor API, plugins, servidor MCP para agentes, modo headless para render em lote. Ainda não está pronto; roda em `new.opencut.app`.
- A versão utilizável é `opencut-app/opencut-classic`, **arquivada desde maio/2026**. Next.js + React + Zustand, compositor GPU em Rust/WASM (wgpu), mídia guardada no navegador (OPFS/IndexedDB), transcrição no navegador por worker.
- O OpenCut **também não é um CapCut completo**: o clássico tem um único efeito (blur), nenhum sistema de transições, nenhum template. A força dele é a **arquitetura do editor**, não o catálogo.

O que vale copiar do OpenCut (conceitos; o código é MIT e pode ser aproveitado com atribuição):

| Subsistema OpenCut | Onde | Ideia |
|---|---|---|
| Faixas livres de qualquer tipo | `commands/timeline/track/*`, `timeline/` | N faixas de vídeo/imagem/texto/sticker/gráfico/áudio; elemento com início livre, sobreposição entre faixas = camadas (PiP, B-roll, logo) |
| Comandos + lote | `commands/base-command.ts`, `batch-command.ts` | Toda alteração é um comando; um gesto = um passo de desfazer |
| Registro de ações e atalhos | `actions/definitions.ts`, `keybindings` | ~28 ações (split-left/right, frame-step, copy/paste, toggle snap/ripple, bookmark…) com atalhos personalizáveis |
| Keyframes genéricos | `animation/*`, `docs/keyframes.md` | Canal por caminho de propriedade (número, cor, discreto); editor de curva Bézier; copiar/colar keyframes |
| Máscaras | `masks/*` | Retângulo, elipse, estrela, coração, losango, barras de cinema, split, texto e livre; feather e inversão |
| Retime | `retime/*` | Velocidade com presets e esticamento de áudio; split respeitando a velocidade |
| Separação de áudio | `timeline/audio-separation` | Liga/desliga o áudio de origem do clipe como item próprio |
| Renderizador único | `services/renderer/*`, `rust/wasm` | Mesmo grafo de nós (vídeo, imagem, texto, sticker, gráfico, fundo desfocado, efeito) na prévia e na exportação |
| Outros | `bookmarks`, `stickers`, `graphics`, `guides`, `preview-snap` | Marcadores, figuras/bandeiras/logos, guias e encaixe no canvas |

## 2. Onde o Studio já está

O Studio está à frente do OpenCut e do CapCut nas partes de IA e de produção, e atrás na edição clássica.

**Já existe:** importação de MP4/MOV/WebM (150 MB/5 min) com FFprobe; montagem de até 120 itens com dividir, duplicar, reordenar, cortar, velocidade 0,25–4×, contain/cover, zoom em imagem; 5 transições (corte, fade, fade preto, slide, wipe); até 8 trilhas de áudio com volume, fades, mute/solo, loop e envelope de ganho; limpeza de voz; extração de áudio; 100 efeitos sonoros CC0; até 8 textos com keyframes de posição/escala/rotação/opacidade; legendas manuais, SRT e transcrição local (faster-whisper) com 10 estilos; cortes automáticos de silêncio/hesitação; exportação MP4/GIF/HTML em 720p/1080p, 24/30 fps; fila durável com worker; agente lateral; geração Seedance, storyboard por briefing e presença da marca.

**Limites estruturais encontrados no código:**

1. **Uma única sequência visual.** `items` são consecutivos; não há segunda faixa de vídeo/imagem. Sem isso não existem PiP, B-roll por cima, logo/sticker na timeline, overlay de vídeo ou green screen.
2. **Dois renderizadores.** Prévia em Canvas 2D (`live-preview.js`) e exportação em FFmpeg. A própria documentação admite diferença em tipografia, mixagem, transições e limpeza de voz. Cada efeito novo precisa ser escrito duas vezes e conferido.
3. **Tempo em segundos `float`**, não em quadros; limites de 300 s por item e 600 s de áudio.
4. **Keyframes só em 5 propriedades** (x, y, escala, rotação, opacidade) e só para itens e textos; sem cor, volume por keyframe no item, efeito ou máscara; sem editor de curva.
5. **Textos limitados a 8**, animação só "fade"; legendas sem destaque palavra a palavra.
6. **Sem**: copiar/colar, marcadores, reverse, congelar quadro, ajustes de cor, filtros/LUT, máscaras, modos de mesclagem, chroma key, stickers/figuras, rampa de velocidade, recorte (crop) livre, estabilização, rastreamento, templates.
7. Ajustes de cor existem só no editor de clipe único antigo (preto e branco, espelhar).

## 3. Matriz de paridade

Legenda: ✅ tem · ◐ parcial · ❌ não tem.

| Recurso CapCut | OpenCut clássico | Studio | Observação |
|---|:-:|:-:|---|
| Importar vídeo/imagem/áudio | ✅ | ✅ | Studio: imagem ainda entra uma por vez |
| Várias faixas de vídeo (camadas, PiP) | ✅ | ❌ | **Bloqueador nº 1** |
| Dividir, cortar, mover, duplicar, apagar | ✅ | ✅ | |
| Ripple / fechar lacuna | ✅ | ◐ | Só na sequência principal |
| Copiar/colar, marcadores | ✅ | ❌ | |
| Atalhos completos (J/K/L, quadro a quadro, S) | ✅ | ◐ | Setas, espaço, delete, Ctrl+Z |
| Encaixe (snap) | ✅ | ✅ | |
| Velocidade constante | ✅ | ✅ | |
| Rampa de velocidade, reverse, congelar | ◐ | ❌ | |
| Transformar (posição, escala, rotação, opacidade) | ✅ | ✅ | |
| Crop livre, fundo desfocado | ✅ | ◐ | Só contain/cover |
| Keyframes em qualquer propriedade + curvas | ✅ | ◐ | 5 propriedades, sem curva Bézier |
| Máscaras com feather | ✅ | ❌ | |
| Mesclagem, chroma key, remover fundo | ❌ | ❌ | |
| Filtros e ajuste de cor | ◐ | ❌ | OpenCut tem blur |
| Efeitos visuais (glitch, shake, glow…) | ❌ | ❌ | |
| Transições | ❌ | ◐ | Studio tem 5 |
| Texto com estilos, fundo, contorno | ✅ | ◐ | Máx. 8, animação só fade |
| Animações de texto (entrada/saída/loop) | ◐ | ❌ | |
| Stickers, figuras, logos | ✅ | ❌ | Logos da marca existem só no storyboard |
| Legendas automáticas | ✅ | ✅ | |
| Legenda palavra a palavra / karaokê | ❌ | ❌ | Padrão de Reels/TikTok |
| Tradução de legendas | ❌ | ❌ | |
| Áudio multifaixa, fades, volume | ✅ | ✅ | |
| Separar áudio do vídeo | ✅ | ✅ | |
| Ducking, normalização, redução de ruído | ◐ | ◐ | Limpeza de voz sim; ducking não |
| Batida/beat sync | ❌ | ❌ | |
| TTS / locução | ❌ | ◐ | Na geração; não como item avulso |
| Cortar silêncios automático | ❌ | ✅ | Vantagem do Studio |
| Geração por IA, storyboard, marca | ❌ | ✅ | Vantagem do Studio |
| Templates | ❌ | ❌ | |
| Prévia = exportação | ✅ | ◐ | Dois renderizadores |
| Exportar 4K / 60 fps / MOV | ◐ | ❌ | Studio: 720/1080, 24/30 |

## 4. Decisões que vêm antes do código

### 4.1 Não incorporar o OpenCut inteiro

Não recomendo fazer fork nem embutir o OpenCut:

- é outro stack (Next.js/React + Rust/WASM), e o Studio é Flask + módulos ES sem bundler de framework;
- o clássico está arquivado e o novo ainda não tem versão utilizável;
- ele guarda a mídia no navegador, e o Studio precisa de mídia por marca, fila no servidor, custos e o agente;
- o catálogo dele (efeitos, transições, templates) é menor que o nosso em parte.

Recomendo **portar a arquitetura** (faixas livres, comandos, registro de ações, canais de keyframe, máscaras) e reaproveitar trechos pontuais do código MIT com atribuição: curvas Bézier e interpolação (`animation/bezier.ts`, `interpolation.ts`), geometria de máscaras (`masks/geometry.ts`, `feather.ts`) e cálculo de retime (`retime/*`). Vale acompanhar o modo headless e o MCP do novo OpenCut como possível motor de render no futuro.

### 4.2 Um renderizador só

É a decisão mais cara e a que mais pesa daqui em diante. Cada máscara, efeito e animação de texto nova exige hoje duas implementações (Canvas e FFmpeg) e testes de equivalência.

| Opção | Prós | Contras |
|---|---|---|
| A. Manter Canvas 2D + FFmpeg e testar equivalência por quadros de referência | Menor mudança agora | Custo dobrado a cada recurso; diferença visual permanente |
| B. **Renderizador WebGL2 em JS na prévia, e a exportação executa o mesmo renderizador no servidor via Chromium headless + WebCodecs, quadro a quadro; FFmpeg só para mux e áudio** | Um código para os dois; prévia igual ao MP4; efeitos/máscaras em shader | Spike necessário: tempo de render, GPU/CPU no servidor, codecs |
| C. Renderizar tudo no servidor (prévia por proxy renderizado) | Simples | Prévia lenta; inviável para edição fluida |

Recomendação: **B**, validada por um spike de 1 semana antes do Marco 2 (render de 60 s em 1080p no servidor de produção, comparação de tempo com o FFmpeg atual). Se o spike falhar, cair para A e restringir o catálogo a efeitos que o FFmpeg faz bem.

### 4.3 Modelo de composição v3

Substituir `items/audio/layers/captions` separados por faixas genéricas, em quadros:

```json
{
  "schema_version": 3,
  "fps": 30, "canvas": {"width": 1080, "height": 1920, "background": {"kind": "blur"}},
  "tracks": [
    {"id": "t_main", "kind": "visual", "main": true, "muted": false, "hidden": false, "locked": false,
     "elements": [{"id": "e1", "type": "video", "asset_id": "...", "start": 0, "duration": 180,
                   "trim_in": 30, "speed": {"kind": "constant", "rate": 1},
                   "transform": {"x": 0.5, "y": 0.5, "scale": 1, "rotation": 0, "opacity": 1, "crop": [0,0,0,0]},
                   "blend": "normal", "masks": [], "effects": [], "transition_out": null,
                   "animations": {"channels": {"transform.scale": [{"frame": 0, "value": 1, "ease": [0.4,0,0.2,1]}]}}}]},
    {"id": "t_overlay", "kind": "visual", "elements": []},
    {"id": "t_text", "kind": "text", "elements": []},
    {"id": "t_captions", "kind": "captions", "style": {}, "elements": []},
    {"id": "t_music", "kind": "audio", "elements": []}
  ],
  "markers": []
}
```

Migração automática v2 → v3 (sequência atual vira `t_main`, áudios viram faixas de áudio, textos e legendas viram faixas próprias). O backend continua normalizando cada campo e nunca aceita filtro, caminho ou expressão vinda do cliente.

## 5. Plano por marcos

Tamanhos relativos: S ≤ 2 dias, M 3–5 dias, L 1–2 semanas.

### Marco 0 — Fundação (3–4 semanas)
- Spike do renderizador único (4.2) — M
- Composição v3 em quadros + migração v2 → v3 + validação no backend — L
- Sistema de comandos com lote e registro de ações/atalhos personalizáveis — M

### Marco 1 — Timeline de verdade (3 semanas)
- Faixas livres: adicionar/remover/ocultar/mutar/travar faixa; arrastar elemento entre faixas; sobreposição = camadas (PiP, B-roll, logo) — L
- Copiar/colar (elementos e keyframes), marcadores, split esquerda/direita, ripple liga/desliga em qualquer faixa, J/K/L, quadro a quadro — M
- Seleção múltipla com caixa, mover em grupo — M

### Marco 2 — Canvas e transformação (2–3 semanas)
- Alças no canvas (mover, escalar, girar), guias, encaixe no centro e na área segura — M
- Crop livre, fundo desfocado/cor para formatos diferentes — S
- Modos de mesclagem e opacidade por faixa — S

### Marco 3 — Animação (2–3 semanas)
- Canais de keyframe para qualquer propriedade numérica e de cor (inclusive volume e parâmetros de efeito) — L
- Editor de curva Bézier com presets de easing — M
- Presets de animação de entrada/saída/loop para texto e mídia (≈20) — M

### Marco 4 — Efeitos, cor e transições (3–4 semanas)
- Ajustes de cor: exposição, contraste, saturação, temperatura, tint, realces/sombras, vinheta; LUT .cube — M
- Pilha de efeitos por elemento (ligar/desligar, reordenar): blur, glow, shake, glitch, RGB split, zoom pulse, granulação, VHS (≈15 no primeiro lote) — L
- Transições: ampliar para ≈20 (zoom, girar, desfoque, deslizar nas 4 direções, flash, glitch) com duração ajustável — M
- Máscaras (retângulo, elipse, estrela, coração, linear, livre) com feather e inversão — L
- Chroma key — M

### Marco 5 — Texto, stickers e legendas sociais (2–3 semanas)
- Texto sem limite de 8, fundo com padding/raio, sombra, curvatura, espaçamento — M
- Legendas palavra a palavra (destaque, karaokê, pop) a partir dos tempos por palavra que o faster-whisper já fornece — M
- Stickers/figuras/emoji e logos do brand kit como elementos da timeline — M
- Tradução de legendas (provedor com custo visível antes) — S

### Marco 6 — Velocidade e áudio avançado (2 semanas)
- Reverse, congelar quadro, rampa de velocidade com presets (montagem, herói, bullet) — M
- Ducking automático da música sob a voz, normalização de loudness por plataforma — M
- Locução TTS como item da timeline; detecção de batida e encaixe de cortes na batida — M

### Marco 7 — Exportação e templates (2 semanas)
- 60 fps, 4K quando a fonte permitir, MOV/WebM, estimativa de tamanho — M
- Templates: salvar composição como modelo com espaços substituíveis (mídia, texto); o agente preenche — L

**Estimativa indicativa:** 19–24 semanas com 1 frontend + 1 backend/mídia, a recalibrar depois do spike do Marco 0.

## 6. O que fica fora (por decisão, não por esquecimento)

Remoção de fundo e rastreamento de movimento por IA, estabilização, avatares e clonagem de voz, colaboração em tempo real, publicação direta nas redes, catálogo de música comercial licenciada, aplicativo móvel. Cada um é um projeto próprio e não impede a edição do dia a dia.

## 7. Alternativa pedida: OpenCut como base principal (React + Python + extensões)

Pedido do usuário em 23/10: usar o OpenCut como base, interface React rápida, Python manipulando a edição e extensões dinâmicas, como os agentes fazem hoje. É viável e substitui a seção 4.1 se for aprovado.

**Arquitetura proposta**

```
React (fork do opencut-classic, só o editor)    ← timeline, canvas WebGPU/WASM, painéis
   │  comandos tipados (JSON)  ▲ estado/patches
   ▼                           │
Flask / Python — "Editor API"                    ← fonte da verdade do projeto
   ├─ projeto + revisões (studio_projects)
   ├─ registro de comandos (split, move, add_effect, add_keyframe…)
   ├─ extensões dinâmicas (efeitos, transições, ações de IA) declaradas por manifesto
   ├─ agente / MCP usa os MESMOS comandos
   └─ worker: proxy, transcrição, autocut, render final
```

- **Base:** fork do `opencut-classic` (MIT, arquivado, estável). O rewrite em Rust não está pronto; pode ser reavaliado quando tiver Editor API e modo headless.
- **O que se aproveita:** timeline, comandos com lote, atalhos, keyframes com Bézier, máscaras, retime, separação de áudio, stickers/figuras, renderizador GPU (Rust/WASM) usado na prévia e na exportação.
- **O que se remove do fork:** Next.js de site (landing, blog, auth, Postgres/Redis próprios) e o armazenamento local OPFS/IndexedDB. O editor vira um app React/Vite montado dentro da página do Studio, autenticado pela sessão Flask.
- **O que se escreve em Python:** a Editor API (mesmo vocabulário de comandos do OpenCut, validado e normalizado no servidor), persistência por marca, custos, e um registro de extensões. Cada extensão declara parâmetros (vira painel automático no React), shader ou filtro de render, e opcionalmente uma ação Python (ex.: "cortar silêncios", "legendar", "gerar cena Seedance") que devolve comandos. O agente lateral passa a chamar esses comandos em vez do formato atual.
- **O que se migra do Studio atual:** ingestão/proxy, autocut, faster-whisper, limpeza de voz, efeitos sonoros, estilos de legenda, brand kit, Seedance/storyboard, fila durável, exportação MP4/GIF/HTML — tudo como extensões ou serviços da Editor API.

**Atenção:** o OpenCut não traz "todos os recursos do CapCut". Transições, filtros/cor, efeitos (só tem blur), animações de texto, legenda palavra a palavra e templates continuam a construir, como extensões — os Marcos 3–7 da seção 5 continuam valendo, só que sobre a base do OpenCut.

**Decisões em aberto**
1. Render final: no navegador (WebCodecs, como o OpenCut) ou no servidor rodando o mesmo renderizador em Chromium headless (recomendado, para não depender da máquina do usuário em vídeos longos).
2. Extensões: só internas (código revisado no repositório) ou também de terceiros/criadas por agente em tempo de execução. Recomendo internas com manifesto; código Python gerado por agente executado no servidor é risco de segurança e precisa de sandbox à parte.
3. Convivência: o editor atual fica disponível até o novo cobrir montagem, legendas, áudio e exportação.

**Estimativa indicativa:** 4–6 semanas para o fork rodar dentro do Studio com Editor API, projeto por marca e exportação; depois os marcos de recursos, mais rápidos que na seção 5 porque a timeline, os keyframes e as máscaras já vêm prontos.

## 8. Próximo passo sugerido

Fazer o spike do renderizador único (4.2) e escrever o schema v3 com sua migração. Sem essas duas peças, faixas livres, máscaras e efeitos vão nascer duplicados (Canvas + FFmpeg) e precisarão ser refeitos.
