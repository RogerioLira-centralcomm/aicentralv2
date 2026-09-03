# Contrato mock — CRM v3

O frontend de `/crm-v3` usa somente rotas em memória sob `/crm-v3/api`.
Os dados reiniciam junto com o processo e não acessam o schema do CRM real.

Todas as respostas usam:

```json
{"success": true, "data": {}}
```

Em erro:

```json
{"success": false, "error": "Mensagem"}
```

## Recursos

- `GET/POST /clientes`
- `GET/PATCH /clientes/:cliente_id`
- `GET/POST /clientes/:cliente_id/contatos`
- `PATCH /contatos/:contato_id`
- `POST /contatos/parse-texto`
- `POST /clientes/:cliente_id/contatos/importar`
- `GET/POST /clientes/:cliente_id/atividades`
- `PATCH/DELETE /atividades/:atividade_id`
- `GET/POST /clientes/:cliente_id/objetivos`
- `PATCH/DELETE /objetivos/:objetivo_id`
- `GET/POST /clientes/:cliente_id/cotacoes`
- `PATCH/DELETE /cotacoes/:cotacao_id`
- `GET/POST /clientes/:cliente_id/notas`
- `PATCH/DELETE /notas/:nota_id`

## Campos compartilhados

- Cliente: `nome`, `cnpj`, `razao_social`, `nome_fantasia`,
  `classificacao_cliente` (`Prospecção`, `Ativo` ou `Geladeira`), `tipo`
  (`Público` ou `Privado`), `tipo_label`, `perfil`, `categoria`, `cidade`,
  `uf`, `segmento`, `fonte`, `data_cadastro` (`YYYY-MM-DD`), `prioridade`,
  `responsavel`, `seguindo`, `favorito`.
- Contato: `nome`, `email`, `cargo`, `telefone`, `telefone_secundario`,
  `setor`, `status`, `principal`.
- Atividade: `titulo`, `descricao`, `data` (`YYYY-MM-DD`), `data_label`,
  `hora`, `prioridade`, `status`, `tipo`, `responsavel`.
- Objetivo: `texto`, `prazo`, `concluido`.
- Cotação: `numero_cotacao` (`COT-YYYYMM-HEX`), `nome_campanha`, `titulo`,
  `valor_total` (numérico), `valor` (alias textual), `periodo_inicio` e
  `periodo_fim` (`YYYY-MM-DD`), `status_canonico`, `status`, `status_label`
  e `data`.
- Nota: `texto`, `autor`, `data` (`YYYY-MM-DD`).

Em cotações, `status_canonico` e `status_label` retornam um destes valores:
`Rascunho`, `Enviada`, `Aprovada`, `Rejeitada`, `Expirada` ou
`Em Acompanhamento`. O campo `status` preserva o alias em slug usado pelo
frontend (`rascunho`, `enviada`, `aprovada`, `rejeitada`, `expirada` ou
`em-acompanhamento`). Create e update aceitam tanto o valor canônico quanto
o slug; os aliases legados `negociacao`, `Em negociação` e `perdida` também
são normalizados para manter compatibilidade.

Exportação de clientes é gerada em CSV no navegador e não possui endpoint.

## IA — endpoints (Fase 3)

- `POST /api/ia/melhorar-texto` — refina descrição/nota. Espera `{"texto"}`.
- `POST /api/ia/sugerir-atividade` — sugere próxima atividade a partir do
  histórico do cliente. Espera `{"cliente_id"}`.
- `POST /api/ia/touchpoints` — cadência (D+1/D+3/D+7/D+14 conforme
  classificação). Espera `{"cliente_id"}`.
- `POST /api/ia/gerar-comunicacao` — email/WhatsApp para contato principal.
  Espera `{"cliente_id","objetivo","tipo","tamanho"}`.
- `POST /api/ia/sugerir-objetivos` — 3-5 objetivos para o próximo mês.
- `POST /api/ia/extrair-contatos` — extrai contatos estruturados a partir de
  texto livre.

Todos usam OpenRouter (Gemini 2.5 Flash) quando `OPENROUTER_API_KEY` está
disponível. Caso contrário, respondem com um fallback determinístico e
`source: "fallback"` no payload — útil para desenvolvimento offline.

## Paridade com o CRM real (`/crm`)

| Recurso                                    | `/crm` | `/crm-v3` | Observação                                                                 |
|--------------------------------------------|:------:|:---------:|----------------------------------------------------------------------------|
| Listagem/CRUD de clientes                  | sim    | sim       | Estruturas idênticas nas respostas.                                        |
| Contatos                                   | sim    | sim       | Import via IA e por texto ambos suportados.                                |
| Atividades                                 | sim    | sim       | Fluxo com drawer + painel IA integrado no v3.                              |
| Objetivos                                  | sim    | sim       | Marcação de conquista via PATCH.                                           |
| Cotações                                   | sim    | sim       | Filtros de status normalizados.                                            |
| Notas / histórico                          | sim    | sim       | Notas persistem via `crm_v3_repository` quando `USE_CRM_V3_STORE=0`.       |
| Agência ↔ clientes finais                  | sim    | sim       | Ver `agencias_vinculadas` no cliente e chips visuais nos cards.            |
| Endpoints IA (`/api/ia/*`)                 | sim    | sim       | Paridade completa via OpenRouter; fallback determinístico offline.         |
| Consolidadas (`/atividades-consolidadas`)  | sim    | não       | Fora do escopo do overhaul. Pode ser reaproveitada do `/crm` até go-live.  |
| Exports CSV (`/api/export/*`)              | sim    | não       | Idem. Frontend v3 gera CSV no navegador.                                   |
| Comunicação/WhatsApp (Wasender)            | sim    | não       | Módulo separado; não faz parte da migração inicial.                        |

### Como habilitar persistência real

- Em produção: `export USE_CRM_V3_STORE=0` (repositório Postgres).
- Em dev/testes: mantém-se o default (`CrmV3Store` em memória) para
  demonstração sem banco.

