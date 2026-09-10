-- Integra clientes do CRM e corrige contratos do fluxo de campanhas criativas.

ALTER TABLE cx_clients DROP CONSTRAINT IF EXISTS uq_cx_clients_crm_client;
DROP INDEX IF EXISTS uq_cx_clients_crm_client;

ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS crm_client_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint constraint_row
          JOIN pg_attribute column_row
            ON column_row.attrelid = constraint_row.conrelid
           AND column_row.attnum = ANY(constraint_row.conkey)
         WHERE constraint_row.conrelid = 'cx_clients'::regclass
           AND constraint_row.confrelid = 'tbl_cliente'::regclass
           AND constraint_row.contype = 'f'
           AND column_row.attname = 'crm_client_id'
    ) THEN
        ALTER TABLE cx_clients
            ADD CONSTRAINT fk_cx_clients_crm_client
            FOREIGN KEY (crm_client_id)
            REFERENCES tbl_cliente(id_cliente)
            ON DELETE SET NULL;
    END IF;
END
$$;

ALTER TABLE cx_clients DROP CONSTRAINT IF EXISTS uq_cx_clients_crm_client;
DROP INDEX IF EXISTS uq_cx_clients_crm_client;
CREATE INDEX IF NOT EXISTS idx_cx_clients_crm_client
    ON cx_clients(crm_client_id)
    WHERE crm_client_id IS NOT NULL;

ALTER TABLE cx_generation_jobs
    DROP CONSTRAINT IF EXISTS chk_cx_generation_job_type;

ALTER TABLE cx_generation_jobs
    ADD CONSTRAINT chk_cx_generation_job_type
    CHECK (
        job_type IN (
            'prompt', 'script', 'image', 'mockup',
            'video_payload', 'display_motion_payload'
        )
    );
