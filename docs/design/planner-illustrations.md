# Ilustrações do Cadu Planner

As telas de espera, modais e estados vazios do Planner têm espaços reservados para ilustração. Hoje cada espaço mostra um placeholder abstrato na paleta do Planner, renderizado por `frontend/planner/Illustration.jsx`. A arte final substitui o placeholder no mesmo lugar e com o mesmo nome, sem mudar as telas.

Cada placeholder carrega o próprio briefing de criação. Ele fica no `<desc>` do SVG e no atributo `data-illustration-brief`, então dá para inspecionar o briefing direto na tela.

## Padrão comum

- **Paleta (só estas cores):**
  - Verdes: `#067647` (principal), `#079455`, `#17B26A`, `#75E0A7`, `#DCFAE6`.
  - Fundo claro: `#F6FEF9`.
  - Neutros: `#101828`, `#475467`, `#D0D5DD`, `#F2F4F7`.
  - São os mesmos valores dos tokens `--planner-tone-*` e `--colors-brand-*` do skin do Planner.
- **Luz:** suave, vinda de cima à esquerda.
- **Sombras:** chapadas em `#DCFAE6`. Nada de preto translúcido.
- **Texto:** nenhum dentro da arte, nem logotipo de terceiros. Ícones de canal aparecem como formas genéricas (tela, celular, jornal, fone).
- **Estilo 3D:** isométrico, acabamento de argila fosca, cantos arredondados, sem textura fotográfica.
- **Estilo 2D:** vetor com traço de 2 px em `#067647`, preenchimentos chapados e cantos arredondados.
- **Movimento** (quando houver versão animada):
  - Até 2,4 s por ciclo.
  - Loop sem corte.
  - Uma versão estática para `prefers-reduced-motion`.

## Entrega

- **Pasta:** `aicentralv2/static/cadu_planner/illustrations/`.
- **Nomes de arquivo:**
  - `<slot>.webp` com fundo transparente, em 2x o tamanho exibido.
  - Arte 2D: também `<slot>.svg`.
  - Versão animada opcional: `<slot>.webm` ou Lottie `<slot>.json`.
- **Peso máximo:** 120 KB por arquivo estático e 400 KB por animação.
- **Troca no código:** em `Illustration.jsx`, a forma placeholder é substituída por `<img src="/static/cadu_planner/illustrations/<slot>.webp">`, mantendo o `slot`.

## Espaços

| Slot | Onde aparece | Tamanho exibido | Estilo | Briefing |
|---|---|---|---|---|
| `radar-scan` | Radar, enquanto a busca roda (cadeia de etapas) | 240×160 | **Arte final** (`static/images/planner/illustrations/radar-scan.webp`, flat editorial #1DBF73) | Mascote com binóculo ao lado da antena varrendo a cidade; notícia, busca e celular acendem. Prompt em `docs/prompts-radar-wizard-image-2-5.md`. |
| `radar-empty` | Radar antes da primeira busca | 240×160 | **Arte final** (`radar-empty.webp`) | Mascote com luneta no morro, horizonte calmo e um brilho verde. |
| `balance` | Balanceamento de mídia carregando | 200×140 | 3D | Balança de pratos em que cada prato tem blocos de cores diferentes (TV, celular, jornal, fone) se equilibrando. Um dos blocos desce suavemente para o lugar. |
| `review` | Revisão final do plano (modal) | 200×140 | 2D | Prancheta com lista de checagem: três itens recebem um check verde e uma lupa fica sobre o último item. |
| `plan-building` | Cadu montando ou recalculando o plano | 240×160 | 3D | Blocos de montar empilhando-se em degraus (briefing, audiência, canais, verba), com o último bloco descendo com um leve brilho verde. |
| `time-saved` | Selo de tempo poupado (revisão e cabeçalho do plano) | 56×56 (lido a 18 px) | 2D | Ampulheta inclinada com a areia em `#17B26A` e um raio pequeno ao lado. Precisa ser legível a 18 px. |

A espera do Radar é um quadrado centralizado: mascote no meio, três órbitas animadas em código e 3 cenas (uma por fase) trocadas com fade: instruções em `docs/prompts-radar-animacao-image-2-5.md`.

Cenas do wizard do Radar (`radar-1-marca` a `radar-5-revisao`, 900 px de largura) já estão em `static/images/planner/illustrations/` e entram no `RadarWizard.jsx` (fase 1 do plano v2).

## Ao criar um espaço novo

1. Acrescente o slot em `ILLUSTRATIONS` (`Illustration.jsx`) com `size`, `style` e `brief`. O briefing termina com a paleta comum.
2. Desenhe a forma placeholder em `shapes`, usando só as classes `ill__*`, que já respeitam a paleta e o movimento reduzido.
3. Registre o slot na tabela acima.
