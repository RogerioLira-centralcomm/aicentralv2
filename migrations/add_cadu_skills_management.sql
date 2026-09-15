-- Gestão interna, ranking e eventos verificáveis do Cadu Skills.

ALTER TABLE cadu_skill_definitions ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE cadu_skill_definitions ADD COLUMN IF NOT EXISTS display_rank INTEGER NOT NULL DEFAULT 999;
ALTER TABLE cadu_skill_definitions ADD COLUMN IF NOT EXISTS is_testable BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE cadu_skill_customizations ADD COLUMN IF NOT EXISTS summary TEXT NOT NULL DEFAULT '';
ALTER TABLE cadu_skill_customizations ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE cadu_skill_customizations ADD COLUMN IF NOT EXISTS instructions TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS cadu_skill_events (
    id BIGSERIAL PRIMARY KEY,
    skill_id BIGINT NOT NULL REFERENCES cadu_skill_definitions(id) ON DELETE CASCADE,
    event_type VARCHAR(32) NOT NULL,
    actor_key VARCHAR(64) NOT NULL,
    user_id BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_skill_event_type_ck CHECK (
        event_type IN ('view', 'copy', 'install', 'run_started', 'run_succeeded', 'run_failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_cadu_skill_events_skill_created
    ON cadu_skill_events(skill_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_skill_events_type_created
    ON cadu_skill_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_skill_customizations_client_project
    ON cadu_skill_customizations(client_id, project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_skill_shares_customization_active
    ON cadu_skill_shares(customization_id, revoked_at);

INSERT INTO cadu_skill_definitions
    (slug, name, summary, category, owner_type, visibility, status, image_url, display_rank, is_testable)
VALUES
    ('cadu-media-planning', 'Planejamento de mídia Cadu', 'Transforma briefing, contexto de marca e canais disponíveis em um plano de mídia defendível.', 'Planejamento de mídia', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 1, TRUE),
    ('copywriting-skills', 'Copy para campanhas', 'Transforma briefing e oferta em mensagens claras para anúncios, landing pages e CRM.', 'Conteúdo', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 2, TRUE),
    ('competitor-analysis', 'Análise de concorrentes', 'Organiza concorrentes, posicionamentos, mensagens e espaços ainda pouco explorados.', 'Estratégia', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 3, TRUE),
    ('content-planning', 'Planejamento de conteúdo', 'Converte objetivos de comunicação em pilares, pautas e uma cadência sustentável.', 'Conteúdo', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 4, TRUE),
    ('script-writing', 'Roteiros para campanhas', 'Escreve roteiros curtos para peças audiovisuais sem gerar vídeo ou áudio.', 'Conteúdo', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 5, TRUE),
    ('social-listening', 'Escuta de redes sociais', 'Estrutura temas, sinais e perguntas para acompanhar conversas sobre uma marca.', 'Dados', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 6, TRUE),
    ('data-analytics', 'Análise de desempenho', 'Transforma tabelas e indicadores em diagnóstico, decisão e próximo teste.', 'Dados', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 7, TRUE),
    ('brand-operation', 'Operação de marca', 'Organiza regras, ativos e decisões para manter a marca consistente no trabalho diário.', 'Marca', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 8, TRUE),
    ('conversion-optimization', 'Otimização de conversão', 'Prioriza hipóteses para reduzir atrito e melhorar a próxima ação do público.', 'Crescimento', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 9, TRUE),
    ('advertising', 'Planejamento de publicidade', 'Conecta mensagem, canal, formato e mensuração em uma campanha coerente.', 'Mídia', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 10, TRUE)
    ,('cadu-channel-intelligence', 'Inteligência de canais Cadu', 'Compara canais da CentralX com audiências e formatos realmente compatíveis.', 'Inteligência de mídia', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 101, TRUE)
    ,('cadu-audience-intelligence', 'Inteligência de audiências Cadu', 'Qualifica audiências por mercado, sinais, funil, canal, origem e qualidade.', 'Dados e audiência', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 102, TRUE)
    ,('cadu-format-intelligence', 'Inteligência de formatos Cadu', 'Escolhe formatos viáveis por canal, dispositivo, objetivo e capacidade criativa.', 'Formatos e criação', 'centralx', 'public', 'published', '/static/images/cadu/products/skills.png', 103, TRUE)
ON CONFLICT (slug) DO UPDATE SET
    owner_type = 'centralx', image_url = EXCLUDED.image_url,
    display_rank = EXCLUDED.display_rank, is_testable = TRUE, updated_at = NOW();

INSERT INTO cadu_skill_versions
    (skill_id, version, manifest, instructions, model, credit_cost, input_limit, output_limit, published_at)
SELECT id, 1, '{"runtime":"cadu-test-agent","tools":false,"video":false}'::jsonb,
       '', 'openai/gpt-4o-mini', CASE WHEN slug = 'cadu-media-planning' THEN 2 ELSE 1 END,
       4000, 700, NOW()
  FROM cadu_skill_definitions
 WHERE slug IN (
    'cadu-media-planning', 'copywriting-skills', 'competitor-analysis', 'content-planning',
    'script-writing', 'social-listening', 'data-analytics', 'brand-operation',
    'conversion-optimization', 'advertising', 'cadu-channel-intelligence',
    'cadu-audience-intelligence', 'cadu-format-intelligence'
 )
ON CONFLICT (skill_id, version) DO NOTHING;

UPDATE cadu_skill_versions v
   SET instructions = source.instructions,
       manifest = '{"runtime":"cadu-test-agent","tools":false,"video":false,"package":"installable"}'::jsonb
  FROM cadu_skill_definitions d
  JOIN (VALUES
    ('cadu-media-planning', 'Congele objetivo, público, praça, período, verba e fontes num Campaign Snapshot. Crie uma tese única antes do mix. Use somente canais, audiências e formatos dos catálogos Cadu. Feche o mix em 100% e audite conflitos; não invente preços, alcance ou resultados.'),
    ('cadu-channel-intelligence', 'Compare somente canais do catálogo Cadu e valide audiência, formato, dispositivo, mínimo, qualidade e snapshot. Diferencie dado, inferência e pendência; não invente disponibilidade ou resultado.'),
    ('cadu-audience-intelligence', 'Use somente audiências ativas do catálogo Cadu. Respeite taxonomia, canal, origem, validade e qualidade; exclua quarentena, não promova status sem evidência e não use preço de custo ou preço de venda. Não invente tamanho, CPM, match rate ou performance.'),
    ('cadu-format-intelligence', 'Escolha um formato principal compatível com canal, dispositivo e objetivo. Diferencie formato, peça, placement, compra e add-on; não invente inventário nem afirme produção inexistente.')
  ) AS source(slug, instructions) ON source.slug = d.slug
 WHERE v.skill_id = d.id
   AND v.id = (SELECT latest.id FROM cadu_skill_versions latest WHERE latest.skill_id = d.id ORDER BY latest.version DESC LIMIT 1);

-- Toda skill pública própria do Cadu com instruções publicadas pode ser
-- executada pelo mesmo agente de teste. Referências externas continuam fora.
UPDATE cadu_skill_definitions d
   SET is_testable = TRUE, updated_at = NOW()
 WHERE d.owner_type = 'centralx' AND d.status = 'published' AND d.visibility = 'public'
   AND EXISTS (
       SELECT 1 FROM cadu_skill_versions v
        WHERE v.skill_id = d.id AND LENGTH(BTRIM(v.instructions)) > 0
   );
