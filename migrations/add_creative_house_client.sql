-- Marcas da modelagem sem cliente comercial passam a viver no CentralComm (174).
-- Várias marcas podem compartilhar o mesmo cliente CRM.

DROP INDEX IF EXISTS uq_cx_clients_crm_client;

CREATE INDEX IF NOT EXISTS idx_cx_clients_crm_client
    ON cx_clients(crm_client_id)
    WHERE crm_client_id IS NOT NULL;

UPDATE cx_clients
   SET crm_client_id = 174
 WHERE crm_client_id IS NULL
   AND EXISTS (
       SELECT 1
         FROM tbl_cliente
        WHERE id_cliente = 174
          AND status = TRUE
   );
