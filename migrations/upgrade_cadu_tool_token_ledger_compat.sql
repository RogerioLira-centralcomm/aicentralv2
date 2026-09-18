-- Compatibilidade entre o histórico de créditos CADU já em produção e o
-- contrato transacional usado pelas ferramentas novas.
--
-- As colunas antigas continuam sendo preenchidas porque alimentam as views
-- administrativas existentes. As colunas canônicas permitem idempotência,
-- reserva e débito por lote para qualquer ferramenta interna.

ALTER TABLE cadu_credits_extras ADD COLUMN IF NOT EXISTS purchased_at TIMESTAMPTZ;
ALTER TABLE cadu_credits_extras ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

UPDATE cadu_credits_extras
   SET purchased_at = COALESCE(purchased_at, purchase_date),
       expires_at = COALESCE(expires_at, expiration_date)
 WHERE purchased_at IS NULL OR expires_at IS NULL;

ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(160);
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS ferramenta VARCHAR(80);
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS etapa VARCHAR(80);
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS total_tokens BIGINT;
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS tokens_cobrados BIGINT NOT NULL DEFAULT 0;
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS custo_adicional NUMERIC(18,8) NOT NULL DEFAULT 0;
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS moeda CHAR(3) NOT NULL DEFAULT 'USD';
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS status VARCHAR(24) NOT NULL DEFAULT 'charged';
ALTER TABLE cadu_tools_token_usage ADD COLUMN IF NOT EXISTS charged_at TIMESTAMPTZ;

UPDATE cadu_tools_token_usage
   SET ferramenta = COALESCE(ferramenta, tool_name),
       etapa = COALESCE(etapa, stage_name, 'execucao'),
       total_tokens = COALESCE(total_tokens, tokens_total),
       tokens_cobrados = CASE WHEN tokens_cobrados = 0 THEN COALESCE(tokens_total, 0) ELSE tokens_cobrados END,
       idempotency_key = COALESCE(idempotency_key, 'legacy:' || id::text),
       charged_at = COALESCE(charged_at, created_at)
 WHERE ferramenta IS NULL OR etapa IS NULL OR total_tokens IS NULL OR idempotency_key IS NULL;

ALTER TABLE cadu_tools_token_usage ALTER COLUMN idempotency_key SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_cadu_tools_token_usage_idempotency
    ON cadu_tools_token_usage (idempotency_key);
CREATE INDEX IF NOT EXISTS idx_cadu_tools_token_usage_studio_root
    ON cadu_tools_token_usage ((metadata->>'studio_root_session_id'))
    WHERE status = 'charged' AND metadata->>'studio_root_session_id' <> '';

CREATE OR REPLACE FUNCTION sync_cadu_tool_token_usage_compat()
RETURNS TRIGGER AS $$
BEGIN
    NEW.ferramenta := COALESCE(NEW.ferramenta, NEW.tool_name);
    NEW.etapa := COALESCE(NEW.etapa, NEW.stage_name, 'execucao');
    NEW.total_tokens := COALESCE(NEW.total_tokens, NEW.tokens_total, 0);
    NEW.tool_name := COALESCE(NEW.tool_name, NEW.ferramenta);
    NEW.stage_name := COALESCE(NEW.stage_name, NEW.etapa);
    NEW.tokens_total := COALESCE(NEW.tokens_total, NEW.total_tokens, 0);
    NEW.session_id := COALESCE(NEW.session_id, NEW.idempotency_key);
    NEW.idempotency_key := COALESCE(NEW.idempotency_key, NEW.session_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_cadu_tool_token_usage_compat ON cadu_tools_token_usage;
CREATE TRIGGER trg_sync_cadu_tool_token_usage_compat
BEFORE INSERT OR UPDATE ON cadu_tools_token_usage
FOR EACH ROW EXECUTE FUNCTION sync_cadu_tool_token_usage_compat();

CREATE OR REPLACE FUNCTION sync_cadu_credits_extras_compat()
RETURNS TRIGGER AS $$
BEGIN
    NEW.purchased_at := COALESCE(NEW.purchased_at, NEW.purchase_date, NOW());
    NEW.expires_at := COALESCE(NEW.expires_at, NEW.expiration_date);
    NEW.purchase_date := COALESCE(NEW.purchase_date, NEW.purchased_at);
    NEW.expiration_date := COALESCE(NEW.expiration_date, NEW.expires_at);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_cadu_credits_extras_compat ON cadu_credits_extras;
CREATE TRIGGER trg_sync_cadu_credits_extras_compat
BEFORE INSERT OR UPDATE ON cadu_credits_extras
FOR EACH ROW EXECUTE FUNCTION sync_cadu_credits_extras_compat();

CREATE INDEX IF NOT EXISTS idx_cadu_credits_extras_spend_compat
    ON cadu_credits_extras (id_cliente, status, expires_at, purchased_at)
 WHERE tokens_used < tokens_amount;
