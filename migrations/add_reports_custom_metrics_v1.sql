-- Reports: catálogo de métricas personalizadas por cliente (criadas num relatório e salvas para reutilizar).
CREATE TABLE IF NOT EXISTS cadu_reports_custom_metrics (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    name VARCHAR(80) NOT NULL,
    definition VARCHAR(300) NOT NULL DEFAULT '',
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('formula', 'manual')),
    formula VARCHAR(200),
    unit VARCHAR(16) NOT NULL DEFAULT 'count',
    direction VARCHAR(8) NOT NULL DEFAULT 'higher' CHECK (direction IN ('higher', 'lower')),
    target NUMERIC(24,6),
    created_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS cadu_reports_custom_metrics_name_idx
    ON cadu_reports_custom_metrics (client_id, lower(name)) WHERE archived_at IS NULL;
