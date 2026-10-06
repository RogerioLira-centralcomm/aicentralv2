-- Origem do lote de tokens + ciclo da franquia mensal do plano.
-- Idempotente. NÃO registrado em ORDER.txt: aplicar só após Q1–Q8 em produção.
-- Usado por aicentralv2/cadu_plan_allowance.py (chave CADU_PLAN_ALLOWANCE_ENABLED).
ALTER TABLE cadu_credits_extras
    ADD COLUMN IF NOT EXISTS source VARCHAR(24) NOT NULL DEFAULT 'purchase', -- plan_allowance|purchase|bonus|adjustment
    ADD COLUMN IF NOT EXISTS label VARCHAR(160),
    ADD COLUMN IF NOT EXISTS client_plan_id BIGINT,
    ADD COLUMN IF NOT EXISTS cycle_start DATE,
    ADD COLUMN IF NOT EXISTS credit_request_id BIGINT;
-- Garante uma única franquia por cliente e ciclo (idempotência da liberação).
CREATE UNIQUE INDEX IF NOT EXISTS uq_cadu_credits_extras_allowance_cycle
    ON cadu_credits_extras (id_cliente, cycle_start) WHERE source = 'plan_allowance';

-- Reverso (manual):
-- DROP INDEX IF EXISTS uq_cadu_credits_extras_allowance_cycle;
-- ALTER TABLE cadu_credits_extras DROP COLUMN IF EXISTS source, DROP COLUMN IF EXISTS label,
--   DROP COLUMN IF EXISTS client_plan_id, DROP COLUMN IF EXISTS cycle_start, DROP COLUMN IF EXISTS credit_request_id;
