-- Leads v3: alvo das contas do Golden Circle e modelos de cadência por papel.
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_prospeccao.sql.
--
-- Golden Circle é uma marca de prioridade do lead no trimestre: cada conta ganha objetivo
-- (coluna meta, já existente), valor-alvo, prazo, próximo marco e os papéis que precisam
-- ser cobertos. Os passos das cadências são tarefas assistidas: o executivo envia com um
-- clique e marca como feito; nada é enviado sozinho.

ALTER TABLE cadu_golden_circle ADD COLUMN IF NOT EXISTS valor_alvo NUMERIC(14,2);
ALTER TABLE cadu_golden_circle ADD COLUMN IF NOT EXISTS prazo DATE;
ALTER TABLE cadu_golden_circle ADD COLUMN IF NOT EXISTS proximo_marco VARCHAR(30);
ALTER TABLE cadu_golden_circle ADD COLUMN IF NOT EXISTS papeis_alvo TEXT[] NOT NULL
    DEFAULT ARRAY['marketing', 'midia', 'criacao', 'diretoria'];

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_golden_circle_proximo_marco') THEN
        ALTER TABLE cadu_golden_circle ADD CONSTRAINT chk_golden_circle_proximo_marco CHECK (
            proximo_marco IS NULL OR proximo_marco IN ('primeira_conversa', 'reuniao', 'apresentacao', 'proposta', 'fechamento'));
    END IF;
END $$;

-- Foco da empresa para personalizar a conexão: canais preferidos e conteúdos de topo e meio
-- de funil (fundo é consequência de um bom trabalho de conexão). Contexto de mercado gerado
-- por busca na web com fontes. Tudo opcional.
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS canais_foco TEXT[];
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS foco_conteudo JSONB;
ALTER TABLE cadu_leads ADD COLUMN IF NOT EXISTS contexto_mercado JSONB;
COMMENT ON COLUMN cadu_leads.foco_conteudo IS '{"topo": "...", "meio": "...", "tom": "...", "evitar": "..."}';
COMMENT ON COLUMN cadu_leads.contexto_mercado IS '{"texto": "...", "fontes": [url], "modelo": "...", "gerado_em": "..."}';

-- Modelos de cadência do sistema: chave estável para semear e escolher por papel.
ALTER TABLE cadu_lead_cadencias ADD COLUMN IF NOT EXISTS chave VARCHAR(40);
ALTER TABLE cadu_lead_cadencias ADD COLUMN IF NOT EXISTS papeis TEXT[] NOT NULL DEFAULT '{}';
CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_cadencias_chave ON cadu_lead_cadencias (chave) WHERE chave IS NOT NULL;

-- Passo: dia (a partir da inscrição), canal (email | whatsapp | linkedin | telefone), acao e objetivo
-- (o objetivo vai para a IA escrever a mensagem do passo).
INSERT INTO cadu_lead_cadencias (chave, nome, descricao, papeis, passos)
VALUES
('marketing_midia', 'Marketing e mídia',
 'Mais toques e canais para quem opera marketing, mídia e criação.',
 ARRAY['marketing', 'midia', 'criacao', 'comercial', 'outro'],
 '[
   {"dia": 0,  "canal": "linkedin", "acao": "conectar", "titulo": "Pedir conexão no LinkedIn", "objetivo": "Convite curto de conexão citando a marca e o interesse em mídia"},
   {"dia": 1,  "canal": "email",    "acao": "enviar",   "titulo": "E-mail de apresentação", "objetivo": "Apresentar a CentralComm e propor uma conversa de 20 minutos sobre mídia"},
   {"dia": 3,  "canal": "whatsapp", "acao": "enviar",   "titulo": "WhatsApp de abordagem", "objetivo": "Mensagem curta retomando o e-mail e pedindo um horário"},
   {"dia": 5,  "canal": "telefone", "acao": "ligar",    "titulo": "Ligação", "objetivo": "Roteiro de ligação de 2 minutos para marcar a reunião"},
   {"dia": 8,  "canal": "email",    "acao": "enviar",   "titulo": "E-mail com case", "objetivo": "Follow-up com um case de mídia do mesmo segmento"},
   {"dia": 12, "canal": "linkedin", "acao": "enviar",   "titulo": "Mensagem no LinkedIn", "objetivo": "Mensagem curta com uma ideia de campanha para a marca"},
   {"dia": 16, "canal": "email",    "acao": "enviar",   "titulo": "E-mail de encerramento", "objetivo": "Encerramento educado, deixando a porta aberta para o próximo trimestre"}
 ]'::jsonb),
('diretoria', 'Diretoria',
 'Menos toques e tom executivo para C-level e diretoria.',
 ARRAY['diretoria'],
 '[
   {"dia": 0,  "canal": "linkedin", "acao": "conectar", "titulo": "Pedir conexão no LinkedIn", "objetivo": "Convite executivo e curto, sem pitch"},
   {"dia": 2,  "canal": "email",    "acao": "enviar",   "titulo": "E-mail executivo", "objetivo": "E-mail executivo de 4 linhas com uma tese de crescimento via mídia"},
   {"dia": 7,  "canal": "linkedin", "acao": "enviar",   "titulo": "Mensagem no LinkedIn", "objetivo": "Mensagem curta pedindo indicação de quem cuida de mídia"},
   {"dia": 12, "canal": "email",    "acao": "enviar",   "titulo": "Follow-up executivo", "objetivo": "Follow-up com um número de resultado relevante para o setor"},
   {"dia": 20, "canal": "email",    "acao": "enviar",   "titulo": "E-mail de encerramento", "objetivo": "Encerramento respeitoso, oferecendo uma conversa futura"}
 ]'::jsonb)
ON CONFLICT (chave) WHERE chave IS NOT NULL DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_cadencia_inscricoes_executivo ON cadu_lead_cadencia_inscricoes (id_executivo, proxima_em) WHERE status = 'ativa';

-- Reverso (manual):
-- ALTER TABLE cadu_leads DROP COLUMN IF EXISTS canais_foco, DROP COLUMN IF EXISTS foco_conteudo, DROP COLUMN IF EXISTS contexto_mercado;
-- DROP INDEX IF EXISTS idx_cadencia_inscricoes_executivo, uq_lead_cadencias_chave;
-- DELETE FROM cadu_lead_cadencias WHERE chave IN ('marketing_midia', 'diretoria');
-- ALTER TABLE cadu_lead_cadencias DROP COLUMN IF EXISTS chave, DROP COLUMN IF EXISTS papeis;
-- ALTER TABLE cadu_golden_circle DROP CONSTRAINT IF EXISTS chk_golden_circle_proximo_marco,
--     DROP COLUMN IF EXISTS valor_alvo, DROP COLUMN IF EXISTS prazo, DROP COLUMN IF EXISTS proximo_marco,
--     DROP COLUMN IF EXISTS papeis_alvo;
