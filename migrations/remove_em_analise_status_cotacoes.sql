-- Remove status legado "Em Análise" das cotações
UPDATE cadu_cotacoes
SET status = 'Rascunho'
WHERE status IN ('Em Análise', 'em_analise');
