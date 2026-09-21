-- Capacity included in the commercial plan, measured in bytes.
ALTER TABLE cadu_plan_definitions
    ADD COLUMN IF NOT EXISTS storage_bytes_limit BIGINT;

ALTER TABLE cadu_client_plans
    ADD COLUMN IF NOT EXISTS storage_bytes_limit BIGINT;

CREATE INDEX IF NOT EXISTS idx_cadu_client_plans_storage
    ON cadu_client_plans (id_cliente, storage_bytes_limit);
