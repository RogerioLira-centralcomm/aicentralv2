-- Leads v3: dossiê de ganchos por empresa e preferências de escrita do executivo.
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_prospeccao.sql.
-- Gancho = um fato verificável (com fonte e data) que puxa conversa sobre mídia, marketing ou
-- comunicação. A pesquisa sugere; o executivo escolhe ou descarta. O uso com cada pessoa fica no
-- payload do evento 'tarefa_feita' (id_gancho), sem tabela própria.
CREATE TABLE IF NOT EXISTS cadu_lead_ganchos (
    id SERIAL PRIMARY KEY,
    id_lead INTEGER NOT NULL REFERENCES cadu_leads(id) ON DELETE CASCADE,
    etapa VARCHAR(10) NOT NULL DEFAULT 'topo' CHECK (etapa IN ('topo', 'meio')),
    tipo VARCHAR(20) NOT NULL DEFAULT 'setor'
        CHECK (tipo IN ('empresa', 'campanha', 'concorrente', 'setor', 'lideranca', 'tendencia')),
    fato TEXT NOT NULL,
    numero VARCHAR(120),
    angulo TEXT,
    fonte_url TEXT,
    fonte_nome VARCHAR(120),
    data_fato VARCHAR(20),
    status VARCHAR(12) NOT NULL DEFAULT 'sugerido' CHECK (status IN ('sugerido', 'escolhido', 'descartado')),
    origem VARCHAR(12) NOT NULL DEFAULT 'pesquisa' CHECK (origem IN ('pesquisa', 'manual')),
    criado_por INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lead_ganchos_lead ON cadu_lead_ganchos (id_lead, status, etapa);

-- Uma linha por executivo (id_usuario = session user_id). Sem FK: o id vem do login do ERP.
CREATE TABLE IF NOT EXISTS cadu_lead_preferencias (
    id_usuario INTEGER PRIMARY KEY,
    assinatura TEXT,
    dispositivo VARCHAR(10) NOT NULL DEFAULT 'nenhum' CHECK (dispositivo IN ('nenhum', 'iphone', 'galaxy')),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Reverso (manual):
-- DROP TABLE IF EXISTS cadu_lead_ganchos, cadu_lead_preferencias;
