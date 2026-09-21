# Cadu · pacote de conhecimento global de marketing e mídia

Status: `draft_review_pending`  
Escopo: `global`  
Idioma: `pt-BR`  
Versão do pacote: `v1.0.0`  
Destino: RAG Global do Cadu

Integração: o pacote é carregado como rascunho pela instalação de modelos da Base Cadu (/api/gestao/base/modelos). A publicação continua manual em cada documento, após revisão.

## Regra de publicação

Estes documentos são material editorial para revisão. Não devem ser indexados como conhecimento aprovado enquanto cada fonte, definição e exemplo não tiver sido conferido. Conteúdo específico de clientes, marcas, projetos ou campanhas nunca entra neste pacote.

## Pacotes

1. `01-glossario-marketing-midia.md` — v1.0.0 — vocabulário e métricas.
2. `02-tipos-de-midia-e-linguagem-tecnica.md` — v1.0.0 — canais, formatos, compra e operação.
3. `03-metodos-de-investimento-em-midia.md` — v1.0.0 — métodos nacionais e internacionais, aplicação e limitações.
4. `04-balanceamento-multicanal-e-estrategia.md` — v1.0.0 — distribuição, cenários, mensuração e otimização.

## Metadados mínimos de ingestão

```json
{
  "knowledge_scope": "global",
  "domain": "marketing_media",
  "language": "pt-BR",
  "status": "draft_review_pending",
  "version": "0.1.0",
  "source_type": "official|academic|industry",
  "review_required": true,
  "reviewed_by": null,
  "reviewed_at": null
}
```

## Critérios de revisão antes do RAG

- conferir cada link e data de publicação;
- separar definição, hipótese, benchmark e recomendação;
- remover números sem contexto, país, período ou fonte;
- indicar quando uma métrica é de plataforma e quando é de negócio;
- marcar métodos que exigem série histórica, experimento ou modelagem;
- registrar limitações e riscos de atribuição;
- testar recuperação por termo, pergunta de planejamento e caso de campanha;
- publicar somente após aprovação editorial.

## Fontes-base

- [IAB Brasil — Glossário de Métricas Retail Media](https://iabbrasil.com.br/glossario-de-metricas-2024/)
- [Google Ads Help — About Reach Planner](https://support.google.com/google-ads/answer/9427120?hl=en)
- [Google Research — Bayesian Hierarchical Media Mix Model](https://research.google/pubs/bayesian-hierarchical-media-mix-model-incorporating-reach-and-frequency-data/)
- [IAB — Unified Media Planning Playbook](https://www.iab.com/insights/2025-unified-media-planning-playbook/)
- [ScienceDirect — Advertising planning problem](https://www.sciencedirect.com/science/article/pii/S0377221707009988)
- [Springer — Data-driven budget allocation](https://link.springer.com/article/10.1057/s41270-024-00294-2)
