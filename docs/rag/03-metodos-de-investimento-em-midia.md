# Métodos de investimento em mídia

Status: `draft_review_pending` · Escopo: `global` · Versão: `v1.0.0`

## Instrução editorial do material

Para cada método, explique autor ou tradição metodológica quando aplicável, premissas, dados necessários, passos, fórmula ou lógica, momento correto de uso, limitações, risco de interpretação e aplicação em uma campanha. Separe recomendação, hipótese e evidência.

O Cadu deve recomendar método, não um número mágico. Toda recomendação precisa declarar objetivo, horizonte, dados disponíveis, restrições e nível de incerteza.

## 1. Percentual da receita

Define uma verba como percentual da receita ou faturamento. É simples e útil quando não há histórico, mas não garante alcance ou resultado. Separar mídia, produção, tecnologia, agência e pesquisa.

## 2. Objetivo e tarefa

1. definir objetivo;
2. quantificar público;
3. estabelecer alcance e frequência;
4. estimar custos por canal;
5. calcular verba necessária;
6. validar viabilidade e cenários.

É o método padrão para planejamento de campanha porque conecta investimento a entrega desejada.

## 3. Paridade competitiva

Usa presença, investimento ou share of voice da categoria como referência. Ajuda em mercados disputados, mas não deve copiar concorrentes sem considerar posicionamento, eficiência e capacidade de conversão.

## 4. Histórico incremental

Parte do orçamento anterior e ajusta por crescimento, sazonalidade, inflação, expansão, pressão competitiva e desempenho. Exige histórico comparável e registro das alterações de estratégia.

## 5. Retorno marginal e elasticidade

Desloca verba para canais em que o próximo investimento ainda produz maior resultado incremental. Exige variação histórica suficiente e controle de sazonalidade. Não confundir média de ROAS com retorno do próximo real investido.

## 6. Marketing Mix Modeling

Modelo agregado que relaciona investimento, vendas e variáveis externas ao longo do tempo. Pode estimar contribuição, adstock, saturação, elasticidade e cenários. É adequado para decisões de escala, mas depende de dados consistentes e não substitui experimentos.

Referência: [Google Research — Bayesian Hierarchical Media Mix Model](https://research.google/pubs/bayesian-hierarchical-media-mix-model-incorporating-reach-and-frequency-data/).

## 7. Experimento incremental

Compara tratamento e controle — por região, público ou período — para estimar causalidade. Usar quando a pergunta é se a mídia causou o resultado. Controlar mudanças de preço, distribuição, estoque, promoções e concorrência.

## 8. Otimização por restrições

Maximiza um objetivo sujeito a orçamento total, alcance mínimo, frequência máxima, limites de canal, regiões, produção e brand safety. É o método mais adequado para transformar estratégia em plano operacional quando as restrições são explícitas.

Referência metodológica: [ScienceDirect — Advertising planning problem](https://www.sciencedirect.com/science/article/pii/S0377221707009988).

## Escolha rápida

| Situação | Método inicial | Complemento |
|---|---|---|
| Sem histórico | objetivo e tarefa | cenários e benchmark declarado |
| Histórico curto | histórico incremental | teste controlado |
| Categoria competitiva | paridade competitiva | objetivo e tarefa |
| Dados semanais robustos | elasticidade ou MMM | experimento incremental |
| Muitas restrições | otimização | análise de sensibilidade |
| Dúvida causal | experimento incremental | atribuição apenas como diagnóstico |

Fontes complementares: [Springer — Data-driven budget allocation](https://link.springer.com/article/10.1057/s41270-024-00294-2) e [Google Reach Planner](https://ads.google.com/home/tools/reach-planner/).

## Perguntas e respostas para recuperação

### Qual método usar quando não existe histórico?

Comece por objetivo e tarefa. Defina público, alcance, frequência, custos, restrições e cenários. Use benchmarks somente como referência declarada e planeje um mecanismo de aprendizado.

### Quando usar MMM?

Quando há série histórica suficientemente consistente, dados agregados por período e variação de investimento, vendas e fatores externos. MMM é mais adequado para decisões de portfólio e escala do que para explicar uma única conversão.

### Quando usar um experimento incremental?

Quando a pergunta principal é causal: “quanto resultado adicional foi gerado pela mídia?”. Use grupos de tratamento e controle, regiões ou períodos comparáveis, e controle estoque, preço, distribuição e promoções.

### Posso combinar métodos?

Sim. Um plano pode usar objetivo e tarefa para construir a verba inicial, histórico incremental para calibrar, experimento para medir causalidade e otimização para distribuir a verba sob restrições.

### Como saber se o orçamento está saturado?

Observe retorno marginal, frequência, alcance incremental, repetição, conversão incremental e sinais de fadiga. Uma média histórica alta não prova que o próximo investimento terá o mesmo retorno.

### Como apresentar uma recomendação de investimento?

Informe método, objetivo, dados usados, premissas, orçamento, cenários, retorno esperado, incertezas, limitações, plano de teste e gatilhos para redistribuição.
