ALTER TABLE system_integration_credentials
    DROP CONSTRAINT IF EXISTS system_integration_credentials_provider_check;

ALTER TABLE system_integration_credentials
    ADD CONSTRAINT system_integration_credentials_provider_check
    CHECK (provider IN ('google_calendar', 'higgsfield', 'openrouter', 'd4sign'));

CREATE TABLE IF NOT EXISTS cx_documento (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    arquivo_nome VARCHAR(255),
    uuid_d4sign VARCHAR(64),
    uuid_safe VARCHAR(64),
    status VARCHAR(40) NOT NULL DEFAULT 'rascunho'
        CHECK (status IN (
            'rascunho', 'aguardando_assinaturas', 'parcialmente_assinado',
            'finalizado', 'cancelado', 'recusado'
        )),
    tipo_vinculo VARCHAR(20) NOT NULL DEFAULT 'interno'
        CHECK (tipo_vinculo IN (
            'cliente', 'agencia', 'parceiro', 'colaborador', 'interno', 'pi'
        )),
    id_vinculo INTEGER,
    vinculo_nome VARCHAR(255),
    criado_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cx_documento_signatario (
    id SERIAL PRIMARY KEY,
    id_documento INTEGER NOT NULL REFERENCES cx_documento(id) ON DELETE CASCADE,
    id_contato INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    email VARCHAR(255) NOT NULL,
    nome VARCHAR(255),
    key_signer VARCHAR(64),
    ordem SMALLINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente', 'assinado', 'recusado')),
    assinado_em TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS cx_documento_evento (
    id SERIAL PRIMARY KEY,
    id_documento INTEGER NOT NULL REFERENCES cx_documento(id) ON DELETE CASCADE,
    type_post VARCHAR(10),
    payload JSONB,
    recebido_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_doc_vinculo
    ON cx_documento (tipo_vinculo, id_vinculo);

CREATE INDEX IF NOT EXISTS idx_cx_doc_status
    ON cx_documento (status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_cx_doc_signatario_email
    ON cx_documento_signatario (lower(email), status);

CREATE INDEX IF NOT EXISTS idx_cx_doc_uuid
    ON cx_documento (uuid_d4sign);
