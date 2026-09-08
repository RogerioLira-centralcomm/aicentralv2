-- Inteligência reutilizável de marca para a Modelagem de Criativos.

ALTER TABLE cx_clients
    ADD COLUMN IF NOT EXISTS website_url TEXT,
    ADD COLUMN IF NOT EXISTS brand_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS analysis_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
