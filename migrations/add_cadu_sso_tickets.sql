-- One-time, short-lived handoff tickets between the PHP and Python applications.
-- Only the SHA-256 digest is persisted; the browser carries the raw token once.

CREATE TABLE IF NOT EXISTS cadu_sso_tickets (
    id BIGSERIAL PRIMARY KEY,
    token_hash CHAR(64) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    source_app VARCHAR(32) NOT NULL,
    target_url TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_sso_source_ck CHECK (source_app IN ('php', 'python'))
);

CREATE INDEX IF NOT EXISTS idx_cadu_sso_tickets_active
    ON cadu_sso_tickets (token_hash, expires_at)
    WHERE consumed_at IS NULL;

COMMENT ON TABLE cadu_sso_tickets IS
    'Tickets SSO de uso único entre cadu.centralcomm.media e os produtos Flask.';
