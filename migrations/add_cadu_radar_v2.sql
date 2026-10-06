-- Radar v2: parâmetros do wizard, radares ativos (alertas agendados) e o vínculo do run com o radar que o disparou.
-- Aditivo e idempotente. Depende de add_cadu_radar.sql.

ALTER TABLE cadu_radar_runs ADD COLUMN IF NOT EXISTS params JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE cadu_radar_runs ADD COLUMN IF NOT EXISTS trigger VARCHAR(12) NOT NULL DEFAULT 'manual';
ALTER TABLE cadu_radar_runs ADD COLUMN IF NOT EXISTS watch_id UUID;

CREATE TABLE IF NOT EXISTS cadu_radar_watches (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL,
    brand_ref TEXT,
    project_ref TEXT,
    name VARCHAR(160) NOT NULL,
    focus TEXT,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    frequency SMALLINT NOT NULL DEFAULT 1,
    min_score SMALLINT NOT NULL DEFAULT 70,
    status VARCHAR(12) NOT NULL DEFAULT 'ativo',
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    last_run_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (frequency BETWEEN 1 AND 3),
    CHECK (min_score BETWEEN 0 AND 100),
    CHECK (status IN ('ativo', 'pausado', 'sem_credito'))
);

CREATE INDEX IF NOT EXISTS cadu_radar_watches_client_idx ON cadu_radar_watches (client_id, status);
CREATE INDEX IF NOT EXISTS cadu_radar_watches_due_idx ON cadu_radar_watches (next_run_at) WHERE status = 'ativo';
CREATE INDEX IF NOT EXISTS cadu_radar_runs_watch_idx ON cadu_radar_runs (watch_id, created_at DESC) WHERE watch_id IS NOT NULL;
