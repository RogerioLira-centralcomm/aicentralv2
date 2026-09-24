"""Read-only, explicit Cadu workflows for everyday agency work."""

import re

from .contracts import RequestContext

WORKFLOWS = {
    "market-radar": ("Radar de mercado", "Notícias e movimentos de concorrentes com fontes.", "Pesquisa", ("web.search",), "Pesquise movimentos recentes do mercado e concorrentes. Separe fato, data, URL da fonte e implicação prática. Faça uma checagem final de cada afirmação factual contra as fontes recebidas; remova o que não estiver sustentado. Não prometa monitoramento contínuo."),
    "audience-map": ("Mapa de audiência", "Hipóteses de público, canais e sinais de pesquisa.", "Planejamento", ("web.search", "planner.research_plan_inputs"), "Mapeie segmentos, necessidades, canais e hipóteses de validação. Separe dados públicos de hipóteses. Não invente tamanho de público."),
    "investment-simulator": ("Simulador de investimento", "Cenários de verba e premissas para mídia.", "Planejamento", ("planner.research_plan_inputs",), "Apresente cenários enxutos de distribuição de verba com contas explícitas e confira se cada cenário soma 100%. Se faltar verba, use percentuais. Não trate referência de catálogo como cotação ou previsão de resultado."),
    "media-plan-audit": ("Auditoria do plano", "Revê coerência, riscos e lacunas do plano.", "Planejamento", ("planner.list_plans", "planner.get_media_plan"), "Revise objetivo, audiência, canais, formatos, verba e mensuração. Aponte inconsistências com evidência e proponha correções em ordem de impacto. Se houver apenas uma lista de planos, peça ao usuário para escolher o correto; a lista não contém detalhes suficientes para uma auditoria. Se não houver plano acessível, peça o plano ou um resumo."),
    "campaign-tracker": ("Acompanhamento de campanha", "Lê relatórios revisados e sugere próximos passos.", "Análise", ("reports.get_recent_project_metrics",), "Analise apenas relatórios importados e revisados disponíveis. Diga período, métricas, variações e próximos passos; compare números somente quando período e definição forem compatíveis. Sem relatório, peça um arquivo ou projeto; não alegue acesso a plataformas em tempo real."),
    "creative-concept": ("Conceito criativo", "Direção, mensagem e variações para campanha.", "Criação", (), "Entregue conceito central, promessa, prova, tom, exemplos por canal e uma alternativa. Use a marca e o projeto quando presentes. Trate qualquer dado sobre consumidores como hipótese se não houver fonte."),
    "channel-copy": ("Copy por canal", "Textos prontos para formatos e canais escolhidos.", "Criação", (), "Produza textos prontos por canal e formato, com CTA e limites de caracteres quando conhecidos. Respeite a voz da marca; não invente regras da plataforma. Se o canal não foi indicado, proponha um conjunto pequeno."),
    "page-review": ("Revisor de página", "Avalia clareza, oferta, CTA e fricções.", "Criação", ("web.read",), "Revise a página fornecida por URL ou conteúdo colado: clareza, oferta, prova, CTA, acessibilidade e fricções. Priorize até cinco correções e cite a URL quando a página tiver sido lida. Se a leitura falhar, diga isso e peça o conteúdo da página."),
    "meeting-copilot": ("Copiloto de reunião", "Pauta, resumo e encaminhamentos objetivos.", "Atendimento", ("google.list_meet_artifacts",), "Com base nas notas ou na transcrição efetivamente fornecidas, entregue resumo, decisões, responsáveis e próximos passos. A listagem do Google Meet contém metadados, não a transcrição: nunca resuma seu conteúdo como se tivesse sido lido. Sem notas, prepare uma pauta útil e não atribua decisões a ninguém."),
    "client-delivery": ("Atendimento e entregas", "Organiza status, pendências e mensagem ao cliente.", "Atendimento", ("projects.list_tasks", "projects.list_resources"), "Monte um status objetivo para o cliente: feito, em andamento, pendências, responsáveis e próximo contato. Diferencie dados confirmados de proposta; não diga que enviou mensagem ou mudou tarefas."),
}


def recent_preferences(request: RequestContext, plugin_id: str) -> list[str]:
    """Infer small presentation hints from this person's completed uses in this project."""
    if plugin_id not in WORKFLOWS:
        return []
    try:
        from ...cadu_family import repository

        rows = repository.rows("""
            WITH previous AS (
                SELECT conversation_id, created_at
                  FROM cadu_family_chat_runs
                 WHERE user_id=%s AND client_id=%s AND status='completed'
                   AND created_at >= NOW() - INTERVAL '90 days'
                   AND response_policy->'plugin'->>'id'=%s
                   AND COALESCE(request_context->>'project_ref','')=%s
                   AND COALESCE(request_context->>'brand_ref','')=%s
                 ORDER BY created_at DESC LIMIT 8
            )
            SELECT message.content
              FROM previous
              JOIN LATERAL (
                SELECT content FROM cadu_conversation_messages
                 WHERE conversation_id=previous.conversation_id AND role='user'
                   AND created_at BETWEEN previous.created_at - INTERVAL '1 minute'
                                      AND previous.created_at + INTERVAL '2 minutes'
                 ORDER BY ABS(EXTRACT(EPOCH FROM (created_at-previous.created_at)))
                 LIMIT 1
              ) message ON TRUE
        """, (request.user_id, request.client_id, plugin_id,
              request.project_ref or "", request.brand_ref or ""))
    except Exception:
        return []
    patterns = (
        (r"\b(?:executiv[oa]|diret[oa]|objetiv[oa])\b", "resposta executiva"),
        (r"\b(?:anal[ií]tic[oa]|aprofundad[oa]|detalhad[oa])\b", "análise detalhada"),
        (r"\b(?:resumid[oa]|curt[oa]|enxut[oa])\b", "resposta curta"),
        (r"\b(?:tabela|quadro comparativo)\b", "apresentação em tabela"),
        (r"\b(?:instagram|reels)\b", "Instagram"),
        (r"\b(?:linkedin)\b", "LinkedIn"),
        (r"\b(?:google ads)\b", "Google Ads"),
    )
    texts = [str(row.get("content") or "")[:500] for row in rows]
    return [label for pattern, label in patterns
            if sum(bool(re.search(pattern, item, re.I)) for item in texts) >= 2][:4]
