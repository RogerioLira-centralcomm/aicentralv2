-- Leads v3: celular revelado pelo Apollo (assíncrono por webhook).
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_prospeccao.sql.
-- O pedido fica marcado como 'pedido' até o Apollo chamar o webhook com o número
-- ('encontrado') ou sem número ('sem_numero').
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS telefone_status VARCHAR(20);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS telefone_pedido_em TIMESTAMP;
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS apollo_person_id VARCHAR(64);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lead_contatos_telefone_status') THEN
        ALTER TABLE cadu_lead_contatos ADD CONSTRAINT chk_lead_contatos_telefone_status CHECK (
            telefone_status IS NULL OR telefone_status IN ('pedido', 'encontrado', 'sem_numero'));
    END IF;
END $$;

-- Reverso (manual):
-- ALTER TABLE cadu_lead_contatos DROP CONSTRAINT IF EXISTS chk_lead_contatos_telefone_status,
--     DROP COLUMN IF EXISTS telefone_status, DROP COLUMN IF EXISTS telefone_pedido_em, DROP COLUMN IF EXISTS apollo_person_id;
