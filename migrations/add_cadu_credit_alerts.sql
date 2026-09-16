CREATE TABLE IF NOT EXISTS cadu_credit_alerts (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT NOT NULL,
    alert_key VARCHAR(40) NOT NULL,
    available_tokens BIGINT NOT NULL,
    source_usage_id BIGINT REFERENCES cadu_tools_token_usage(id),
    notified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_cliente, alert_key)
);

CREATE INDEX IF NOT EXISTS idx_cadu_credit_alerts_client
    ON cadu_credit_alerts (id_cliente, notified_at DESC);
