ALTER TABLE tbl_contato_cliente
    ADD COLUMN IF NOT EXISTS cadu_avatar_badge VARCHAR(48);

COMMENT ON COLUMN tbl_contato_cliente.cadu_avatar_badge IS
    'Fallback visual escolhido para o avatar Cadu quando não há foto de perfil.';
