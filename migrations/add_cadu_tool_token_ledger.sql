CREATE TABLE IF NOT EXISTS cadu_credits_extras (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT NOT NULL,
    tokens_amount BIGINT NOT NULL CHECK (tokens_amount >= 0),
    tokens_used BIGINT NOT NULL DEFAULT 0 CHECK (tokens_used >= 0 AND tokens_used <= tokens_amount),
    purchased_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    status VARCHAR(24) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_credits_extras_spend
    ON cadu_credits_extras (id_cliente, status, expires_at, purchased_at)
    WHERE tokens_used < tokens_amount;

CREATE TABLE IF NOT EXISTS cadu_tools_token_usage (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key VARCHAR(160) NOT NULL UNIQUE,
    id_cliente BIGINT NOT NULL,
    id_contato_cliente BIGINT NOT NULL,
    ferramenta VARCHAR(80) NOT NULL,
    etapa VARCHAR(80) NOT NULL,
    modelo VARCHAR(160) NOT NULL,
    tokens_entrada BIGINT NOT NULL DEFAULT 0 CHECK (tokens_entrada >= 0),
    tokens_saida BIGINT NOT NULL DEFAULT 0 CHECK (tokens_saida >= 0),
    total_tokens BIGINT NOT NULL DEFAULT 0 CHECK (total_tokens >= 0),
    tokens_cobrados BIGINT NOT NULL DEFAULT 0 CHECK (tokens_cobrados >= 0),
    custo_interno NUMERIC(18,8) NOT NULL DEFAULT 0,
    custo_adicional NUMERIC(18,8) NOT NULL DEFAULT 0,
    moeda CHAR(3) NOT NULL DEFAULT 'USD',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    charged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_tools_token_usage_client_created
    ON cadu_tools_token_usage (id_cliente, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_tools_token_usage_user_created
    ON cadu_tools_token_usage (id_contato_cliente, created_at DESC);
