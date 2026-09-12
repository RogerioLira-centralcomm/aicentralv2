-- Places: inventário comercial de aeroportos, shoppings e eventos.
-- Idempotente. Sem Alembic.

CREATE TABLE IF NOT EXISTS cx_places (
    id              BIGSERIAL PRIMARY KEY,
    slug            VARCHAR(80)  NOT NULL,
    preview_token   VARCHAR(64)  NOT NULL,
    place_type      VARCHAR(20)  NOT NULL,
    city            VARCHAR(8)   NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'draft',
    title           VARCHAR(160) NOT NULL,
    code            VARCHAR(16),
    operator        VARCHAR(160),
    subtitle        TEXT,
    payload         JSONB        NOT NULL DEFAULT '{}'::jsonb,
    published_at    TIMESTAMPTZ,
    created_by      INTEGER,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_cx_places_type
        CHECK (place_type IN ('aeroporto', 'shopping', 'evento')),
    CONSTRAINT chk_cx_places_city
        CHECK (city IN ('bh', 'sp', 'rj')),
    CONSTRAINT chk_cx_places_status
        CHECK (status IN ('draft', 'published', 'archived', 'mapping'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_cx_places_slug
    ON cx_places (slug);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cx_places_preview_token
    ON cx_places (preview_token);
CREATE INDEX IF NOT EXISTS idx_cx_places_city_type
    ON cx_places (city, place_type);
CREATE INDEX IF NOT EXISTS idx_cx_places_status
    ON cx_places (status);
CREATE INDEX IF NOT EXISTS idx_cx_places_payload
    ON cx_places USING GIN (payload);

CREATE TABLE IF NOT EXISTS cx_place_inquiries (
    id           BIGSERIAL PRIMARY KEY,
    place_id     BIGINT NOT NULL REFERENCES cx_places(id) ON DELETE CASCADE,
    name         VARCHAR(160) NOT NULL,
    company      VARCHAR(160),
    email        VARCHAR(200),
    phone        VARCHAR(40),
    message      TEXT,
    source_slug  VARCHAR(80)  NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cx_place_inquiries_place
    ON cx_place_inquiries (place_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cx_place_inquiries_slug
    ON cx_place_inquiries (source_slug);
