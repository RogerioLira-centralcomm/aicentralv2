# [Video Studio] Projetos, versões, jobs, desempenho e custos

## Objetivo

Tornar o Studio recuperável e operável: vários projetos, revisões, autosave, fila durável, desempenho previsível e custos auditáveis.

![Mockup — projetos, jobs e custos](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/07-projetos-jobs-custos.png)

## Cena representada no mockup

O dashboard lista projetos e status, mostra gasto confirmado/em processamento e armazenamento. Um drawer exibe versões restauráveis/comparáveis. A tabela de jobs reúne proxy, transcrição, geração e exportação com fila, progresso, falha e retry.

## Estado atual

- Projetos já usam SQLite, IDs, revisões imutáveis e conflito por revisão.
- A interface ainda não oferece gestão completa de projetos ou restauração de versões.
- Exportações usam `ThreadPoolExecutor`; não sobrevivem como fila distribuída/durável.
- Ledger atual registra gerações, locução, Trocr e export local.

## Escopo funcional

- Listar, criar, renomear, duplicar, arquivar e reabrir projetos.
- Autosave idempotente com estado Salvando, Salvo e Conflito.
- Histórico de revisões, restaurar, comparar e criar cópia recuperável.
- Worker/fila durável com lease, heartbeat, retry e retomada após restart.
- Estados queued, processing, ready, failed e cancelled.
- Prioridades e concorrência por workspace para proxy, transcrição, geração e export.
- Timeline e waveforms virtualizadas; cache de poster/proxy; cancelamento de requests obsoletos.
- Telemetria de duração de etapa, fila, codec, erro, CPU e memória.
- Ledger estimado/confirmado por operação, modelo, ativo, projeto, revisão e request id.
- Separar custos de IA, processamento/armazenamento e operações locais.

## Backend

- Reutilizar infraestrutura durável existente quando compatível.
- Migração/backup do projeto e políticas de retenção/cleanup.
- Métricas e logs correlacionados por job/request.

## Frontend

- Dashboard de projetos, versões, jobs e custos.
- Recuperação de conflito 409 sem perda silenciosa.
- Progressos continuam visíveis após reload.

## Critérios de aceite

- [ ] Dois projetos da mesma marca permanecem independentes.
- [ ] Duas abas nunca sobrescrevem trabalho silenciosamente.
- [ ] Reiniciar web/worker não perde jobs nem deixa status eterno.
- [ ] Exportação iniciada permanece vinculada à revisão original.
- [ ] Projeto de 5 min/30 clipes/4 faixas/300 captions continua utilizável.
- [ ] Custos pagos aparecem antes da confirmação e depois são conciliados sem duplicidade.
- [ ] Arquivar/restaurar e restaurar revisão não perdem ativos.

## Dependências

- É base transversal para ingestão, transcrição, geração e exportação.

