"""Categorias comerciais das cotações.

Este domínio é intencionalmente separado de ``cadu_pi_tipo``: o tipo de PI
existente descreve a operação/plataforma, enquanto ``tipo_comercial`` escolhe
qual produto, precificação e fluxo operacional a cotação usará.
"""

COTACAO_TIPOS = {
    "midia": "Mídia",
    "parceiros": "Parceiros",
    "formatos_interativos": "Formatos interativos",
    "dados": "Dados",
}

TIPO_COMERCIAL_PADRAO = "midia"

COTACAO_WORKSPACES = {
    "parceiros": {
        "titulo": "Proposta de parceiros",
        "orientacao": "Organize escopo, participação comercial e condições antes de estruturar o PI próprio.",
        "proximo_passo": "Definir entregas e responsabilidades do parceiro",
    },
    "formatos_interativos": {
        "titulo": "Proposta de formatos interativos",
        "orientacao": "Consolide experiência, produção e requisitos técnicos antes de estruturar o PI próprio.",
        "proximo_passo": "Detalhar formato, produção e critérios de aceite",
    },
    "dados": {
        "titulo": "Proposta de dados",
        "orientacao": "Registre fonte, cobertura, finalidade e regras de uso antes de estruturar o PI próprio.",
        "proximo_passo": "Definir escopo, governança e forma de entrega",
    },
}

COTACAO_MONTAGENS = {
    "parceiros": {
        "item_label": "Entrega do parceiro",
        "item_placeholder": "Ex.: Cota de conteúdo patrocinado",
        "fields": (
            ("parceiro", "Parceiro"),
            ("modelo_comercial", "Modelo comercial"),
            ("prazo_entrega", "Prazo de entrega"),
        ),
    },
    "formatos_interativos": {
        "item_label": "Formato ou experiência",
        "item_placeholder": "Ex.: Pull to reveal 300x600",
        "fields": (
            ("ambiente", "Ambiente"),
            ("tecnologia", "Tecnologia"),
            ("dimensoes", "Dimensões"),
            ("criterio_aceite", "Critério de aceite"),
        ),
    },
    "dados": {
        "item_label": "Segmento ou pacote de dados",
        "item_placeholder": "Ex.: Intenção de compra automotiva",
        "fields": (
            ("fonte", "Fonte"),
            ("cobertura", "Cobertura"),
            ("licenca", "Modelo de licença"),
            ("periodo_uso", "Período de uso"),
        ),
    },
}


def normalizar_tipo_comercial(valor, *, estrito=True):
    """Retorna o slug canônico; dados legados vazios são sempre Mídia."""
    slug = str(valor or TIPO_COMERCIAL_PADRAO).strip().lower().replace("-", "_")
    if slug in COTACAO_TIPOS:
        return slug
    if estrito:
        raise ValueError("Tipo de cotação inválido.")
    return TIPO_COMERCIAL_PADRAO


def rotulo_tipo_comercial(valor):
    return COTACAO_TIPOS[normalizar_tipo_comercial(valor, estrito=False)]


def destino_tipo_comercial(valor):
    """Retorna endpoint Flask e sufixo canônicos para continuar a cotação."""
    slug = normalizar_tipo_comercial(valor, estrito=False)
    if slug == TIPO_COMERCIAL_PADRAO:
        return "cotacoes.cotacao_detalhes", "detalhes"
    return "cotacoes.cotacao_workspace", "workspace"


def workspace_tipo_comercial(valor):
    """Retorna o conteúdo comercial do workspace dos novos produtos."""
    slug = normalizar_tipo_comercial(valor)
    workspace = COTACAO_WORKSPACES.get(slug)
    if not workspace:
        return None
    return {**workspace, **COTACAO_MONTAGENS[slug]}


def campos_item_tipo_comercial(valor):
    """Campos específicos permitidos na montagem do tipo informado."""
    slug = normalizar_tipo_comercial(valor)
    montagem = COTACAO_MONTAGENS.get(slug)
    return tuple(field for field, _ in montagem["fields"]) if montagem else ()


def validar_status_tipo_comercial(tipo, status):
    """Valida o tipo sem acoplar estágio comercial ao gerador de PI.

    Os quatro produtos compartilham o pipeline. A geração de PI continua
    protegida separadamente e só pode usar o fluxo de Mídia.
    """
    slug = normalizar_tipo_comercial(tipo)
    return slug
