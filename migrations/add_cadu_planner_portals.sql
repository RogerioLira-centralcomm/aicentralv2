CREATE TABLE IF NOT EXISTS cadu_planner_portals (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(180) NOT NULL,
    domain VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(80),
    description TEXT,
    audience_estimate VARCHAR(120),
    audience_period VARCHAR(80),
    audience_source_url TEXT,
    audience_checked_at TIMESTAMPTZ,
    public_attributes JSONB NOT NULL DEFAULT '[]'::jsonb,
    featured_rank SMALLINT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_crawled_at TIMESTAMPTZ,
    source_url TEXT,
    source_hash CHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (featured_rank IS NULL OR featured_rank BETWEEN 1 AND 200),
    CHECK (audience_estimate IS NULL OR (audience_source_url IS NOT NULL AND audience_checked_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS cadu_planner_portals_category_name_idx
    ON cadu_planner_portals (category, name) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS cadu_planner_portals_featured_idx
    ON cadu_planner_portals (featured_rank NULLS LAST) WHERE active = TRUE;

ALTER TABLE IF EXISTS cadu_planner_plan_items
    DROP CONSTRAINT IF EXISTS cadu_planner_plan_items_kind_check;
ALTER TABLE IF EXISTS cadu_planner_plan_items
    ADD CONSTRAINT cadu_planner_plan_items_kind_check
    CHECK (kind IN ('audiencias', 'canais', 'formatos', 'interativos', 'places', 'portais'));

ALTER TABLE IF EXISTS cadu_planner_selections
    DROP CONSTRAINT IF EXISTS chk_cadu_planner_selection_kind;
ALTER TABLE IF EXISTS cadu_planner_selections
    ADD CONSTRAINT chk_cadu_planner_selection_kind
    CHECK (kind IN ('audiencias', 'canais', 'formatos', 'interativos', 'places', 'portais'));
