-- Leads v3: registro do que o Apollo devolveu em cada chamada (busca, revelar, pedido de celular, webhook),
-- para diagnosticar contato que chega sem e-mail ou celular e saber o que pode ter cobrado crédito.
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_prospeccao.sql.
--   pago      a chamada pode cobrar crédito (people/match; webhook com credits_consumed).
--   resumo    contagens e flags (com e-mail, telefone sim/talvez, créditos do webhook).
--   resposta  o que interessa da resposta (a busca guarda só id, nome mascarado, cargo e flags).
CREATE TABLE IF NOT EXISTS cadu_apollo_chamadas (
    id BIGSERIAL PRIMARY KEY,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    endpoint VARCHAR(60) NOT NULL,
    id_lead INTEGER REFERENCES cadu_leads(id) ON DELETE SET NULL,
    id_contato INTEGER REFERENCES cadu_lead_contatos(id) ON DELETE SET NULL,
    http_status INTEGER,
    pago BOOLEAN NOT NULL DEFAULT FALSE,
    erro TEXT,
    pedido JSONB,
    resumo JSONB,
    resposta JSONB,
    usuario_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_apollo_chamadas_contato ON cadu_apollo_chamadas (id_contato, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_apollo_chamadas_lead ON cadu_apollo_chamadas (id_lead, criado_em DESC);

-- Reverso (manual):
-- DROP TABLE IF EXISTS cadu_apollo_chamadas;
