-- Campos da Proposta CentralComm Programmatic em cadu_cotacoes
-- frequencia_impacto: usado para calcular estimativa de impactos únicos no PDF
-- premissas / observacoes_gerais: textos exibidos no PDF (com defaults na criação)

ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS frequencia_impacto INTEGER DEFAULT 3;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS premissas TEXT;
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS observacoes_gerais TEXT;
