# CADU Audience Intelligence — produto, dados reais e transição do legado

## Usuário no centro

O catálogo deve reduzir trabalho de planejamento, não expor uma planilha de fornecedores.

| Usuário | Decisão que precisa tomar | Resposta que o produto deve dar |
|---|---|---|
| Gestor de mídia de agência | Como construir uma recomendação defensável para o briefing? | Quais conceitos combinam com mercado, objetivo, estágio do funil, sinal e canais disponíveis. |
| Analista de mídia | Quais segmentos são ativáveis e quais restrições existem? | Fonte, tipo de dado, sinal, disponibilidade por canal, atualização e nível de curadoria. |
| Gestor de mídia do cliente | Por que essa estratégia é melhor para o negócio? | Explicação simples do público, hipótese de mídia, momento da jornada e próximo passo. |
| Comercial/planejamento | O que precisa ser cotado ou desenhado? | Lista de interesse, briefing capturado e mercados relacionados; nunca preço exposto prematuramente. |

## Fluxo CX proposto

`Mercado do cliente → objetivo da campanha → públicos e sinais → canais disponíveis → lista de interesse → pedir plano de mídia/cotação`

O catálogo deve mostrar primeiro o benefício estratégico. Fonte, formato e requisito de cotação entram como evidência de viabilidade; CPM e preço permanecem no ambiente comercial interno.

## Dados que a Taxonomia V2 já permite estruturar

- conceito de audiência versus contexto, perfil transversal, tática e formato;
- nome canônico de exibição, separado do nome bruto importado e da fonte;
- mercado principal e mercados relacionados;
- submercado;
- orientação B2B/B2C/híbrida;
- tipo de sinal: intenção, afinidade, visitação, firmográfico, cargo, CRM etc.;
- estágio recomendado do funil;
- confiança da classificação e status de curadoria;
- relações muitos-para-muitos entre item e mercado;
- proveniência da classificação, para preservar edição humana.

## Estrutura já criada no banco

A migração `add_cadu_audience_taxonomy.sql` criou, de forma aditiva:

- `cadu_taxonomy_markets`: os 10 mercados de navegação;
- `cadu_audience_taxonomy`: classificação V2, curadoria e metadados de qualidade;
- `cadu_audience_market_relations`: relação muitos-para-muitos entre audiência e mercados;
- `cadu_audience_measurements`: série de medições verificáveis por audiência, canal, período e fonte.

Também foram incluídos campos ainda vazios para `data_quality_status`, origem, referência, data observada, validade, metodologia, estimativa, canais disponíveis, geografia e restrições. Eles existem para receber informação real sem reaproveitar campos legados de forma ambígua.

O campo `canonical_name` é o nome que deve aparecer ao usuário. `cadu_audiencias.nome` permanece como rótulo bruto importado para rastreabilidade e compatibilidade. Referências como fornecedor, metodologia e código de segmento não devem aparecer no nome canônico.

## Dados que ainda não podem ser vendidos como verdade de mercado

Números de alcance, CPM, CTR, conversão e afinidade só poderão entrar em comunicação externa ou recomendação quantitativa quando tiverem origem, data de coleta, metodologia, território, janela temporal e canal registrados. Estimativas sem isso devem aparecer, no máximo, como referência interna rotulada.

## Instrumentação para criar inteligência própria

### Sinais de demanda no produto

Registrar eventos com usuário/conta, audiência, mercado, canal, contexto e timestamp:

- visualizou audiência;
- filtrou por mercado, objetivo ou sinal;
- salvou em lista de interesse;
- removeu da lista;
- iniciou pedido de plano;
- solicitou cotação;
- proposta enviada, aprovada, perdida ou convertida.

Isso forma um índice de demanda de planejamento por mercado e por tipo de sinal. Os campos atuais `views_count`, `added_to_cart_count` e `quoted_count` não são suficientes para esse produto: a base possui visualizações, mas não possui seleções nem cotações registradas nesses contadores.

### Dados reais de ativação

Para cada oferta por canal, adicionar posteriormente:

- data de atualização e validade;
- fornecedor, metodologia e permissão de uso;
- praça/geografia elegível;
- estimativa de alcance, com janela e definição;
- formatos e dispositivos disponíveis;
- restrições de segmentação;
- métricas agregadas de entrega: impressões, alcance, frequência, viewability, VTR, CTR, conversão e custo;
- identificador de campanha e período, sem expor dados pessoais.

## Produtos de dados que passam a ser possíveis

1. **Mapa de cobertura por mercado**: quais sinais, canais e fornecedores atendem cada vertical.
2. **Brief-to-audience recommender**: recomendação explicável de públicos por mercado, objetivo e funil.
3. **Radar de demanda de planejamento**: o que agências e anunciantes pesquisam, salvam e cotam — com agregação e privacidade.
4. **Matriz de disponibilidade por canal**: onde cada conceito pode ser ativado, com filtros por formato, praça e restrições.
5. **Benchmark de execução**: somente depois de receber métricas reais, comparações agregadas por mercado/canal/objetivo, com amostra e período declarados.
6. **Mapa de lacunas de oferta**: mercados com demanda de planejamento sem cobertura de sinais ou canais suficientes.

## Transição segura do legado

1. A Taxonomia V2 coexiste com `categoria_id` e `subcategoria_id`.
2. Interfaces legadas seguem lendo os campos antigos; as telas administrativas passam a exibir V2 como informação adicional.
3. APIs novas expõem V2 sem alterar o contrato das APIs existentes.
4. Após curadoria, novas interfaces devem usar V2 como fonte primária.
5. Só depois de instrumentação, reconciliação de usos históricos e uma janela de compatibilidade, os campos antigos podem ser descontinuados em uma migração separada.
