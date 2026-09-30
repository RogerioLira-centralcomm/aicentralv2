# Revisão — Capturas e audiência ao vivo

Escopo: capturas Firecrawl, cache, hook de prévias e painel de visitantes. Skill TypeSafe AI aplicada para conferir estado, evidência e identidade; documentação de State consultada em https://docs.typesafe.ai/concepts/state. Não foi usada inferência Jev para decidir identidades ou métricas.

## Achados

1. **P1 — Estado de imagens atravessa a troca de contexto em caso de falha.** `useFlowPreviews.js:24` mantém items de old e atribui a nova url. Após trocar fluxo/cliente, uma falha transforma imagens anteriores em estado válido para o novo contexto. IDs de nós coincidentes exibem capturas incorretas. Limpar items se old.url não corresponder à url da requisição; nunca reetiquetar estado anterior.
2. **P2 — Requisição de prévias sem timeout.** `useFlowPreviews.js:18` pode ficar com pending=true indefinidamente; nenhum timer é agendado até fetch terminar. Adotar timeout/abort por consulta e recuperação com backoff, inclusive ao ocultar a aba.
3. **P2 — Regeneração reaplicada ao mudar fluxo/revisão.** `useFlowPreviews.js:7,13,21` limpa somente a variável local requested, mantendo regenerate no estado React. Novo efeito restaura o ID anterior: pode gerar 404 recorrente no novo fluxo ou nova captura cobrada se o ID coincidir. Consumir a intenção uma vez e associá-la ao escopo.
4. **P2 — Arquivo perdido não gera recaptura.** `_state` em `reports_flow_previews.py:34` retorna ready mesmo se o WebP não existir; `_schedule:101` não agenda ready. Reproduzido com metadado ready sem arquivo: resultado ready. Reconhecer ausência/corrupção e reclassificar missing.
5. **P2 — Sessões online desaparecem após nova publicação.** `reports_flow.py:1708` só inclui published_revision atual. A ingestão fixa sessões à revisão inicial em `reports_flow_versions.py:90`. Sessões ainda ativas na versão anterior somem do painel sem aviso de escopo. Separar audiência online global do grafo por revisão ou informar explicitamente a limitação e oferecer consulta por versão; não mapear nós de versões diferentes.
6. **P2 — Filtro de identificação incompleto sob truncamento.** `reports_flow_live.py:53` corta as 100 sessões antes de `FlowLiveAudience.jsx:8` aplicar o filtro. Com 100 anônimas recentes e uma conhecida online mais antiga, Identificadas mostra nenhuma. Fazer filtro/paginação no servidor ou apresentar estado de amostra parcial sem afirmar ausência.

## Verificação

14 testes existentes de live/workspace passaram. Reprodução isolada confirmou falha do cache sem imagem. Testes atuais não cobrem captura real, regeneração/contexto, autorização de imagens nem a consulta SQL de identidade. Sem chamada paga Firecrawl, sem banco de produção, sem alterações de produto nesta revisão.
