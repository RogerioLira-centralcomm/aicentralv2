# Plano — Normalização do Cadu Studio (2026-10-02)

Público: gestores, planejadores e criativos de agências e times de marketing in-house.
Objetivo: uma suíte com **uma linguagem visual, uma navegação e uma base de testes confiável**,
sem Untitled UI — o Studio usa componentes próprios, altamente personalizados.

## 1. Diagnóstico (estado atual verificado)

| Módulo | Stack hoje | Tamanho | Testes | Situação |
|---|---|---|---|---|
| **Home logada** | Jinja `cadu_studio/home.html` + `mc-cadu-home.js` + `mc-studio-library.js`, Font Awesome CDN, 4 CSS (`home`, `library`, `navigation`, `frame`) | ~470 linhas CSS | `mc-studio-library.test.cjs` | Hero de marketing dentro do produto logado; CTAs duplicados (hero + 3 cards); biblioteca boa mas presa em JS legado |
| **Criar** | Jinja `create.html` (HTML em linhas gigantes) + `cadu-studio-create-v2.js` + `mc-studio-create.js` (889) | create-v2 CSS 518 | `test_studio_create*.py` | Instabilidade visual: cards de resultado hardcoded no template, 7 `<dialog>` soltos, estado em `data-state` manipulado por JS imperativo |
| **Editar** | React (`frontend/cadu-studio-editor`, Vite) | App 594 + 3 componentes | `tmp/studio-editor-check` (ad-hoc), `test_studio_media_editor.py` | Mais evoluído; ainda carrega `api.js` legado, CSS próprio e verificações fora da suíte |
| **Vídeo** | Vanilla: `mc-cadu-video.js` (1231) + `static/js/cadu-video/*` (~2,3k) + `tailwind.studio` | ~3,5k JS | `mc-video-editor`, `mc-studio-workflow` (passam) | Evolução parada; UI diferente das demais; Tailwind isolado |
| **Áudio** | React mínimo (`AudioStudioApp.jsx`, 128) + `studio_audio.py` (20) | pequeno | nenhum dedicado | Interface menos evoluída; backend é stub |
| **Analisador** | Herdado do PHP: `creative_analyzer/*` (~1,3k py) + `creative-analyzer-studio.js` (449) | — | `test_creative_analyzer.py` (24 ok, **mockado**), `creative-analyzer-studio.test.cjs` | Nunca rodou ponta a ponta neste ambiente (DB real, storage, processor, IA) |
| **Navbar** | `mc-cadu-nav.js` (94) + `_context_bar.html` + `cadu-studio-navigation.css`; versões de cache divergentes (`?v=8` vs `?v=9`) | — | `test_studio_workspace_boundary` **falhando** | Cada tela importa sua própria versão |

Baseline de testes (`.venv`, Python 3.13):
- `tests/test_studio_*.py` + `test_video_studio*.py`: **149 ok / 3 falhas**
  - `test_studio_workspace_boundary::test_studio_navigation_has_one_authoritative_active_state`
  - `test_video_studio::test_export_routes_are_idempotent_and_brand_scoped`
  - `test_video_studio::test_private_upload_library_and_cross_brand_lookup`
- Frontend (`node tests/frontend/*.test.cjs`): analyzer, video-editor, workflow — passam.

## 2. Princípio de arquitetura

Criar **`frontend/cadu-studio-ui/`** — o kit próprio do Studio (sem Untitled, sem react-aria-components
como dependência visual; react-aria só para comportamento acessível se necessário):

- `tokens.css` — cor, tipografia, raio, sombra, motion, densidade; tema claro/escuro.
- Primitivos: `Button`, `IconButton`, `Segmented`, `Panel`, `Rail`, `Dialog`, `Sheet` (mobile), `Toast`,
  `ProgressCard`, `MediaCard`, `FormatPicker`, `BrandChip`, `CreditMeter`, `EmptyState`.
- Ícones: um único set SVG próprio (remover Font Awesome CDN do Studio).
- `StudioShell` = **Navbar** + rail de contexto (projeto/marca) + área de trabalho + dock de conta.
- Um único `vite.studio.config.mjs` multi-entry (home, create, editor, video, audio, analyzer) com chunk
  compartilhado do kit — substitui `vite.studio-editor` e `vite.studio-audio`.
- Jinja vira só bootstrap JSON (padrão já usado em `audio.html`).

## 3. Fases

### Fase 0 — Base verde e rede de segurança (1–2 dias)
1. Corrigir as 3 falhas acima (ou registrar como bug real com causa).
2. Mover `tmp/studio-check` e `tmp/studio-editor-check` para `tests/frontend/` como testes de verdade.
3. Script `npm run test:studio` (pytest studio + node frontend studio) e capturas de referência
   (Playwright 390/768/1280/1440) por tela — base para medir "estabilidade visual".

### Fase 1 — Kit `cadu-studio-ui` + Navbar React (3–4 dias)
1. Tokens extraídos do que já funciona no Editor e na Home (não inventar paleta nova).
2. `StudioNavbar`: Início · Criar · Editar · Vídeo · Áudio · Analisar · Biblioteca; seletor de
   projeto/marca; créditos; conta. Estado ativo **único** vindo do bootstrap (resolve o teste de boundary).
3. Montar a navbar como ilha React em todas as telas Jinja atuais (sem reescrevê-las ainda) e remover
   `mc-cadu-nav.js` + `_context_bar.html`.

### Fase 2 — Criar (estabilidade visual) (4–5 dias)
Reescrever em React sobre o kit, mantendo as APIs `/studio/api` de `studio_create.py`:
máquina de estados explícita (`draft → directing → review → generating → results → error`),
resultados renderizados a partir de dados (sem cards fixos), diálogos do kit, painel Entrega como `Sheet`
no mobile. Testes: unit da máquina de estados + Playwright do fluxo completo + regressão visual.

### Fase 3 — Editar: limpar legado e refazer testes (3 dias)
Migrar para o kit (botões, painéis, modal), substituir `api.js` por cliente tipado compartilhado,
remover CSS duplicado. Suíte nova: máscara, composer, histórico, download, handoff Criar→Editar.

### Fase 4 — Vídeo: normalizar interface e criação (6–8 dias)
1. Manter o motor (`cadu-video/state|timeline|composition|render`) — testado e funcional.
2. Nova casca React (toolbar, painéis, inspector, biblioteca) sobre o kit; o motor vira módulo importado.
3. Unificar "criar vídeo" com o padrão de Criar: briefing → direção → cenas → timeline.
4. Aposentar `tailwind.studio.config.js` / `video-studio.css`.
5. Manter verdes `mc-video-editor` e `mc-studio-workflow` em cada passo.

### Fase 5 — Áudio (4–5 dias)
Backend real em `studio_audio.py` (hoje 20 linhas): geração/TTS, trilhas, biblioteca, billing por crédito.
UI: mesma estrutura de Criar (pedido → opções → resultado → enviar para Vídeo). Testes novos dos dois lados.

### Fase 6 — Analisador de criativos (4 dias)
1. Rodar ponta a ponta de verdade: migração `add_studio_creative_analyzer.sql` aplicada num banco local,
   storage real, `processor.py` com um criativo de fixture, chamada de IA real atrás de flag.
2. Teste de integração (não-mockado) marcado `@pytest.mark.integration`.
3. UI React no kit; resultado do analisador abre ação "Ajustar no Editor".

### Fase 7 — Home logada (2–3 dias)
Remover hero de marketing; virar painel de trabalho: "Continuar" (sessões abertas), atalhos para as 5
ferramentas, biblioteca com filtros, créditos e marca ativa. Reaproveita `mc-studio-library` portado.

### Fase 8 — Limpeza
Remover JS/CSS legados (`mc-studio-create.js`, `cadu-studio-create.css`, `mc-cadu-video.js` casca,
Font Awesome), unificar build no deploy (`build_frontend.sh`) e atualizar docs.

## 3.1 Prompts por produto (modelos e OpenRouter permanecem como estão; vídeo segue Seedance 2.5)

| Produto | Onde | Problema observado | Melhoria |
|---|---|---|---|
| Criar | `studio_create.system_prompt` (~1,2k palavras, gpt-5-nano) | Prompt monolítico mistura diretor, revisor e regras de marca; schema do topo não inclui `reference_plan`, pedido só no fim; `max_tokens=900+320·n` com modelo de raciocínio pode zerar a resposta (tokens de raciocínio consomem o teto) | Quebrar em blocos versionados (papel · contrato JSON completo no topo · regras de marca · referências · checklist); subir/remover teto; registrar `prompt_version` em cada criação |
| Editar | `studio_prompt.py` (compiler v1) | `protected_literals` captura toda sequência capitalizada/número → muitos fallbacks silenciosos para o prompt original | Medir taxa de fallback; separar "literal visível" de "nome próprio de contexto"; devolver motivo do fallback à UI |
| Vídeo | `studio_agent.py` + `prompts.py` + skill `seedance-2-5-image-to-video` | `prompt[:400]` corta depois de prefixar o roteiro → a direção de câmera/movimento pode sumir; presets bons mas sem marca/briefing | Orçamento por seção (sujeito · câmera · luz · áudio · end card) antes de cortar; levar briefing e marca do Criar; manter Seedance 2.5 |
| Áudio | `studio_audio.py` (só filtros ffmpeg) | Não há prompt de áudio; locução vive dentro do agente de vídeo | Extrair `NARRATION_SYSTEM` para serviço de áudio próprio (locução, trilha, SFX) reutilizado por Vídeo |
| Analisador | `creative_analyzer/processor.py` (gpt-5.4, 2 passagens) | Schema com `0` como default + `_clamp(None)=0` → "sem evidência" vira nota zero; não recebe marca/briefing/canal; vídeo = 4 frames sem áudio | Defaults `null` e UI de "não avaliado"; injetar marca, objetivo e canal; rubrica explícita por score; mais frames + transcrição |
| Transversal | — | Prompts espalhados, sem versão nem conjunto de avaliação | `creative_media/prompt_registry` + `tests/prompt_evals/` com 10–20 briefings reais por produto, rodando contra OpenRouter atrás de flag |

## 4. Ordem e critérios de aceite
Ordem: 0 → 1 → **1.5 Biblioteca única + "Enviar para Vídeo"** (ver `docs/design/storyboard-cadu-studio-60s.md`)
→ 2 → 3 → 7 → 4 → 5. **Fase 6 (Analisador) adiada** — existe versão PHP do backend que será enviada depois.
Cada fase só fecha com: `npm run test:studio` verde, capturas 390–1440px sem regressão, zero erro de
console, nenhuma importação de Untitled UI em `frontend/cadu-studio-*`.

## 5. Decisões tomadas (2026-10-02)
1. **Vídeo:** casca React nova sobre o motor atual (`cadu-video/*`); Seedance 2.5 permanece.
2. **Áudio:** ElevenLabs via API direta (TTS, música, SFX), atrás de `studio_audio_provider` para
   permitir trocar depois; billing em créditos Cadu como os demais. Ainda não há integração no repo.
3. **Analisador:** o único banco é o online do `.env` (credenciais já configuradas). Teste real usa
   cliente/projeto dedicado `studio-qa`, prefixo nos registros e limpeza ao fim; migrações aplicadas
   só com confirmação explícita.
4. **Tema:** Studio **sempre escuro**. Um único conjunto de tokens, sem variante clara nem
   `prefers-color-scheme`; testes de contraste AA só sobre o escuro.

## 6. Andamento (2026-10-02)
- **Fase 0 (parcial):** 4 testes desatualizados corrigidos (CSRF `studio_csrf_token`, patch da rota de
  export, estado ativo da navbar, versões de cache). `npm run test:studio` criado: 157 pytest + 3 suítes
  de frontend verdes. Pendente: mover `tmp/studio-check` e `tmp/studio-editor-check` e capturas de referência.
- **Fase 1.5 (parcial):**
  - `POST /api/format-lab/studio/send-to-video` — valida marca/projeto e posse das imagens, grava
    as cenas em ordem num único run da biblioteca do Vídeo e devolve `scene_ids`.
  - Criar: botões "Enviar para vídeo" (por variação) e "Levar todas para o vídeo".
  - Vídeo: abre com `?scenes=` e monta o storyboard (1 cena = animar still; 2+ = storyboard Seedance).
  - Toda imagem do Criar é registrada em `cx_studio_assets` (`source_type='studio_create'`).
  - Backfill `migrations/run_backfill_studio_assets.py` aplicado: 11 imagens.
  - Pendente: registrar clipes/exports do Vídeo no hub e ler a biblioteca do Vídeo a partir do hub.
- **Rodada 2 (2026-10-02):**
  - Prompts: tetos de tokens do Criar/Editar/Vídeo ajustados ao raciocínio do gpt-5-nano (`reasoning: low`);
    `reference_plan` no contrato JSON do diretor; voz da locução sem perder a direção; motivo de fallback no Editar.
  - Biblioteca única: clipes prontos registrados (`source_type='studio_video'`); backfill de 6 clipes.
  - **Fase 1 (núcleo):** `frontend/cadu-studio-ui` (tokens dark-only, `StudioNavbar`, `ProjectPicker`,
    `CreditMeter`, `AccountMenu`, `csu-button`), build `vite.studio-ui.config.mjs` (+ deploy.sh).
    Jinja: ilha React sobre o contrato `#mcCaduProject`/eventos `cadu:*` (mc-cadu-nav.js segue como controlador).
    Editor e Áudio usam o mesmo componente. Rótulos unificados: Início · Criar · Editar · Vídeo · Áudio · Analisar · Biblioteca.
  - Testes de navegador autossuficientes (Playwright do projeto, fixtures geradas do template atual).
- **Rodada 3 (2026-10-02):**
  - Editor: CSRF corrigido (era 403 em upload/sessões/tarefas); cotação aberta a contas do Studio;
    design system/Untitled removido do bundle (392→47 KB, visual idêntico); `StudioDialog` no kit;
    teste de fluxo de navegador.
  - Criar: estabilidade visual com CLS medido e travado no teste (<0,1 em 1440/1024/768/390);
    5 causas corrigidas no CSS/JS atual. Esse teste vira a especificação de paridade da versão React (Fase 2).
