-- Plataforma principal da cotação (editável no modal de campanha)
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS plataforma_campanha VARCHAR(120);
