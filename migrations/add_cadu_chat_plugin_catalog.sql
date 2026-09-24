-- Catalog metadata is stored and versioned independently from Python execution.
CREATE TABLE IF NOT EXISTS cadu_chat_plugins (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'plugin' CHECK (kind IN ('plugin', 'integration')),
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Cadu',
    logo TEXT,
    sort_order INTEGER NOT NULL DEFAULT 100,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    selectable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE cadu_chat_plugins
    ADD COLUMN IF NOT EXISTS selectable BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS cadu_chat_plugin_versions (
    plugin_id TEXT NOT NULL REFERENCES cadu_chat_plugins(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    maturity TEXT NOT NULL CHECK (maturity IN ('active', 'in_development', 'early', 'planned')),
    description TEXT NOT NULL DEFAULT '',
    manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    changelog TEXT NOT NULL DEFAULT '',
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plugin_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS cadu_chat_plugin_one_current_version
    ON cadu_chat_plugin_versions (plugin_id) WHERE is_current;
CREATE INDEX IF NOT EXISTS cadu_chat_plugins_listing
    ON cadu_chat_plugins (kind, enabled, sort_order, name);

INSERT INTO cadu_chat_plugins (id, kind, name, category, sort_order, selectable) VALUES
    ('insights', 'plugin', 'Insights de mercado', 'Pesquisa e inteligência', 10, TRUE),
    ('planner', 'plugin', 'Planner', 'Planejamento', 20, TRUE),
    ('project-search', 'plugin', 'Busca no projeto', 'Projetos', 30, TRUE),
    ('project-activities', 'plugin', 'Atividades do projeto', 'Projetos', 40, TRUE),
    ('campaign-search', 'plugin', 'Buscar campanhas', 'Pesquisa e inteligência', 50, FALSE),
    ('reports', 'plugin', 'Reports', 'Análise', 60, FALSE),
    ('studio', 'plugin', 'Studio', 'Criação', 70, FALSE),
    ('trello', 'integration', 'Trello', 'Projetos e tarefas', 10, FALSE),
    ('asana', 'integration', 'Asana', 'Projetos e tarefas', 20, FALSE),
    ('slack', 'integration', 'Slack', 'Comunicação', 30, FALSE),
    ('google', 'integration', 'Google', 'Pesquisa e mídia', 40, FALSE)
ON CONFLICT (id) DO UPDATE SET
    kind = EXCLUDED.kind, name = EXCLUDED.name, category = EXCLUDED.category,
    sort_order = EXCLUDED.sort_order, selectable = EXCLUDED.selectable, updated_at = NOW();

INSERT INTO cadu_chat_plugin_versions (plugin_id, version, maturity, description, manifest, changelog, is_current)
VALUES
    ('insights', '0.3.0', 'active', 'Combina busca pública, pesquisa web e revisão factual para entregar insights atuais de marketing, comunicação e mídia.',
     '{"triggers":["search_insights"],"internal_tools":["insights.research_market"],"context":["conversation","project optional","brand optional"],"external_connectors":[],"known_gaps":["Pesquisa de campanhas da própria marca e métricas internas continuam nos fluxos de Campaign Search e Reports."],"inputs":["tema de mercado"],"outputs":["insight de mercado revisado com dados recentes"]}', 'Combinação de pesquisa web e revisão factual no chat.', TRUE),
    ('planner', '0.2.0', 'in_development', 'Consulta os catálogos do Cadu para preparar e iterar uma proposta de plano de mídia dentro do chat.',
     '{"triggers":["plan_campaign","analyze_plan","compare_plan"],"internal_tools":["planner.research_plan_inputs","planner.search_catalog","planner.get_media_plan","artifacts.create_draft","artifacts.update_draft"],"context":["conversation","project for saved plan"],"external_connectors":[],"known_gaps":["As páginas de planejamento serão repensadas; o chat ainda não salva alterações no plano canônico/versionado."],"inputs":["objetivos","canais","audiências","investimento","prazo"],"outputs":["proposta de plano editável no chat"]}', 'Catálogos, audiências e propostas de canais dentro do chat.', TRUE),
    ('project-search', '0.1.0', 'in_development', 'Busca arquivos, artefatos, tarefas e informações indexadas no projeto selecionado, sem obrigar que pedidos de criação usem o projeto como contexto.',
     '{"triggers":["search_project","project_readout","describe_project","search_campaigns"],"internal_tools":["workspace.search_project_content","projects.search_knowledge","projects.list_resources","resources.search","projects.get_source_chunks","artifacts.list"],"context":["selected project required for private project search","new work can start without a project"],"external_connectors":[],"known_gaps":["Busca geral reutiliza o índice e os recursos atuais do projeto; busca transversal entre projetos não está habilitada."],"inputs":["projeto selecionado","pergunta ou termo de busca"],"outputs":["resultados priorizados com tipo e origem","síntese com referências internas"]}', 'Busca de conhecimento, arquivos e artefatos delimitada ao projeto selecionado.', TRUE),
    ('project-activities', '0.1.0', 'in_development', 'Consulta, propõe e organiza atividades do projeto a partir das tarefas, recursos e contexto disponíveis.',
     '{"triggers":["list_project_tasks","plan_project_tasks"],"internal_tools":["projects.list_tasks","projects.list_resources","workspace.get_project_context","projects.create_initial_task_list","projects.create_task","projects.create_tasks","projects.update_task","artifacts.create_draft","artifacts.update_draft"],"context":["selected project required for project tasks","proposals may be drafted before explicit confirmation"],"external_connectors":[],"known_gaps":["Alterações persistentes em atividades continuam sujeitas a confirmação e aos contratos de escrita já existentes."],"inputs":["projeto selecionado","objetivo ou instrução","tarefas e recursos existentes"],"outputs":["lista atual","proposta de atividades","artefato de acompanhamento"]}', 'Reúne leitura e planejamento das atividades do projeto no chat.', TRUE),
    ('campaign-search', '0.1.0', 'planned', 'Localiza campanhas na marca ou na base do projeto ativo.',
     '{"triggers":["search_campaigns"],"internal_tools":["brands.get_context","workspace.search_project_content"],"context":["brand or project"],"external_connectors":[],"known_gaps":["Busca limitada aos registros retornados pelo contexto de marca ou projeto."],"inputs":["marca ou projeto","termo de busca"],"outputs":["campanhas e cases encontrados"]}', 'Definição inicial do fluxo de busca.', TRUE),
    ('reports', '0.1.0', 'early', 'Analisa métricas importadas e revisadas; compara desempenho a um plano quando ambos forem selecionados.',
     '{"triggers":["analyze_report","compare_report_to_plan"],"internal_tools":["reports.list_project_reports","reports.get_report_metrics","reports.compare_report_to_plan"],"context":["project and reviewed report"],"external_connectors":[],"known_gaps":["Ingestão e revisão dos dados ainda são fluxos separados; não há conector de métricas em tempo real."],"inputs":["relatório revisado","plano opcional"],"outputs":["leitura de métricas e comparação"]}', 'Definição inicial do fluxo.', TRUE),
    ('studio', '0.1.0', 'planned', 'Gera ou edita imagens e aproveita identidade e referências quando disponíveis.',
     '{"triggers":["create_image","edit_image"],"internal_tools":["media.creation_capabilities","media.generate_image","media.edit_image"],"context":["conversation","brand optional","project optional","references optional"],"external_connectors":[],"known_gaps":["A geração existe no MCP do Studio, mas o fluxo de confirmação de custo ainda precisa ser integrado ao chat antes de acionamento automático."],"inputs":["brief criativo","referências opcionais"],"outputs":["imagem gerada ou editada"]}', 'Definição inicial do fluxo.', TRUE),
    ('trello', '0.1.0', 'planned', 'Quadros e tarefas do Trello conectados ao planejamento do Cadu.', '{"logo":"trello.svg","provider":"Trello","external_connectors":["trello MCP or API"],"known_gaps":["Integração ainda não disponível."]}', 'Vitrine de integração planejada.', TRUE),
    ('asana', '0.1.0', 'planned', 'Projetos e tarefas do Asana conectados ao planejamento do Cadu.', '{"logo":"asana.svg","provider":"Asana","external_connectors":["Asana MCP or API"],"known_gaps":["Integração ainda não disponível."]}', 'Vitrine de integração planejada.', TRUE),
    ('slack', '0.1.0', 'planned', 'Conversas e atualizações do Slack conectadas aos fluxos do Cadu.', '{"logo":"slack.svg","provider":"Slack","external_connectors":["Slack MCP or API"],"known_gaps":["Integração ainda não disponível."]}', 'Vitrine de integração planejada.', TRUE),
    ('google', '0.1.0', 'planned', 'Pesquisa e mídia do Google conectadas aos fluxos do Cadu.', '{"logo":"google.svg","provider":"Google","external_connectors":["Google APIs"],"known_gaps":["Integração ainda não disponível."]}', 'Vitrine de integração planejada.', TRUE)
ON CONFLICT (plugin_id, version) DO NOTHING;
