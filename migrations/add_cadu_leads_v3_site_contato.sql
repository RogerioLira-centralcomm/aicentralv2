-- Leads v3: lead que chega pelo formulário do site já entra com a pessoa em Contatos e o domínio
-- do e-mail corporativo. Aditivo e idempotente. Depende de add_cadu_leads_v3_prospeccao.sql.
-- O site grava direto em cadu_leads, por isso é gatilho e não código da aplicação. Só vale para
-- inserções novas (leads antigos não são tocados); o nome da empresa continua sendo sugestão na tela.
-- A lista de e-mails pessoais é a mesma de FREE_EMAIL_DOMAINS (leads_v3_prospeccao.py).
CREATE OR REPLACE FUNCTION cadu_leads_site_completar() RETURNS trigger AS $$
DECLARE
    email_dom TEXT := lower(split_part(trim(COALESCE(NEW.email, '')), '@', 2));
BEGIN
    IF COALESCE(NEW.status, '') = 'nao_qualificado' THEN
        RETURN NULL;
    END IF;
    IF NULLIF(trim(COALESCE(NEW.dominio, '')), '') IS NULL AND email_dom <> '' AND email_dom NOT IN (
        'gmail.com', 'hotmail.com', 'hotmail.com.br', 'outlook.com', 'outlook.com.br', 'yahoo.com',
        'yahoo.com.br', 'bol.com.br', 'uol.com.br', 'terra.com.br', 'icloud.com', 'me.com', 'live.com',
        'msn.com', 'ig.com.br', 'aol.com', 'protonmail.com', 'proton.me') THEN
        UPDATE cadu_leads SET dominio = left(email_dom, 255) WHERE id = NEW.id;
    END IF;
    IF NULLIF(trim(COALESCE(NEW.nome, '')), '') IS NOT NULL
       AND (NULLIF(trim(COALESCE(NEW.email, '')), '') IS NOT NULL OR NULLIF(trim(COALESCE(NEW.telefone, '')), '') IS NOT NULL)
       AND NOT EXISTS (SELECT 1 FROM cadu_lead_contatos c WHERE c.id_lead = NEW.id) THEN
        INSERT INTO cadu_lead_contatos (id_lead, nome, email, telefone, cargo, is_principal, origem_dado)
        VALUES (NEW.id, left(trim(NEW.nome), 200), NULLIF(left(lower(trim(COALESCE(NEW.email, ''))), 255), ''),
                NULLIF(left(trim(COALESCE(NEW.telefone, '')), 50), ''), NULLIF(left(trim(COALESCE(NEW.cargo, '')), 150), ''),
                TRUE, 'site');
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cadu_leads_site_completar ON cadu_leads;
CREATE TRIGGER trg_cadu_leads_site_completar
    AFTER INSERT ON cadu_leads
    FOR EACH ROW WHEN (NEW.fonte = 'site')
    EXECUTE FUNCTION cadu_leads_site_completar();

-- Reverso (manual):
-- DROP TRIGGER IF EXISTS trg_cadu_leads_site_completar ON cadu_leads; DROP FUNCTION IF EXISTS cadu_leads_site_completar();
