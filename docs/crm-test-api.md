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

- Cliente: `nome`, `tipo_label`, `perfil`, `categoria`, `prioridade`,
  `responsavel`, `seguindo`, `favorito`.
- Contato: `nome`, `email`, `cargo`, `telefone`, `telefone_secundario`,
  `principal`.
- Atividade: `titulo`, `descricao`, `data` (`YYYY-MM-DD`), `data_label`,
  `hora`, `prioridade`, `status`, `tipo`, `responsavel`.
- Objetivo: `texto`, `prazo`, `concluido`.
- Cotação: `titulo`, `valor`, `status`, `status_label`, `data`.
- Nota: `texto`, `autor`, `data` (`YYYY-MM-DD`).

Exportação de clientes é gerada em CSV no navegador e não possui endpoint.
