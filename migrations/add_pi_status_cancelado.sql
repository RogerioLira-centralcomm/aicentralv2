-- Status Cancelado para PI (idempotente)
-- Nota: key 5 em cadu_pi_sub_status ja e Finalizado; Cancelada em campanhas ja existe (id 3).

INSERT INTO cadu_pi_sub_status (key, display)
SELECT 6, 'Cancelado'
WHERE NOT EXISTS (
    SELECT 1 FROM cadu_pi_sub_status WHERE key = 6 OR display = 'Cancelado'
);

INSERT INTO cadu_pi_aux_status (id, descricao, id_setor, id_sub_status_pi)
SELECT 14, 'Cancelado', 1, 6
WHERE NOT EXISTS (
    SELECT 1 FROM cadu_pi_aux_status WHERE descricao = 'Cancelado'
);
