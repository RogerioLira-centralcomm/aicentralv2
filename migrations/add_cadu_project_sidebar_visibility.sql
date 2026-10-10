-- Projeto fixado (ou não) na sidebar principal e no Chat. Aditivo e idempotente; todos os projetos existentes continuam visíveis.
ALTER TABLE cadu_ci_projetos ADD COLUMN IF NOT EXISTS mostrar_na_sidebar BOOLEAN NOT NULL DEFAULT TRUE;
COMMENT ON COLUMN cadu_ci_projetos.mostrar_na_sidebar IS 'Se o projeto aparece na sidebar principal e no Chat; escolha do projeto, vale para toda a conta.';
