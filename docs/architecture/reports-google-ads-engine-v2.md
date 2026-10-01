# Reports · Motor Google Ads v2

Script de leitura (Google Ads Scripts) que alimenta o Reports com mais do que métricas por campanha.
O v1 (`google-ads-monitor.js`, endpoint `/api/v1/reports/ingest/google-ads`) continua funcionando para
instalações antigas; novas chaves geram o v2.

## Peças

| Peça | Arquivo |
|---|---|
| Script (cole em Ferramentas > Scripts) | `aicentralv2/static/cadu_connect/google-ads-engine-v2.js` |
| Endpoint | `POST /connect/api/v1/reports/ingest/google-ads/v2` em `aicentralv2/cadu_connect/reports_ingest_v2.py` |
| Tabelas | `migrations/add_reports_google_ads_engine_v2.sql` |
| Gerador no Reports | `frontend/reports-v1/main.jsx` (já aponta para o v2) |
| Testes | `tests/test_reports_ingest_v2.py`, `tests/test_google_ads_engine_v2_js.py` (+ `tests/js/`) |

A chave de ingestão é a mesma do v1 (`cadu_reports_ingest_keys`, `source_kind='google_ads_script'`): MCC, lista de
contas autorizadas e vínculo da conta seguem as mesmas regras de confiança.

## Conjuntos de dados

| Dataset | Tipo | Tabela | Chave natural |
|---|---|---|---|
| `campaign_metrics` | diário | `cadu_reports_campaign_daily_metrics` (v1) | campanha + data |
| `ad_group_metrics` | diário | `cadu_reports_gads_ad_group_daily` | grupo + data |
| `keyword_metrics` | diário | `cadu_reports_gads_keyword_daily` | grupo + critério + data (inclui Índice de Qualidade) |
| `search_term_metrics` | diário | `cadu_reports_gads_search_term_daily` | grupo + hash do termo + data |
| `device_metrics` | diário | `cadu_reports_gads_device_daily` | campanha + dispositivo + data |
| `landing_page_metrics` | diário | `cadu_reports_gads_landing_page_daily` | campanha + hash da URL final + data (guarda `page_host`/`page_path` para cruzar com a Super Tag) |
| `campaign_settings` | snapshot | `cadu_reports_gads_campaign_settings` | campanha (orçamento, lances, veiculação) |
| `negative_keywords` | snapshot | `cadu_reports_gads_negative_keywords` | impressão digital de nível + escopo + texto + correspondência |
| `run_summary` | heartbeat | `cadu_reports_source_runs` | uma por conta por execução |

Negativas cobrem três níveis: campanha, grupo de anúncios e lista compartilhada (com as campanhas vinculadas em
`attached_campaign_ids`).

## Contrato

Cada requisição: `schema_version: 2`, `run_key`, `account {id,name,currency,time_zone}`, `manager_account_id`,
`dataset`, `chunk {index,total}`, `records` (máx. 500) e, para snapshots, `snapshot {id, final}`.

- **Idempotência**: cada lote vira uma linha em `cadu_reports_source_runs` (`google_ads_engine_v2_chunk`) com chave
  `run_key:conta:dataset:índice`. Reenvio devolve `duplicate: true` sem regravar. Os upserts também são seguros.
- **Snapshots**: os registros são gravados a cada lote; só o lote `final: true` marca `removed_at` no que ficou de
  fora do snapshot. Assim uma palavra negativa removida no Google fica no histórico em vez de sumir. Um snapshot
  cortado por `maxRows` é enviado com `final: false` para nunca marcar remoções indevidas.
- **Heartbeat**: `run_summary` chega mesmo sem linhas e atualiza `last_used_at` da chave. Registra, por conjunto,
  `ok | empty | truncated | skipped | error`, linhas e mensagem de erro. Status `partial` quando algum conjunto falhou.
  É esse registro que prova "conectado, mas sem dados" versus "nunca conectou".
- **Falha isolada**: um conjunto com erro (por exemplo campo GAQL inválido numa versão da API) não derruba os outros.
  O script termina com erro visível no painel do Google depois de enviar o resumo.
- **Falha fatal**: HTTP 401/403 interrompe a execução na hora.

## Configuração (topo do script)

`windowDays` (7), `chunkSize` (300), `maxRuntimeMs` (25 min), `dryRun` (só loga contagens) e, por dataset,
`enabled` e `maxRows` (corta pelos de maior custo). Os marcadores `__CADU_INGEST_URL__`, `__CADU_API_KEY__` e
`__CADU_ACCOUNT_IDS__` são preenchidos pelo Reports.

## Adicionar um novo conjunto de dados

1. Coletor em `COLLECTORS` no script (`kind` + `collect`).
2. Entrada em `CADU.datasets`.
3. Normalizador, escritor e linha em `DATASETS` em `reports_ingest_v2.py`.
4. Tabela na migration e testes nos dois arquivos de teste.

## Fora do escopo desta versão

Anúncios (`ad_group_ad`), geografia, relação palavra-chave → página (o Google Ads só expõe página por campanha/grupo, não por palavra), conversões por ação, parcela de impressões e extensões. Cada um é um coletor
novo seguindo os quatro passos acima. Nenhuma tela do Reports consome ainda as tabelas `cadu_reports_gads_*`.

## Retenção

Linhas de lote (`google_ads_engine_v2_chunk`) com mais de 30 dias são apagadas pelo ciclo pesado do worker do monitor
(`prune_chunk_runs`), desde que nenhuma linha de dados ainda aponte para elas por `last_run_id`. Os resumos
(`google_ads_engine_v2`) ficam. A lista de execuções do Reports já oculta os lotes.
