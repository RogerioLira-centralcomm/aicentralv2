-- Briefing para cotação (hub de mídia, F6): modo do briefing, prazo de resposta de 24 h, arquivos anexados e leitura da IA,
-- mais a tabela de rascunho da cotação (os arquivos são lidos antes de o briefing existir; só o envio cria a linha em
-- cadu_briefings, assim rascunho nenhum aparece nas listas do CentralX). Sem chave estrangeira. Idempotente.

ALTER TABLE cadu_briefings ADD COLUMN IF NOT EXISTS modo VARCHAR(20) NOT NULL DEFAULT 'planejamento';   -- cotacao, pi_antigo, planejamento
ALTER TABLE cadu_briefings ADD COLUMN IF NOT EXISTS prazo_resposta_em TIMESTAMPTZ;
ALTER TABLE cadu_briefings ADD COLUMN IF NOT EXISTS respondido_em TIMESTAMPTZ;
ALTER TABLE cadu_briefings ADD COLUMN IF NOT EXISTS arquivos JSONB;
ALTER TABLE cadu_briefings ADD COLUMN IF NOT EXISTS leitura_ia JSONB;
ALTER TABLE cadu_briefings ADD COLUMN IF NOT EXISTS pi_origem_id INTEGER;
ALTER TABLE cadu_briefings ADD COLUMN IF NOT EXISTS lembretes JSONB;
CREATE INDEX IF NOT EXISTS ix_cadu_briefings_prazo ON cadu_briefings (prazo_resposta_em) WHERE prazo_resposta_em IS NOT NULL AND respondido_em IS NULL;

CREATE TABLE IF NOT EXISTS hub_briefing_cotacao (
    id BIGSERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL,
    id_cliente INTEGER NOT NULL,
    id_contato INTEGER,
    status VARCHAR(16) NOT NULL DEFAULT 'recebido',          -- recebido, lendo, lido, erro, enviado
    arquivos JSONB NOT NULL DEFAULT '[]'::jsonb,             -- [{nome, sha256, tamanho, caminho, tipo}]
    leitura JSONB,                                           -- o que o modelo entendeu (campos do briefing + o que faltou)
    erro TEXT,
    modelo VARCHAR(80),
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_saida INTEGER NOT NULL DEFAULT 0,
    briefing_id INTEGER,                                     -- preenchido no envio
    prazo_resposta_em TIMESTAMPTZ,                           -- prazo prometido ao cliente no envio
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE hub_briefing_cotacao ADD COLUMN IF NOT EXISTS prazo_resposta_em TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS ux_hub_briefing_cotacao_uuid ON hub_briefing_cotacao (uuid);
CREATE INDEX IF NOT EXISTS ix_hub_briefing_cotacao_cliente ON hub_briefing_cotacao (id_cliente, criado_em DESC);
