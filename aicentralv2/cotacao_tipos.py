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


def validar_status_tipo_comercial(tipo, status):
    """Novos produtos ficam em rascunho até seus módulos próprios existirem."""
    slug = normalizar_tipo_comercial(tipo)
    status_normalizado = str(status or "Rascunho").strip().casefold()
    if slug != TIPO_COMERCIAL_PADRAO and status_normalizado != "rascunho":
        raise ValueError(
            f"{COTACAO_TIPOS[slug]} ainda está em preparação. "
            "Por enquanto, essa cotação deve permanecer como rascunho."
        )
    return slug
