-- Leads v3: vários celulares por contato (só celular/WhatsApp, sem fixo) e o que a busca grátis do Apollo
-- disse que existe, para não gastar crédito revelando quem não tem e-mail nem celular.
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_telefone_apollo.sql.
--   celulares           [{numero: '+5531988880000', status: 'valido' | 'nao_verificado'}]; o principal
--                       (o do WhatsApp) continua em telefone.
--   apollo_tem_email    has_email da busca (NULL = não se sabe).
--   apollo_tem_celular  has_direct_phone da busca: 'Yes' = TRUE, 'Maybe' = NULL.
--   apollo_revelado_em  última consulta paga (people/match) ao Apollo para esta pessoa.
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS celulares JSONB;
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS apollo_tem_email BOOLEAN;
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS apollo_tem_celular BOOLEAN;
ALTER TABLE cadu_lead_contatos ADD COLUMN IF NOT EXISTS apollo_revelado_em TIMESTAMP;

-- Quem veio de um candidato do Apollo herda o que a busca disse (só preenche o que está vazio).
UPDATE cadu_lead_contatos c
   SET apollo_tem_email = COALESCE(c.apollo_tem_email,
           CASE WHEN jsonb_typeof(k.payload -> 'has_email') = 'boolean' THEN (k.payload ->> 'has_email')::boolean END),
       apollo_tem_celular = COALESCE(c.apollo_tem_celular,
           CASE WHEN lower(k.payload ->> 'has_direct_phone') IN ('yes', 'true') THEN TRUE
                WHEN lower(k.payload ->> 'has_direct_phone') IN ('no', 'false') THEN FALSE END)
  FROM cadu_lead_contato_candidatos k
 WHERE k.id_contato = c.id AND k.provedor = 'apollo'
   AND (c.apollo_tem_email IS NULL OR c.apollo_tem_celular IS NULL);

-- Celular que já está em telefone entra na lista (fixo fica só em telefone, como foi digitado).
UPDATE cadu_lead_contatos
   SET celulares = jsonb_build_array(jsonb_build_object(
           'numero', '+55' || right(regexp_replace(telefone, '\D', '', 'g'), 11), 'status', 'nao_verificado'))
 WHERE celulares IS NULL
   AND regexp_replace(telefone, '\D', '', 'g') ~ '^(55)?[1-9][0-9]9[0-9]{8}$';

-- Reverso (manual):
-- ALTER TABLE cadu_lead_contatos DROP COLUMN IF EXISTS celulares, DROP COLUMN IF EXISTS apollo_tem_email,
--     DROP COLUMN IF EXISTS apollo_tem_celular, DROP COLUMN IF EXISTS apollo_revelado_em;
