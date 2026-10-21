-- Leads v3: fluxos de cadência editáveis e comuns a todos os executivos.
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_cadencias_alvo.sql.
-- Cada fluxo diz para que estágio da relação ele serve (pessoa nova, já em conversa, conta parada,
-- veio do site) e cada passo diz a etapa do funil (topo, meio, fundo): é ela que orienta a IA a
-- escrever conteúdo de topo ou de meio para aquela pessoa. Editar os passos de um fluxo em uso cria
-- uma versão nova; quem já estava na versão antiga termina nela (id_versao_anterior guarda a ligação).

ALTER TABLE cadu_lead_cadencias ADD COLUMN IF NOT EXISTS estagio VARCHAR(20) NOT NULL DEFAULT 'novo';
ALTER TABLE cadu_lead_cadencias ADD COLUMN IF NOT EXISTS id_versao_anterior INTEGER REFERENCES cadu_lead_cadencias(id) ON DELETE SET NULL;
ALTER TABLE cadu_lead_cadencias DROP CONSTRAINT IF EXISTS chk_lead_cadencias_estagio;
ALTER TABLE cadu_lead_cadencias ADD CONSTRAINT chk_lead_cadencias_estagio
    CHECK (estagio IN ('novo', 'em_conversa', 'reativacao', 'inbound'));

-- Passos sem etapa ganham a mesma regra que a tela usava: primeira metade topo, o resto meio.
UPDATE cadu_lead_cadencias cad
   SET passos = (
        SELECT jsonb_agg(
                   CASE WHEN t.p ? 'etapa' THEN t.p
                        ELSE t.p || jsonb_build_object('etapa',
                             CASE WHEN t.ord <= ceil(jsonb_array_length(cad.passos) / 2.0) THEN 'topo' ELSE 'meio' END)
                   END ORDER BY t.ord)
          FROM jsonb_array_elements(cad.passos) WITH ORDINALITY AS t(p, ord)
       )
 WHERE jsonb_array_length(passos) > 0
   AND EXISTS (SELECT 1 FROM jsonb_array_elements(cad.passos) e WHERE NOT (e ? 'etapa'));

UPDATE cadu_lead_cadencias SET estagio = 'novo' WHERE chave IN ('marketing_midia', 'diretoria') AND estagio IS DISTINCT FROM 'novo';

-- Fluxos para outros estágios da relação.
INSERT INTO cadu_lead_cadencias (chave, nome, descricao, papeis, estagio, passos)
VALUES
('em_conversa', 'Já conversou',
 'Para quem já falou com a gente: aprofunda o desafio com conteúdo de meio de funil e chega ao próximo passo.',
 ARRAY['marketing', 'midia', 'criacao', 'diretoria', 'comercial', 'compras', 'outro'], 'em_conversa',
 '[
   {"dia": 0,  "canal": "email",    "acao": "enviar", "etapa": "meio",  "titulo": "Retomar a conversa", "objetivo": "Retomar o que foi conversado e trazer um dado novo ligado ao desafio que a pessoa citou"},
   {"dia": 3,  "canal": "linkedin", "acao": "enviar", "etapa": "meio",  "titulo": "Material sob medida", "objetivo": "Compartilhar um material ou leitura específica para o desafio da marca"},
   {"dia": 7,  "canal": "email",    "acao": "enviar", "etapa": "meio",  "titulo": "Diagnóstico curto", "objetivo": "Oferecer um diagnóstico rápido de mídia sobre o ponto discutido e propor 15 minutos"},
   {"dia": 12, "canal": "whatsapp", "acao": "enviar", "etapa": "fundo", "titulo": "Próximo passo", "objetivo": "Propor um próximo passo concreto: conversa com o time ou um briefing"}
 ]'::jsonb),
('reativacao', 'Reativar conta parada',
 'Para contas que esfriaram: volta com um fato novo, sem cobrar a resposta antiga.',
 ARRAY['marketing', 'midia', 'criacao', 'diretoria', 'comercial', 'compras', 'outro'], 'reativacao',
 '[
   {"dia": 0,  "canal": "linkedin", "acao": "enviar", "etapa": "topo", "titulo": "Reaproximação", "objetivo": "Retomar o contato com um fato novo da empresa, sem cobrar resposta antiga"},
   {"dia": 4,  "canal": "email",    "acao": "enviar", "etapa": "topo", "titulo": "Dado do setor", "objetivo": "Trazer um dado recente do setor e perguntar a leitura da pessoa"},
   {"dia": 10, "canal": "email",    "acao": "enviar", "etapa": "meio", "titulo": "Ideia para o trimestre", "objetivo": "Ligar o dado a uma oportunidade de mídia do próximo trimestre e propor 15 minutos"}
 ]'::jsonb),
('inbound', 'Veio do site',
 'Para quem pediu contato pelo site: responde rápido, entende o desafio e marca a conversa.',
 ARRAY['marketing', 'midia', 'criacao', 'diretoria', 'comercial', 'compras', 'outro'], 'inbound',
 '[
   {"dia": 0, "canal": "email",    "acao": "enviar", "etapa": "meio",  "titulo": "Resposta ao contato do site", "objetivo": "Responder o pedido feito no site com uma pergunta para entender o desafio"},
   {"dia": 1, "canal": "whatsapp", "acao": "enviar", "etapa": "meio",  "titulo": "WhatsApp de apoio", "objetivo": "Mensagem curta avisando do e-mail e oferecendo um horário"},
   {"dia": 4, "canal": "telefone", "acao": "ligar",  "etapa": "meio",  "titulo": "Ligação", "objetivo": "Roteiro curto para entender o desafio e marcar a conversa"},
   {"dia": 9, "canal": "email",    "acao": "enviar", "etapa": "fundo", "titulo": "Próximo passo", "objetivo": "Propor a conversa com o time e dizer o que será levado"}
 ]'::jsonb)
ON CONFLICT (chave) WHERE chave IS NOT NULL DO NOTHING;

-- Reverso (manual):
-- DELETE FROM cadu_lead_cadencias WHERE chave IN ('em_conversa', 'reativacao', 'inbound')
--   AND NOT EXISTS (SELECT 1 FROM cadu_lead_cadencia_inscricoes i WHERE i.id_cadencia = cadu_lead_cadencias.id);
-- ALTER TABLE cadu_lead_cadencias DROP CONSTRAINT IF EXISTS chk_lead_cadencias_estagio,
--     DROP COLUMN IF EXISTS estagio, DROP COLUMN IF EXISTS id_versao_anterior;
