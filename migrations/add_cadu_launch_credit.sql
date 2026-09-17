-- Benefício de entrada Cadu: concedido uma única vez por organização.
-- O saldo vive no mesmo ledger transacional usado por todas as ferramentas.

CREATE TABLE IF NOT EXISTS cadu_credit_entitlements (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT NOT NULL,
    entitlement_key VARCHAR(80) NOT NULL,
    tokens_amount BIGINT NOT NULL DEFAULT 0 CHECK (tokens_amount >= 0),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    status VARCHAR(24) NOT NULL DEFAULT 'granted',
    credit_lot_id BIGINT REFERENCES cadu_credits_extras(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_cliente, entitlement_key)
);

CREATE INDEX IF NOT EXISTS idx_cadu_credit_entitlements_client
    ON cadu_credit_entitlements (id_cliente, status);

CREATE OR REPLACE FUNCTION grant_cadu_launch_credit(p_client_id BIGINT)
RETURNS VOID AS $$
DECLARE
    entitlement_id BIGINT;
    lot_id BIGINT;
BEGIN
    -- Client 174 already has the internal test balance and is intentionally
    -- excluded from the public launch allowance.
    IF p_client_id = 174 THEN
        INSERT INTO cadu_credit_entitlements
            (id_cliente, entitlement_key, tokens_amount, expires_at, status)
        VALUES (p_client_id, 'cadu_launch_100k', 0, NOW() + INTERVAL '7 months', 'excluded_test')
        ON CONFLICT (id_cliente, entitlement_key) DO NOTHING;
        RETURN;
    END IF;

    INSERT INTO cadu_credit_entitlements
        (id_cliente, entitlement_key, tokens_amount, expires_at, status)
    VALUES (p_client_id, 'cadu_launch_100k', 100000, NOW() + INTERVAL '7 months', 'granted')
    ON CONFLICT (id_cliente, entitlement_key) DO NOTHING
    RETURNING id INTO entitlement_id;

    IF entitlement_id IS NULL THEN
        RETURN;
    END IF;

    INSERT INTO cadu_credits_extras
        (id_cliente, tokens_amount, tokens_used, purchase_date, expiration_date,
         purchased_at, expires_at, status)
    VALUES (p_client_id, 100000, 0, NOW(), NOW() + INTERVAL '7 months',
            NOW(), NOW() + INTERVAL '7 months', 'active')
    RETURNING id INTO lot_id;

    UPDATE cadu_credit_entitlements
       SET credit_lot_id = lot_id
     WHERE id = entitlement_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION grant_cadu_launch_credit_on_plan()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.plan_status = 'active'
       AND (TG_OP = 'INSERT' OR COALESCE(OLD.plan_status, '') <> 'active') THEN
        PERFORM grant_cadu_launch_credit(NEW.id_cliente);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_grant_cadu_launch_credit ON cadu_client_plans;
CREATE TRIGGER trg_grant_cadu_launch_credit
AFTER INSERT OR UPDATE OF plan_status ON cadu_client_plans
FOR EACH ROW EXECUTE FUNCTION grant_cadu_launch_credit_on_plan();

-- Backfill every active Cadu account now. The function is idempotent and the
-- entitlement key guarantees that neither re-running this migration nor a
-- future plan activation can grant the benefit twice.
DO $$
DECLARE
    record_client RECORD;
BEGIN
    FOR record_client IN
        SELECT DISTINCT id_cliente
          FROM cadu_client_plans
         WHERE plan_status = 'active'
    LOOP
        PERFORM grant_cadu_launch_credit(record_client.id_cliente);
    END LOOP;
END;
$$;
