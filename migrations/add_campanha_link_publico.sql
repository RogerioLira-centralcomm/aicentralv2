-- Link público da página de acompanhamento (nível campanha, dados do PI).

ALTER TABLE cadu_pi_campanha
    ADD COLUMN IF NOT EXISTS link_publico_token VARCHAR(64),
    ADD COLUMN IF NOT EXISTS link_publico_ativo BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS link_publico_expires_at TIMESTAMP WITHOUT TIME ZONE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pi_campanha_link_publico_token
    ON cadu_pi_campanha(link_publico_token)
    WHERE link_publico_token IS NOT NULL;
