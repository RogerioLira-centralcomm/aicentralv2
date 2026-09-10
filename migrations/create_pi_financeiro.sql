-- PI no Financeiro: snapshot de fechamento, estados e checklist fase financeiro.

CREATE TABLE IF NOT EXISTS cadu_pi_financeiro (
    id_pi INTEGER PRIMARY KEY REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    status_financeiro VARCHAR(40) NOT NULL DEFAULT 'aguardando_comprovacao'
        CHECK (status_financeiro IN (
            'aguardando_comprovacao',
            'aguardando_assinatura',
            'pronto_nf',
            'nf_emitida',
            'aguardando_pagamento',
            'encerrado',
            'bloqueado'
        )),
    updated_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP)
);
CREATE INDEX IF NOT EXISTS idx_pi_financeiro_status
    ON cadu_pi_financeiro(status_financeiro);

CREATE TABLE IF NOT EXISTS cadu_pi_resultado_fechamento (
    id BIGSERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    versao INTEGER NOT NULL DEFAULT 1,
    gasto_midia_realizado NUMERIC(14, 2),
    gasto_midia_previsto NUMERIC(14, 2),
    pct_gasto_midia NUMERIC(8, 2),
    objetivo_contratado NUMERIC(16, 4),
    objetivo_atingido NUMERIC(16, 4),
    pct_objetivo NUMERIC(8, 2),
    valor_bruto NUMERIC(14, 2),
    valor_liquido NUMERIC(14, 2),
    margem_cc NUMERIC(14, 2),
    tech_fee NUMERIC(14, 2),
    com_vendas NUMERIC(14, 2),
    pl_incentivos NUMERIC(14, 2),
    impostos NUMERIC(14, 2),
    margem_liquida_calculada NUMERIC(14, 2),
    zona_lucratividade SMALLINT,
    zonas_json JSONB,
    saude_pi VARCHAR(20),
    saude_json JSONB,
    desvio_aceitavel_pct NUMERIC(8, 2),
    lucrativo BOOLEAN,
    observacoes_operacao TEXT,
    payload_json JSONB,
    fechado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    fechado_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    motivo_reabertura TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP),
    UNIQUE (id_pi, versao)
);
CREATE INDEX IF NOT EXISTS idx_pi_resultado_fechamento_pi
    ON cadu_pi_resultado_fechamento(id_pi, versao DESC);

CREATE TABLE IF NOT EXISTS cadu_pi_resultado_campanha (
    id BIGSERIAL PRIMARY KEY,
    id_pi INTEGER NOT NULL REFERENCES cadu_pi(id_pi) ON DELETE CASCADE,
    id_campanha INTEGER REFERENCES cadu_pi_campanha(id_campanha) ON DELETE SET NULL,
    versao INTEGER NOT NULL DEFAULT 1,
    plataforma TEXT,
    nome_campanha TEXT,
    gasto_realizado NUMERIC(14, 2),
    gasto_previsto NUMERIC(14, 2),
    pct_gasto NUMERIC(8, 2),
    obj_contratado NUMERIC(16, 4),
    obj_atingido NUMERIC(16, 4),
    pct_objetivo NUMERIC(8, 2),
    preco_unitario_orcado NUMERIC(14, 6),
    preco_unitario_realizado NUMERIC(14, 6),
    periodo_inicio DATE,
    periodo_fim DATE,
    status_nome TEXT,
    link_dash TEXT,
    flags_json JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT date_trunc('second', CURRENT_TIMESTAMP)
);
CREATE INDEX IF NOT EXISTS idx_pi_resultado_campanha_pi
    ON cadu_pi_resultado_campanha(id_pi, versao);

INSERT INTO cadu_pi_checklist_material (
    id_pi, id_campanha, codigo, escopo, fase, ordem, modo_conclusao,
    descricao, obrigatorio, concluido
)
SELECT
    p.id_pi,
    NULL,
    item.codigo,
    'pi',
    'financeiro',
    item.ordem,
    item.modo,
    item.descricao,
    TRUE,
    FALSE
FROM cadu_pi p
CROSS JOIN (
    VALUES
        ('comprovacao_veiculacao', 'Comprovação de veiculação anexada/gerada', 140, 'manual'),
        ('carta_bonificacao', 'Carta de bonificação gerada (se aplicável)', 150, 'manual'),
        ('relatorio_cliente_enviado', 'Relatório enviado ao cliente', 160, 'automatico'),
        ('assinatura_d4sign', 'Documentos assinados via D4Sign', 170, 'automatico'),
        ('nf_vinculada', 'NF vinculada ao PI', 180, 'automatico'),
        ('pagamento_confirmado', 'Pagamento registrado', 190, 'automatico')
) AS item(codigo, descricao, ordem, modo)
WHERE p.id_sub_status_pi IN (4, 5)
  AND NOT EXISTS (
      SELECT 1
        FROM cadu_pi_checklist_material cm
       WHERE cm.id_pi = p.id_pi
         AND cm.codigo = item.codigo
         AND cm.id_campanha IS NULL
  );
