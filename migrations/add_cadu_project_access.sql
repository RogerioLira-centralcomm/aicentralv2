-- Project-scoped access is additive; tenant access remains the outer boundary.
CREATE TABLE IF NOT EXISTS cadu_family_project_visibility (
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'team', 'restricted')),
    updated_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (client_id, project_ref)
);

CREATE TABLE IF NOT EXISTS cadu_family_project_access (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'member', 'viewer')),
    source TEXT NOT NULL DEFAULT 'direct' CHECK (source IN ('owner', 'team', 'direct', 'inherited')),
    granted_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE (client_id, project_ref, user_id)
);

CREATE INDEX IF NOT EXISTS cadu_family_project_access_project
    ON cadu_family_project_access (client_id, project_ref, revoked_at);
