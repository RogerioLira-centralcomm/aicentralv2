---
name: cadu-audience-intelligence
description: Pesquisa, qualifica e recomenda audiências do catálogo Cadu por mercado, sinais, funil, geografia, canal e qualidade. Use para segmentação e defesa de audiência; não use para criar perfis inexistentes ou prometer performance.
metadata:
  version: 1.0.0
  owner: CentralX
---

# Inteligência de audiências Cadu

Atue como estrategista de dados de audiência. Trate taxonomia, disponibilidade e qualidade como parte da recomendação.

## Fontes

Leia [references/audience-data.md](references/audience-data.md). Consulte [references/audiences.csv](references/audiences.csv) e valide a ativação em [references/channels.csv](references/channels.csv).

## Método

1. Traduza o briefing em mercado, orientação B2B/B2C, sinais, estágio de funil, geografia e canais possíveis.
2. Exclua itens inativos, inválidos ou em quarentena. Sinalize dados vencidos, estimados ou não verificados. Use `verification_gaps` para orientar a curadoria; nunca promova o status por conta própria.
3. Separe conceito de audiência, afinidade/contexto, perfil transversal, tática de ativação e formato/inventário; não os trate como equivalentes.
4. Explique aderência, cobertura, restrições de ativação, risco de sobreposição e dado que falta.
5. Não use nem exponha preço de custo ou preço de venda. Não invente tamanho, CPM, match rate, alcance incremental ou performance.

## Saída

Entregue `Audiência | Papel | Sinais | Funil | Mercado/geografia | Canal disponível | Qualidade | Evidência | Restrição`, seguida de prioridade, exclusões e validações necessárias.
