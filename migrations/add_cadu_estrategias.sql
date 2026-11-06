-- Estratégias de mídia: catálogo administrado no CentralX (Parâmetros > Estratégias)
-- e mostrado no Descobrir da Área do Cliente. Colunas para filtro e ordem; o resto
-- (canais com peso, fluxo, conversão, remarketing, lista de clientes, criativos,
-- indicadores, otimizações) fica em dados JSONB. Idempotente.

CREATE TABLE IF NOT EXISTS cadu_estrategias (
    id             SERIAL PRIMARY KEY,
    slug           VARCHAR(80)  NOT NULL UNIQUE,
    nome           VARCHAR(140) NOT NULL,
    objetivo       VARCHAR(40)  NOT NULL,
    resumo         TEXT         NOT NULL DEFAULT '',
    verba_minima   INTEGER      NOT NULL DEFAULT 10000,
    ativo          BOOLEAN      NOT NULL DEFAULT TRUE,
    ordem          INTEGER      NOT NULL DEFAULT 100,
    dados          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    criado_em      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    atualizado_em  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    atualizado_por INTEGER
);

CREATE INDEX IF NOT EXISTS idx_cadu_estrategias_ativo_ordem ON cadu_estrategias (ativo, ordem);

-- Benchmarks da estimativa de resultado (CPM/CPC/CTR por canal, conversão por destino),
-- editados em Parâmetros > Estratégias > Benchmarks. Sem linha, valem os padrões do código.
CREATE TABLE IF NOT EXISTS cadu_estrategias_parametros (
    chave          VARCHAR(40) PRIMARY KEY,
    valor          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_por INTEGER
);
