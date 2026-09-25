"""Read-only, explicit Cadu workflows for everyday agency work."""

import re

from .contracts import RequestContext

WORKFLOWS = {
    "market-intelligence": ("Market Intelligence", "Pesquisas rápidas, profundas ou personalizadas com evidências e fontes rastreáveis.", "Pesquisa", (), "Use a modalidade indicada (quick, deep ou custom). Consulte somente fontes públicas para pesquisa externa; contexto privado autorizado serve à síntese e nunca deve ser copiado para consultas públicas. Diferencie fato, interpretação e hipótese, cite somente fontes efetivamente recuperadas, indique lacunas e não invente métricas, datas ou concorrentes. A pesquisa longa é executada como trabalho retomável e termina em artefato editável."),
    "market-radar": ("Radar de mercado", "Movimentos recentes da marca, do setor e dos concorrentes com fontes.", "Pesquisa", ("web.search",), "Use primeiro o contexto aprovado da marca vinculada ao projeto: nome, segmento e concorrentes registrados. A busca externa deve citar a marca pelo nome e pesquisar movimentos recentes dela e de concorrentes diretos; nunca pesquisar ou descrever apenas o nome genérico do projeto. Se não for possível resolver uma marca única, não pesquise nem conclua que o vínculo não existe: diga que não foi possível identificar a marca e peça para selecioná-la ou vinculá-la ao projeto. Separe fatos públicos datados de interpretação e explique a implicação prática para a marca. No resultado web.search, somente fontes com read_status=read foram lidas; resultados discovered são candidatos, não sustentação de fatos. Cite URL de fonte lida para cada afirmação e diferencie data da página de metadado da busca. Se a busca falhar ou não trouxer conteúdo lido relevante para a marca, diga isso claramente; não substitua por artigos genéricos sobre como analisar concorrentes e não invente sinais. Não prometa monitoramento contínuo."),
    "audience-map": ("Mapa de audiência", "Hipóteses de público, canais e sinais de pesquisa.", "Planejamento", ("web.search", "planner.research_plan_inputs"), "Mapeie segmentos, necessidades, canais e hipóteses de validação. Separe dados públicos de hipóteses. Dados públicos exigem conteúdo de fonte efetivamente lida (read_status=read); resultado apenas descoberto é pista de pesquisa, não evidência. O catálogo do Planner é inventário de opções, não prova de tamanho, preço ou desempenho. Não invente tamanho de público."),
    "investment-simulator": ("Simulador de investimento", "Cenários de verba e premissas para mídia.", "Planejamento", ("planner.research_plan_inputs", "planner.simulate_investment"), "Use os totais determinísticos de planner.simulate_investment como exemplos iniciais; adapte a recomendação ao objetivo e ao contexto sem alterar as contas recebidas. Se faltar verba, use percentuais. Não trate referência de catálogo como cotação ou previsão de resultado."),
    "media-plan-audit": ("Auditoria do plano", "Revê coerência, riscos e lacunas do plano.", "Planejamento", ("planner.list_plans", "planner.get_media_plan"), "Revise objetivo, audiência, canais, formatos, verba e mensuração. Quando planner.get_media_plan retornar calculation_review, preserve os achados aritméticos e seus valores exatos; não diga que uma distribuição com finding blocking está correta. Distinga a verificação aritmética da sua avaliação estratégica e proponha correções em ordem de impacto. A revisão não altera o plano. Se houver apenas uma lista de planos, peça ao usuário para escolher o correto; a lista não contém detalhes suficientes para uma auditoria. Se não houver plano acessível, peça o plano ou um resumo."),
    "campaign-tracker": ("Acompanhamento de campanha", "Analisa relatórios enviados e sugere próximos passos.", "Análise", (), "Analise diretamente o relatório anexado como fonte principal, sem depender do módulo Reports nem de relatórios importados. Extraia período, objetivo, canais, métricas e resultados explícitos; calcule variações somente com valores e períodos comparáveis. Separe fatos do relatório, interpretações e recomendações, cite páginas ou trechos quando disponíveis, indique lacunas e proponha próximos passos priorizados. Não invente valores nem alegue consulta a plataformas ou a relatórios do projeto. Se não houver arquivo ou métricas fornecidas na conversa, peça o material necessário."),
    "creative-concept": ("Conceito criativo", "Direção, mensagem e variações para campanha.", "Criação", (), "Entregue conceito central, promessa, prova, tom, exemplos por canal e uma alternativa. Use a marca e o projeto quando presentes. Trate qualquer dado sobre consumidores como hipótese se não houver fonte."),
    "channel-copy": ("Copy por canal", "Textos prontos para formatos e canais escolhidos.", "Criação", (), "Produza textos prontos por canal e formato, com CTA e limites de caracteres quando conhecidos. Respeite a voz da marca; não invente regras da plataforma. Se o canal não foi indicado, proponha um conjunto pequeno."),
    "page-review": ("Revisor de página", "Avalia clareza, oferta, CTA e fricções.", "Criação", ("web.read",), "Revise a página fornecida por URL ou conteúdo colado. Para cada uma das até cinco correções prioritárias, separe: elemento observado e trecho que o demonstra, hipótese sobre o efeito para o usuário, mudança proposta e forma de verificar depois. Cite a URL somente quando a leitura tiver ocorrido. Texto extraído não comprova layout, interação, velocidade nem conformidade de acessibilidade; indique o que exigiria inspeção visual ou teste. Se a leitura falhar, diga isso e peça o conteúdo da página."),
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
