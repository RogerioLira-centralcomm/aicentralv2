-- Snapshot do percentual de imposto usado na cotação (preserva histórico ao mudar a config global).
ALTER TABLE cadu_cotacoes ADD COLUMN IF NOT EXISTS imposto_percentual NUMERIC(5, 2);

-- Inferir das linhas existentes quando possível (perc_impostos é fração decimal, ex. 0.15).
UPDATE cadu_cotacoes c
SET imposto_percentual = sub.pct
FROM (
    SELECT cotacao_id, ROUND(AVG(perc_impostos::numeric) * 100, 2) AS pct
    FROM cadu_cotacao_linhas
    WHERE perc_impostos IS NOT NULL
      AND COALESCE(is_header, false) = false
      AND COALESCE(is_subtotal, false) = false
    GROUP BY cotacao_id
) sub
WHERE c.id = sub.cotacao_id
  AND c.imposto_percentual IS NULL;

-- Cotações sem linhas com imposto gravado: assumir taxa anterior padrão (15%).
UPDATE cadu_cotacoes
SET imposto_percentual = 15.00
WHERE imposto_percentual IS NULL;
