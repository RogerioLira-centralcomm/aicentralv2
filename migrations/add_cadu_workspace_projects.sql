-- Native Workspace dossiers. Additive: existing Cadu/CI records remain intact.
CREATE TABLE IF NOT EXISTS cadu_ci_projetos (
    id UUID PRIMARY KEY,
    id_cliente BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    criado_por BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente),
    nome VARCHAR(150) NOT NULL,
    descricao TEXT,
    instrucoes TEXT,
    tipo VARCHAR(40) NOT NULL DEFAULT 'projeto',
    cor VARCHAR(16),
    status VARCHAR(24) NOT NULL DEFAULT 'ativo',
    tom_de_voz TEXT,
    publico TEXT,
    posicionamento TEXT,
    total_arquivos INTEGER NOT NULL DEFAULT 0,
    total_conversas INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_ci_projetos_client_status_updated
    ON cadu_ci_projetos (id_cliente, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS cadu_ci_projeto_arquivos (
    id BIGSERIAL PRIMARY KEY,
    projeto_id UUID NOT NULL REFERENCES cadu_ci_projetos(id) ON DELETE CASCADE,
    id_cliente BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    criado_por BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente),
    nome_arquivo VARCHAR(220) NOT NULL,
    mime VARCHAR(160),
    tamanho BIGINT NOT NULL DEFAULT 0,
    storage_path TEXT NOT NULL,
    doc_form VARCHAR(40),
    indexing_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    word_count INTEGER NOT NULL DEFAULT 0,
    tokens INTEGER NOT NULL DEFAULT 0,
    erro_msg TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_ci_project_files_owner
    ON cadu_ci_projeto_arquivos (projeto_id, id_cliente, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_ci_chunks (
    id BIGSERIAL PRIMARY KEY,
    projeto_id UUID NOT NULL REFERENCES cadu_ci_projetos(id) ON DELETE CASCADE,
    id_cliente BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    arquivo_id BIGINT REFERENCES cadu_ci_projeto_arquivos(id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL DEFAULT 0,
    titulo VARCHAR(220),
    conteudo TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding_norm DOUBLE PRECISION NOT NULL DEFAULT 0,
    dim INTEGER NOT NULL DEFAULT 0,
    modelo VARCHAR(120),
    tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_ci_chunks_project_file
    ON cadu_ci_chunks (projeto_id, arquivo_id, ordem);
