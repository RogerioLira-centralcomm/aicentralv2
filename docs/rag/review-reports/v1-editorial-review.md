# Relatório de revisão editorial — pacote global de mídia v1

Data da revisão: 2026-09-21  
Revisor: revisão local assistida por pesquisa web  
Status: `draft_review_pending`  
Revisão externa OpenRouter/Perplexity: `not_executed_in_this_session`

## Escopo verificado

- quatro documentos independentes;
- instruções editoriais;
- definições e fórmulas;
- distinção entre métrica de entrega, ação e negócio;
- distinção entre atribuição, previsão e causalidade;
- perguntas e respostas para recuperação;
- URLs e referências principais;
- compatibilidade com chunking semântico.

## Resultado por material

| Documento | Resultado | Ajustes aplicados | Pendência |
|---|---|---|---|
| Glossário | aprovado para revisão externa | termos, fórmulas, Q&A e regras contra ROAS como lucro | ampliar citações primárias por termo |
| Tipos de mídia | aprovado para revisão externa | canal, veículo, formato, placement, função e Q&A | validar nomenclatura por mercado brasileiro |
| Métodos de investimento | aprovado para revisão externa | oito métodos, escolha rápida, Q&A, autores e experimento geo | confirmar referências bibliográficas originais |
| Balanceamento multicanal | aprovado para revisão externa | processo, cenários, matriz, riscos e Q&A | incluir exemplos numéricos depois da validação das premissas |

## Correções de precisão

1. Reach Planner é ferramenta de previsão, não medição observada de campanha.
2. Alcance, frequência e TRP dependem do universo, período e metodologia.
3. ROAS não representa lucro.
4. Atribuição não comprova causalidade.
5. MMM exige dados agregados, variação e controles; não deve ser recomendado para qualquer conta.
6. Retorno médio não é retorno marginal.
7. Percentuais de distribuição de mídia são hipóteses, não regras universais.
8. Fontes de plataforma devem ser identificadas como documentação do próprio fornecedor.

## Fontes verificadas na pesquisa

- [Google Ads Help — About Reach Planner](https://support.google.com/google-ads/answer/9427120?hl=en): confirma que o Reach Planner produz previsões baseadas em público, orçamento, localização, formatos e histórico, além de definir métricas como alcance, frequência, TRP, CPM e CPP.
- [IAB — Unified Media Planning Playbook](https://www.iab.com/guidelines/unified-media-planning-playbook/): sustenta a necessidade de planejamento integrado diante de IDs, métricas e mecanismos de compra fragmentados.
- [Google Research — Measuring Ad Effectiveness Using Geo Experiments](https://research.google.com/pubs/archive/38355.pdf): referência para experimentos geográficos e estimativa de efeito incremental.
- [Google Research — Bayesian Hierarchical Media Mix Model](https://research.google/pubs/bayesian-hierarchical-media-mix-model-incorporating-reach-and-frequency-data/): referência para incorporar alcance e frequência a modelos de mix de mídia.
- [IAB Brasil — Glossário de Métricas Retail Media](https://iabbrasil.com.br/glossario-de-metricas-2024/): referência brasileira de terminologia de métricas de retail media.

## Pendências antes da publicação global

- executar a revisão com o modelo externo escolhido e registrar `model`, `generation_id`, custo e data;
- conferir fontes acadêmicas originais de Dorfman–Steiner, Charnes–Cooper e Tellis;
- adicionar exemplos com dados sintéticos, identificados como exemplos;
- gerar Q&A em JSON com IDs estáveis e fontes por item;
- revisar por especialista humano de mídia;
- salvar uma nova versão no administrador da Base Cadu;
- publicar somente após aprovação.

## Integração com o RAG Global

O carregamento foi conectado ao instalador de modelos da Base Cadu. Os quatro documentos são criados como versões editáveis com escopo institucional e nota de origem, sem publicação automática. O fluxo de publicação permanece no administrador da Base Cadu e não usa o RAG de projeto.

## Decisão

O pacote está consistente para uma rodada externa de revisão e já está preparado para ser carregado como rascunho no RAG Global. Não deve ser publicado como conhecimento institucional aprovado enquanto as pendências acima não forem concluídas.
