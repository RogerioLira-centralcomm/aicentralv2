-- SOMENTE LEITURA. Rodar em produção e conferir o resultado antes de qualquer UPDATE.
-- Contas ativas, fora da CentralComm, sem nenhum contato admin/superadmin ativo.
-- Para cada conta, mostra o primeiro contato (candidato a admin da conta).
WITH sem_admin AS (
  SELECT c.id_cliente
  FROM tbl_cliente c
  WHERE UPPER(TRIM(COALESCE(c.nome_fantasia, ''))) <> 'CENTRALCOMM'
    AND NOT EXISTS (
      SELECT 1 FROM tbl_contato_cliente u
      WHERE u.pk_id_tbl_cliente = c.id_cliente
        AND u.status = TRUE
        AND u.user_type IN ('admin', 'superadmin')
    )
    AND EXISTS (
      SELECT 1 FROM tbl_contato_cliente u
      WHERE u.pk_id_tbl_cliente = c.id_cliente AND u.status = TRUE
    )
)
SELECT c.id_cliente,
       c.nome_fantasia,
       (SELECT COUNT(*) FROM tbl_contato_cliente u
         WHERE u.pk_id_tbl_cliente = c.id_cliente AND u.status = TRUE) AS contatos_ativos,
       p.id_contato_cliente AS primeiro_contato_id,
       p.nome_completo,
       p.email,
       p.user_type
FROM sem_admin s
JOIN tbl_cliente c ON c.id_cliente = s.id_cliente
JOIN LATERAL (
  SELECT u.id_contato_cliente, u.nome_completo, u.email, u.user_type
  FROM tbl_contato_cliente u
  WHERE u.pk_id_tbl_cliente = c.id_cliente AND u.status = TRUE
  ORDER BY u.id_contato_cliente ASC
  LIMIT 1
) p ON TRUE
ORDER BY c.id_cliente;
