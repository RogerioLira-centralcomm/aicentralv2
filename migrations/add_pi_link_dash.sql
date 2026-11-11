-- Dashboard Looker Studio no nível do PI (lista de campanhas na página pública).
-- Idempotente.

ALTER TABLE cadu_pi
    ADD COLUMN IF NOT EXISTS link_dash TEXT,
    ADD COLUMN IF NOT EXISTS link_dash_incorporar BOOLEAN NOT NULL DEFAULT TRUE;
