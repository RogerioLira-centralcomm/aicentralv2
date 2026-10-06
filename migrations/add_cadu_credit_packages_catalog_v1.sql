-- Catálogo ÚNICO de pacotes de tokens extras (decisão do dono, 2026-10-06).
-- Idempotente. NÃO registrado em ORDER.txt: aplicar só após Q1–Q8 em produção.
-- Atenção: creative_media/studio_sessions.py usa o pacote de menor preço/token
-- para precificar o Studio; conferir as linhas existentes antes do seed.
CREATE TABLE IF NOT EXISTS cadu_credit_packages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0),
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    description VARCHAR(240),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE cadu_credit_packages
    ADD COLUMN IF NOT EXISTS slug VARCHAR(40),
    ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'tokens',      -- tokens | storage
    ADD COLUMN IF NOT EXISTS storage_gb NUMERIC(10,2),                         -- só kind='storage'
    ADD COLUMN IF NOT EXISTS validity_months INTEGER;                          -- NULL = não expira
CREATE UNIQUE INDEX IF NOT EXISTS uq_cadu_credit_packages_slug
    ON cadu_credit_packages (slug) WHERE slug IS NOT NULL;

INSERT INTO cadu_credit_packages (slug, kind, name, credits, price, description, display_order, validity_months)
VALUES
  ('extra-essencial', 'tokens', 'Extra Essencial', 100000, 49.00, 'Reforço pontual para uma operação em andamento.', 10, NULL),
  ('extra-equipe',    'tokens', 'Extra Equipe',    500000, 179.00, 'Mais margem para planejamento, auditoria e produção.', 20, NULL),
  ('extra-agencia',   'tokens', 'Extra Agência',  1000000, 299.00, 'Volume para múltiplos projetos e clientes.', 30, NULL)
ON CONFLICT (slug) WHERE slug IS NOT NULL DO NOTHING;
-- Pacotes de armazenamento (Vultr): inserir com kind='storage', storage_gb e price
-- quando o dono definir os valores. credits deve ser > 0 pelo CHECK legado: use 1.

-- Reverso (manual):
-- DROP INDEX IF EXISTS uq_cadu_credit_packages_slug;
-- ALTER TABLE cadu_credit_packages DROP COLUMN IF EXISTS slug, DROP COLUMN IF EXISTS kind,
--   DROP COLUMN IF EXISTS storage_gb, DROP COLUMN IF EXISTS validity_months;
