ALTER TABLE cadu_credit_requests
    ADD COLUMN IF NOT EXISTS credit_lot_id BIGINT REFERENCES cadu_credits_extras(id);

CREATE INDEX IF NOT EXISTS idx_cadu_credit_requests_lot
    ON cadu_credit_requests (credit_lot_id);
