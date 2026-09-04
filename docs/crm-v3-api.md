# Contrato de API — CRM v3

O frontend de `/crm-v3` usa rotas sob `/crm-v3/api`. O padrão é o
repositório Postgres; o store em memória é habilitado explicitamente para
testes com `USE_CRM_V3_STORE=mock`.

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
- `POST /clientes/:cliente_id/atividades/sequencia`
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

## Copiloto comercial contextual

- `POST /api/ia/gerar-roteiro` — cria roteiro de execução separado da
  comunicação. Retorna `texto`, `motivo`, `contexto_utilizado`, `source`
  e, quando a migration está aplicada, `history_id`.
- `POST /api/ia/melhorar-texto` — revisão real do texto existente; não gera
  roteiro quando o texto está vazio.
- `POST /api/ia/sugerir-atividade` — sugere próxima atividade a partir do
  contexto comercial. Retorna recomendação única, motivo e ação sugerida.
- `POST /api/ia/touchpoints` — devolve uma sequência editável. A persistência
  deve ser feita em uma única chamada a
  `POST /clientes/:cliente_id/atividades/sequencia` com `{"itens":[...]}`.
- `POST /api/ia/gerar-comunicacao` — cria e-mail ou WhatsApp separado do
  roteiro. Espera `cliente_id`, `contato_id`, `objetivo`, `tipo` e `tamanho`.
- `POST /api/ia/sugerir-objetivos` — devolve objetos com `texto`,
  `prazo_dias` e `motivo` para preview e seleção.
- `POST /api/ia/extrair-contatos` — extrai contatos estruturados a partir de
  texto livre no mesmo schema do OCR (`nome`, `email`, `telefone`,
  `telefone2`, `cargo`).
- `GET /api/clientes/:cliente_id/ia/historico` — lista saídas persistidas.
- `PATCH /api/ia/historico/:id/aplicar` — marca uma sugestão como aplicada.

Todos usam OpenRouter (Gemini 2.5 Flash) quando `OPENROUTER_API_KEY` está
disponível. Caso contrário, respondem com um fallback determinístico e
`source: "fallback"` no payload. Falhas do provider são registradas no log.
Os prompts recebem contexto minimizado por perfil e não recebem CNPJ,
telefone, e-mail, listas completas ou valores exatos desnecessários.

### Migration

Aplicar `migrations/create_crm_copilot_history_sequences.sql` para persistir
histórico de IA e vínculos das sequências. Sem ela, o CRM continua funcional:
as sequências permanecem atômicas e o histórico fica apenas na sessão.

## Paridade com o CRM real (`/crm`)

| Recurso                                    | `/crm` | `/crm-v3` | Observação                                                                 |
|--------------------------------------------|:------:|:---------:|----------------------------------------------------------------------------|
| Listagem/CRUD de clientes                  | sim    | sim       | Estruturas idênticas nas respostas.                                        |
| Contatos                                   | sim    | sim       | Import via IA e por texto ambos suportados.                                |
| Atividades                                 | sim    | sim       | Fluxo com drawer + painel IA integrado no v3.                              |
| Objetivos                                  | sim    | sim       | Marcação de conquista via PATCH.                                           |
| Cotações                                   | sim    | sim       | Filtros de status normalizados.                                            |
| Notas / histórico                          | sim    | sim       | Notas persistem via `crm_v3_repository` (default: banco real).             |
| Agência ↔ clientes finais                  | sim    | sim       | Ver `agencias_vinculadas` no cliente e chips visuais nos cards.            |
| Endpoints IA (`/api/ia/*`)                 | sim    | sim       | Paridade completa via OpenRouter; fallback determinístico offline.         |
| Consolidadas (`/atividades-consolidadas`)  | sim    | não       | Fora do escopo do overhaul. Pode ser reaproveitada do `/crm` até go-live.  |
| Exports CSV (`/api/export/*`)              | sim    | não       | Idem. Frontend v3 gera CSV no navegador.                                   |
| Comunicação/WhatsApp (Wasender)            | sim    | não       | Módulo separado; não faz parte da migração inicial.                        |

### Feature flag `USE_CRM_V3_STORE`

O default é **banco real** (repositório Postgres via `db.py`). Se a conexão
falhar, a API responde 503; dados fictícios nunca substituem a base
silenciosamente.

- Produção: **não seta nada** — usa banco por default.
- Forçar mock para demo/teste: `export USE_CRM_V3_STORE=mock`
  (aceita também `memory`, `in-memory`, `1`, `true`, `yes`).
- Forçar banco (explícito): `export USE_CRM_V3_STORE=real`
  (aceita também `db`, `0`, `false` ou qualquer valor não listado
  acima).

