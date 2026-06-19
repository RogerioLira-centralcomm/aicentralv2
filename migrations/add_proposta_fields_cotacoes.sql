-- Migration: Campos de cabeçalho da Proposta CentralComm Programmatic
-- Tabela: cadu_cotacoes
-- Descrição: Adiciona campos usados na geração do PDF da proposta programática
--            (frequência, impactos únicos, dados demográficos, perfil da
--            audiência, data de envio, validade e premissas). A praça é
--            reutilizada da campanha (cadu_cotacoes.praca).

ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS praca TEXT;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS frequencia_impacto VARCHAR(120);
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS estimativa_impactos_unicos BIGINT;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS dados_demograficos TEXT;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS perfil_audiencia_interesses TEXT;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS data_envio DATE;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS validade_dias INTEGER;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS premissas TEXT;

COMMENT ON COLUMN cadu_cotacoes.praca IS 'Praça/abrangência geográfica da campanha (cabeçalho da proposta)';
COMMENT ON COLUMN cadu_cotacoes.frequencia_impacto IS 'Frequência de impacto da campanha';
COMMENT ON COLUMN cadu_cotacoes.estimativa_impactos_unicos IS 'Estimativa de impactos únicos da campanha';
COMMENT ON COLUMN cadu_cotacoes.dados_demograficos IS 'Dados demográficos (sexo, idade, classe social)';
COMMENT ON COLUMN cadu_cotacoes.perfil_audiencia_interesses IS 'Perfil geral da audiência e interesses';
COMMENT ON COLUMN cadu_cotacoes.data_envio IS 'Data de envio da proposta ao cliente';
COMMENT ON COLUMN cadu_cotacoes.validade_dias IS 'Validade da proposta em dias';
COMMENT ON COLUMN cadu_cotacoes.premissas IS 'Premissas da proposta (texto livre)';
