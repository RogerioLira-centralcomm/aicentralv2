-- External references belong to a Workspace project even before a provider
-- is connected through OAuth. Existing installations may have a text project
-- identifier while new ones use UUID, therefore inherit the parent type.
DO $$
DECLARE project_id_type TEXT;
BEGIN
    SELECT format_type(a.atttypid, a.atttypmod)
      INTO project_id_type
      FROM pg_attribute a
      JOIN pg_class c ON c.oid = a.attrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relname = 'cadu_ci_projetos'
       AND a.attname = 'id' AND a.attnum > 0 AND NOT a.attisdropped;

    IF project_id_type IS NULL THEN
        RAISE EXCEPTION 'Tabela cadu_ci_projetos não encontrada';
    END IF;

    EXECUTE format($sql$
        CREATE TABLE IF NOT EXISTS cadu_ci_projeto_links (
            id UUID PRIMARY KEY,
            projeto_id %s NOT NULL REFERENCES cadu_ci_projetos(id) ON DELETE CASCADE,
            id_cliente INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
            criado_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
            provider VARCHAR(32) NOT NULL DEFAULT 'generic'
                CHECK (provider IN ('google_drive', 'clickup', 'trello', 'miro', 'generic')),
            url TEXT NOT NULL,
            titulo VARCHAR(180) NOT NULL,
            position SMALLINT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (projeto_id, url)
        )
    $sql$, project_id_type);
END $$;

CREATE INDEX IF NOT EXISTS cadu_ci_projeto_links_project_idx
    ON cadu_ci_projeto_links (id_cliente, projeto_id, position, created_at DESC);
