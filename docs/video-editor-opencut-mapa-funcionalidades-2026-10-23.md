# Editor de vídeo do Studio (base OpenCut): mapa de funcionalidades e o que desenvolver

23/10/2026. Continuação de `video-studio-paridade-capcut-opencut-2026-10-23.md`. Parte 1 registra o spike feito hoje; parte 2 mapeia cada área contra uma ferramenta grande de mercado (CapCut, Premiere, DaVinci Resolve) e diz o que construir para cada item funcionar melhor e com menos custo.

---

## Parte 1 — Resultado do spike

O fork do `opencut-classic` (MIT, commit `cf5e79e`) roda dentro do Studio, sem o Next.js, com projeto, biblioteca e upload unificados com os do Studio.

| Peça | Onde | Estado |
|---|---|---|
| Editor OpenCut compilado com Vite (React 19 isolado do React 18 do app) | `frontend/cadu-studio-video/` → `aicentralv2/static/cadu_studio/video_editor/` | Funciona; 4 arquivos do OpenCut alterados (página, provider, storage, project-manager), todos marcados "Cadu:" |
| Projeto = projeto do Studio (`cx_studio_projects`), timeline na chave `video_editor`, com revisão e conflito 409; o resto do documento é preservado | `creative_media/studio_video_editor.py` | Funciona e tem teste |
| Biblioteca única por marca: upload do editor vira `clip-/sound-/image-*.json` (FFprobe/Pillow, sem confiar na extensão); vídeos gerados, sons CC0 e uploads antigos aparecem no diálogo "Biblioteca do Studio" | idem | Funciona; vídeos gerados não testados (dependem do banco) |
| Editor API: `add_text`, `add_media`, `split`, `delete` (ripple), `move`, `trim`, `set_params`, em lote atômico, em segundos | `POST …/video-editor/projects/<id>/commands` | Funciona e tem teste |
| Extensões internas por manifesto JSON (formulário gerado no editor): "Título na tela" e "Legendas automáticas" (Whisper local) | `creative_media/video_editor_extensions/` | Título testado na tela; legendas sem teste real (exigem o modelo do worker) |
| Render no servidor: tarefa `opencut_render` na fila existente; o worker abre o editor compilado no Chromium headless (Playwright), entrega projeto e mídias do disco e grava o MP4 | `scripts/studio-video-render.mjs` | Funciona: 9,1 s em 1080p com áudio, quadros iguais à prévia, 23 s neste Mac |

**Verificação feita:** 7 testes novos (`tests/test_studio_video_editor.py`) + 39 testes das suítes do Studio passando; fluxo no navegador com o servidor isolado `tests/frontend/video_editor_dev_server.py` (SQLite local, sem tocar no banco de produção): abrir, enviar vídeo/áudio/imagem, montar por comandos, recarregar, aplicar extensão, vincular som da biblioteca, renderizar e baixar.

**Achados que mudam o plano:**
1. Forçar `--use-angle=swiftshader` no Chromium gera vídeo **preto**; sem a flag o render sai certo no Mac. **Não foi testado no Linux do servidor** (sem GPU). É o maior risco: precisa de um teste no servidor antes de qualquer outra coisa.
2. O export do OpenCut codifica H.264 pelo WebCodecs do navegador. O Chromium do Playwright no Linux pode não ter codificador H.264. Saída provável: exportar VP9/AV1 e converter para MP4 com FFmpeg, ou usar o canal `chrome`.
3. Trocar a timeline com o editor montado desmonta o React. Mudanças feitas no servidor (extensões, agente) recarregam a página. O certo, depois, é aplicar o diff dos comandos no `EditorCore` sem recarregar.
4. O bundle tem 32 MB; 21 MB são o ONNX que o OpenCut usa para transcrever no navegador. Como a transcrição é no servidor, esse código sai.
5. A mídia vai inteira para o navegador antes de tocar (`BlobSource`). Para vídeos grandes, trocar por leitura por faixas (range) e proxy de 720p.
6. Interface toda em inglês; abas "Transições" e "Ajustes" são placeholders; há um único efeito (blur).

### Fase 1 — andamento (23/10)

| Item | Estado |
|---|---|
| Render no Linux | Preparado, **não executado**: `scripts/studio_video_render_check.py` (roda no servidor, sem banco). Fallback automático: Chromium sem H.264/AAC exporta WebM e o worker converte para MP4; testado aqui nos dois caminhos. `install_media_worker.sh` instala o Chromium do Playwright em `instance/ms-playwright` e põe o `node` no `PATH` do worker |
| Remover ONNX | Feito. Legendas usam o Whisper do worker (`POST …/projects/<id>/transcriptions`, idioma do seletor). Bundle de 32 MB → 10 MB |
| Build no deploy | Feito: `build_frontend_fast.sh` e `npm run build:vite` compilam `frontend/cadu-studio-video` |
| Testes | `tests/test_studio_video_editor.py` (8 testes) entra em `npm run test:studio`; 84 testes das suítes do Studio passando |
| PT-BR, tema do Studio, 5 abas, `UrlSource`, upload em tarefa | **Pendentes** — próxima etapa, depois de ver o render no servidor |

### Render: diagnóstico da lentidão (24/10)

| Onde | Vídeo | Tempo | Observação |
|---|---|---|---|
| Servidor Linux (sem GPU) | 6 s, 1080p | 226 s | Todas as checagens OK; ~37× o tempo real |
| Mac, Chromium headless (software, SwiftShader) | 9 s, 1080p / 720p | 26 s / 14 s | Mesmo modo do servidor, CPU mais forte |
| Mac, headless com GPU (`CADU_RENDER_GPU=metal`) | 9 s, 1080p / 720p | 6 s / 2,9 s | |
| **Navegador do usuário (botão Exportar, GPU)** | 6 s, 1080p | **4 s** | |

Por quadro em 1080p: compor (enfileirar) 3,5 ms; capturar e codificar 87 ms por software contra 11 ms com GPU. O codificador H.264 sozinho faz 7–20 ms/quadro (`scripts/studio-video-encode-bench.mjs`); o custo é o compositor WebGL/wgpu rodando por software na captura do quadro. 720p corta o tempo pela metade, mas o OpenCut não tem resolução de saída diferente do canvas (exige escala no compositor).

**Proposta:**
1. **Exportar no navegador do usuário por padrão** e enviar o MP4 pronto para a biblioteca do Studio (validado por FFprobe). Custo zero de servidor, ~1,5× o tempo real com GPU. É o desenho original do OpenCut.
2. **Render no servidor só para automação** (agente, lote, variações), numa máquina com GPU dedicada ao worker, com `CADU_RENDER_GPU=vulkan`, a validar em Linux com GPU.
3. Enquanto não houver GPU: render no servidor fica para fila sem pressa; paralelizar por trechos só vale com muitos núcleos (o SwiftShader já usa ~5 núcleos por render no Mac). Medir `nproc` e rodar o benchmark no servidor antes de decidir.

**Depois do deploy, no servidor:**

```sh
.venv/bin/python scripts/studio_video_render_check.py
```

Saída esperada: duas linhas `OK` (codec do navegador e WebM → MP4), com o tempo de render. Abrir o editor: `/studio/video-editor?client_id=<marca>&project=<id do projeto do Studio>` (ainda sem link no menu).

---

## Parte 2 — Mapa por área

Legenda de tamanho: **P** até 3 dias · **M** 1 semana · **G** 2–3 semanas · **GG** precisa ser fatiado.
Coluna "Hoje" considera o fork + o que o Studio antigo já tem e pode ser reaproveitado.

### 1. Interface minimalista

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Idioma | Interface localizada | Tudo em inglês | Extrair textos para um dicionário PT-BR (≈400 strings); o OpenCut não tem i18n | M |
| Tema | Escuro, contraste alto, cor de destaque única | Tokens shadcn com azul OpenCut | Aplicar os tokens do Studio (dark-only, já decidido) em `globals.css`; remover o modo claro | P |
| Menos painéis | CapCut mostra só o necessário para a seleção | 9 abas fixas à esquerda + propriedades à direita | 5 abas: **Mídia · Texto · Áudio · Efeitos · Legendas**. Stickers e Configurações saem para menus; Transições e Ajustes entram em Efeitos. Propriedades só aparecem com algo selecionado | M |
| Barra contextual | Ações do item selecionado perto dele | Barra fixa de 10 ícones na timeline | Barra flutuante na seleção (dividir, apagar, velocidade, volume, animação) e paleta de comandos `Ctrl+K` que usa o mesmo registro de ações e as extensões | M |
| Estado vazio | Começa com "Importar" ou modelos | "Drag and drop…" | Três entradas: enviar, abrir biblioteca da marca, pedir ao Cadu ("monte um corte de 15 s com estes vídeos") | P |

**Eficiência:** tirar as abas vazias e o ONNX reduz o bundle inicial de 2,1 MB (gzip 600 kB) para menos da metade; carregar Efeitos e Legendas sob demanda (`import()` por aba).

### 2. Legendas

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Transcrição | Automática, vários idiomas | Whisper local no worker (extensão), SRT/ASS no OpenCut | Rodar como **tarefa** (hoje a extensão roda dentro da requisição); Whisper `small` → avaliar `large-v3-turbo` para PT-BR; cache por hash do áudio | M |
| Palavra a palavra | Destaque, karaokê, pop por palavra (padrão Reels/TikTok) | Não existe; o Whisper já devolve o tempo de cada palavra | Novo tipo de elemento "legenda" com palavras e tempos; renderizador desenha a palavra ativa com outra cor/escala. Precisa mexer no `text-node` do OpenCut | G |
| Estilos | Dezenas de modelos prontos | 10 modelos no Studio antigo (`styles.json`) | Portar os 10 modelos e criar 20 animados (karaokê, caixa que segue a palavra, bounce, contorno grosso); aplicar a todas ou a uma | M |
| Edição | Lista com texto e tempo, busca/substituir, dividir/unir | Cada legenda vira um texto solto na timeline | Painel de legendas como lista (rolagem virtual para 500+ itens); editar texto sem mexer no tempo; buscar e substituir nome de marca | M |
| Tradução | Legenda em outro idioma | Não existe | Haiku 5.5 traduz segmento a segmento mantendo os tempos; custo mostrado antes | P |
| Exportar | SRT/VTT e queimada no vídeo | SRT no antigo; queimada pelo render | Exportar SRT/VTT da faixa de legendas | P |

**Eficiência:** uma faixa de legendas como **um** elemento com lista interna, em vez de centenas de elementos de texto, deixa timeline, save e render bem mais leves.

### 3. Fontes

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Catálogo | Centenas de fontes com prévia | 1.920 Google Fonts no seletor do OpenCut (atlas de prévia) | Manter; curar 40 "recomendadas" no topo | P |
| Fontes da marca | Brand kit | O Studio já guarda as fontes da marca (`brand_fonts`) | Mostrar as fontes da marca primeiro e carregá-las por `@font-face` da URL do Studio | P |
| Hospedagem | — | Baixa de `fonts.gstatic.com` em tempo de uso, também no render | Servir as fontes usadas pelo próprio Studio (cache no servidor); o worker não deve depender da internet. Requer licença OFL (Google Fonts é OFL) | M |
| Consistência prévia × render | Igual | Mesmo navegador nos dois lados, então igual se a fonte carregar | Esperar `document.fonts.ready` antes de cada quadro no render (verificar no `scene-exporter`) | P |

### 4. Texto e títulos animados

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Animação de entrada/saída/loop | Centenas de presets (digitar, subir, zoom, piscar) | Keyframes manuais com editor de curva Bézier | Biblioteca de **presets** que gera keyframes (≈30 na primeira leva), aplicável por clique e editável depois | M |
| Por letra/palavra | Kinetic typography | Não existe | Animação por caractere precisa de nova propriedade no `text-node` (atraso por índice) | G |
| Títulos prontos | Templates de texto | Extensão "Título na tela" (1 estilo) | Pacote de 20 títulos da marca (cores/fontes do brand kit) como extensões | M |

### 5. Transições de alto nível

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Sistema de transição | Item entre dois clipes, com duração e sobreposição | **Não existe no OpenCut** (aba "coming soon"); o Studio antigo tinha 5 no FFmpeg | Modelo de dados (transição pertence à junção, consome "handles" dos dois clipes), UI de arrastar para a junção, renderizador que desenha os dois clipes no intervalo e mistura | G |
| Catálogo | 100+ (dissolve, zoom, giro, glitch, luz, deslizar, máscara) | — | Cada transição = shader de mistura (WebGL/WGSL) com parâmetros. Primeira leva de 25: dissolve, fade preto/branco, deslizar ×4, empurrar ×4, zoom in/out, giro, desfoque, flash, glitch, RGB split, wipe ×4, íris, light leak, whip pan | G |
| Ajuste | Duração, direção, suavização | — | Parâmetros no painel; duração por arraste na junção | P |
| Escolha por IA | "Auto transições" | — | Opus/Haiku escolhe do **catálogo** por junção, a partir do ritmo e da cena (não gera shader) | P |

**Eficiência:** shaders rodam no mesmo compositor da prévia e do render; não há segunda implementação em FFmpeg (o problema do editor antigo).

### 6. Efeitos, cor e camadas de ajuste

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Pilha de efeitos | Vários por clipe, ligar/desligar, reordenar | Estrutura pronta (passes GPU, multi-pass, keyframe por parâmetro), só **1 efeito** (blur) | Escrever efeitos sobre o registro existente: **cor** (exposição, contraste, saturação, temperatura, tint, realces/sombras, vinheta), **estilo** (glow, granulação, VHS, desfoque de movimento, nitidez), **movimento** (shake, zoom pulse, glitch, RGB split, espelho, pixelar). 20 na primeira leva | G |
| LUT | Importar `.cube` | Não existe | Efeito com textura 3D; LUTs da marca no brand kit | M |
| Camada de ajuste | Efeito aplicado a tudo abaixo | Faixa `effect` já existe no modelo | Ativar na UI (aba "Ajustes" é placeholder) | P |
| Máscaras e mesclagem | Máscaras com feather, blend modes | 8 máscaras + livre, feather, inversão; blend modes no modelo | Expor na UI simplificada; testar no render | P |
| Chroma key / remover fundo | Sim | Não | Chroma key em shader (M). Remover fundo por IA é projeto à parte (modelo de segmentação no worker) | M / GG |

### 7. Edição e timeline

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Base | Multifaixa, split, ripple, snap, copiar/colar, marcadores, atalhos | **Já vem pronta** no OpenCut | Traduzir atalhos e ajustar ao padrão CapCut (`S` dividir, `Q/W` cortar à esquerda/direita) | P |
| Ferramentas de trim | Roll, slip, slide | Só trim e ripple | Slip e roll na faixa principal | M |
| Velocidade | Rampa, reverse, congelar, manter tom | Velocidade constante com áudio esticado | Rampa por curva (keyframe em `retime.rate`), reverse (pré-processar no worker), congelar quadro | M |
| Agrupar | Grupos/compound | Cenas múltiplas existem | Usar cenas como "clipe composto" | M |
| Desfazer de mudanças do servidor | — | Recarrega a página | Aplicar o resultado dos comandos como lote no `CommandManager` (um passo de desfazer) | M |

### 8. Áudio: compressão, ruído e mixagem

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Redução de ruído | Um clique, neural | Studio antigo: `afftdn` + EQ no FFmpeg (presets limpa/encorpada/ruído); OpenCut: nada | **No servidor, como mídia derivada:** a extensão gera uma versão limpa do áudio e troca a referência (original preservado, reversível). Começar com o filtro atual; depois testar modelo neural (DeepFilterNet/RNNoise) no Lab antes de trocar | M |
| Compressor, EQ, de-esser por faixa | Sim, em tempo real | OpenCut só tem limiter mestre (WebAudio) | Cadeia **WebAudio** por faixa (`DynamicsCompressor`, `BiquadFilter`) com presets "voz", "música", "podcast". O mesmo grafo roda no `OfflineAudioContext` do export, então prévia e render ficam iguais | M |
| Loudness | Normalizar para −14 LUFS (redes) | Não | Medir LUFS no worker (FFmpeg `ebur128`) e aplicar ganho por faixa; alvo por canal no export | P |
| Ducking | Música baixa sob a fala | Não | Comando no servidor: detecta voz (VAD do Whisper) e grava keyframes de volume na faixa de música | P |
| Separar voz e fundo | Sim | Não | Modelo de separação no worker (Demucs) gera duas mídias derivadas | G |

**Eficiência:** o que é tempo real (compressor/EQ/volume) fica no navegador e não custa servidor; o que é pesado (denoise neural, separação, loudness) roda uma vez no worker e vira um arquivo novo, em cache por hash.

### 9. Cortes inteligentes

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Remover silêncios e hesitações | Sim | Studio antigo: `studio_autocut` (silêncio + palavras do Whisper + revisão de repetições) | Portar como extensão que devolve `split` + `delete ripple` e abre uma **lista de revisão** antes de aplicar | M |
| Editar pelo texto | Apagar frase na transcrição apaga o trecho | Não | Painel de transcrição ligado aos tempos; apagar texto gera os comandos de corte | G |
| Melhores momentos / corte por duração | "Gerar 15 s / 30 s" | Não | Opus 5.5 lê transcrição + índice de cenas e devolve um plano de cortes (comandos), revisável antes de aplicar | M |
| Detecção de cena | Split automático em mudança de plano | Não | FFmpeg `scdet` no worker na hora do upload; marcadores na timeline | P |

### 10. IA com Opus 5.5 pelo OpenRouter

Modelos disponíveis hoje no OpenRouter: `anthropic/claude-opus-5.5` (US$ 4 / 20 por milhão de tokens de entrada/saída) e `anthropic/claude-haiku-5.5` (US$ 0,10 / 0,50). O repositório já chama o OpenRouter em vários módulos, com cobrança de ferramenta (`cadu_tool_billing`).

| Uso | Modelo | Como funciona | Tam. |
|---|---|---|---|
| **Biblioteca de cenas** | Haiku 5.5 (visão) | No upload: `scdet` divide em planos → 1 quadro por plano → Haiku descreve (o que aparece, enquadramento, movimento, cor, texto na tela, logo) → índice pesquisável por marca ("close de produto", "pessoa sorrindo"). Opus só quando a busca precisar de raciocínio | M |
| **Diretor de edição** | Opus 5.5 | Recebe transcrição, índice de cenas, duração e objetivo; devolve comandos da Editor API (rough cut, ordem, cortes, títulos, música). O usuário vê o plano e aplica num passo de desfazer | M |
| **Transições e ritmo** | Haiku 5.5 | Escolhe transição do catálogo por junção e sugere cortes na batida | P |
| **Legendas e títulos** | Haiku 5.5 | Tradução, revisão de ortografia/nomes, títulos curtos | P |

**Custo estimado por vídeo de 60 s:** índice de ~20 cenas pelo Haiku ≈ US$ 0,01; um plano do Opus (≈20 mil tokens de entrada e 3 mil de saída) ≈ US$ 0,14. Cobrança pela regra do Studio (tokens reais com margem no crédito).

**Regra do projeto:** prompts e escolha de modelo do diretor passam por A/B no Lab antes de entrar no Studio (decisão registrada).

### 11. Render, exportação e desempenho

| Item | Mercado | Hoje | O que desenvolver | Tam. |
|---|---|---|---|---|
| Render no servidor | — | Funciona no Mac | **Validar no Linux de produção** (GPU ausente, codec H.264); definir VP9 + FFmpeg ou Chrome estável; instalar Chromium no deploy; limite de 1 render por worker | M |
| Formatos | 4K/60, MP4/MOV/WebM, GIF | MP4/WebM, qualidade em 4 níveis | 4K/60 quando a fonte permitir; GIF e HTML público reaproveitando o `studio_delivery` antigo | P |
| Proxy | Edição com proxy, render com original | Edita com o arquivo enviado (convertido para H.264, mesma resolução) | Proxy 720p para a prévia; o render usa o original | M |
| Mídia por streaming | — | Baixa o arquivo inteiro para o navegador | `UrlSource` (leitura por faixas) do mediabunny no lugar de `BlobSource` | P |
| Upload | Retomável, em segundo plano | Síncrono na requisição (até 5 min) | Passar para a fila de tarefas (já existe `kind=import`) com progresso; upload em partes | M |
| Bundle | — | 32 MB / 2,1 MB de JS inicial | Remover ONNX/transformers; dividir por aba | P |

### 12. Biblioteca, projetos e marca

| Item | Hoje | O que desenvolver | Tam. |
|---|---|---|---|
| Biblioteca única | Uploads, imagens, sons e CC0 da marca; vídeos gerados na lista (não testado) | Incluir imagens geradas no Studio; filtros e busca usando o índice de cenas; paginação | M |
| Entrada pelo Studio | Página `/studio/video-editor?client_id=&project=` existe, sem link no menu | Botão "Editar vídeo" no projeto e no resultado do Seedance; levar o projeto atual | P |
| Brand kit | Logos, cores e fontes existem no Studio | Logos como stickers, paleta no seletor de cor, fontes no topo | P |
| Modelos (templates) | Não | Salvar timeline como modelo com campos substituíveis; o diretor preenche | G |
| Editor antigo | Continua no ar | Manter até o novo cobrir legendas, áudio e exportação; migrar `composition` v2 → timeline OpenCut por um conversor | M |

---

## Ordem recomendada

1. **Fundação (2 semanas):** validar o render no Linux; PT-BR + tema do Studio + 5 abas; remover ONNX; `UrlSource`; upload em tarefa; aplicar comandos sem recarregar.
2. **Legendas e texto (3 semanas):** faixa de legendas palavra a palavra, 30 estilos, painel de lista, transcrição em tarefa, presets de animação de texto.
3. **Transições e efeitos (3–4 semanas):** sistema de transição + 25 shaders; 20 efeitos; LUT; aba de ajustes.
4. **Áudio e cortes (2–3 semanas):** cadeia WebAudio por faixa, denoise como mídia derivada, loudness, ducking, autocut com revisão, detecção de cena.
5. **IA (2–3 semanas, com Lab):** biblioteca de cenas (Haiku), diretor de edição (Opus 5.5), transições sugeridas, tradução.
6. **Acabamento (2 semanas):** 4K/60, proxies, modelos, brand kit, entrada pelo Studio, desligar o editor antigo.

Total indicativo: **14–17 semanas** com 1 frontend + 1 backend/mídia.

## Decisões pendentes

1. Renderizar no servidor com GPU (máquina com GPU) ou aceitar render por CPU mais lento: depende do teste no Linux.
2. Denoise neural (DeepFilterNet) vale o custo de CPU? Medir no Lab antes.
3. Liberar o editor novo para todos ou por marca piloto, convivendo com o antigo.
4. Onde guardar o build de 32 MB → menos de 10 MB depois da limpeza: no git (padrão atual) ou gerado no deploy.
