-- Site discovery is kept as evidence until a Reports user selects a page.
ALTER TABLE cadu_reports_flow_steps
    ADD COLUMN IF NOT EXISTS page_host VARCHAR(253),
    ADD COLUMN IF NOT EXISTS is_entry BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE cadu_reports_flow_events
    ADD COLUMN IF NOT EXISTS page_host VARCHAR(253);

ALTER TABLE cadu_reports_flow_events_test
    ADD COLUMN IF NOT EXISTS page_host VARCHAR(253);

CREATE UNIQUE INDEX IF NOT EXISTS cadu_reports_flow_single_entry_idx
    ON cadu_reports_flow_steps (tag_id)
    WHERE is_active=TRUE AND is_entry=TRUE;

CREATE TABLE IF NOT EXISTS cadu_reports_flow_discovery_runs (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    tag_id UUID NOT NULL REFERENCES cadu_reports_site_tags(id) ON DELETE CASCADE,
    root_url TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'completed'
        CHECK (status IN ('completed','partial','failed')),
    page_count INTEGER NOT NULL DEFAULT 0 CHECK (page_count >= 0),
    created_by BIGINT NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_discovery_runs_scope_idx
    ON cadu_reports_flow_discovery_runs (organization_id,client_id,tag_id,created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_reports_flow_discovered_pages (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cadu_reports_flow_discovery_runs(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    tag_id UUID NOT NULL REFERENCES cadu_reports_site_tags(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    page_host VARCHAR(253) NOT NULL,
    path_prefix VARCHAR(500) NOT NULL,
    title VARCHAR(500) NOT NULL DEFAULT '',
    suggested_role VARCHAR(20) NOT NULL DEFAULT 'intermediate'
        CHECK (suggested_role IN ('entry','intermediate','form','conversion')),
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    form_count SMALLINT NOT NULL DEFAULT 0 CHECK (form_count >= 0),
    form_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    selected_kind VARCHAR(20) CHECK (selected_kind IN ('page','form','conversion')),
    selected_as_entry BOOLEAN NOT NULL DEFAULT FALSE,
    step_id BIGINT REFERENCES cadu_reports_flow_steps(id) ON DELETE SET NULL,
    selected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_reports_flow_discovered_page_run_unique UNIQUE (run_id,page_host,path_prefix)
);
CREATE INDEX IF NOT EXISTS cadu_reports_flow_discovered_page_scope_idx
    ON cadu_reports_flow_discovered_pages (organization_id,client_id,tag_id,run_id);
