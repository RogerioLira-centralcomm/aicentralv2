# Reports: auditoria de interface (2026-10-07)

Escopo: todas as rotas de `frontend/reports-v1/shell/routes.js` em 1440, 820 e 390 px, com o pacote compilado e dados simulados
(bootstrap do fixture `tests/fixtures/reports_clients_accounts.json`; as demais APIs devolvem `{}`). Script: `audit.cjs` no
scratchpad da sessão. Medido: rolagem lateral, elementos que saem da tela, proporção de elementos dentro de `.untitled-scope`,
botões e campos do kit (react-aria) contra nativos, classes legadas (`reports-`, `rs-`, `flow-` etc.) e erros de página.

## Limite desta passada

As 7 telas de Site & Jornada (exceto Navegação e Heatmap), Criativos e Fluxos caem no "Não foi possível exibir o Reports"
porque o `{}` simulado não tem as listas que a API real devolve (`isEmpty` lê `.length` de `undefined`). Não é bug de produção,
mas mostra que uma resposta parcial derruba a aplicação inteira em vez de só o card. Para auditar essas telas com fidelidade é
preciso uma passada com dados reais (navegador logado) ou mocks completos por endpoint.

## Situação por área

| Área | Untitled UI | CSS legado | Problemas vistos em 390 px |
|---|---|---|---|
| Visão geral | 0% (hubs/overview, 52 classes legadas) | overview.css | — |
| Conhecer o Reports | migrada | onboarding.css (próprio, tokens do kit) | — |
| Mídia (visão, Google Ads, Criativos) | 0% | styles.css, google-ads-actions.css | abas cortadas sem indicação de rolagem |
| Mídia › Campanhas | parcial (tabela e filtros legados) | styles.css | cabeçalho do card espremido; "Gerenciar em Clientes e contas" cortado; nomes quebram palavra por palavra na tabela |
| Site & Jornada (7 telas) | 0% | journey.css, page-detail.css, tech-panel.css | não renderizou (ver limite) |
| Fluxos (editor e índice) | 0% | flow-workspace.css, flow-canvas.css, flows-index.css (~90 KB) | não renderizou |
| Relatórios | migrada | — | — |
| Alertas | 0% no layout (botões do kit) | alerts-center.css | grade de indicadores com célula cinza vazia; "Configurar alertas" e "Exportar" fora do kit |
| Fontes de dados › Visão geral | 0% | styles.css | tabela de sites corta "Eventos (30 dias)"; seletor de cliente reduzido a "L" |
| Fontes › Conexões e chaves | 83% | — | 5 alvos de toque abaixo de 24 px |
| Fontes › Super Tag | 83% | super tag parts | subabas quebram em 3 linhas |
| Fontes › Eventos | 46% | — | botão "Evento personalizado" cortado na borda |
| Fontes › Importações | 69% | — | — |
| Link Tester | 85% | — | — |
| Clientes e contas | 97% | — | 21 alvos de toque abaixo de 24 px (lápis de editar) |
| Acessos | 68% | — | — |

Nenhuma rota rolou a página na horizontal: os cortes acontecem dentro de cards com `overflow:hidden`, por isso a métrica de
rolagem não pega e só a captura mostra.

CSS próprio do Reports: ~300 KB em 22 arquivos; os maiores são `flow-workspace.css` (58 KB), `styles.css` (52 KB),
`shell.css` (37 KB), `flow-canvas.css` (24 KB) e `reports-refinement.css` (23 KB).

## Plano proposto (uma área por entrega, cada uma com teste de tela em 3 larguras)

1. **Correções de viewport já vistas** (pequeno, sem migrar): célula vazia de Alertas, cabeçalho e botão de Mídia › Campanhas,
   botão de Eventos, tabela de sites em Fontes, alvos de toque de Clientes e contas, e um limite de erro por página para que
   uma resposta parcial derrube só a tela e não o Reports.
2. **Visão geral** para o kit.
3. **Mídia** (visão, Campanhas, Google Ads, Criativos).
4. **Alertas** e **Fontes de dados › Visão geral**.
5. **Site & Jornada** (7 telas), com passada de dados reais antes.
6. **Fluxos** (editor e índice): o maior bloco de CSS; pede plano próprio porque o canvas tem regras específicas.
7. Remover o CSS que ficar sem uso a cada etapa (medido por cobertura, não à mão).
