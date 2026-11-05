-- Link público de acompanhamento no nível do PI (agrupa as campanhas do PI).
-- Os tokens por campanha (cadu_pi_campanha.link_publico_token) seguem válidos
-- e passam a abrir a página do PI correspondente. Idempotente.

ALTER TABLE cadu_pi
    ADD COLUMN IF NOT EXISTS link_publico_token VARCHAR(64),
    ADD COLUMN IF NOT EXISTS link_publico_ativo BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS link_publico_expires_at TIMESTAMP WITHOUT TIME ZONE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pi_link_publico_token
    ON cadu_pi(link_publico_token)
    WHERE link_publico_token IS NOT NULL;
