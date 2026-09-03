# Migração Cadu Para Design System Enterprise

Este documento guia a migração incremental das páginas do menu Cadu para componentes vanilla/Tailwind `cx-*`, preservando Flask/Jinja e evitando mudanças de regra de negócio.

## Critérios De Aprovação Visual

- Usar `enterprise-system.css` como referência de tokens e componentes.
- Evitar classes DaisyUI novas em componentes migrados: `btn`, `badge`, `modal`, `card`, `select`, `table`, `alert`.
- Manter contraste AA em texto normal.
- Não usar textos abaixo de 12px.
- Usar cores fortes apenas para ação, atenção, sucesso ou erro.
- Tabelas devem ser densas, neutras e com ações claras por linha.
- Modais devem ter mensagem curta, corpo escaneável e rodapé fixo.

## Ordem De Migração

1. **Categorias**
   - `aicentralv2/templates/cadu_categorias.html`
   - `aicentralv2/templates/cadu_categorias_form.html`
   - `aicentralv2/templates/cadu_categorias_detalhes.html`
   - Baixo risco: templates menores e padrão repetível para lista/form/detalhe.

2. **Subcategorias**
   - `aicentralv2/templates/cadu_subcategorias.html`
   - `aicentralv2/templates/cadu_subcategorias_form.html`
   - `aicentralv2/templates/cadu_subcategorias_detalhes.html`
   - Baixo a médio risco: mesma estrutura de Categorias, com dependência de categoria pai.

3. **Interesses**
   - `aicentralv2/templates/interesse_produto.html`
   - Médio risco: filtros e autocomplete, mas sem modais complexos.

4. **Nova Audiência**
   - `aicentralv2/templates/up_audiencia.html`
   - Médio risco: formulário grande, upload e estados de loading.

5. **Métricas Plataforma**
   - `aicentralv2/templates/admin_metrics_dashboard.html`
   - Médio a alto risco: dashboard com Chart.js e muitos cards.

6. **Audiências**
   - `aicentralv2/templates/cadu_audiencias.html`
   - Alto risco: template grande, múltiplos modais, geração de imagem e JS inline extenso.

## Checklist Por Página

- Migrar layout para `base_erp.html` quando a navbar/topbar estiver aprovada.
- Trocar botões por `.cx-btn`.
- Trocar inputs/selects/textareas por `.cx-input`, `.cx-select`, `.cx-textarea`.
- Trocar badges por `.cx-badge-*`.
- Trocar cards/listas por `.cx-section`, `.cx-card`, `.cx-table`.
- Trocar modais por `<dialog class="cx-modal">` apenas depois de validar seletores JS.
- Manter IDs, names, rotas e atributos usados por JavaScript.
- Validar renderização Jinja.
- Testar fluxo principal da página antes de migrar a próxima.

## Regressão

Se uma página migrada apresentar problema, manter os templates antigos no histórico Git e reverter apenas o template da página afetada. Não remover DaisyUI até todas as páginas críticas passarem por validação.
