# Revisão da taxonomia de audiências

Este diretório contém uma proposta **não destrutiva** de classificação dos 935 registros do catálogo CADU.

## Arquivos

- `taxonomy_draft.csv`: mapeamento item a item, mantendo categoria e subcategoria atuais para comparação.
- `taxonomy_draft_summary.json`: contagens agregadas da proposta.

## Como interpretar

- `papel_catalogo_proposto` separa conceito, contexto, perfil transversal, tática e formato/inventário.
- `escopo_mercado = transversal` significa que o registro não precisa de mercado principal.
- `mercado_principal_proposto` é a porta de entrada sugerida para conceitos verticais.
- `mercados_relacionados_propostos` permite descoberta cruzada sem duplicar o conceito.
- `confianca_regra = média` exige curadoria antes de uma migração definitiva.
- `acao_migracao = avaliar consolidação conceitual` indica nome repetido entre registros e/ou fornecedores.

## Limites

O arquivo é uma base de trabalho editorial, não um script de migração. Nenhuma mudança foi realizada no PostgreSQL. A subcategoria legada só é usada como fallback de baixa autoridade quando o nome não contém sinal de mercado; ela nunca deve sobrescrever uma decisão editorial.

Para regenerar o arquivo, primeiro execute `scripts/analyze_audience_catalog.py` com acesso somente leitura ao banco e depois `scripts/build_audience_taxonomy_draft.py`.
