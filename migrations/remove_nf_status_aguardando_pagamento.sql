-- Remove o status de NF "Aguardando pagamento" e realinha cadu_pi_financeiro.
-- Idempotente: pode ser executado mais de uma vez.

DO $$
DECLARE
    id_aguardando INTEGER;
    id_nf_emitida INTEGER;
BEGIN
    SELECT id INTO id_aguardando
    FROM cadu_pi_nota_fiscal_status
    WHERE lower(trim(descricao)) = 'aguardando pagamento'
    LIMIT 1;

    SELECT id INTO id_nf_emitida
    FROM cadu_pi_nota_fiscal_status
    WHERE lower(trim(descricao)) = 'nf emitida'
    LIMIT 1;

    IF id_aguardando IS NOT NULL AND id_nf_emitida IS NOT NULL THEN
        UPDATE cadu_pi_nota_fiscal
        SET status = id_nf_emitida
        WHERE status = id_aguardando;
    END IF;

    UPDATE cadu_pi_financeiro
    SET status_financeiro = 'nf_emitida'
    WHERE status_financeiro = 'aguardando_pagamento';

    IF id_aguardando IS NOT NULL THEN
        DELETE FROM cadu_pi_nota_fiscal_status
        WHERE id = id_aguardando;
    END IF;
END $$;

ALTER TABLE cadu_pi_financeiro
    DROP CONSTRAINT IF EXISTS cadu_pi_financeiro_status_financeiro_check;

ALTER TABLE cadu_pi_financeiro
    ADD CONSTRAINT cadu_pi_financeiro_status_financeiro_check
    CHECK (status_financeiro IN (
        'aguardando_comprovacao',
        'aguardando_assinatura',
        'pronto_nf',
        'nf_emitida',
        'encerrado',
        'bloqueado'
    ));
