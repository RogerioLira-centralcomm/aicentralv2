"""What the Cadu MCP tells an external agent about itself.

The text is the agent's only description of the product. It answers "o que você pode
fazer?" and decides how fast work reaches a project or the Studio, so it names the
exact tool for each job instead of listing capabilities in the abstract.
"""
from __future__ import annotations

SERVER_DESCRIPTION = "Projetos, marcas, documentos, mídia e relatórios da sua conta Cadu."

SERVER_INSTRUCTIONS = """\
O Cadu é o workspace de marketing da agência. Esta conexão libera apenas os módulos e permissões que a pessoa aprovou; se uma ferramenta não aparecer, diga que o módulo está desativado e que ele se ativa em Integrações → Agentes de IA.

Quando perguntarem o que você faz com o Cadu, responda por área, com um exemplo de pedido em cada uma:
• Projetos e biblioteca: listar projetos, ler o contexto, pesquisar fontes e links, enviar notas, links, arquivos e tarefas.
• Documentos: criar rascunhos editáveis e páginas HTML, versionar, revisar e finalizar no projeto.
• Marcas: ler identidade, cores, logo e imagens aprovadas; cadastrar marca, enviar ativos e iniciar auditoria.
• Studio: abrir uma sessão pronta de imagem, anúncio, edição ou vídeo, com marca e briefing já preenchidos.
• Marketing: planos de mídia, briefings, catálogo do Planner e relatórios.
• Google, conta e créditos: Calendar, Meet, equipe, saldo e consumo.

Atalhos, na ordem em que costumam render:
1. Enviar o trabalho feito aqui para um projeto. Texto, resumo ou briefing: projects.create_note (vira fonte pesquisável). Documento editável, plano ou HTML: artifacts.create_draft e, depois da aprovação, artifacts.finalize_to_project. Link: projects.create_link_reference. Arquivo: resources.add com mode=file_upload ou projects.prepare_source_upload, e envie o arquivo ao upload_url devolvido. Pedido solto como "joga isso no projeto" ou "faz um doc disso": intent.interpret e depois intent.execute com o conteúdo explícito.
2. Criar imagem, anúncio ou vídeo. Há duas formas; leia a marca antes com brands.get_context (e brands.list_assets para referências aprovadas) e escreva um prompt completo: objetivo, público, formato e proporção, texto exato da peça, tom e referências. Anúncio exige marca.
   a) Link do Studio, sempre disponível: media.start_studio_session com kind (image, ad, image_edit, video, video_edit), brand_id e o prompt. Devolve studio_url, que abre no navegador já no projeto, na página certa e com o briefing preenchido; a pessoa dirige, escolhe variações e aprova lá, e é no Studio que os créditos são gastos. Ideal para vídeo, para ajustar a direção ou quando ela quer ver as opções.
   b) Geração direta, só se media.generate_image e media.edit_image estiverem na lista (a pessoa liberou "Gerar e editar imagens"): chame media.creation_capabilities, mostre o custo estimado e espere a aprovação dela; então use media.generate_image (ou media.edit_image com source_url) com index_in_project=true para a imagem já ficar no projeto. Se as ferramentas não aparecerem, ofereça o link do Studio.
   Não diga que a mídia foi criada ao abrir a sessão; acompanhe com media.list_jobs e media.get_job.
3. Pesquisar antes de criar. projects.search_knowledge e workspace.search_project_content trazem trechos citáveis do projeto; cite a fonte e diga quando não houver evidência.
4. Retomar trabalho. context.open devolve um context_handle reutilizável; operations.get confirma uma escrita já feita sem repeti-la.

Regras de uso:
• O projeto escolhido na conexão é o padrão; chame workspace.list_projects e pergunte somente se houver mais de um candidato plausível. Informe project_ref (formato ci:ID) apenas para outro projeto.
• Descubra sozinho o que as ferramentas de leitura respondem (projeto, marca, ativos); pergunte à pessoa só o que falta de verdade, e tudo de uma vez.
• Mostre o que será salvo antes de escrever e peça confirmação para ações irreversíveis, externas, de equipe ou de créditos.
• Depois de salvar, devolva o link do projeto ou do Studio e diga em uma frase o que foi feito."""

_SESSION_FIELDS = {
    "required": ["kind", "prompt"],
    "optional": ["brand_id", "title", "source_url", "source_id", "request_id"],
}
_EXTERNAL_KINDS = {
    "image": {"use_for": "Nova imagem a partir de um briefing.", "brand_id": "opcional, recomendado"},
    "ad": {"use_for": "Anúncio de uma marca validada.", "brand_id": "obrigatório"},
    "image_edit": {"use_for": "Alterar uma imagem existente preservando o resto.", "needs": "source_url (HTTPS ou ativo do Studio)"},
    "video": {"use_for": "Roteiro e plano de vídeo; a geração é feita no Studio a partir de uma imagem ou cenas."},
    "video_edit": {"use_for": "Editar um vídeo existente.", "needs": "source_url ou source_id"},
}
_BRIEF_CHECKLIST = ["objetivo da peça", "público", "formato e proporção", "texto exato que deve aparecer",
                    "tom de voz", "referências aprovadas da marca (brands.list_assets)"]


def external_media_capabilities(value: dict, can_generate: bool = False) -> dict:
    """Shape media.creation_capabilities for an external agent.

    The internal payload describes direct generation unconditionally. An outside agent only has those
    tools when the person granted `media:generate`, so the answer reflects what this connection can do.
    """
    result = {key: value[key] for key in ("image_cost_estimate", "video_plan_cost_estimate") if key in value}
    result.update({
        "how_to_create": "media.start_studio_session",
        "session_payload": _SESSION_FIELDS,
        "kinds": _EXTERNAL_KINDS,
        "brief_checklist": _BRIEF_CHECKLIST,
        "generation_available_via_mcp": ["image", "image_edit"] if can_generate else [],
        "result": "Devolve studio_url (abre já no projeto e na página certa) e session_id; a aprovação ocorre no Studio.",
    })
    if can_generate:
        result["direct_generation"] = {
            "image": "media.generate_image", "image_edit": "media.edit_image",
            "before_calling": "Mostre image_cost_estimate à pessoa e espere a aprovação; passe index_in_project=true para salvar no projeto.",
        }
        result["note"] = ("Use a geração direta quando a pessoa aprovar o custo; use a sessão do Studio para vídeo, "
                          "para ajustar a direção ou quando ela preferir escolher no navegador. Só diga que a mídia "
                          "existe depois do resultado da geração ou de media.get_job mostrar o job concluído.")
    else:
        result["note"] = ("Esta conexão não tem permissão para gerar imagens diretamente; a sessão não gera mídia nem consome "
                          "créditos. Entregue o studio_url e, se a pessoa quiser gerar daqui, diga que ela pode liberar "
                          "'Gerar e editar imagens' ao reconectar o Cadu.")
    return result
