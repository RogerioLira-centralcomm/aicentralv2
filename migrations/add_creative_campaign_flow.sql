-- Integra clientes do CRM e corrige contratos do fluxo de campanhas criativas.

ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS crm_client_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'fk_cx_clients_crm_client'
           AND conrelid = 'cx_clients'::regclass
    ) THEN
        ALTER TABLE cx_clients
            ADD CONSTRAINT fk_cx_clients_crm_client
            FOREIGN KEY (crm_client_id)
            REFERENCES tbl_cliente(id_cliente)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_clients_crm_client
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
