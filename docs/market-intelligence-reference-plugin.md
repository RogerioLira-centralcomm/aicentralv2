# Market Intelligence — plugin de referência

Market Intelligence demonstra como um plugin Cadu combina contexto autorizado,
pesquisa pública, modelos por função, jobs retomáveis, evidências e artefatos.
O catálogo identifica o plugin; o backend mantém a lista de ferramentas
executáveis. Configuração de cliente nunca concede permissões novas.

## Modos

| Modo | Fluxo | Limites padrão |
|---|---|---|
| `quick` | Busca, leitura, análise e mini relatório | 15 fontes-alvo, até 5 consultas, 24 mil tokens |
| `deep` | Plano, rodadas de busca e extração, análise de lacunas, crítica, checagem e artefato | 60 fontes-alvo, máximo 150, até 30 consultas, 4 rodadas, 120 mil tokens |
| `custom` | Herda Deep e aplica perfil validado da conta | Limites configuráveis, com os mesmos tetos de segurança |

No chat, invoque `/market-intelligence quick`, `/market-intelligence deep` ou
`/market-intelligence custom`, seguido do objetivo. O card do plugin inicia
Quick Scan. O pedido vira um job durável, com estado consultável e etapas
retomáveis. O worker pode encerrar rodadas restantes quando a análise de
lacunas indicar cobertura suficiente.

## Contexto, pesquisa e evidências

Marca e projeto são resolvidos por ferramentas MCP autorizadas. Esses dados
privados entram na análise e nas implicações, não nas consultas públicas. A
busca usa o objetivo público filtrado e campos públicos aprovados da marca;
Firecrawl pesquisa e lê páginas. URLs são normalizadas e deduplicadas. Claims
extraídos ficam ligados ao ID da fonte, trecho, data, entidade, tema e
confiança. O artefato inclui relatório, base de evidências, índice de fontes e
estado das lacunas. Fonte localizada sem conteúdo legível aparece identificada
como indisponível. Uma leitura que falha é marcada como indisponível para não
ser repetida nas rodadas seguintes. A síntese recebe apenas evidências de
fontes lidas. Se uma versão gerada citar fonte não lida ou trouxer referência
incompleta, a entrega é reconstruída a partir dos achados extraídos das fontes
lidas.

Fontes proprietárias além do projeto/marca e da web só podem entrar quando
houver um conector Cadu autorizado. A configuração atual não executa código
nem aceita novas ferramentas fornecidas pelo cliente.

## Modelos e custo

As chamadas passam pelo OpenRouter e têm papéis separados: `fast_classifier`,
`query_generator`, `structured_extractor`, `research_reasoner`, `critic` e
`editorial_writer`. Cada papel usa a variável correspondente
`CADU_MARKET_MI_<ROLE>_MODEL`; sem variável própria, usa o modelo padrão
OpenRouter. A política por chamada fica na tabela de chamadas do job com
provedor, modelo, tokens e role.

Para permitir GLM-5 num perfil de cliente, inclua o ID exato do modelo na lista
de servidor `CADU_MARKET_MI_ALLOWED_MODELS` e selecione-o no perfil. Um modelo
não aprovado é rejeitado. Configure um papel `critic` diferente de
`research_reasoner` para obter revisão independente com outro modelo.

## Perfil por conta

Somente administrador da conta pode consultar ou alterar o perfil:

```http
GET /workspace/api/v2/market-intelligence/profile
PUT /workspace/api/v2/market-intelligence/profile
Content-Type: application/json
X-CSRF-Token: <token da sessão>
```

Exemplo de corpo do `PUT`:

```json
{
  "profile": {
    "source_target": 80,
    "max_queries": 20,
    "search_rounds": 3,
    "token_budget": 90000,
    "include_domains": ["gov.br", "abia.org.br"],
    "methodology": "Compare movimentos, evidência e implicação para a marca.",
    "taxonomy": "Produto, preço, distribuição e comunicação.",
    "scoring": "Dê mais peso a evidência recente e fonte primária.",
    "review_policy": "Rejeite afirmações sustentadas por uma única fonte fraca.",
    "artifact_template": "Resumo executivo, concorrentes, tendências e ações.",
    "model_roles": {"research_reasoner": "z-ai/glm-5"}
  }
}
```

Os campos aceitos são `source_target` (10–150), `max_queries` (3–30),
`search_rounds` (1–4), `token_budget` (10.000–120.000),
`max_agent_calls` (1–40), `max_extractor_calls` (1–80), `include_domains`,
`exclude_domains`, `methodology`, `taxonomy`, `scoring`, `source_preferences`,
`review_policy`, `artifact_template` e `model_roles`. Listas de domínio aceitam
até dez domínios e não podem ser usadas simultaneamente. A atualização cria
uma nova versão do perfil; jobs já criados preservam o snapshot que receberam.

## Ativação

Aplicar a migration após `add_cadu_long_running_jobs.sql`:

```sh
python migrations/run_sql_migration.py add_cadu_market_intelligence.sql
```

O catálogo apresenta o card depois da migration. Para refletir a nova sugestão
de prompt da interface no bundle estático, execute `npm run build:conversations`
quando for seguro atualizar os artefatos compilados do checkout.
