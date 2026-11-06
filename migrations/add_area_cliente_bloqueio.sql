-- Área do Cliente aberta por padrão: todo contato ativo de cliente ativo que
-- entra no Cadu já acessa clientes.centralcomm.media. A equipe CentralComm só
-- bloqueia, por cliente inteiro (tbl_cliente) ou por contato, no CRM v3 e na
-- edição do cliente no CentralX. Quem bloqueou e quando fica na auditoria.
-- A coluna antiga area_cliente_acesso (liberação manual) deixa de ser lida.
-- Idempotente.

ALTER TABLE tbl_contato_cliente
    ADD COLUMN IF NOT EXISTS area_cliente_bloqueado BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE tbl_cliente
    ADD COLUMN IF NOT EXISTS area_cliente_bloqueada BOOLEAN NOT NULL DEFAULT FALSE;
