# Índices propostos para o Workspace (não aplicados)

Origem: auditoria de consultas do back end do Workspace, 2026-10-06. **Nada aqui roda no deploy.**
Os arquivos de `migrations/` são executados pelo deploy; estes ficam fora de propósito, porque
`CREATE INDEX CONCURRENTLY` não roda dentro de transação e porque cada índice precisa de
`EXPLAIN (ANALYZE, BUFFERS)` num banco local com dados sintéticos antes de existir em produção.
Alguns podem já existir no banco (criados pelo PHP legado): confira com `\d tabela` antes.

## 1. Studio por projeto do Workspace (`routes.py`, consulta de `cx_studio_sessions` no detalhe do projeto)
A consulta filtra por `s.metadata->>'workspace_project_ref'` e hoje não filtra por cliente.
Correção de código associada: acrescentar `AND s.client_id = %s` (também reforça o isolamento entre clientes).

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cx_studio_sessions_client_workspace_project
    ON cx_studio_sessions (client_id, (metadata->>'workspace_project_ref'));
```

## 2. Artefatos e memórias por cliente + projeto
Os índices atuais começam por `organization_id`, mas as consultas filtram só por `client_id` e `project_ref`.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workspace_artifacts_client_project
    ON cadu_workspace_artifacts (client_id, project_ref, updated_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_working_memories_client_project
    ON cadu_working_memories (client_id, project_ref, updated_at DESC);
```
Confirme os nomes reais das tabelas em `migrations/` (os índices existentes se chamam
`cadu_workspace_artifacts_scope` e `cadu_working_memories_scope`).

## Como validar cada um
1. Banco local com volume sintético (milhares de linhas por cliente, vários clientes).
2. `EXPLAIN (ANALYZE, BUFFERS)` da consulta antes e depois; esperado: `Seq Scan` vira `Index Scan`.
3. Só então escrever a migração em `migrations/` e registrá-la na ordem de deploy.
