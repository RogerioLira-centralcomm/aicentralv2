-- Leads v3 (fase 0): esquema da prospecção, seguindo o fluxo
-- listar contatos → entender contatos da empresa → separar empresas → cadências.
-- Plano em docs/leads-v3-plano.md.
--
-- Aditivo e idempotente. As tabelas-base (cadu_leads, cadu_lead_contatos) nascem no
-- repositório do site e podem divergir dele; aqui só se assume que os ids são inteiros.
-- Não altera os CHECKs de status/fonte nem as views vw_leads_*, então os formulários do
-- site continuam gravando sem mudança. Toda coluna nova é opcional ou tem default.
-- Executivo (id_executivo) e cliente (id_cliente) seguem o padrão das tabelas-base:
-- inteiro sem chave estrangeira.

-- ─────────────────────────────────────────────────────
-- 1. Listar e entender contatos: dados por pessoa
-- ─────────────────────────────────────────────────────
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS papel VARCHAR(20);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS senioridade VARCHAR(20);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS influencia VARCHAR(20);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS origem_dado VARCHAR(20);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS origem_ref VARCHAR(255);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS enriquecido_em TIMESTAMP;
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS email_status VARCHAR(20);
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS tem_whatsapp BOOLEAN;
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS saiu_da_empresa BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lead_contatos_papel') THEN
        ALTER TABLE cadu_lead_contatos ADD CONSTRAINT chk_lead_contatos_papel CHECK (
            papel IS NULL OR papel IN ('marketing', 'midia', 'criacao', 'diretoria', 'compras', 'comercial', 'outro'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lead_contatos_senioridade') THEN
        ALTER TABLE cadu_lead_contatos ADD CONSTRAINT chk_lead_contatos_senioridade CHECK (
            senioridade IS NULL OR senioridade IN ('c_level', 'diretor', 'gerente', 'coordenador', 'analista', 'outro'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lead_contatos_influencia') THEN
        ALTER TABLE cadu_lead_contatos ADD CONSTRAINT chk_lead_contatos_influencia CHECK (
            influencia IS NULL OR influencia IN ('decisor', 'influenciador', 'usuario', 'bloqueador'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lead_contatos_origem_dado') THEN
        ALTER TABLE cadu_lead_contatos ADD CONSTRAINT chk_lead_contatos_origem_dado CHECK (
            origem_dado IS NULL OR origem_dado IN ('site', 'manual', 'import', 'apollo', 'pesquisa_web', 'outro'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lead_contatos_email_status') THEN
        ALTER TABLE cadu_lead_contatos ADD CONSTRAINT chk_lead_contatos_email_status CHECK (
            email_status IS NULL OR email_status IN ('nao_verificado', 'valido', 'arriscado', 'invalido'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_lead_contatos_papel ON cadu_lead_contatos (id_lead, papel);

COMMENT ON COLUMN cadu_lead_contatos.papel IS 'Área da pessoa no comitê de compra: marketing, midia, criacao, diretoria, compras, comercial, outro';
COMMENT ON COLUMN cadu_lead_contatos.influencia IS 'Peso na decisão: decisor, influenciador, usuario, bloqueador';
COMMENT ON COLUMN cadu_lead_contatos.origem_dado IS 'De onde veio o dado da pessoa (LGPD): site, manual, import, apollo, pesquisa_web, outro';
COMMENT ON COLUMN cadu_lead_contatos.origem_ref IS 'Referência na fonte (ex.: id da pessoa no Apollo)';

-- Pessoas encontradas por enriquecimento aguardam revisão do executivo antes de virar contato.
CREATE TABLE IF NOT EXISTS cadu_lead_contato_candidatos (
    id SERIAL PRIMARY KEY,
    id_lead INTEGER NOT NULL REFERENCES cadu_leads(id) ON DELETE CASCADE,
    provedor VARCHAR(30) NOT NULL,                 -- apollo | pesquisa_web | ...
    provedor_ref VARCHAR(255),
    nome VARCHAR(200) NOT NULL,
    cargo VARCHAR(200),
    papel_sugerido VARCHAR(20),
    senioridade_sugerida VARCHAR(20),
    email VARCHAR(255),
    email_status VARCHAR(20),
    telefone VARCHAR(50),
    linkedin_url VARCHAR(500),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    custo_creditos NUMERIC(10,2),
    status VARCHAR(20) NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente', 'aprovado', 'descartado')),
    id_contato INTEGER REFERENCES cadu_lead_contatos(id) ON DELETE SET NULL,
    buscado_por INTEGER,
    revisado_por INTEGER,
    revisado_em TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lead_candidatos_lead_status ON cadu_lead_contato_candidatos (id_lead, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_candidatos_provedor_ref
    ON cadu_lead_contato_candidatos (id_lead, provedor, provedor_ref) WHERE provedor_ref IS NOT NULL;

-- ─────────────────────────────────────────────────────
-- 2. Separar empresas
-- ─────────────────────────────────────────────────────
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS cnpj VARCHAR(18);
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS dominio VARCHAR(255);
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS grupo_economico VARCHAR(200);
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS prioridade_conta CHAR(1);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_leads_prioridade_conta') THEN
        ALTER TABLE cadu_leads ADD CONSTRAINT chk_leads_prioridade_conta CHECK (
            prioridade_conta IS NULL OR prioridade_conta IN ('A', 'B', 'C'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_leads_cnpj ON cadu_leads (cnpj) WHERE cnpj IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_dominio ON cadu_leads (lower(dominio)) WHERE dominio IS NOT NULL;

COMMENT ON COLUMN cadu_leads.dominio IS 'Domínio da empresa (sem www), usado para deduplicar e buscar pessoas';
COMMENT ON COLUMN cadu_leads.grupo_economico IS 'Grupo ou sistema (ex.: Unimed, Sicredi, Grupo Senhor do Bonfim)';

-- Golden Circle: contas-alvo de cada executivo no trimestre.
-- A conta pode ser um lead (captação) ou um cliente já na carteira (expansão).
CREATE TABLE IF NOT EXISTS cadu_golden_circle (
    id SERIAL PRIMARY KEY,
    id_executivo INTEGER NOT NULL,
    trimestre VARCHAR(7) NOT NULL CHECK (trimestre ~ '^[0-9]{4}-Q[1-4]$'),
    nome_conta VARCHAR(255) NOT NULL,
    id_lead INTEGER REFERENCES cadu_leads(id) ON DELETE SET NULL,
    id_cliente INTEGER,
    objetivo VARCHAR(20) NOT NULL DEFAULT 'captacao'
        CHECK (objetivo IN ('captacao', 'expansao')),
    meta TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'planejada'
        CHECK (status IN ('planejada', 'em_contato', 'reuniao', 'proposta', 'ganha', 'pausada', 'perdida')),
    ordem SMALLINT NOT NULL DEFAULT 0,
    criado_por INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_golden_circle_conta
    ON cadu_golden_circle (id_executivo, trimestre, lower(nome_conta));
CREATE INDEX IF NOT EXISTS idx_golden_circle_trimestre ON cadu_golden_circle (trimestre, id_executivo);
CREATE INDEX IF NOT EXISTS idx_golden_circle_lead ON cadu_golden_circle (id_lead) WHERE id_lead IS NOT NULL;

-- ─────────────────────────────────────────────────────
-- 3. Cadências de conexão
-- ─────────────────────────────────────────────────────
-- Opt-out global por canal (valor normalizado: e-mail em minúsculas, telefone só dígitos).
CREATE TABLE IF NOT EXISTS cadu_lead_optout (
    id SERIAL PRIMARY KEY,
    canal VARCHAR(20) NOT NULL CHECK (canal IN ('email', 'whatsapp', 'telefone', 'linkedin')),
    valor VARCHAR(255) NOT NULL,
    motivo VARCHAR(200),
    origem VARCHAR(30),                            -- link_descadastro | resposta | manual
    registrado_por INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (canal, valor)
);

-- Modelo de cadência. passos: [{"dia": 0, "canal": "email", "acao": "enviar", "template": "..."}, ...]
CREATE TABLE IF NOT EXISTS cadu_lead_cadencias (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    passos JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(passos) = 'array'),
    pausar_ao_responder BOOLEAN NOT NULL DEFAULT TRUE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Uma pessoa dentro de uma cadência.
CREATE TABLE IF NOT EXISTS cadu_lead_cadencia_inscricoes (
    id SERIAL PRIMARY KEY,
    id_cadencia INTEGER NOT NULL REFERENCES cadu_lead_cadencias(id) ON DELETE CASCADE,
    id_lead INTEGER NOT NULL REFERENCES cadu_leads(id) ON DELETE CASCADE,
    id_contato INTEGER NOT NULL REFERENCES cadu_lead_contatos(id) ON DELETE CASCADE,
    id_executivo INTEGER,
    passo_atual SMALLINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ativa'
        CHECK (status IN ('ativa', 'pausada', 'respondeu', 'concluida', 'cancelada', 'erro')),
    proxima_em TIMESTAMP,
    motivo_parada VARCHAR(200),
    inscrito_por INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Uma pessoa não fica duas vezes na mesma cadência em andamento.
CREATE UNIQUE INDEX IF NOT EXISTS uq_cadencia_inscricao_ativa
    ON cadu_lead_cadencia_inscricoes (id_cadencia, id_contato) WHERE status IN ('ativa', 'pausada');
CREATE INDEX IF NOT EXISTS idx_cadencia_inscricoes_fila
    ON cadu_lead_cadencia_inscricoes (proxima_em) WHERE status = 'ativa';
CREATE INDEX IF NOT EXISTS idx_cadencia_inscricoes_lead ON cadu_lead_cadencia_inscricoes (id_lead);

-- Eventos de mensagem (envio, entrega, abertura, resposta...) por pessoa, para timeline e métricas.
-- id_comunicacao aponta para cadu_lead_comunicacoes sem FK: aquela tabela é criada no boot do app.
CREATE TABLE IF NOT EXISTS cadu_lead_mensagem_eventos (
    id BIGSERIAL PRIMARY KEY,
    id_lead INTEGER NOT NULL REFERENCES cadu_leads(id) ON DELETE CASCADE,
    id_contato INTEGER REFERENCES cadu_lead_contatos(id) ON DELETE SET NULL,
    id_inscricao INTEGER REFERENCES cadu_lead_cadencia_inscricoes(id) ON DELETE SET NULL,
    id_comunicacao INTEGER,
    canal VARCHAR(20) NOT NULL CHECK (canal IN ('email', 'whatsapp', 'linkedin', 'telefone')),
    direcao VARCHAR(10) NOT NULL CHECK (direcao IN ('saida', 'entrada')),
    evento VARCHAR(20) NOT NULL
        CHECK (evento IN ('enviado', 'entregue', 'aberto', 'clicado', 'respondeu', 'bounce', 'falhou', 'optout', 'tarefa_feita')),
    provedor VARCHAR(30),
    provedor_message_id VARCHAR(255),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ocorreu_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mensagem_eventos_lead ON cadu_lead_mensagem_eventos (id_lead, ocorreu_em DESC);
CREATE INDEX IF NOT EXISTS idx_mensagem_eventos_contato ON cadu_lead_mensagem_eventos (id_contato, ocorreu_em DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mensagem_eventos_provedor
    ON cadu_lead_mensagem_eventos (provedor, provedor_message_id, evento) WHERE provedor_message_id IS NOT NULL;

-- updated_at automático nas tabelas novas.
CREATE OR REPLACE FUNCTION cadu_leads_v3_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_golden_circle_updated_at ON cadu_golden_circle;
CREATE TRIGGER trg_golden_circle_updated_at BEFORE UPDATE ON cadu_golden_circle
    FOR EACH ROW EXECUTE FUNCTION cadu_leads_v3_touch_updated_at();
DROP TRIGGER IF EXISTS trg_lead_cadencias_updated_at ON cadu_lead_cadencias;
CREATE TRIGGER trg_lead_cadencias_updated_at BEFORE UPDATE ON cadu_lead_cadencias
    FOR EACH ROW EXECUTE FUNCTION cadu_leads_v3_touch_updated_at();
DROP TRIGGER IF EXISTS trg_cadencia_inscricoes_updated_at ON cadu_lead_cadencia_inscricoes;
CREATE TRIGGER trg_cadencia_inscricoes_updated_at BEFORE UPDATE ON cadu_lead_cadencia_inscricoes
    FOR EACH ROW EXECUTE FUNCTION cadu_leads_v3_touch_updated_at();

-- Reverso (manual):
-- DROP TABLE IF EXISTS cadu_lead_mensagem_eventos, cadu_lead_cadencia_inscricoes, cadu_lead_cadencias,
--     cadu_lead_optout, cadu_golden_circle, cadu_lead_contato_candidatos;
-- DROP FUNCTION IF EXISTS cadu_leads_v3_touch_updated_at();
-- ALTER TABLE cadu_leads DROP CONSTRAINT IF EXISTS chk_leads_prioridade_conta,
--     DROP COLUMN IF EXISTS cnpj, DROP COLUMN IF EXISTS dominio,
--     DROP COLUMN IF EXISTS grupo_economico, DROP COLUMN IF EXISTS prioridade_conta;
-- ALTER TABLE cadu_lead_contatos DROP COLUMN IF EXISTS papel, DROP COLUMN IF EXISTS senioridade,
--     DROP COLUMN IF EXISTS influencia, DROP COLUMN IF EXISTS linkedin_url, DROP COLUMN IF EXISTS origem_dado,
--     DROP COLUMN IF EXISTS origem_ref, DROP COLUMN IF EXISTS enriquecido_em, DROP COLUMN IF EXISTS email_status,
--     DROP COLUMN IF EXISTS tem_whatsapp, DROP COLUMN IF EXISTS saiu_da_empresa;
