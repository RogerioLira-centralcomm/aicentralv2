-- Kits IAB base por marca. Idempotente.

CREATE TABLE IF NOT EXISTS cx_plate_kits (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL
        REFERENCES cx_clients(id) ON DELETE CASCADE,
    name VARCHAR(180) NOT NULL,
    product VARCHAR(160) NOT NULL DEFAULT '',
    copy JSONB NOT NULL DEFAULT '{}'::jsonb,
    product_assets JSONB NOT NULL DEFAULT '{}'::jsonb,
    plates JSONB NOT NULL DEFAULT '[]'::jsonb,
    bindings JSONB NOT NULL DEFAULT '{}'::jsonb,
    passes JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_plate_kits_client
    ON cx_plate_kits(client_id, created_at DESC);
