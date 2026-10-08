# Radar: plano de refatoração da interface (mockup "workspace de radares")

Plano de 2026-10-08. Parte do mockup de 2026-10-07 (detalhe de um radar: "Mídia programática e CTV para varejo no 1º trimestre de 2027"). Continua `docs/radar-v2-plano.md`.

## Decisão de estrutura

O mockup é um **software de trabalho**, não uma vitrine. Isso substitui a entrada atual (hero + abas de feed). O hero com foto sai do Radar; as imagens ficam só no estado de primeiro uso.

| Tela | Rota | Papel |
|---|---|---|
| **Lista de radares** | `/radar` | Sidebar (Novo radar, Meus radares, Compartilhados, Favoritos, Lixeira; Marcas; Status; Período) + tabela/cartões de radares |
| **Detalhe do radar** | `/radar/<id>` | Cabeçalho, 6 abas, coluna lateral "Sobre este radar" |
| **Novo radar** | `/radar?novo=1` | O assistente atual, sem mudança |

A unidade da tela passa a ser o **radar** (uma busca ou um radar ativo com suas rodadas), não a notícia. O feed de notícias que fiz (`RadarHub`) vira a aba **Sinais** do detalhe e uma visão "Em alta" opcional na lista.

## O que o mockup pede, e o que já existe

| Elemento do mockup | Existe? | Fonte hoje | O que falta |
|---|---|---|---|
| Lista por marca, status, período | Parcial | `cadu_radar_runs` (brand_ref, status, created_at) | Filtros e contagens por marca/status/período (SQL) |
| Favoritos, Lixeira, Compartilhados | Não | — | Colunas `favorite`, `deleted_at` no run; compartilhamento só depois |
| Título, marca, categoria, período, criado por, tokens | Parcial | `focus`, `brand_ref`, `params`, `cost`, `created_by` | Categoria e período: já vêm do wizard em `params`? Conferir; senão derivar do tema |
| Descrição do radar | Não | — | Texto do tema (já temos `focus`); descrição longa é opcional |
| Chips de tema (CTV, Varejo…) | Não | — | Palavras-chave extraídas na etapa `angles` (campo novo no JSON) |
| Resumo executivo | Não | — | Uma chamada de modelo ao fim do run (barata, Haiku) gravada no run |
| 4 KPIs (sinais, fontes, ângulos, em plano) | Sim | signals, opportunities, status `em_plano` | Só consulta |
| Ângulos: prioridade (Alta/Média), tags, imagem | Parcial | `score_breakdown` (rank, formats, channels) | Prioridade: derivar de `rank` ou pedir ao modelo; imagem: ver abaixo |
| Aba Sinais | Sim | `cadu_radar_signals` | Já feita no `RadarHub` |
| Aba Evidências | Sim | `signals.verification` (tier, url_status) + fontes | Tabela por fonte, com nível e link |
| Aba Aplicações | Não | — | Formatos/canais agregados dos ângulos, com atalho para o catálogo |
| Aba Metodologia | Sim | `run.steps` | É o "Como a busca foi feita" que já existe |
| Territórios explorados | Não | — | Agrupar sinais por tema; sai da mesma extração de palavras-chave |
| Planos relacionados | Parcial | oportunidade `em_plano` | Guardar `plan_id` na oportunidade; listar os planos |
| Transformar em plano / Adicionar ao plano | Sim | `/radar/opportunities/<id>/plan` | "Adicionar ao plano" existente (hoje só cria plano novo) |
| Compartilhar, Exportar, Favoritar | Não | — | Fase tardia |

## Decisões que precisam do seu sim

1. **Imagem nos ângulos.** O mockup tem foto por ângulo. Não temos fonte de imagem. Opções: (a) imagem da notícia (og:image do Firecrawl, já na leitura), (b) capa gerada pelo Studio (custo por ângulo), (c) sem imagem. Recomendo (a) com fallback sem imagem.
2. **Prioridade "Alta/Média oportunidade".** Recomendo derivar do `rank` (1º e 2º = Alta, resto = Média) até haver nota explicável. Nota de verdade volta só com o scoring do Radar v2.
3. **Resumo executivo e territórios.** Exigem uma chamada de modelo a mais por busca (estimativa: 1–2 mil tokens). Recomendo incluir no `save`, com a mesma reserva.
4. **Favoritos/Lixeira/Compartilhados.** Recomendo Favoritos e Lixeira na fase 2 (colunas simples) e deixar Compartilhados para quando existir o modelo de compartilhamento do Planner (hoje só o plano tem link público).

## Fases

**Fase 0: sem dado novo (só reorganizar).** Entregável visível, sem migração.
- Layout de duas colunas com sidebar e a lista de radares (runs) em cartões, filtros de marca/status/período no cliente.
- Detalhe `/radar/<id>` com cabeçalho, KPIs, abas Visão geral, Ângulos, Sinais, Evidências, Metodologia e coluna "Sobre este radar".
- Remover hero, "Consultas realizadas" e a duplicação com `/radares` (já parcialmente feito).
- Testes: renderização com dados de exemplo (como o harness desta semana) e nav boot.

**Fase 1: dados do detalhe.** Uma migração aditiva (`add_cadu_radar_v4.sql`).
- Em `cadu_radar_runs`: `summary` (resumo executivo), `keywords` (chips), `territories` (JSONB).
- Em `cadu_radar_opportunities`: `plan_id`, `priority`.
- Pipeline: extrair palavras-chave e territórios na etapa `angles`; gerar o resumo no `save`. Reserva de tokens ajustada e medida no Lab antes de ir ao produto (regra da casa).
- Aba Aplicações e "Planos relacionados".

**Fase 2: organização.** `favorite`, `deleted_at`, restaurar da lixeira, filtros e contagens por SQL.

**Fase 3: compartilhar e exportar.** Depende do modelo de compartilhamento; exportar PDF/CSV dos ângulos.

## Riscos

- Produção diverge do esquema do repo: testar cada migração em Postgres local e conferir `ORDER.txt` (regra de deploy).
- Nenhum radar rodou ainda em escala; o resumo executivo e as palavras-chave precisam de amostra real para não inventar. Fase 0 não depende disso.
- `docs/radar-v2-plano.md` já prevê Alertas e Agentes no mesmo menu: a sidebar nova precisa reservar esses lugares.
- A tela atual de feed (`RadarHub`) e o `feed.py` não se perdem: viram a aba Sinais.

## Ordem sugerida

Fase 0 primeiro (uma sessão, sem risco de dados), depois medir no Lab o resumo e as palavras-chave, depois a fase 1.
