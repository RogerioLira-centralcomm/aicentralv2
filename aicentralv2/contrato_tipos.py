"""Tipo de contrato comercial (operação própria vs representação)."""

import unicodedata

TIPOS_DE_CONTRATO = {
    "operacao_propria": "Operação própria",
    "representacao_comercial": "Representação comercial",
}

TIPO_DE_CONTRATO_PADRAO = "operacao_propria"


def _slug_tipo_de_contrato(valor):
    text = unicodedata.normalize("NFKD", str(valor or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.strip().lower().replace("-", "_")
    return "_".join(text.split())


def normalizar_tipo_de_contrato(valor, *, estrito=True):
    """Retorna o slug canônico; vazio usa Operação própria."""
    slug = _slug_tipo_de_contrato(valor or TIPO_DE_CONTRATO_PADRAO)
    aliases = {
        "operacao_propria": "operacao_propria",
        "operacao": "operacao_propria",
        "representacao_comercial": "representacao_comercial",
        "representacao": "representacao_comercial",
    }
    slug = aliases.get(slug, slug)
    if slug in TIPOS_DE_CONTRATO:
        return slug
    if estrito:
        raise ValueError("Tipo de contrato inválido.")
    return TIPO_DE_CONTRATO_PADRAO


def rotulo_tipo_de_contrato(valor):
    return TIPOS_DE_CONTRATO[normalizar_tipo_de_contrato(valor, estrito=False)]


CATEGORIA_PLATAFORMA_DADOS = "Dados"


def categoria_plataforma_eh_dados(categoria) -> bool:
    return (categoria or "").strip().casefold() == CATEGORIA_PLATAFORMA_DADOS.casefold()


def plataforma_permitida_para_tipo_contrato(categoria, tipo_de_contrato=None) -> bool:
    """Operação própria: todas exceto Dados; representação: só categoria Dados."""
    slug = normalizar_tipo_de_contrato(tipo_de_contrato, estrito=False)
    if slug == "representacao_comercial":
        return categoria_plataforma_eh_dados(categoria)
    return not categoria_plataforma_eh_dados(categoria)


def filtrar_plataformas_por_tipo_contrato(plataformas, tipo_de_contrato=None):
    resultado = []
    for item in plataformas or []:
        cat = (item.get("categoria") or "").strip() or "Sem categoria"
        if plataforma_permitida_para_tipo_contrato(cat, tipo_de_contrato):
            resultado.append(item)
    return resultado
