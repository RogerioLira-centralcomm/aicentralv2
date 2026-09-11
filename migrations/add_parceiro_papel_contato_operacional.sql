ALTER TABLE cadu_pi_contato_operacional
  DROP CONSTRAINT IF EXISTS cadu_pi_contato_operacional_papel_check;

ALTER TABLE cadu_pi_contato_operacional
  ADD CONSTRAINT cadu_pi_contato_operacional_papel_check
  CHECK (papel IN ('agencia', 'cliente_final', 'parceiro'));
