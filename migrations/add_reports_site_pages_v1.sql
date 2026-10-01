-- Catálogo de páginas por cliente e domínio, montado a partir do sitemap. Não pertence a um fluxo:
-- planos sem site também buscam páginas aqui. O nome vem do endereço; o título real é buscado aos poucos.
CREATE TABLE IF NOT EXISTS cadu_reports_site_pages (
    client_id BIGINT NOT NULL,
    host VARCHAR(253) NOT NULL,
    path VARCHAR(500) NOT NULL,
    name VARCHAR(200) NOT NULL,
    title VARCHAR(500),
    title_checked_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (client_id, host, path)
);
CREATE TABLE IF NOT EXISTS cadu_reports_site_catalogs (
    client_id BIGINT NOT NULL,
    host VARCHAR(253) NOT NULL,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    page_count INTEGER NOT NULL DEFAULT 0,
    truncated BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (client_id, host)
);
