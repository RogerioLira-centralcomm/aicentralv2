"""Read-only, explicit Cadu workflows for everyday agency work."""

WORKFLOWS = {
    "market-radar": ("Radar de mercado", "Notícias e movimentos de concorrentes com fontes.", "Pesquisa", ("web.search",), "Pesquise movimentos recentes do mercado e concorrentes. Separe fato, data, fonte e implicação prática. Não prometa monitoramento contínuo."),
    "audience-map": ("Mapa de audiência", "Hipóteses de público, canais e sinais de pesquisa.", "Planejamento", ("web.search", "planner.research_plan_inputs"), "Mapeie segmentos, necessidades, canais e hipóteses de validação. Separe dados públicos de hipóteses. Não invente tamanho de público."),
    "investment-simulator": ("Simulador de investimento", "Cenários de verba e premissas para mídia.", "Planejamento", ("planner.research_plan_inputs",), "Apresente cenários enxutos de distribuição de verba com contas explícitas. Se faltar verba, use percentuais. Não trate referência de catálogo como cotação ou previsão de resultado."),
    "media-plan-audit": ("Auditoria do plano", "Revê coerência, riscos e lacunas do plano.", "Planejamento", ("planner.get_media_plan", "planner.research_plan_inputs"), "Revise objetivo, audiência, canais, formatos, verba e mensuração. Aponte inconsistências com evidência e proponha correções em ordem de impacto. Se não houver plano acessível, peça o plano ou um resumo."),
    "campaign-tracker": ("Acompanhamento de campanha", "Lê relatórios revisados e sugere próximos passos.", "Análise", ("reports.get_recent_project_metrics",), "Analise apenas relatórios importados e revisados disponíveis. Diga período, métricas, variações e próximos passos. Sem relatório, peça um arquivo ou projeto; não alegue acesso a plataformas em tempo real."),
    "creative-concept": ("Conceito criativo", "Direção, mensagem e variações para campanha.", "Criação", (), "Entregue conceito central, promessa, prova, tom, exemplos por canal e uma alternativa. Use a marca e o projeto quando presentes. Trate qualquer dado sobre consumidores como hipótese se não houver fonte."),
    "channel-copy": ("Copy por canal", "Textos prontos para formatos e canais escolhidos.", "Criação", (), "Produza textos prontos por canal e formato, com CTA e limites de caracteres quando conhecidos. Respeite a voz da marca; não invente regras da plataforma. Se o canal não foi indicado, proponha um conjunto pequeno."),
    "page-review": ("Revisor de página", "Avalia clareza, oferta, CTA e fricções.", "Criação", ("web.read",), "Revise a página fornecida por URL ou conteúdo colado: clareza, oferta, prova, CTA, acessibilidade e fricções. Priorize até cinco correções. Se a leitura falhar, diga isso e peça o conteúdo da página."),
    "meeting-copilot": ("Copiloto de reunião", "Pauta, resumo e encaminhamentos objetivos.", "Atendimento", ("google.list_meet_artifacts",), "Com base nas notas ou artefatos disponíveis, entregue resumo, decisões, responsáveis e próximos passos. Sem transcrição ou notas, prepare uma pauta útil e não atribua decisões a ninguém."),
    "client-delivery": ("Atendimento e entregas", "Organiza status, pendências e mensagem ao cliente.", "Atendimento", ("projects.list_tasks", "projects.list_resources"), "Monte um status objetivo para o cliente: feito, em andamento, pendências, responsáveis e próximo contato. Diferencie dados confirmados de proposta; não diga que enviou mensagem ou mudou tarefas."),
}


def entry(plugin_id: str) -> dict | None:
    workflow = WORKFLOWS.get(plugin_id)
    if not workflow:
        return None
    name, description, category, tools, instruction = workflow
    return {
        "id": plugin_id, "kind": "plugin", "name": name, "description": description,
        "category": category, "logo": None, "sort_order": 100 + list(WORKFLOWS).index(plugin_id) * 10,
        "selectable": True, "version": "1.0.0", "maturity": "active", "manifest": {},
        "triggers": [f"/{plugin_id}"], "internal_tools": list(tools),
        "context": ["conversation", "selected project/brand when available"],
        "external_connectors": [], "known_gaps": [], "inputs": ["user objective"],
        "outputs": ["answer in chat"], "instruction": instruction,
    }
