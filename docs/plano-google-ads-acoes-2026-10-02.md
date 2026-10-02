# Google Ads · dois scripts: Leitura e Ações

Data: 2026-10-02 · Status: fases 1 e 2 implementadas (migração ainda não aplicada)

## Objetivo

Fechar o ciclo das recomendações do Reports: hoje cada regra de `reports_google_ads_rules.py` termina em
"execute no Google Ads Editor com o CSV". Com o script de Ações, a pessoa aprova no Reports e a mudança é aplicada
na conta na próxima execução. Sem Google Ads API: tudo roda por Google Ads Scripts.

## Por que dois scripts

| | Leitura (existente) | Ações (novo) |
|---|---|---|
| Arquivo | `static/cadu_connect/google-ads-engine-v2.js` | `static/cadu_connect/google-ads-actions.js` |
| Faz | lê a conta e envia ao Reports | busca comandos aprovados, aplica, devolve o resultado |
| Escreve no Google Ads | nunca | só operações da lista fechada |
| Agenda | diária | de hora em hora (mínimo permitido pelo Google) |
| Chave | `source_kind='google_ads_script'` | chave própria `source_kind='google_ads_actions'` |
| Muda com frequência | sim (novos dados) | raramente (lista de operações estável) |

Vantagens da separação:
- O cliente pode autorizar só a Leitura. Ações é opt-in, por conta.
- Revogar a chave de Ações corta a escrita sem parar os relatórios.
- Cada script tem seus próprios 30 minutos de execução; uma leitura pesada não atrasa uma pausa.
- Atualizar a Leitura nunca toca no código que escreve na conta, e vice-versa.

## Fluxo

```
Recomendação ou ação manual no Reports
  → comando criado (pending_approval)
  → pessoa com permissão aprova (approved)
  → script de Ações busca: GET /connect/api/gads/actions?account_id=…   (approved → sent, com lease)
  → aplica cada comando, conferindo a pré-condição
  → POST /connect/api/gads/actions/result   (sent → applied | failed | skipped)
  → a próxima Leitura confirma o novo estado (snapshot de campanhas e negativas)
```

## Operações (lista fechada no código colado)

Fase 1, reversíveis com um clique:

| op | alvo | Google Ads Scripts |
|---|---|---|
| `campaign.pause` / `campaign.enable` | campanha | `AdsApp.campaigns()` + `performanceMaxCampaigns()`, `shoppingCampaigns()`, `videoCampaigns()` → `.pause()` / `.enable()` |
| `ad_group.pause` / `ad_group.enable` | grupo | `AdsApp.adGroups().withIds([id])` |
| `keyword.pause` / `keyword.enable` | palavra-chave | `AdsApp.keywords().withIds([[adGroupId, criterionId]])` |
| `negative.add` | campanha, grupo ou lista compartilhada | `createNegativeKeyword(texto)` / `negativeKeywordLists().withIds([id])…addNegativeKeyword` |

Fase 3, com teto:

| op | teto padrão |
|---|---|
| `keyword.set_cpc` | ±30% sobre o lance atual |
| `campaign.set_budget` | ±30% sobre o orçamento atual; recusa orçamento compartilhado |

Comando:

```json
{"id": "uuid", "op": "campaign.pause",
 "target": {"campaign_id": "123"},
 "params": {},
 "expect": {"status": "ENABLED"},
 "expires_at": "2026-10-03T12:00:00Z"}
```

`expect` é a pré-condição: se a conta mudou desde a aprovação (alguém já pausou, o orçamento já é outro), o script
devolve `skipped` com o estado real em vez de aplicar uma decisão velha.

## Travas

No código colado (o servidor não consegue afrouxar):
- `allowWrites` no `CADU`: o cliente desliga a escrita editando uma linha, sem depender de nós.
- `allowedOps`: qualquer `op` fora da lista é recusada.
- `maxChangesPerRun` (padrão 50), `maxBudgetChangePct` e `maxCpcChangePct` (padrão 30).
- Comando vencido (`expires_at`, padrão 24 h após a aprovação) é recusado.
- Em Pré-visualização do Google Ads (`AdsApp.getExecutionInfo().isPreview()`) nada é gravado; o resultado volta como simulação.

No servidor:
- Aprovar exige papel com permissão de operação na conta; quem criou e quem aprovou ficam registrados.
- Lease: comando entregue fica `sent` por 2 h; sem resultado, vira `unknown` e é resolvido pela próxima Leitura.
- Idempotência por `id`: reenvio do mesmo resultado não duplica nada.
- Fase 1 sem aplicação automática: toda ação passa por aprovação humana.

Tudo também aparece no Histórico de alterações do Google Ads, com o usuário que autorizou o script.

## Dados

`cadu_reports_gads_actions`: `id`, `client_id`, `account_id`, `op`, `target jsonb`, `params jsonb`, `expect jsonb`,
`status` (`pending_approval`, `approved`, `sent`, `applied`, `failed`, `skipped`, `expired`, `cancelled`, `unknown`),
`origin` (`rule:<chave>`, `manual`, `cadu`), `undo_of`, `created_by`, `approved_by`, `approved_at`, `sent_at`,
`lease_run_key`, `applied_at`, `result jsonb`, `expires_at`, `created_at`.

Chave de Ações: reaproveita `cadu_reports_ingest_keys` com `source_kind='google_ads_actions'`.

## Interface (Reports › Google Ads)

- Recomendações com ação mapeável ganham "Aplicar no Google Ads" (cria o comando já com `expect`).
- Aba "Ações": fila para aprovar, enviados, aplicados, falhas; seleção em lote.
- "Desfazer" em ação aplicada gera o comando inverso (pausar ↔ ativar, negativa → remover, orçamento → valor anterior).
- Conta sem script de Ações instalado: o botão vira "Instalar script de Ações" com o código pronto para colar.
- Selo "script desatualizado" quando a versão enviada pela Leitura ou pelas Ações é menor que a mínima.

## Fases

1. **Base:** migração, endpoints `actions` e `actions/result`, script de Ações com pausar/ativar e negativas,
   testes Python e harness JS com `AdsApp` simulado.
2. **Interface:** botão nas recomendações, aba Ações, desfazer, geração da chave e do script de Ações.
3. **Lances e orçamento** com teto; o Cadu passa a propor ações na fila (ainda com aprovação).

## Decisões (2026-10-02)

- Qualquer pessoa com edição no cliente aprova; aprovar = agendar (não há segunda etapa). Leitores (`viewer`) não aprovam.
- Tetos de 30% para lance e orçamento como padrão; escolhidos ao gerar os scripts, gravados na chave e no código colado.
  Pedido acima do teto é limitado ao teto e o rótulo da ação diz isso.
- Latência de até 1 h aceita, com contador na tela ("aplica em mm:ss", calculado pelo intervalo real entre execuções)
  e avisos quando a mudança é aplicada, falha ou é ignorada (na tela e, se ligado, no navegador).
- Os dois scripts são gerados juntos em Mídia › Dados, cada um com nome `Cadu_GoogleAds_<Leitura|Acoes>_<conta ou MCC>_v<versão>`
  e download em .txt.

## Implementado

- `migrations/add_reports_google_ads_actions.sql` (no `deploy.sh`): `cadu_reports_gads_actions`, `cadu_reports_gads_action_agents`,
  `cadu_reports_ingest_keys.limits`.
- `cadu_connect/reports_google_ads_actions.py`: validação (`normalize`), teto (`clamp`), desfazer (`inverse`), próxima execução
  (`next_run`); rotas do script `POST /connect/api/gads/actions/next` e `/actions/result`; rotas do app
  `GET|POST /api/v2/reports/google-ads/actions`, `/<id>/cancel`, `/<id>/undo`.
- `static/cadu_connect/google-ads-actions.js` v1.0.0: pausar/ativar campanha, grupo e palavra-chave; adicionar palavra-chave;
  lance; orçamento; adicionar e remover negativa (campanha, grupo, lista).
- Recomendações com `proposal` (negativar termo, adicionar termo, pausar palavra-chave, remover negativa em conflito, pausar
  campanha fora da meta, ajustar orçamento) e `queued` com o estado da ação.
- Tela: aba "Ações" (script por conta, fila, histórico, desfazer, avisos), botão em cada recomendação, "Aplicar N mudanças",
  "Negativar/Adicionar no Google Ads" em Termos de pesquisa; Mídia › Dados gera os dois scripts.
- Status de ação usados: `approved`, `sent`, `applied`, `failed`, `skipped`, `expired`, `cancelled`
  (`pending_approval` e `unknown` ficaram de fora: aprovar já agenda, e a entrega sem resposta volta à fila após 90 min).

Pendente: fase 3 (o Cadu propondo ações na fila).
