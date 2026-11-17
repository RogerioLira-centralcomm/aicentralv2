-- Entrada de PI automatizada (CentralX, Comercial): fila de PDFs lidos por OCR, página de verificação e
-- ajustes com justificativa. Tela nova, ao lado da atual (/cadu_pi/novo); nada aqui altera cadu_pi.
-- Sem chave estrangeira para tabelas antigas: a produção diverge do esquema do repositório em tipos de id.
-- Idempotente.

CREATE TABLE IF NOT EXISTS pi_entrada (
    id BIGSERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL,
    origem VARCHAR(20) NOT NULL DEFAULT 'centralx',          -- centralx ou hub
    status VARCHAR(24) NOT NULL DEFAULT 'recebido',          -- recebido, lendo, lido, aprovado, rascunho, erro
    id_cliente_envio INTEGER,                                -- quem enviou pelo hub (tbl_cliente.id_cliente)
    id_contato_envio INTEGER,                                -- contato que enviou (tbl_contato_cliente.id_contato_cliente)
    id_usuario_criou INTEGER,                                -- executivo que arrastou o PDF no CentralX
    id_executivo INTEGER,                                    -- executivo responsável pela conta
    id_cliente_detectado INTEGER,
    id_agencia_detectada INTEGER,
    cotacao_id INTEGER,
    numero_pi VARCHAR(40),
    titulo VARCHAR(200),
    modelo VARCHAR(80),
    prompt_versao VARCHAR(40),
    metodo_leitura VARCHAR(12),                              -- texto ou ocr
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_saida INTEGER NOT NULL DEFAULT 0,
    confianca NUMERIC(4,3),
    json_extraido JSONB,                                     -- o que o modelo leu, sem edição
    json_revisado JSONB,                                     -- o que o executivo confirmou ou ajustou
    conferencias JSONB,
    rascunho JSONB,
    erro TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lido_em TIMESTAMPTZ,
    aprovado_em TIMESTAMPTZ,
    id_usuario_aprovou INTEGER,
    enviado_em TIMESTAMPTZ,                                  -- hub: quando o cliente enviou ao executivo
    mensagem_cliente TEXT                                    -- hub: recado do cliente ao executivo
);
-- Entradas criadas antes destas colunas (quem aplicou a primeira versão localmente).
ALTER TABLE pi_entrada ADD COLUMN IF NOT EXISTS enviado_em TIMESTAMPTZ;
ALTER TABLE pi_entrada ADD COLUMN IF NOT EXISTS mensagem_cliente TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS ux_pi_entrada_uuid ON pi_entrada (uuid);
CREATE INDEX IF NOT EXISTS ix_pi_entrada_hub ON pi_entrada (id_cliente_envio, criado_em DESC) WHERE origem = 'hub';
CREATE INDEX IF NOT EXISTS ix_pi_entrada_status ON pi_entrada (status, criado_em DESC);
CREATE INDEX IF NOT EXISTS ix_pi_entrada_executivo ON pi_entrada (id_executivo, status);
CREATE INDEX IF NOT EXISTS ix_pi_entrada_numero ON pi_entrada (numero_pi);

CREATE TABLE IF NOT EXISTS pi_entrada_arquivo (
    id BIGSERIAL PRIMARY KEY,
    id_entrada BIGINT NOT NULL REFERENCES pi_entrada(id) ON DELETE CASCADE,
    nome_original VARCHAR(255) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    tamanho_bytes BIGINT NOT NULL,
    paginas INTEGER,
    caminho VARCHAR(500) NOT NULL,                           -- fora de static/: servido por rota autenticada
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_pi_entrada_arquivo_entrada ON pi_entrada_arquivo (id_entrada);
CREATE INDEX IF NOT EXISTS ix_pi_entrada_arquivo_sha ON pi_entrada_arquivo (sha256);

CREATE TABLE IF NOT EXISTS pi_entrada_ajuste (
    id BIGSERIAL PRIMARY KEY,
    id_entrada BIGINT NOT NULL REFERENCES pi_entrada(id) ON DELETE CASCADE,
    campo VARCHAR(80) NOT NULL,
    tipo VARCHAR(10) NOT NULL DEFAULT 'ajuste',              -- ajuste (mudou o valor) ou aceite (manteve, mesmo divergente)
    valor_lido TEXT,
    valor_final TEXT,
    motivo VARCHAR(40) NOT NULL,
    justificativa TEXT NOT NULL,
    id_usuario INTEGER,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_pi_entrada_ajuste_entrada ON pi_entrada_ajuste (id_entrada, campo);

CREATE TABLE IF NOT EXISTS pi_entrada_log (
    id BIGSERIAL PRIMARY KEY,
    id_entrada BIGINT NOT NULL REFERENCES pi_entrada(id) ON DELETE CASCADE,
    etapa VARCHAR(40) NOT NULL,
    duracao_ms INTEGER,
    detalhe TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_pi_entrada_log_entrada ON pi_entrada_log (id_entrada, criado_em);
