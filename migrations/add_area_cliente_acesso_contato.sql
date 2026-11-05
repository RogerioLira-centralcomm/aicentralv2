-- Área do Cliente (clientes.centralcomm.media): liberação por contato,
-- marcada no CRM v3 (Cliente › Contatos). Quem liberou e quando fica na
-- auditoria (audit.registrar_acao_admin). Idempotente.

ALTER TABLE tbl_contato_cliente
    ADD COLUMN IF NOT EXISTS area_cliente_acesso BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_contato_cliente_area_cliente
    ON tbl_contato_cliente (pk_id_tbl_cliente)
    WHERE area_cliente_acesso;
