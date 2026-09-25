-- Versioned Market Intelligence workflow profiles and bounded research jobs.
ALTER TABLE cadu_agent_long_jobs
    ADD COLUMN IF NOT EXISTS brand_ref TEXT,
    ADD COLUMN IF NOT EXISTS mode TEXT,
    ADD COLUMN IF NOT EXISTS workflow_config JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE cadu_agent_long_jobs
    DROP CONSTRAINT IF EXISTS cadu_agent_long_jobs_source_target_check;
ALTER TABLE cadu_agent_long_jobs
    ADD CONSTRAINT cadu_agent_long_jobs_source_target_check CHECK (source_target BETWEEN 0 AND 150);

ALTER TABLE cadu_agent_long_jobs
    DROP CONSTRAINT IF EXISTS cadu_agent_long_jobs_kind_check;
ALTER TABLE cadu_agent_long_jobs
    ADD CONSTRAINT cadu_agent_long_jobs_kind_check CHECK (
        kind IN ('deep_research','long_document','multi_source_analysis','artifact_revision','market_intelligence')
    );

ALTER TABLE cadu_agent_long_job_units
    DROP CONSTRAINT IF EXISTS cadu_agent_long_job_units_kind_check;
ALTER TABLE cadu_agent_long_job_units
    ADD CONSTRAINT cadu_agent_long_job_units_kind_check CHECK (
        kind IN ('discover','extract','classify','summarize','synthesize','compose','review','render',
                 'plan','gap_analysis','followup_search','analyze','critic','evidence_check')
    );

CREATE TABLE IF NOT EXISTS cadu_market_intelligence_profiles (
    client_id INTEGER PRIMARY KEY REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO cadu_chat_plugins (id, kind, name, category, sort_order, selectable)
VALUES ('market-intelligence', 'plugin', 'Market Intelligence', 'Pesquisa', 95, TRUE)
ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, category=EXCLUDED.category,
    sort_order=EXCLUDED.sort_order, selectable=TRUE, enabled=TRUE, updated_at=NOW();

UPDATE cadu_chat_plugin_versions SET is_current=FALSE
WHERE plugin_id='market-intelligence' AND is_current;

INSERT INTO cadu_chat_plugin_versions
    (plugin_id, version, maturity, description, manifest, changelog, is_current)
VALUES (
    'market-intelligence', '1.0.0', 'active',
    'Pesquisa de mercado rápida, profunda ou configurada pela metodologia do cliente.',
    '{"triggers":["/market-intelligence"],"internal_tools":["web.search","web.read","brands.get_context","workspace.get_project_context"],"context":["conversation","selected brand","selected project"],"external_connectors":["firecrawl","openrouter"],"inputs":["objective","mode","client methodology"],"outputs":["quick scan","research report","evidence and source index","editable artifact"],"workflows":["quick","deep","custom"],"known_gaps":["Custom sources require an enabled connector and explicit tenant configuration"]}'::jsonb,
    'Plugin de referência com três modalidades, fontes rastreáveis e política de modelos por etapa.', TRUE
)
ON CONFLICT (plugin_id, version) DO UPDATE SET
    is_current=TRUE, maturity=EXCLUDED.maturity, description=EXCLUDED.description,
    manifest=EXCLUDED.manifest, changelog=EXCLUDED.changelog;
