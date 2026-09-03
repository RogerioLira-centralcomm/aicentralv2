# Contrato mock — Teste CRM

O frontend de `/teste-crm` usa somente rotas em memória sob `/teste-crm/api`.
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
