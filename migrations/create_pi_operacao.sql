-- Operação do PI. Pode ser executada repetidamente, sem Alembic.

ALTER TABLE cadu_pi_campanha
    ADD COLUMN IF NOT EXISTS id_responsavel_operacao INTEGER;

UPDATE cadu_pi_campanha campanha
   SET id_responsavel_operacao = pi.id_resp_comercial
  FROM cadu_pi pi
 WHERE campanha.id_pi = pi.id_pi
   AND campanha.id_responsavel_operacao IS NULL
   AND pi.id_resp_comercial IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'fk_pi_campanha_responsavel_operacao'
           AND conrelid = 'cadu_pi_campanha'::regclass
    ) THEN
        ALTER TABLE cadu_pi_campanha
            ADD CONSTRAINT fk_pi_campanha_responsavel_operacao
            FOREIGN KEY (id_responsavel_operacao)
            REFERENCES tbl_contato_cliente(id_contato_cliente)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_pi_campanha_responsavel_operacao
    ON cadu_pi_campanha(id_responsavel_operacao);

CREATE TABLE IF NOT EXISTS cadu_pi_operacao_etapa (
    id BIGSERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    etapa VARCHAR(60) NOT NULL,
    concluida_em TIMESTAMP WITHOUT TIME ZONE,
    concluida_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    CONSTRAINT uq_pi_operacao_etapa UNIQUE (id_pi, etapa)
);
CREATE INDEX IF NOT EXISTS idx_pi_operacao_etapa_pi ON cadu_pi_operacao_etapa(id_pi);

CREATE TABLE IF NOT EXISTS cadu_pi_contato_operacional (
    id BIGSERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    id_contato_cliente INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    papel VARCHAR(20) NOT NULL CHECK (papel IN ('agencia', 'cliente_final', 'parceiro')),
    padrao BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    CONSTRAINT uq_pi_contato_operacional UNIQUE (id_pi, id_contato_cliente)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pi_contato_operacional_padrao_papel
    ON cadu_pi_contato_operacional(id_pi, papel) WHERE padrao;
CREATE INDEX IF NOT EXISTS idx_pi_contato_operacional_pi
    ON cadu_pi_contato_operacional(id_pi);

CREATE TABLE IF NOT EXISTS cadu_pi_checklist_material (
    id BIGSERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    id_campanha INTEGER REFERENCES cadu_pi_campanha(id_campanha) ON DELETE CASCADE,
    codigo VARCHAR(60),
    escopo VARCHAR(12) NOT NULL DEFAULT 'campanha'
        CHECK (escopo IN ('pi', 'campanha')),
    fase VARCHAR(30) NOT NULL DEFAULT 'preparacao',
    ordem SMALLINT NOT NULL DEFAULT 0,
    modo_conclusao VARCHAR(12) NOT NULL DEFAULT 'manual'
        CHECK (modo_conclusao IN ('manual', 'automatico')),
    descricao TEXT NOT NULL,
    obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
    concluido BOOLEAN NOT NULL DEFAULT FALSE,
    evidencia TEXT,
    concluido_em TIMESTAMP WITHOUT TIME ZONE,
    concluido_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP)
);
CREATE INDEX IF NOT EXISTS idx_pi_checklist_material_pi
    ON cadu_pi_checklist_material(id_pi);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pi_checklist_material_item
    ON cadu_pi_checklist_material(id_pi, COALESCE(id_campanha, 0), descricao);

-- Compatibilidade para bancos onde a tabela foi criada por uma versão anterior.
ALTER TABLE cadu_pi_checklist_material
    ADD COLUMN IF NOT EXISTS codigo VARCHAR(60),
    ADD COLUMN IF NOT EXISTS escopo VARCHAR(12) DEFAULT 'campanha',
    ADD COLUMN IF NOT EXISTS fase VARCHAR(30) DEFAULT 'preparacao',
    ADD COLUMN IF NOT EXISTS ordem SMALLINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS modo_conclusao VARCHAR(12) DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS evidencia TEXT;

UPDATE cadu_pi_checklist_material
   SET escopo = CASE WHEN id_campanha IS NULL THEN 'pi' ELSE 'campanha' END,
       fase = COALESCE(fase, 'preparacao'),
       ordem = COALESCE(ordem, 0),
       modo_conclusao = COALESCE(modo_conclusao, 'manual')
 WHERE escopo IS NULL
    OR fase IS NULL
    OR ordem IS NULL
    OR modo_conclusao IS NULL;

ALTER TABLE cadu_pi_checklist_material
    ALTER COLUMN escopo SET NOT NULL,
    ALTER COLUMN fase SET NOT NULL,
    ALTER COLUMN ordem SET NOT NULL,
    ALTER COLUMN modo_conclusao SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_pi_checklist_escopo'
           AND conrelid = 'cadu_pi_checklist_material'::regclass
    ) THEN
        ALTER TABLE cadu_pi_checklist_material
            ADD CONSTRAINT ck_pi_checklist_escopo
            CHECK (escopo IN ('pi', 'campanha'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'ck_pi_checklist_modo_conclusao'
           AND conrelid = 'cadu_pi_checklist_material'::regclass
    ) THEN
        ALTER TABLE cadu_pi_checklist_material
            ADD CONSTRAINT ck_pi_checklist_modo_conclusao
            CHECK (modo_conclusao IN ('manual', 'automatico'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pi_checklist_codigo
    ON cadu_pi_checklist_material(id_pi, COALESCE(id_campanha, 0), codigo)
    WHERE codigo IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pi_checklist_fase_ordem
    ON cadu_pi_checklist_material(id_pi, fase, ordem);

CREATE TABLE IF NOT EXISTS cadu_pi_email_log (
    id BIGSERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    tipo VARCHAR(60) NOT NULL,
    assunto TEXT NOT NULL,
    destinatario_nome TEXT,
    destinatario_email TEXT NOT NULL,
    html TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente', 'enviando', 'sucesso', 'erro')),
    brevo_message_id TEXT,
    erro TEXT,
    criado_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    enviado_em TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP)
);
CREATE INDEX IF NOT EXISTS idx_pi_email_log_pi_created
    ON cadu_pi_email_log(id_pi, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_pi_interacao (
    id BIGSERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    tipo VARCHAR(40) NOT NULL DEFAULT 'nota',
    descricao TEXT NOT NULL,
    autor_id INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP)
);
CREATE INDEX IF NOT EXISTS idx_pi_interacao_pi_created
    ON cadu_pi_interacao(id_pi, created_at DESC);

-- Checklist operacional canônico: itens gerais existem uma vez por PI.
INSERT INTO cadu_pi_checklist_material
       (id_pi, codigo, escopo, fase, ordem, modo_conclusao, descricao)
SELECT p.id_pi, item.codigo, 'pi', item.fase, item.ordem,
       item.modo_conclusao, item.descricao
  FROM cadu_pi p
 CROSS JOIN (
    VALUES
        ('verificar_informacoes_pi', 'preparacao', 10, 'manual', 'Verificar informações do PI'),
        ('verificar_cotacao_enviada', 'preparacao', 20, 'manual', 'Verificar cotação enviada'),
        ('comunicar_campanha_iniciada', 'veiculacao', 60, 'automatico', 'Enviar e-mail ao cliente com campanha iniciada'),
        ('comunicar_campanha_otimizada', 'veiculacao', 100, 'automatico', 'Enviar e-mail com campanha otimizada'),
        ('comunicar_campanha_finalizada', 'fechamento', 110, 'automatico', 'Informar cliente sobre campanha finalizada'),
        ('enviar_relatorios_faturamento', 'fechamento', 120, 'manual', 'Enviar dashboard e relatórios para faturamento'),
        ('enviar_financeiro', 'fechamento', 130, 'automatico', 'Enviar PI para o Financeiro')
 ) AS item(codigo, fase, ordem, modo_conclusao, descricao)
ON CONFLICT DO NOTHING;

-- Itens que precisam ser acompanhados separadamente em cada campanha.
INSERT INTO cadu_pi_checklist_material
       (id_pi, id_campanha, codigo, escopo, fase, ordem,
        modo_conclusao, descricao)
SELECT c.id_pi, c.id_campanha, item.codigo, 'campanha', item.fase,
       item.ordem, item.modo_conclusao, item.descricao
  FROM cadu_pi_campanha c
 CROSS JOIN (
    VALUES
        ('verificar_criativos', 'preparacao', 30, 'manual', 'Verificar criativos'),
        ('preparar_plataforma', 'preparacao', 40, 'manual', 'Preparar campanha na plataforma'),
        ('campanha_iniciada', 'veiculacao', 50, 'automatico', 'Campanha iniciada'),
        ('objetivo_50', 'veiculacao', 70, 'automatico', 'Objetivo atingido em 50%'),
        ('objetivo_90', 'veiculacao', 90, 'automatico', 'Objetivo atingido em 90%')
 ) AS item(codigo, fase, ordem, modo_conclusao, descricao)
ON CONFLICT DO NOTHING;

-- Backfill apenas de evidências inequívocas; métricas são sincronizadas pelo serviço.
UPDATE cadu_pi_checklist_material item
   SET concluido = TRUE,
       concluido_em = COALESCE(item.concluido_em, campanha.updated_at, CURRENT_TIMESTAMP),
       evidencia = COALESCE(item.evidencia, 'Status da campanha no CentralX')
  FROM cadu_pi_campanha campanha
  JOIN cadu_pi_camp_status status ON status.id = campanha.id_status
 WHERE item.id_campanha = campanha.id_campanha
   AND item.codigo = 'campanha_iniciada'
   AND LOWER(TRIM(status.descricao)) IN ('ativa', 'finalizada', 'concluída', 'concluida', 'encerrada');

UPDATE cadu_pi_checklist_material item
   SET concluido = TRUE,
       concluido_em = COALESCE(item.concluido_em, email.enviado_em, email.created_at),
       evidencia = COALESCE(item.evidencia, 'E-mail enviado pelo CentralX')
  FROM (
    SELECT id_pi, tipo, MAX(enviado_em) AS enviado_em, MAX(created_at) AS created_at
      FROM cadu_pi_email_log
     WHERE status = 'sucesso'
       AND tipo IN ('campanha_iniciada', 'campanha_otimizada', 'campanha_finalizada')
     GROUP BY id_pi, tipo
  ) email
 WHERE item.id_pi = email.id_pi
   AND item.codigo = CASE email.tipo
       WHEN 'campanha_iniciada' THEN 'comunicar_campanha_iniciada'
       WHEN 'campanha_otimizada' THEN 'comunicar_campanha_otimizada'
       WHEN 'campanha_finalizada' THEN 'comunicar_campanha_finalizada'
   END;

UPDATE cadu_pi_checklist_material item
   SET concluido = TRUE,
       concluido_em = COALESCE(item.concluido_em, pi.updated_at, CURRENT_TIMESTAMP),
       evidencia = COALESCE(item.evidencia, 'PI em faturamento')
  FROM cadu_pi pi
 WHERE item.id_pi = pi.id_pi
   AND item.codigo = 'enviar_financeiro'
   AND pi.id_sub_status_pi IN (4, 5);

-- Backfill conservador dos marcos que podem ser comprovados pelo estado atual.
INSERT INTO cadu_pi_operacao_etapa (id_pi, etapa, concluida_em)
SELECT p.id_pi, 'dados_validados', COALESCE(p.updated_at, CURRENT_TIMESTAMP)
  FROM cadu_pi p
 WHERE p.id_cliente IS NOT NULL
   AND p.id_resp_comercial IS NOT NULL
   AND p.id_pi_tipo IS NOT NULL
   AND p.periodo_inicio IS NOT NULL
   AND p.periodo_fim IS NOT NULL
   AND NULLIF(TRIM(p.vr_bruto_pi::text), '') IS NOT NULL
ON CONFLICT (id_pi, etapa) DO NOTHING;

INSERT INTO cadu_pi_operacao_etapa (id_pi, etapa, concluida_em)
SELECT p.id_pi, 'campanhas_configuradas', MAX(c.updated_at)
  FROM cadu_pi p
  JOIN cadu_pi_campanha c ON c.id_pi = p.id_pi
 GROUP BY p.id_pi
HAVING BOOL_AND(
    c.id_plataforma IS NOT NULL
    AND c.id_objetivos_campanha IS NOT NULL
    AND c.id_responsavel_operacao IS NOT NULL
    AND c.periodo_inicio IS NOT NULL
    AND c.periodo_fim IS NOT NULL
)
ON CONFLICT (id_pi, etapa) DO NOTHING;

INSERT INTO cadu_pi_operacao_etapa (id_pi, etapa, concluida_em)
SELECT c.id_pi, 'campanha_iniciada', MIN(c.updated_at)
  FROM cadu_pi_campanha c
  JOIN cadu_pi_camp_status s ON s.id = c.id_status
 WHERE LOWER(TRIM(s.descricao)) = 'ativa'
 GROUP BY c.id_pi
ON CONFLICT (id_pi, etapa) DO NOTHING;

INSERT INTO cadu_pi_operacao_etapa (id_pi, etapa, concluida_em)
SELECT p.id_pi, 'enviado_financeiro', COALESCE(p.updated_at, CURRENT_TIMESTAMP)
  FROM cadu_pi p
 WHERE p.id_sub_status_pi IN (4, 5)
ON CONFLICT (id_pi, etapa) DO NOTHING;
