-- Registra a última alteração material da marca. A coluna é usada tanto pela
-- edição direta do Workspace quanto pelos patches confirmados via Cadu/MCP e
-- pela aprovação de uma auditoria.
ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE cx_clients
   SET updated_at = COALESCE(created_at, NOW())
 WHERE updated_at IS NULL;

ALTER TABLE cx_clients
    ALTER COLUMN updated_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET NOT NULL;

