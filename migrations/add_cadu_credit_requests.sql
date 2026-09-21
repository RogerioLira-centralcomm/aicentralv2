CREATE TABLE IF NOT EXISTS cadu_credit_requests (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT NOT NULL,
    requested_by BIGINT,
    package_name VARCHAR(160) NOT NULL,
    tokens_amount BIGINT NOT NULL CHECK (tokens_amount > 0),
    price_brl NUMERIC(12,2) NOT NULL CHECK (price_brl >= 0),
    billing_mode VARCHAR(24) NOT NULL DEFAULT 'prepaid' CHECK (billing_mode IN ('prepaid','postpaid')),
    status VARCHAR(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    note TEXT,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_credit_requests_client ON cadu_credit_requests (id_cliente, created_at DESC);
ALTER TABLE cadu_credit_requests
    ADD COLUMN IF NOT EXISTS billing_mode VARCHAR(24) NOT NULL DEFAULT 'prepaid';
