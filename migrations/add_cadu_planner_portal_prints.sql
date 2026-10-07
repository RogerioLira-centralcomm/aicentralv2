-- Prints reais da home dos portais (captura com data e fonte). Só prints 'aprovado' aparecem na vitrine. Aditivo e idempotente.
CREATE TABLE IF NOT EXISTS cadu_planner_portal_prints (
    id BIGSERIAL PRIMARY KEY,
    portal_id BIGINT NOT NULL REFERENCES cadu_planner_portals(id) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL DEFAULT 'home' CHECK (kind IN ('home', 'noticia', 'anuncio')),
    file_path TEXT NOT NULL,
    source_url TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(12) NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'aprovado', 'descartado')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    UNIQUE (portal_id, kind, file_path)
);
CREATE INDEX IF NOT EXISTS idx_cadu_planner_portal_prints_portal ON cadu_planner_portal_prints (portal_id, status, captured_at DESC);
