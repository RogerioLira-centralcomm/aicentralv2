-- Leads v3: cliente que volta para lead (pelo CRM v3) e lead que volta a ser cliente.
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_prospeccao.sql.
-- cliente_origem_id guarda de que cliente o lead veio; a reconversão reativa esse mesmo cadastro
-- em vez de criar outro. O cliente fica inativo (tbl_cliente.status = FALSE) enquanto é lead.
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS cliente_origem_id INTEGER;
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS voltou_de_cliente_em TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_cadu_leads_cliente_origem ON cadu_leads (cliente_origem_id) WHERE cliente_origem_id IS NOT NULL;
COMMENT ON COLUMN cadu_leads.cliente_origem_id IS 'tbl_cliente.id_cliente de onde o lead voltou (CRM v3 → Leads); sem FK porque tbl_cliente não é apagado';

-- Reverso (manual):
-- DROP INDEX IF EXISTS idx_cadu_leads_cliente_origem;
-- ALTER TABLE cadu_leads DROP COLUMN IF EXISTS cliente_origem_id, DROP COLUMN IF EXISTS voltou_de_cliente_em;
