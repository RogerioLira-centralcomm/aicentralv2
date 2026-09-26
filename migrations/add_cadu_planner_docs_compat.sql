-- Compatibilidade idempotente do Smart Docs PHP para o Planner Python.
-- Preserva todas as linhas e identificadores já existentes.
CREATE TABLE IF NOT EXISTS cadu_artifacts (
    id BIGSERIAL PRIMARY KEY,
    id_cliente INTEGER NOT NULL,
    id_contato_cliente INTEGER,
    projeto_id UUID,
    titulo VARCHAR(255) NOT NULL,
    tipo VARCHAR(40) NOT NULL DEFAULT 'documento',
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    conteudo_html TEXT NOT NULL DEFAULT '',
    template_id INTEGER,
    branding_id INTEGER,
    share_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    share_token VARCHAR(128),
    export_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    allow_download BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE cadu_artifacts ADD COLUMN IF NOT EXISTS template_id INTEGER;
ALTER TABLE cadu_artifacts ADD COLUMN IF NOT EXISTS projeto_id UUID;
ALTER TABLE cadu_artifacts ADD COLUMN IF NOT EXISTS branding_id INTEGER;
ALTER TABLE cadu_artifacts ADD COLUMN IF NOT EXISTS share_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE cadu_artifacts ADD COLUMN IF NOT EXISTS share_token VARCHAR(128);
ALTER TABLE cadu_artifacts ADD COLUMN IF NOT EXISTS export_config JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE cadu_artifacts ADD COLUMN IF NOT EXISTS allow_download BOOLEAN NOT NULL DEFAULT FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS ux_cadu_artifacts_share_token ON cadu_artifacts (share_token) WHERE share_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cadu_artifacts_client_recent ON cadu_artifacts (id_cliente, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_artifacts_project_recent ON cadu_artifacts (projeto_id, id_cliente, updated_at DESC)
    WHERE projeto_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cadu_docs_templates (
    id BIGSERIAL PRIMARY KEY, id_cliente INTEGER, slug VARCHAR(120) NOT NULL,
    nome VARCHAR(255) NOT NULL, descricao TEXT, categoria VARCHAR(80), icone VARCHAR(80), cor_tema VARCHAR(32),
    conteudo_html_padrao TEXT NOT NULL DEFAULT '', is_system BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE, ordem INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cadu_docs_templates_available ON cadu_docs_templates (id_cliente, ativo, ordem);
CREATE TABLE IF NOT EXISTS cadu_docs_branding (
    id BIGSERIAL PRIMARY KEY, id_cliente INTEGER NOT NULL, nome VARCHAR(255) NOT NULL,
    logo_url TEXT, cor_primaria VARCHAR(16), cor_secundaria VARCHAR(16), fonte_titulo VARCHAR(120), fonte_texto VARCHAR(120),
    is_default BOOLEAN NOT NULL DEFAULT FALSE, ativo BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cadu_docs_client_images (
    id BIGSERIAL PRIMARY KEY, id_cliente INTEGER NOT NULL, id_contato_cliente INTEGER, source VARCHAR(20) NOT NULL DEFAULT 'upload',
    file_path TEXT NOT NULL, title VARCHAR(255), mime VARCHAR(64), file_bytes BIGINT, ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cadu_docs_design_pages (
    id BIGSERIAL PRIMARY KEY, id_cliente INTEGER NOT NULL, id_contato_cliente INTEGER, tipo VARCHAR(20) NOT NULL,
    nome VARCHAR(255) NOT NULL DEFAULT 'Sem título', conteudo_html TEXT NOT NULL, orientation VARCHAR(20) NOT NULL DEFAULT 'portrait',
    meta JSONB NOT NULL DEFAULT '{}'::jsonb, ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Referências escolhidas para um plano em construção. O snapshot é somente
-- contexto de histórico; os catálogos continuam nas tabelas cadu_* e cx_places.
CREATE TABLE IF NOT EXISTS cadu_planner_selections (
    id BIGSERIAL PRIMARY KEY, client_id INTEGER NOT NULL, actor_id INTEGER NOT NULL,
    kind VARCHAR(20) NOT NULL, resource_id VARCHAR(128) NOT NULL, snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cadu_planner_selection_kind CHECK (kind IN ('audiencias','canais','formatos','interativos','places','portais')),
    CONSTRAINT ux_cadu_planner_selection UNIQUE (client_id, actor_id, kind, resource_id)
);
CREATE INDEX IF NOT EXISTS idx_cadu_planner_selections_actor ON cadu_planner_selections (client_id, actor_id, created_at DESC);
