-- Restore the permanent internal test account after the original credit lots
-- expired. This is deliberately scoped to CENTRALCOMM (client 174), and the
-- entitlement key makes it safe to run more than once.

DO $$
DECLARE
    pro_plan_id BIGINT;
    entitlement_id BIGINT;
    lot_id BIGINT;
BEGIN
    SELECT id
      INTO pro_plan_id
      FROM cadu_plan_definitions
     WHERE plan_name = 'Pro' AND is_active = TRUE
     ORDER BY id
     LIMIT 1;

    IF pro_plan_id IS NULL THEN
        RAISE EXCEPTION 'A definição ativa do plano Pro não foi encontrada.';
    END IF;

    -- The account record said "pro" but referenced the Free definition. Keep
    -- its plan and credit limit aligned, with no artificial expiry for tests.
    UPDATE cadu_client_plans
       SET id_plan_definition = pro_plan_id,
           plan_type = 'pro',
           plan_status = 'active',
           tokens_monthly_limit = 2000000,
           max_users = 5,
           plan_start_date = NOW(),
           plan_end_date = NULL,
           valid_from = CURRENT_DATE,
           valid_until = NULL,
           updated_at = NOW()
     WHERE id_cliente = 174;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'O plano da conta de testes CENTRALCOMM (cliente 174) não foi encontrado.';
    END IF;

    INSERT INTO cadu_credit_entitlements
        (id_cliente, entitlement_key, tokens_amount, expires_at, status)
    VALUES (174, 'centralcomm_internal_test_2m', 2000000, NULL, 'granted')
    ON CONFLICT (id_cliente, entitlement_key)
    DO UPDATE SET tokens_amount = EXCLUDED.tokens_amount,
                  expires_at = NULL,
                  status = 'granted'
    RETURNING id, credit_lot_id INTO entitlement_id, lot_id;

    IF lot_id IS NULL THEN
        INSERT INTO cadu_credits_extras
            (id_cliente, tokens_amount, tokens_used, purchase_date, expiration_date,
             purchased_at, expires_at, status)
        VALUES (174, 2000000, 0, NOW(), NULL, NOW(), NULL, 'active')
        RETURNING id INTO lot_id;

        UPDATE cadu_credit_entitlements
           SET credit_lot_id = lot_id
         WHERE id = entitlement_id;
    ELSE
        -- Never reset tokens_used on a repeat run: it must preserve real test
        -- consumption. Only restore the permanent lot's active eligibility.
        UPDATE cadu_credits_extras
           SET status = 'active',
               expires_at = NULL,
               expiration_date = NULL
         WHERE id = lot_id AND id_cliente = 174;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'O lote interno % referenciado pela conta 174 não foi encontrado.', lot_id;
        END IF;
    END IF;
END;
$$;
